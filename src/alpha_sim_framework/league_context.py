import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .alpha_types import ContextSyncResult, LeagueContextConfig

SCHEMA_VERSION = "1.0"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_json(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def _atomic_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_default_json))
    temp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _to_context_config(config: Optional[Dict[str, Any]]) -> LeagueContextConfig:
    if isinstance(config, LeagueContextConfig):
        return config
    if not isinstance(config, dict):
        raise ValueError("build_league_context requires a config dict or LeagueContextConfig")

    if config.get("league_id") is None:
        raise ValueError("build_league_context requires config['league_id']")
    if config.get("year") is None:
        raise ValueError("build_league_context requires config['year']")

    return LeagueContextConfig(
        league_id=int(config["league_id"]),
        year=int(config["year"]),
        swid=config.get("swid"),
        espn_s2=config.get("espn_s2"),
        context_dir=str(config.get("context_dir", "data/league_context")),
        lookback_seasons=int(config.get("lookback_seasons", 3)),
        start_year=config.get("start_year"),
        end_year=config.get("end_year"),
        full_refresh=bool(config.get("full_refresh", False)),
        include_playoffs=bool(config.get("include_playoffs", False)),
    )


def resolve_context_years(base_year: int, config: LeagueContextConfig) -> List[int]:
    if config.start_year is not None or config.end_year is not None:
        start = int(config.start_year if config.start_year is not None else base_year)
        end = int(config.end_year if config.end_year is not None else base_year)
        if start > end:
            start, end = end, start
        return list(range(start, end + 1))

    # Default is last 3 seasons + current season.
    lookback = max(0, int(config.lookback_seasons))
    return list(range(base_year - lookback, base_year + 1))


def _week_from_timestamp_ms(ts_ms: int, season_year: int, reg_weeks: int) -> int:
    # Approximate kickoff anchor keeps this deterministic for normalization.
    season_start = datetime(season_year, 9, 1, tzinfo=timezone.utc)
    dt = datetime.fromtimestamp(max(0, ts_ms) / 1000, tz=timezone.utc)
    week = ((dt - season_start).days // 7) + 1
    return int(max(1, min(reg_weeks, week)))


def _starter_from_slot(player: Any) -> bool:
    slot = str(getattr(player, "lineupSlot", getattr(player, "slot_position", "")) or "").upper()
    return slot not in {"BE", "BENCH", "IR", "", "FA"}


def _player_record(player: Any) -> Dict[str, Any]:
    return {
        "playerId": getattr(player, "playerId", getattr(player, "name", id(player))),
        "name": str(getattr(player, "name", "")),
        "position": str(getattr(player, "position", "")),
        "lineupSlot": str(getattr(player, "lineupSlot", getattr(player, "slot_position", "BE"))),
        "slot_position": str(getattr(player, "slot_position", getattr(player, "lineupSlot", "BE"))),
        "projected_total_points": float(getattr(player, "projected_total_points", 0.0) or 0.0),
        "projected_avg_points": float(getattr(player, "projected_avg_points", 0.0) or 0.0),
        "avg_points": float(getattr(player, "avg_points", 0.0) or 0.0),
        "stats": dict(getattr(player, "stats", {}) or {}),
        "injuryStatus": str(getattr(player, "injuryStatus", "NONE") or "NONE"),
        "injured": bool(getattr(player, "injured", False)),
        "percent_started": float(getattr(player, "percent_started", 0.0) or 0.0),
        "pro_pos_rank": float(getattr(player, "pro_pos_rank", 0.0) or 0.0),
    }


def _points_for_week(player: Any, week: int) -> float:
    stats = getattr(player, "stats", {})
    if not isinstance(stats, dict):
        return 0.0
    entry = stats.get(week)
    if not isinstance(entry, dict):
        return 0.0
    try:
        return float(entry.get("points", 0.0) or 0.0)
    except Exception:
        return 0.0


def _write_table(table_path: Path, rows: List[Dict[str, Any]], warnings: List[str]) -> int:
    table_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    try:
        frame.to_parquet(table_path, index=False)
    except Exception as exc:
        fallback = table_path.with_suffix(".json")
        fallback.write_text(frame.to_json(orient="records", indent=2))
        warnings.append(f"table_fallback_json:{table_path.name}:{exc}")
    return int(len(frame))


def _read_table(table_path: Path) -> pd.DataFrame:
    if table_path.exists():
        return pd.read_parquet(table_path)
    fallback = table_path.with_suffix(".json")
    if fallback.exists():
        records = json.loads(fallback.read_text())
        return pd.DataFrame(records)
    return pd.DataFrame()


def _lineup_stability(week_sets: List[set]) -> float:
    if len(week_sets) <= 1:
        return 0.0
    sims: List[float] = []
    for idx in range(1, len(week_sets)):
        prev_ids = week_sets[idx - 1]
        curr_ids = week_sets[idx]
        union = prev_ids | curr_ids
        sims.append(1.0 if not union else len(prev_ids & curr_ids) / len(union))
    return float(np.mean(sims)) if sims else 0.0


def _compute_behavior_features(
    year: int,
    teams_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    lineups_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    team_ids = sorted(set(int(value) for value in teams_df.get("team_id", [])))

    for team_id in team_ids:
        team_name = ""
        subset = teams_df[teams_df["team_id"] == team_id] if "team_id" in teams_df else pd.DataFrame()
        if not subset.empty and "team_name" in subset:
            team_name = str(subset.iloc[0]["team_name"])

        score_slice = weekly_df[weekly_df["team_id"] == team_id] if "team_id" in weekly_df else pd.DataFrame()
        scores = [float(value) for value in score_slice.get("team_score", []) if pd.notna(value)]
        volatility = float(np.std(scores, ddof=1)) if len(scores) >= 2 else 0.0
        percentile_75 = float(np.percentile(scores, 75)) if scores else 0.0
        high_ceiling_rate = (
            float(np.mean([1.0 if score >= percentile_75 and percentile_75 > 0 else 0.0 for score in scores]))
            if scores
            else 0.0
        )
        games = max(1, len(scores))

        lineup_slice = lineups_df[lineups_df["team_id"] == team_id] if "team_id" in lineups_df else pd.DataFrame()
        week_sets: List[set] = []
        if not lineup_slice.empty and "week" in lineup_slice:
            for _, week_df in lineup_slice.groupby("week"):
                ids = set(int(value) for value in week_df.get("player_id", []) if pd.notna(value))
                week_sets.append(ids)
        stability = _lineup_stability(week_sets)
        churn = max(0.0, 1.0 - stability)

        txn_slice = transactions_df[transactions_df["team_id"] == team_id] if "team_id" in transactions_df else pd.DataFrame()
        txn_count = int(len(txn_slice))
        transaction_cadence = float(txn_count / games)
        waiver_aggressiveness = float(min(1.0, txn_count / max(1.0, games * 2.5)))

        if len(scores) >= 4:
            cut = max(1, len(scores) // 3)
            early = float(np.mean(scores[:cut]))
            late = float(np.mean(scores[-cut:]))
            early_late_delta = early - late
        else:
            early_late_delta = 0.0

        reactivity_index = (
            (30.0 * waiver_aggressiveness)
            + (30.0 * churn)
            + (0.8 * volatility)
            + (15.0 * high_ceiling_rate)
        )

        rows.append(
            {
                "year": year,
                "team_id": team_id,
                "team_name": team_name,
                "games": games,
                "score_volatility": volatility,
                "high_ceiling_rate": high_ceiling_rate,
                "lineup_stability_index": stability,
                "lineup_churn_index": churn,
                "waiver_aggressiveness_proxy": waiver_aggressiveness,
                "transaction_cadence": transaction_cadence,
                "early_late_delta": early_late_delta,
                "reactivity_index": reactivity_index,
            }
        )

    return pd.DataFrame(rows)


def _serialize_box_matchup(matchup: Any) -> Dict[str, Any]:
    home_team = getattr(matchup, "home_team", None)
    away_team = getattr(matchup, "away_team", None)
    return {
        "home_team_id": int(getattr(home_team, "team_id", -1)),
        "away_team_id": int(getattr(away_team, "team_id", -1)),
        "home_score": float(getattr(matchup, "home_score", 0.0) or 0.0),
        "away_score": float(getattr(matchup, "away_score", 0.0) or 0.0),
        "home_lineup": [_player_record(player) for player in getattr(matchup, "home_lineup", [])],
        "away_lineup": [_player_record(player) for player in getattr(matchup, "away_lineup", [])],
    }


def _build_year_context(
    context_root: Path,
    year: int,
    league: Any,
    sync_mode: str,
    previous_watermark: Dict[str, int],
    warnings: List[str],
) -> Dict[str, Any]:
    reg_weeks = int(getattr(getattr(league, "settings", None), "reg_season_count", 14) or 14)
    teams = list(getattr(league, "teams", []))
    team_map = {int(getattr(team, "team_id")): team for team in teams}

    raw_root = context_root / "raw" / str(year)
    table_root = context_root / "tables" / str(year)
    raw_root.mkdir(parents=True, exist_ok=True)
    (raw_root / "box_scores").mkdir(parents=True, exist_ok=True)
    (raw_root / "activity").mkdir(parents=True, exist_ok=True)
    table_root.mkdir(parents=True, exist_ok=True)

    teams_rows: List[Dict[str, Any]] = []
    for team in teams:
        schedule = [int(getattr(opponent, "team_id", opponent)) for opponent in getattr(team, "schedule", [])]
        teams_rows.append(
            {
                "year": year,
                "team_id": int(getattr(team, "team_id")),
                "team_name": str(getattr(team, "team_name", "")),
                "wins": int(getattr(team, "wins", 0) or 0),
                "losses": int(getattr(team, "losses", 0) or 0),
                "points_for": float(getattr(team, "points_for", 0.0) or 0.0),
                "reg_season_count": reg_weeks,
                "schedule": schedule,
            }
        )

    snapshot_payload = {
        "year": year,
        "league_id": int(getattr(league, "league_id", 0) or 0),
        "current_week": int(getattr(league, "current_week", 1) or 1),
        "reg_season_count": reg_weeks,
        "playoff_team_count": int(getattr(getattr(league, "settings", None), "playoff_team_count", 4) or 4),
        "teams": [
            {
                "team_id": int(getattr(team, "team_id")),
                "team_name": str(getattr(team, "team_name", "")),
                "wins": int(getattr(team, "wins", 0) or 0),
                "losses": int(getattr(team, "losses", 0) or 0),
                "scores": list(getattr(team, "scores", []) or []),
                "outcomes": list(getattr(team, "outcomes", []) or []),
                "schedule": [int(getattr(opponent, "team_id", opponent)) for opponent in getattr(team, "schedule", [])],
                "roster": [_player_record(player) for player in getattr(team, "roster", [])],
            }
            for team in teams
        ],
    }
    _atomic_json_write(raw_root / "league_snapshot.json", snapshot_payload)

    weekly_rows: List[Dict[str, Any]] = []
    lineups_rows: List[Dict[str, Any]] = []
    start_week = 1
    if sync_mode == "incremental":
        start_week = max(1, int(previous_watermark.get("last_completed_week", 0)) + 1)

    for week in range(start_week, reg_weeks + 1):
        try:
            matchups = list(league.box_scores(week=week))
        except Exception as exc:
            warnings.append(f"year={year}:box_scores_week_{week}_failed:{exc}")
            continue

        serialized = [_serialize_box_matchup(matchup) for matchup in matchups]
        _atomic_json_write(raw_root / "box_scores" / f"week_{week}.json", {"year": year, "week": week, "matchups": serialized})

        for matchup in matchups:
            home_team = getattr(matchup, "home_team", None)
            away_team = getattr(matchup, "away_team", None)
            home_id = int(getattr(home_team, "team_id", -1))
            away_id = int(getattr(away_team, "team_id", -1))
            home_name = str(getattr(home_team, "team_name", ""))
            away_name = str(getattr(away_team, "team_name", ""))
            home_score = float(getattr(matchup, "home_score", 0.0) or 0.0)
            away_score = float(getattr(matchup, "away_score", 0.0) or 0.0)

            weekly_rows.append(
                {
                    "year": year,
                    "week": week,
                    "team_id": home_id,
                    "team_name": home_name,
                    "opponent_id": away_id,
                    "opponent_name": away_name,
                    "team_score": home_score,
                    "opponent_score": away_score,
                }
            )
            weekly_rows.append(
                {
                    "year": year,
                    "week": week,
                    "team_id": away_id,
                    "team_name": away_name,
                    "opponent_id": home_id,
                    "opponent_name": home_name,
                    "team_score": away_score,
                    "opponent_score": home_score,
                }
            )

            for side, team_id, team_name in (
                ("home", home_id, home_name),
                ("away", away_id, away_name),
            ):
                lineup = list(getattr(matchup, f"{side}_lineup", []) or [])
                for player in lineup:
                    if not _starter_from_slot(player):
                        continue
                    lineups_rows.append(
                        {
                            "year": year,
                            "week": week,
                            "team_id": team_id,
                            "team_name": team_name,
                            "player_id": getattr(player, "playerId", getattr(player, "name", id(player))),
                            "player_name": str(getattr(player, "name", "")),
                            "position": str(getattr(player, "position", "")),
                            "lineup_slot": str(getattr(player, "lineupSlot", getattr(player, "slot_position", ""))),
                            "points": _points_for_week(player, week),
                        }
                    )

    transactions_rows: List[Dict[str, Any]] = []
    start_offset = 0 if sync_mode == "full" else max(0, int(previous_watermark.get("last_activity_offset", 0)))
    offset = start_offset
    while True:
        try:
            activities = list(league.recent_activity(size=100, offset=offset))
        except Exception as exc:
            warnings.append(f"year={year}:recent_activity_failed:{exc}")
            break
        if not activities:
            break

        raw_acts = []
        for activity in activities:
            date_ms = int(getattr(activity, "date", 0) or 0)
            act_payload = {"date": date_ms, "actions": []}
            for action in getattr(activity, "actions", []) or []:
                if len(action) < 3:
                    continue
                team, action_name, player = action[0], str(action[1]), action[2]
                bid = action[3] if len(action) > 3 else 0
                team_id = int(getattr(team, "team_id", -1))
                if team_id <= 0:
                    continue
                week = _week_from_timestamp_ms(date_ms, year, reg_weeks)
                player_id = getattr(player, "playerId", getattr(player, "name", id(player)))
                player_name = str(getattr(player, "name", ""))
                player_pos = str(getattr(player, "position", ""))

                act_payload["actions"].append(
                    {
                        "team_id": team_id,
                        "team_name": str(getattr(team, "team_name", "")),
                        "action": action_name,
                        "player_id": player_id,
                        "player_name": player_name,
                        "player_position": player_pos,
                        "bid": float(bid or 0.0),
                    }
                )
                transactions_rows.append(
                    {
                        "year": year,
                        "week": week,
                        "date_ms": date_ms,
                        "date_iso": datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc).isoformat(),
                        "team_id": team_id,
                        "team_name": str(getattr(team, "team_name", "")),
                        "action": action_name,
                        "player_id": player_id,
                        "player_name": player_name,
                        "player_position": player_pos,
                        "bid": float(bid or 0.0),
                    }
                )

            raw_acts.append(act_payload)

        _atomic_json_write(raw_root / "activity" / f"activity_offset_{offset}.json", {"year": year, "offset": offset, "activities": raw_acts})
        if len(activities) < 100:
            offset += len(activities)
            break
        offset += 100

    behavior_df = _compute_behavior_features(
        year=year,
        teams_df=pd.DataFrame(teams_rows),
        weekly_df=pd.DataFrame(weekly_rows),
        lineups_df=pd.DataFrame(lineups_rows),
        transactions_df=pd.DataFrame(transactions_rows),
    )

    counts = {
        "teams": _write_table(table_root / "teams.parquet", teams_rows, warnings),
        "weekly_team_scores": _write_table(table_root / "weekly_team_scores.parquet", weekly_rows, warnings),
        "lineups": _write_table(table_root / "lineups.parquet", lineups_rows, warnings),
        "transactions": _write_table(table_root / "transactions.parquet", transactions_rows, warnings),
        "team_behavior_features": _write_table(
            table_root / "team_behavior_features.parquet",
            behavior_df.to_dict(orient="records"),
            warnings,
        ),
    }

    return {
        "year": year,
        "record_counts": counts,
        "watermark": {
            "last_activity_offset": max(0, int(offset)),
            "last_completed_week": reg_weeks,
        },
        "quality_flags": [],
    }


def _load_manifest(context_root: Path) -> Dict[str, Any]:
    return _read_json(context_root / "context_manifest.json", default={})


def _choose_sync_mode(config: LeagueContextConfig, previous_manifest: Dict[str, Any]) -> str:
    if config.full_refresh or not previous_manifest:
        return "full"
    last_sync = previous_manifest.get("last_sync_utc")
    if not last_sync:
        return "full"
    try:
        last_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
    except Exception:
        return "full"
    age_days = (datetime.now(timezone.utc) - last_dt).days
    return "full" if age_days >= 7 else "incremental"


def build_league_context(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = _to_context_config(config)
    seasons = resolve_context_years(cfg.year, cfg)

    context_root = Path(cfg.context_dir) / str(cfg.league_id)
    previous_manifest = _load_manifest(context_root)
    sync_mode = _choose_sync_mode(cfg, previous_manifest)

    warnings: List[str] = []
    seasons_synced: List[int] = []
    seasons_skipped: List[int] = []
    record_counts: Dict[str, Any] = {}
    endpoint_watermarks = dict(previous_manifest.get("endpoint_watermarks", {}))
    quality_flags: set = set(previous_manifest.get("data_quality_flags", []))

    league_loader = None
    if isinstance(config, dict):
        league_loader = config.get("league_loader")
    if league_loader is None:
        from espn_api.football import League

        def league_loader(load_year: int):
            return League(
                league_id=cfg.league_id,
                year=load_year,
                swid=cfg.swid,
                espn_s2=cfg.espn_s2,
            )

    for year in seasons:
        previous_watermark = endpoint_watermarks.get(str(year), {})
        try:
            league = league_loader(year)
        except Exception as exc:
            seasons_skipped.append(year)
            warnings.append(f"year={year}:league_load_failed:{exc}")
            quality_flags.add("partial_sync")
            continue

        year_result = _build_year_context(
            context_root=context_root,
            year=year,
            league=league,
            sync_mode=sync_mode,
            previous_watermark=previous_watermark,
            warnings=warnings,
        )
        seasons_synced.append(year)
        record_counts[str(year)] = year_result["record_counts"]
        endpoint_watermarks[str(year)] = year_result["watermark"]
        for flag in year_result.get("quality_flags", []):
            quality_flags.add(flag)

    derived_root = context_root / "derived"
    derived_root.mkdir(parents=True, exist_ok=True)
    feature_frames = []
    for year in seasons_synced:
        frame = _read_table(context_root / "tables" / str(year) / "team_behavior_features.parquet")
        if not frame.empty:
            feature_frames.append(frame)

    rankings: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"total_teams": 0, "top_reactive": [], "least_reactive": []}
    if feature_frames:
        combined = pd.concat(feature_frames, ignore_index=True)
        grouped = (
            combined.groupby(["team_id", "team_name"], dropna=False)
            .agg(
                seasons_observed=("year", "nunique"),
                avg_reactivity=("reactivity_index", "mean"),
                avg_waiver_aggressiveness=("waiver_aggressiveness_proxy", "mean"),
                avg_lineup_stability=("lineup_stability_index", "mean"),
                avg_score_volatility=("score_volatility", "mean"),
            )
            .reset_index()
        )
        grouped = grouped.sort_values("avg_reactivity", ascending=False)
        rankings = grouped.to_dict(orient="records")
        summary = {
            "total_teams": int(len(grouped)),
            "top_reactive": rankings[:5],
            "least_reactive": list(reversed(rankings[-5:])),
        }

    _atomic_json_write(derived_root / "team_reactivity_rankings.json", {"generated_at": _utcnow_iso(), "rankings": rankings})
    _atomic_json_write(derived_root / "league_behavior_summary.json", {"generated_at": _utcnow_iso(), **summary})

    manifest = {
        "league_id": cfg.league_id,
        "seasons": seasons,
        "last_sync_utc": _utcnow_iso(),
        "sync_mode": sync_mode,
        "record_counts": record_counts,
        "data_quality_flags": sorted(quality_flags),
        "schema_version": SCHEMA_VERSION,
        "endpoint_watermarks": endpoint_watermarks,
    }
    _atomic_json_write(context_root / "context_manifest.json", manifest)

    result = ContextSyncResult(
        context_root=str(context_root),
        sync_mode=sync_mode,
        seasons_requested=seasons,
        seasons_synced=seasons_synced,
        seasons_skipped=seasons_skipped,
        warnings=warnings,
        record_counts=record_counts,
    )
    return asdict(result)


def load_league_context(path: str) -> Dict[str, Any]:
    root = Path(path)
    if (root / "context_manifest.json").exists():
        context_root = root
    else:
        candidates = sorted(root.glob("*/context_manifest.json"))
        if not candidates:
            raise FileNotFoundError(f"No context manifest found under {path}")
        context_root = candidates[0].parent

    manifest = _load_manifest(context_root)
    seasons = [int(value) for value in manifest.get("seasons", [])]
    tables: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for year in seasons:
        table_root = context_root / "tables" / str(year)
        tables[str(year)] = {
            "teams": _read_table(table_root / "teams.parquet").to_dict(orient="records"),
            "weekly_team_scores": _read_table(table_root / "weekly_team_scores.parquet").to_dict(orient="records"),
            "lineups": _read_table(table_root / "lineups.parquet").to_dict(orient="records"),
            "transactions": _read_table(table_root / "transactions.parquet").to_dict(orient="records"),
            "team_behavior_features": _read_table(table_root / "team_behavior_features.parquet").to_dict(orient="records"),
        }

    return {
        "context_root": str(context_root),
        "manifest": manifest,
        "tables": tables,
        "derived": {
            "team_reactivity_rankings": _read_json(context_root / "derived" / "team_reactivity_rankings.json", default={}),
            "league_behavior_summary": _read_json(context_root / "derived" / "league_behavior_summary.json", default={}),
        },
    }


def _dict_to_player(player_data: Dict[str, Any]) -> Any:
    return SimpleNamespace(**player_data)


def _dict_to_team(team_data: Dict[str, Any]) -> Any:
    roster = [_dict_to_player(player) for player in team_data.get("roster", [])]
    return SimpleNamespace(
        team_id=int(team_data.get("team_id")),
        team_name=str(team_data.get("team_name", "")),
        wins=int(team_data.get("wins", 0) or 0),
        losses=int(team_data.get("losses", 0) or 0),
        scores=list(team_data.get("scores", []) or []),
        outcomes=list(team_data.get("outcomes", []) or []),
        schedule=list(team_data.get("schedule", []) or []),
        roster=roster,
        points_for=float(sum(score for score in team_data.get("scores", []) if isinstance(score, (int, float)))),
    )


def build_league_loader_from_context(context_path: str):
    payload = load_league_context(context_path)
    context_root = Path(payload["context_root"])

    def _loader(year: int):
        raw_root = context_root / "raw" / str(year)
        snapshot = _read_json(raw_root / "league_snapshot.json", default=None)
        if snapshot is None:
            raise FileNotFoundError(f"Missing league snapshot for year={year}")

        teams = [_dict_to_team(team_data) for team_data in snapshot.get("teams", [])]
        team_map = {team.team_id: team for team in teams}
        reg_weeks = int(snapshot.get("reg_season_count", 14) or 14)

        def _box_scores(week: int = None):
            if week is None:
                return []
            week_payload = _read_json(raw_root / "box_scores" / f"week_{int(week)}.json", default={})
            out = []
            for matchup in week_payload.get("matchups", []):
                home_team = team_map.get(int(matchup.get("home_team_id", -1)))
                away_team = team_map.get(int(matchup.get("away_team_id", -1)))
                out.append(
                    SimpleNamespace(
                        home_team=home_team,
                        away_team=away_team,
                        home_score=float(matchup.get("home_score", 0.0) or 0.0),
                        away_score=float(matchup.get("away_score", 0.0) or 0.0),
                        home_lineup=[_dict_to_player(player) for player in matchup.get("home_lineup", [])],
                        away_lineup=[_dict_to_player(player) for player in matchup.get("away_lineup", [])],
                    )
                )
            return out

        return SimpleNamespace(
            league_id=int(snapshot.get("league_id", 0) or 0),
            year=int(snapshot.get("year", year)),
            current_week=int(snapshot.get("current_week", 1) or 1),
            teams=teams,
            settings=SimpleNamespace(
                reg_season_count=reg_weeks,
                playoff_team_count=int(snapshot.get("playoff_team_count", 4) or 4),
            ),
            box_scores=_box_scores,
            recent_activity=lambda size=25, msg_type=None, offset=0: [],
        )

    return _loader

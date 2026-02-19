from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .alpha_types import HistoricalBacktestConfig


def _normalize_name(value: str) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


def _lineup_slot(player: Any) -> str:
    return str(getattr(player, "lineupSlot", getattr(player, "slot_position", "")) or "").upper()


def _starter_from_slot(player: Any) -> bool:
    slot = _lineup_slot(player)
    return slot not in {"BE", "BENCH", "IR", "", "FA"}


def _player_id(player: Any) -> Any:
    return getattr(player, "playerId", getattr(player, "name", id(player)))


def _safe_mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(np.mean(values))


def _safe_std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.std(values, ddof=1))


def _to_config(config: Optional[Dict[str, Any]]) -> HistoricalBacktestConfig:
    if config is None:
        return HistoricalBacktestConfig()
    if isinstance(config, HistoricalBacktestConfig):
        return config

    payload = HistoricalBacktestConfig()
    for key, value in config.items():
        if hasattr(payload, key):
            setattr(payload, key, value)
    return payload


def _resolve_year_window(base_year: int, config: HistoricalBacktestConfig) -> List[int]:
    if config.start_year is not None or config.end_year is not None:
        start = int(config.start_year if config.start_year is not None else base_year)
        end = int(config.end_year if config.end_year is not None else base_year)
        if start > end:
            start, end = end, start
        return list(range(start, end + 1))

    lookback = max(1, int(config.lookback_seasons))
    start = base_year - lookback + 1
    return list(range(start, base_year + 1))


def _find_team_in_season(
    teams: List[Any], target_team_id: int, target_team_name: str
) -> Tuple[Optional[Any], Optional[str], Optional[str]]:
    for team in teams:
        if int(getattr(team, "team_id", -1)) == int(target_team_id):
            return team, None, None

    norm_target = _normalize_name(target_team_name)
    for team in teams:
        if _normalize_name(getattr(team, "team_name", "")) == norm_target:
            warning = (
                f"team_id_mismatch: mapped requested team_id={target_team_id} "
                f"to team_name='{getattr(team, 'team_name', '')}'"
            )
            return team, warning, "team_id_drift"

    return None, f"team_not_found: team_id={target_team_id} team_name='{target_team_name}'", "team_missing"


def _get_week_lineups(league: Any, teams_by_id: Dict[int, Any], week: int) -> Tuple[Dict[int, List[Any]], bool]:
    try:
        box_scores = league.box_scores(week=week)
    except Exception:
        box_scores = []

    if not box_scores:
        return {}, False

    result: Dict[int, List[Any]] = {}
    for matchup in box_scores:
        for side in ("home", "away"):
            team = getattr(matchup, f"{side}_team", None)
            lineup = getattr(matchup, f"{side}_lineup", [])
            team_id = getattr(team, "team_id", team)
            if team_id is None:
                continue
            result[int(team_id)] = [player for player in lineup if _starter_from_slot(player)]

    for team_id in teams_by_id:
        result.setdefault(team_id, [])
    return result, True


def _fallback_lineups(teams_by_id: Dict[int, Any]) -> Dict[int, List[Any]]:
    return {
        int(team_id): [player for player in getattr(team, "roster", []) if _starter_from_slot(player)]
        for team_id, team in teams_by_id.items()
    }


def _week_points_for_player(player: Any, week: int) -> float:
    stats = getattr(player, "stats", {})
    entry = stats.get(week) if isinstance(stats, dict) else None
    if not isinstance(entry, dict):
        return 0.0
    try:
        return float(entry.get("points", 0.0) or 0.0)
    except Exception:
        return 0.0


def _position_points(lineup: List[Any], week: int) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for player in lineup:
        pos = str(getattr(player, "position", "") or "").upper()
        if not pos:
            continue
        totals[pos] = totals.get(pos, 0.0) + _week_points_for_player(player, week)
    return totals


def _lineup_stability(lineups: List[List[Any]]) -> float:
    if len(lineups) <= 1:
        return 1.0 if lineups else 0.0

    similarities = []
    for idx in range(1, len(lineups)):
        prev_ids = {_player_id(player) for player in lineups[idx - 1]}
        curr_ids = {_player_id(player) for player in lineups[idx]}
        union = prev_ids | curr_ids
        if not union:
            similarities.append(1.0)
            continue
        similarities.append(len(prev_ids & curr_ids) / len(union))
    return float(_safe_mean(similarities))


def _waiver_aggressiveness(lineups: List[List[Any]]) -> float:
    if len(lineups) <= 1:
        return 0.0

    changes = []
    for idx in range(1, len(lineups)):
        prev_ids = {_player_id(player) for player in lineups[idx - 1]}
        curr_ids = {_player_id(player) for player in lineups[idx]}
        if not prev_ids and not curr_ids:
            changes.append(0.0)
            continue
        changes.append(len(prev_ids ^ curr_ids) / max(1, len(prev_ids | curr_ids)))

    return float(_safe_mean(changes))


def _first_last_split_delta(scores: List[float]) -> float:
    if len(scores) < 4:
        return 0.0
    cut = max(1, len(scores) // 3)
    first = _safe_mean(scores[:cut])
    last = _safe_mean(scores[-cut:])
    return float(first - last)


def _build_narrative(
    quant: Dict[str, Any], confidence_band: str, min_weeks: int
) -> Tuple[List[str], str]:
    tags: List[str] = []
    evidence: List[str] = []

    volatility = float(quant.get("score_volatility", 0.0))
    if volatility >= 18.0:
        tags.append("Boom/Bust scorer")
        evidence.append(f"score_volatility={volatility:.1f}")

    high_ceiling = float(quant.get("high_ceiling_rate", 0.0))
    if high_ceiling >= 0.4:
        tags.append("High-ceiling threat")
        evidence.append(f"high_ceiling_rate={high_ceiling:.2f}")

    stability = float(quant.get("lineup_stability_index", 0.0))
    if stability >= 0.75 and volatility <= 12.0:
        tags.append("Stable lineup grinder")
        evidence.append(f"lineup_stability_index={stability:.2f}")

    split_delta = float(quant.get("early_season_delta", 0.0))
    if split_delta >= 5.0:
        tags.append("Fast starter")
        evidence.append(f"early_season_delta={split_delta:.1f}")

    pressure = quant.get("position_pressure_index", {})
    top_pos = pressure.get("top_position")
    top_delta = float(pressure.get("top_delta", 0.0))
    if top_pos and top_delta >= 1.5:
        tags.append(f"{top_pos}-heavy pressure")
        evidence.append(f"top_position_delta={top_delta:.2f}")

    games = int(quant.get("games_sampled", 0))
    if games < min_weeks:
        tags.append("Sparse sample")
        evidence.append(f"games_sampled={games}")

    if not tags:
        tags.append("Balanced tendency profile")
        evidence.append("no major threshold triggers")

    summary = f"{'; '.join(tags)}. Evidence: {', '.join(evidence)}. Confidence={confidence_band}."
    return tags, summary


def _statistical_confidence(games: int, volatility: float, flags: List[str]) -> float:
    sample_term = min(0.95, games / 10.0)
    volatility_penalty = min(0.35, max(0.0, (volatility - 10.0) / 40.0))
    quality_penalty = 0.1 if flags else 0.0
    return float(max(0.05, sample_term - volatility_penalty - quality_penalty))


def _confidence_band(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def run_historical_backtest(simulator: Any, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = _to_config(config)
    runtime_config = config or {}

    target_team_id = runtime_config.get("team_id")
    if target_team_id is None:
        raise ValueError("run_historical_opponent_backtest requires config['team_id']")

    league_id = runtime_config.get("league_id", getattr(simulator.league, "league_id", None))
    if league_id is None:
        raise ValueError("run_historical_opponent_backtest requires config['league_id']")

    current_year = int(
        runtime_config.get("year")
        or getattr(simulator.league, "year", None)
        or datetime.now().year
    )
    years = _resolve_year_window(current_year, payload)

    league_loader = runtime_config.get("league_loader")
    if league_loader is None:
        from espn_api.football import League

        def league_loader(load_year: int):
            return League(
                league_id=league_id,
                year=load_year,
                swid=runtime_config.get("swid"),
                espn_s2=runtime_config.get("espn_s2"),
            )

    current_target_team = simulator._team_map.get(int(target_team_id))
    target_name = getattr(current_target_team, "team_name", f"team-{target_team_id}")

    aggregate: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    skipped_years: List[int] = []
    analyzed_years: List[int] = []

    for year in years:
        try:
            league = league_loader(year)
        except Exception as exc:
            skipped_years.append(year)
            warnings.append(f"year={year}: load_failed: {exc}")
            continue

        teams = list(getattr(league, "teams", []))
        teams_by_id = {int(getattr(team, "team_id")): team for team in teams if hasattr(team, "team_id")}
        target_team, team_warning, team_warning_code = _find_team_in_season(teams, int(target_team_id), target_name)
        if target_team is None:
            skipped_years.append(year)
            if team_warning:
                warnings.append(f"year={year}: {team_warning}")
            continue
        if team_warning:
            warnings.append(f"year={year}: {team_warning}")

        analyzed_years.append(year)
        reg_weeks = int(getattr(getattr(league, "settings", None), "reg_season_count", len(getattr(target_team, "schedule", []))) or 0)
        total_weeks = len(getattr(target_team, "schedule", []))
        final_week = total_weeks if payload.include_playoffs else min(total_weeks, reg_weeks)

        season_team_points: Dict[int, List[float]] = {}
        for team in teams:
            scores = [float(score) for score in getattr(team, "scores", []) if score is not None]
            season_team_points[int(getattr(team, "team_id"))] = scores

        season_pos_history: Dict[int, Dict[str, List[float]]] = {int(getattr(team, "team_id")): {} for team in teams}
        season_lineups: Dict[int, List[List[Any]]] = {int(getattr(team, "team_id")): [] for team in teams}
        season_used_lineup_fallback = False

        for week in range(1, final_week + 1):
            lineup_map, used_box = _get_week_lineups(league, teams_by_id, week=week)
            if not used_box:
                lineup_map = _fallback_lineups(teams_by_id)
                season_used_lineup_fallback = True

            for team_id, lineup in lineup_map.items():
                season_lineups.setdefault(team_id, []).append(lineup)
                pos_points = _position_points(lineup, week)
                history = season_pos_history.setdefault(team_id, {})
                for pos, points in pos_points.items():
                    history.setdefault(pos, []).append(points)

        target_schedule = list(getattr(target_team, "schedule", []) or [])
        target_scores = list(getattr(target_team, "scores", []) or [])

        for idx in range(final_week):
            if idx >= len(target_schedule):
                break
            week = idx + 1
            opponent_ref = target_schedule[idx]
            opponent_id = int(getattr(opponent_ref, "team_id", opponent_ref))
            opponent_team = teams_by_id.get(opponent_id)
            if opponent_team is None or opponent_id == int(getattr(target_team, "team_id", -1)):
                continue

            your_points = float(target_scores[idx]) if idx < len(target_scores) and target_scores[idx] is not None else None
            opp_scores = list(getattr(opponent_team, "scores", []) or [])
            opp_points = float(opp_scores[idx]) if idx < len(opp_scores) and opp_scores[idx] is not None else None
            if your_points is None or opp_points is None:
                continue

            opp_name = str(getattr(opponent_team, "team_name", f"team-{opponent_id}"))
            opp_name_norm = _normalize_name(opp_name)
            canonical_key = f"name:{opp_name_norm}"

            slot = aggregate.setdefault(
                canonical_key,
                {
                    "opponent_team_id_latest": opponent_id,
                    "opponent_team_name": opp_name,
                    "games": [],
                    "opponent_all_scores": [],
                    "vs_you_lineups": [],
                    "season_lineups": [],
                    "vs_you_position_points": {},
                    "season_position_points": {},
                    "quality_flags": set(),
                    "seasons": set(),
                    "team_mapping_flags": set(),
                },
            )

            if team_warning_code == "team_id_drift":
                slot["team_mapping_flags"].add("target_team_id_drift")
            if season_used_lineup_fallback:
                slot["quality_flags"].add("box_score_lineups_missing")

            season_scores = season_team_points.get(opponent_id, [])
            if season_scores:
                slot["opponent_all_scores"].extend(season_scores)

            opp_vs_you_lineup = season_lineups.get(opponent_id, [])[idx] if idx < len(season_lineups.get(opponent_id, [])) else []
            slot["vs_you_lineups"].append(opp_vs_you_lineup)
            slot["season_lineups"].extend(season_lineups.get(opponent_id, []))

            vs_you_pos = _position_points(opp_vs_you_lineup, week)
            for pos, points in vs_you_pos.items():
                slot["vs_you_position_points"].setdefault(pos, []).append(points)

            season_pos = season_pos_history.get(opponent_id, {})
            for pos, values in season_pos.items():
                slot["season_position_points"].setdefault(pos, []).extend(values)

            percentile_75 = float(np.percentile(season_scores, 75)) if season_scores else 0.0
            slot["games"].append(
                {
                    "year": year,
                    "week": week,
                    "your_points": your_points,
                    "opponent_points": opp_points,
                    "opponent_win": 1.0 if opp_points > your_points else 0.0,
                    "high_ceiling_hit": 1.0 if opp_points >= percentile_75 and percentile_75 > 0 else 0.0,
                }
            )
            slot["seasons"].add(year)

    opponent_reports: List[Dict[str, Any]] = []
    for key, data in aggregate.items():
        games = data["games"]
        games_count = len(games)
        if games_count == 0:
            continue

        your_points = [float(item["your_points"]) for item in games]
        opp_points = [float(item["opponent_points"]) for item in games]
        win_rate = _safe_mean([float(item["opponent_win"]) for item in games])
        high_ceiling = _safe_mean([float(item["high_ceiling_hit"]) for item in games])

        position_delta: Dict[str, float] = {}
        for pos, values in data["vs_you_position_points"].items():
            season_values = data["season_position_points"].get(pos, [])
            position_delta[pos] = _safe_mean(values) - _safe_mean(season_values)

        top_position = ""
        top_delta = 0.0
        if position_delta:
            top_position, top_delta = max(position_delta.items(), key=lambda item: item[1])

        early_delta = _first_last_split_delta(data["opponent_all_scores"])
        lineup_stability = _lineup_stability(data["vs_you_lineups"])
        waiver_proxy = _waiver_aggressiveness(data["season_lineups"])

        quant = {
            "games_sampled": games_count,
            "avg_points_for_vs_you": _safe_mean(opp_points),
            "avg_points_against_you": _safe_mean(your_points),
            "win_rate_vs_you": win_rate,
            "score_volatility": _safe_std(opp_points),
            "high_ceiling_rate": high_ceiling,
            "position_pressure_index": {
                "by_position": position_delta,
                "top_position": top_position,
                "top_delta": top_delta,
            },
            "lineup_stability_index": lineup_stability,
            "waiver_aggressiveness_proxy": waiver_proxy,
            "early_season_delta": early_delta,
        }

        data_quality_flags = sorted(set(data["quality_flags"]) | set(data["team_mapping_flags"]))
        if games_count < int(payload.min_weeks_per_opponent):
            data_quality_flags.append("low_sample_size")
        stat_conf = _statistical_confidence(games_count, quant["score_volatility"], data_quality_flags)
        band = _confidence_band(stat_conf)
        tags, narrative = _build_narrative(quant, band, int(payload.min_weeks_per_opponent))

        opponent_reports.append(
            {
                "opponent_key": key,
                "opponent_team_name": data["opponent_team_name"],
                "opponent_team_id_latest": data["opponent_team_id_latest"],
                "seasons_observed": sorted(data["seasons"]),
                "quant_metrics": quant,
                "qualitative_tags": tags,
                "narrative_summary": narrative,
                "confidence": {
                    "sample_size": games_count,
                    "statistical_confidence": stat_conf,
                    "confidence_band": band,
                    "data_quality_flags": data_quality_flags,
                },
            }
        )

    opponent_reports.sort(
        key=lambda item: (
            -item["quant_metrics"]["games_sampled"],
            item["opponent_team_name"],
        )
    )

    return {
        "analysis_window": {
            "years_requested": years,
            "years_analyzed": analyzed_years,
            "years_skipped": skipped_years,
            "include_playoffs": bool(payload.include_playoffs),
            "config": asdict(payload),
        },
        "target": {
            "league_id": league_id,
            "team_id": int(target_team_id),
            "team_name": target_name,
        },
        "opponents": opponent_reports,
        "warnings": warnings,
    }

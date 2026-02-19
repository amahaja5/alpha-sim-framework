import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


OUTLIKE_STATUSES = {"OUT", "DOUBTFUL", "IR", "SUSPENSION", "SUSP", "PUP", "COVID-19"}
DOME_NFL_TEAMS = {"ATL", "DAL", "DET", "HOU", "IND", "LV", "MIN", "NO"}

DEFAULT_WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
DEFAULT_SLEEPER_PLAYERS_ENDPOINT = "https://api.sleeper.app/v1/players/nfl"
DEFAULT_SLEEPER_ADD_ENDPOINT = "https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=200"
DEFAULT_SLEEPER_DROP_ENDPOINT = "https://api.sleeper.app/v1/players/nfl/trending/drop?lookback_hours=24&limit=200"
DEFAULT_ODDS_ENDPOINT = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?regions=us&markets=h2h,spreads,totals"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clip(value: Any, low: float, high: float, default: float = 0.0) -> float:
    return max(low, min(high, _safe_float(value, default)))


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text or text in {"NONE", "NA", "ACTIVE", "HEALTHY", "PROBABLE", "P"}:
        return "NONE"
    if text == "Q":
        return "QUESTIONABLE"
    if text == "D":
        return "DOUBTFUL"
    return text


def _team_id(team: Any) -> Optional[int]:
    try:
        return int(getattr(team, "team_id", team))
    except Exception:
        return None


def _player_id(player: Any) -> str:
    return str(getattr(player, "playerId", getattr(player, "name", id(player))))


def _player_position(player: Any) -> str:
    return str(getattr(player, "position", "") or "").upper()


def _player_projection(player: Any, reg_games: int = 14) -> float:
    projected_avg = _safe_float(getattr(player, "projected_avg_points", 0.0), 0.0)
    if projected_avg > 0:
        return projected_avg

    projected_total = _safe_float(getattr(player, "projected_total_points", 0.0), 0.0)
    if projected_total > 0:
        return projected_total / max(1.0, float(reg_games))

    return _safe_float(getattr(player, "avg_points", 0.0), 0.0)


def _player_recent_points(player: Any, week: int) -> List[float]:
    stats = _as_dict(getattr(player, "stats", {}))
    points: List[Tuple[int, float]] = []
    for stat_week, row in stats.items():
        row = _as_dict(row)
        if "points" not in row:
            continue
        week_id = _safe_int(stat_week, -1)
        if week_id <= 0 or week_id > int(week):
            continue
        points.append((week_id, _safe_float(row.get("points"), 0.0)))
    points.sort(key=lambda item: item[0], reverse=True)
    return [value for _, value in points]


def _player_nfl_team(player: Any) -> str:
    for attr in ("proTeam", "pro_team", "proTeamAbbreviation", "pro_team_abbreviation"):
        raw = getattr(player, attr, None)
        if raw is None:
            continue
        text = str(raw).strip().upper()
        if not text:
            continue
        if text in {"WSH", "WFT"}:
            return "WAS"
        return text
    return ""


def _top_qb_nfl_team(team: Any) -> str:
    qbs = [player for player in list(getattr(team, "roster", []) or []) if _player_position(player) == "QB"]
    if not qbs:
        return ""
    best = sorted(qbs, key=lambda player: _player_projection(player), reverse=True)[0]
    return _player_nfl_team(best)


def _with_query(url: str, params: Dict[str, Any]) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    if not query:
        return url
    return f"{url}{'&' if '?' in url else '?'}{query}"


def _http_get_json(url: str, headers: Dict[str, str], timeout: float, retries: int, backoff: float) -> Any:
    last_error = ""
    for attempt in range(max(0, int(retries)) + 1):
        try:
            request = urllib.request.Request(url=url, headers=headers, method="GET")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw)
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries and backoff > 0:
                time.sleep(backoff)
    raise RuntimeError(last_error or "request_failed")


def _schedule_strengths(teams: List[Any], week: int, horizon: int = 4) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    start_idx = max(0, int(week) - 1)
    denom = max(1.0, float(max(1, week - 1)))
    for team in teams:
        team_id = _team_id(team)
        if team_id is None:
            continue
        own_wins = _safe_float(getattr(team, "wins", 0), 0.0)
        values: List[float] = []
        for opp in list(getattr(team, "schedule", []) or [])[start_idx : start_idx + max(1, horizon)]:
            opp_wins = _safe_float(getattr(opp, "wins", 0), 0.0)
            values.append(round((opp_wins - own_wins) / denom, 3))
        output[str(team_id)] = values if values else 0.0
    return output


def _team_projected_totals(teams: List[Any]) -> Dict[str, float]:
    projected: Dict[str, float] = {}
    for team in teams:
        team_id = _team_id(team)
        if team_id is None:
            continue
        roster = list(getattr(team, "roster", []) or [])
        top = sorted((_player_projection(player) for player in roster), reverse=True)[:9]
        projected[str(team_id)] = round(sum(top), 4)
    return projected


def _sleeper_players_for_roster(
    endpoints: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float,
    retries: int,
    backoff: float,
    warnings: List[str],
) -> Dict[str, Any]:
    players_endpoint = str(
        endpoints.get("injury_players")
        or endpoints.get("market_players")
        or DEFAULT_SLEEPER_PLAYERS_ENDPOINT
    )
    try:
        payload = _http_get_json(players_endpoint, headers, timeout, retries, backoff)
        if isinstance(payload, dict):
            return payload
        warnings.append("sleeper_players_not_object")
    except Exception as exc:
        warnings.append(f"sleeper_players_fetch_failed:{exc}")
    return {}


def _free_weather_payload(
    endpoint_map: Dict[str, Any],
    headers: Dict[str, str],
    league: Any,
    timeout: float,
    retries: int,
    backoff: float,
) -> Dict[str, Any]:
    warnings: List[str] = []
    quality_flags = ["free_api_mode"]
    wind_mph = 8.0
    precip_prob = 0.15

    weather_endpoint = str(endpoint_map.get("weather_forecast") or DEFAULT_WEATHER_ENDPOINT)
    lat = _safe_float(endpoint_map.get("weather_lat"), 39.9008)
    lon = _safe_float(endpoint_map.get("weather_lon"), -75.1675)
    weather_url = _with_query(
        weather_endpoint,
        {
            "latitude": lat,
            "longitude": lon,
            "current": "wind_speed_10m,precipitation_probability",
            "wind_speed_unit": "mph",
            "forecast_days": 1,
        },
    )

    try:
        payload = _http_get_json(weather_url, headers, timeout, retries, backoff)
        current = _as_dict(_as_dict(payload).get("current", {}))
        wind_mph = _safe_float(current.get("wind_speed_10m"), wind_mph)
        precip_prob = _safe_float(current.get("precipitation_probability"), precip_prob)
        if precip_prob > 1.0:
            precip_prob = precip_prob / 100.0
        precip_prob = _clip(precip_prob, 0.0, 1.0, 0.0)
        quality_flags.extend(["live_fetch", "free_api_open_meteo"])
    except Exception as exc:
        quality_flags.append("free_api_fallback")
        warnings.append(f"weather_free_source_failed:{exc}")

    is_dome_default = str(endpoint_map.get("weather_is_dome_default", "")).strip().lower() in {"1", "true", "yes"}
    teams = list(getattr(league, "teams", []) or [])
    team_weather: Dict[str, Dict[str, Any]] = {}
    for index, team in enumerate(teams):
        team_id = _team_id(team)
        if team_id is None:
            continue
        nfl_team = _top_qb_nfl_team(team)
        is_dome = is_dome_default or nfl_team in DOME_NFL_TEAMS
        offset = ((index % 3) - 1) * 1.25
        team_weather[str(team_id)] = {
            "is_dome": bool(is_dome),
            "wind_mph": round(max(0.0, wind_mph + offset), 3),
            "precip_prob": round(_clip(precip_prob + (offset * 0.01), 0.0, 1.0), 4),
        }

    return {
        "data": {"team_weather": team_weather},
        "source_timestamp": _utc_now(),
        "quality_flags": quality_flags,
        "warnings": warnings,
    }


def _free_market_payload(
    endpoint_map: Dict[str, Any],
    headers: Dict[str, str],
    league: Any,
    week: int,
    timeout: float,
    retries: int,
    backoff: float,
) -> Dict[str, Any]:
    teams = list(getattr(league, "teams", []) or [])
    warnings: List[str] = []
    quality_flags = ["free_api_mode"]

    add_counts: Dict[str, float] = {}
    drop_counts: Dict[str, float] = {}

    trending_add_endpoint = str(endpoint_map.get("market_trending_add") or DEFAULT_SLEEPER_ADD_ENDPOINT)
    trending_drop_endpoint = str(endpoint_map.get("market_trending_drop") or DEFAULT_SLEEPER_DROP_ENDPOINT)

    try:
        add_rows = _as_list(_http_get_json(trending_add_endpoint, headers, timeout, retries, backoff))
        for row in add_rows:
            row = _as_dict(row)
            pid = str(row.get("player_id", "")).strip()
            if pid:
                add_counts[pid] = _safe_float(row.get("count"), 0.0)
    except Exception as exc:
        warnings.append(f"sleeper_trending_add_failed:{exc}")

    try:
        drop_rows = _as_list(_http_get_json(trending_drop_endpoint, headers, timeout, retries, backoff))
        for row in drop_rows:
            row = _as_dict(row)
            pid = str(row.get("player_id", "")).strip()
            if pid:
                drop_counts[pid] = _safe_float(row.get("count"), 0.0)
    except Exception as exc:
        warnings.append(f"sleeper_trending_drop_failed:{exc}")

    if add_counts or drop_counts:
        quality_flags.extend(["live_fetch", "free_api_sleeper_trending"])
    else:
        quality_flags.append("free_api_fallback")

    max_count = max([1.0] + list(add_counts.values()) + list(drop_counts.values()))
    schedule_strength = _schedule_strengths(teams, week)

    projections: Dict[str, float] = {}
    usage_trend: Dict[str, float] = {}
    sentiment: Dict[str, Any] = {}
    ownership: Dict[str, float] = {}

    for team in teams:
        roster = list(getattr(team, "roster", []) or [])
        for player in roster:
            pid = _player_id(player)
            projection = _player_projection(player)
            projections[pid] = round(projection, 4)

            add_value = _safe_float(add_counts.get(pid), 0.0)
            drop_value = _safe_float(drop_counts.get(pid), 0.0)
            trend = _clip(((add_value - drop_value) / max_count) * 3.0, -3.0, 3.0, 0.0)
            usage_trend[pid] = round(trend, 4)

            started_pct = _clip(_safe_float(getattr(player, "percent_started", 50.0), 50.0) / 100.0, 0.0, 1.0)
            ownership[pid] = round(started_pct, 4)
            sentiment[pid] = {
                "score": round(_clip(trend / 3.0, -1.0, 1.0, 0.0), 4),
                "start_delta": round((add_value - drop_value) / max_count * 20.0, 4),
            }

    return {
        "data": {
            "projections": projections,
            "usage_trend": usage_trend,
            "sentiment": sentiment,
            "future_schedule_strength": schedule_strength,
            "ownership_by_player": ownership,
        },
        "source_timestamp": _utc_now(),
        "quality_flags": quality_flags,
        "warnings": warnings,
    }


def _free_injury_payload(
    endpoint_map: Dict[str, Any],
    headers: Dict[str, str],
    league: Any,
    timeout: float,
    retries: int,
    backoff: float,
) -> Dict[str, Any]:
    teams = list(getattr(league, "teams", []) or [])
    warnings: List[str] = []
    quality_flags = ["free_api_mode"]

    sleeper_index = _sleeper_players_for_roster(endpoint_map, headers, timeout, retries, backoff, warnings)
    if sleeper_index:
        quality_flags.extend(["live_fetch", "free_api_sleeper_injuries"])
    else:
        quality_flags.append("free_api_fallback")

    injury_status: Dict[str, str] = {}
    injuries_by_team: Dict[str, Dict[str, int]] = {}
    backup_ratio: Dict[str, float] = {}

    for team in teams:
        team_id = _team_id(team)
        if team_id is None:
            continue
        roster = list(getattr(team, "roster", []) or [])
        injuries_by_team[str(team_id)] = {}
        by_pos: Dict[str, List[Any]] = {}
        for player in roster:
            by_pos.setdefault(_player_position(player), []).append(player)

        for position, players in by_pos.items():
            ordered = sorted(players, key=lambda item: _player_projection(item), reverse=True)
            for index, player in enumerate(ordered):
                pid = _player_id(player)
                sleeper_row = _as_dict(sleeper_index.get(pid, {}))
                source_status = sleeper_row.get("injury_status", getattr(player, "injuryStatus", "NONE"))
                status = _normalize_status(source_status)
                injury_status[pid] = status

                if status in OUTLIKE_STATUSES or status == "QUESTIONABLE":
                    injuries_by_team[str(team_id)][position] = injuries_by_team[str(team_id)].get(position, 0) + 1
                    baseline = max(0.01, _player_projection(player))
                    backup = None
                    for candidate in ordered[index + 1 :]:
                        candidate_pid = _player_id(candidate)
                        candidate_status = _normalize_status(
                            _as_dict(sleeper_index.get(candidate_pid, {})).get(
                                "injury_status",
                                getattr(candidate, "injuryStatus", "NONE"),
                            )
                        )
                        if candidate_status not in OUTLIKE_STATUSES:
                            backup = candidate
                            break
                    backup_proj = _player_projection(backup) if backup is not None else 0.0
                    backup_ratio[pid] = round(_clip(backup_proj / baseline, 0.0, 1.0), 4)

    return {
        "data": {
            "injury_status": injury_status,
            "team_injuries_by_position": injuries_by_team,
            "backup_projection_ratio_by_player": backup_ratio,
        },
        "source_timestamp": _utc_now(),
        "quality_flags": quality_flags,
        "warnings": warnings,
    }


def _odds_market_bias(
    endpoint_map: Dict[str, Any],
    api_keys: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float,
    retries: int,
    backoff: float,
    warnings: List[str],
) -> Tuple[Optional[float], Optional[float], List[str]]:
    flags: List[str] = []
    api_key = str(api_keys.get("odds") or "").strip()
    if not api_key:
        return None, None, flags

    endpoint = str(endpoint_map.get("odds_nfl") or DEFAULT_ODDS_ENDPOINT)
    odds_url = _with_query(endpoint, {"apiKey": api_key})
    totals: List[float] = []
    spreads: List[float] = []
    try:
        rows = _as_list(_http_get_json(odds_url, headers, timeout, retries, backoff))
        for event in rows:
            event = _as_dict(event)
            for book in _as_list(event.get("bookmakers")):
                book = _as_dict(book)
                for market in _as_list(book.get("markets")):
                    market = _as_dict(market)
                    key = str(market.get("key", "")).strip().lower()
                    if key == "totals":
                        for outcome in _as_list(market.get("outcomes")):
                            outcome = _as_dict(outcome)
                            point = _safe_float(outcome.get("point"), math.nan)
                            if math.isfinite(point):
                                totals.append(point)
                    if key == "spreads":
                        for outcome in _as_list(market.get("outcomes")):
                            outcome = _as_dict(outcome)
                            point = _safe_float(outcome.get("point"), math.nan)
                            if math.isfinite(point):
                                spreads.append(abs(point))
        if totals or spreads:
            flags.extend(["live_fetch", "free_api_the_odds_api"])
        return (
            statistics.mean(totals) if totals else None,
            statistics.mean(spreads) if spreads else None,
            flags,
        )
    except Exception as exc:
        warnings.append(f"odds_market_fetch_failed:{exc}")
        return None, None, flags


def _free_odds_payload(
    endpoint_map: Dict[str, Any],
    api_keys: Dict[str, Any],
    headers: Dict[str, str],
    league: Any,
    week: int,
    timeout: float,
    retries: int,
    backoff: float,
) -> Dict[str, Any]:
    teams = list(getattr(league, "teams", []) or [])
    warnings: List[str] = []
    quality_flags = ["free_api_mode", "free_api_heuristic_odds"]

    league_total_bias, spread_bias, market_flags = _odds_market_bias(
        endpoint_map=endpoint_map,
        api_keys=api_keys,
        headers=headers,
        timeout=timeout,
        retries=retries,
        backoff=backoff,
        warnings=warnings,
    )
    for flag in market_flags:
        if flag not in quality_flags:
            quality_flags.append(flag)

    projected_totals = _team_projected_totals(teams)
    schedule_strength = _schedule_strengths(teams, week)

    spread_by_team: Dict[str, float] = {}
    implied_totals: Dict[str, float] = {}
    win_prob: Dict[str, float] = {}
    opening_spread: Dict[str, float] = {}
    closing_spread: Dict[str, float] = {}
    live_state: Dict[str, Dict[str, float]] = {}
    defense_vs_position: Dict[str, Dict[str, float]] = {}
    player_props: Dict[str, Dict[str, float]] = {}

    for team in teams:
        team_id = _team_id(team)
        if team_id is None:
            continue
        key = str(team_id)
        own_total = _safe_float(projected_totals.get(key), 0.0)
        opp = None
        schedule = list(getattr(team, "schedule", []) or [])
        if 0 <= int(week) - 1 < len(schedule):
            opp = schedule[int(week) - 1]
        opp_id = _team_id(opp) if opp is not None else None
        opp_total = _safe_float(projected_totals.get(str(opp_id), own_total), own_total)

        spread = round((opp_total - own_total) / 2.0, 4)
        if spread_bias is not None:
            spread = round((spread * 0.7) + (_safe_float(spread_bias) * 0.3 * (-1 if spread < 0 else 1)), 4)
        spread_by_team[key] = spread
        opening_spread[key] = round(spread + 0.5, 4)
        closing_spread[key] = spread

        implied = own_total
        if league_total_bias is not None:
            implied = (own_total * 0.5) + ((_safe_float(league_total_bias, own_total) / 2.0) * 0.5)
        implied_totals[key] = round(implied, 4)

        probability = 1.0 / (1.0 + math.exp(spread / 5.5))
        win_prob[key] = round(_clip(probability, 0.0, 1.0), 4)
        live_state[key] = {
            "quarter": 1,
            "time_remaining_sec": 3600.0,
            "score_differential": 0.0,
        }

        defense_vs_position[key] = {
            "QB": round(_clip(-spread / 10.0, -1.5, 1.5), 4),
            "RB": round(_clip(-spread / 12.0, -1.5, 1.5), 4),
            "WR": round(_clip(-spread / 11.0, -1.5, 1.5), 4),
            "TE": round(_clip(-spread / 14.0, -1.5, 1.5), 4),
        }

        roster = list(getattr(team, "roster", []) or [])
        for player in roster:
            pid = _player_id(player)
            base_line = max(0.0, _player_projection(player))
            started_pct = _clip(_safe_float(getattr(player, "percent_started", 50.0)) / 100.0, 0.0, 1.0, 0.5)
            player_props[pid] = {
                "line_open": round(base_line * 0.95, 4),
                "line_current": round(base_line * 1.02, 4),
                "sharp_over_pct": round(started_pct, 4),
            }

    return {
        "data": {
            "defense_vs_position": defense_vs_position,
            "spread_by_team": spread_by_team,
            "implied_total_by_team": implied_totals,
            "schedule_strength_by_team": schedule_strength,
            "player_props_by_player": player_props,
            "win_probability_by_team": win_prob,
            "live_game_state_by_team": live_state,
            "opening_spread_by_team": opening_spread,
            "closing_spread_by_team": closing_spread,
        },
        "source_timestamp": _utc_now(),
        "quality_flags": quality_flags,
        "warnings": warnings,
    }


def _free_nextgen_payload(league: Any, week: int) -> Dict[str, Any]:
    teams = list(getattr(league, "teams", []) or [])
    quality_flags = ["free_api_mode", "free_api_heuristic_nextgenstats"]
    warnings: List[str] = []
    metrics: Dict[str, Dict[str, float]] = {}

    for team in teams:
        roster = list(getattr(team, "roster", []) or [])
        team_total = sum(max(0.0, _player_projection(player)) for player in roster) or 1.0
        for player in roster:
            pid = _player_id(player)
            pos = _player_position(player)
            baseline = max(0.1, _player_projection(player))
            points = _player_recent_points(player, week)
            current_avg = statistics.mean(points[:3]) if points else baseline
            prev_avg = statistics.mean(points[3:6]) if len(points) > 3 else baseline
            volatility = statistics.pstdev(points[:4]) if len(points) >= 2 else 0.0
            started_pct = _clip(_safe_float(getattr(player, "percent_started", 50.0)) / 100.0, 0.0, 1.0, 0.5)

            usage_over_expected = _clip((current_avg - baseline) / max(1.0, baseline), -3.0, 3.0, 0.0)
            route_base = 1.0 if pos == "QB" else 0.72 if pos in {"WR", "TE"} else 0.58 if pos == "RB" else 0.35
            route_participation = _clip(route_base + ((started_pct - 0.5) * 0.15), 0.0, 1.0, route_base)
            avg_separation = 1.4 if pos == "RB" else 2.0 if pos in {"WR", "TE"} else 1.1
            avg_separation = max(0.1, avg_separation + (usage_over_expected * 0.2))
            explosive_rate = _clip(0.12 + abs(usage_over_expected) * 0.1 + started_pct * 0.12, 0.0, 1.0, 0.15)
            red_zone_share = _clip((baseline / team_total) * 1.4, 0.0, 1.0, 0.0)
            trend = _clip((current_avg - prev_avg) / max(2.0, baseline), -1.0, 1.0, 0.0)
            snap_share = _clip(started_pct * 0.9 + 0.1, 0.0, 1.0, started_pct)
            snap_trend = _clip(trend * 0.4, -1.0, 1.0, 0.0)

            metrics[pid] = {
                "usage_over_expected": round(usage_over_expected, 4),
                "route_participation": round(route_participation, 4),
                "avg_separation": round(avg_separation, 4),
                "explosive_play_rate": round(explosive_rate, 4),
                "volatility_index": round(max(0.0, volatility), 4),
                "red_zone_touch_share": round(red_zone_share, 4),
                "red_zone_touch_trend": round(trend, 4),
                "snap_share": round(snap_share, 4),
                "snap_share_trend": round(snap_trend, 4),
            }

    return {
        "data": {"player_metrics": metrics},
        "source_timestamp": _utc_now(),
        "quality_flags": quality_flags,
        "warnings": warnings,
    }


def fetch_free_feed(
    *,
    feed_name: str,
    endpoint: str,
    endpoint_map: Dict[str, Any],
    api_keys: Dict[str, Any],
    headers: Dict[str, str],
    league: Any,
    week: int,
    timeout: float,
    retries: int,
    backoff: float,
) -> Dict[str, Any]:
    _ = endpoint
    name = str(feed_name or "").strip().lower()

    if name == "weather":
        return _free_weather_payload(
            endpoint_map=endpoint_map,
            headers=headers,
            league=league,
            timeout=timeout,
            retries=retries,
            backoff=backoff,
        )
    if name == "market":
        return _free_market_payload(
            endpoint_map=endpoint_map,
            headers=headers,
            league=league,
            week=week,
            timeout=timeout,
            retries=retries,
            backoff=backoff,
        )
    if name in {"injury_news", "injury-news"}:
        return _free_injury_payload(
            endpoint_map=endpoint_map,
            headers=headers,
            league=league,
            timeout=timeout,
            retries=retries,
            backoff=backoff,
        )
    if name == "odds":
        return _free_odds_payload(
            endpoint_map=endpoint_map,
            api_keys=api_keys,
            headers=headers,
            league=league,
            week=week,
            timeout=timeout,
            retries=retries,
            backoff=backoff,
        )
    if name == "nextgenstats":
        return _free_nextgen_payload(league=league, week=week)

    return {
        "data": {},
        "source_timestamp": _utc_now(),
        "quality_flags": ["free_api_mode", "unsupported_feed"],
        "warnings": [f"unsupported_free_feed:{feed_name}"],
    }

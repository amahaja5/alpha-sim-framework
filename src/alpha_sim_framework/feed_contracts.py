from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def _is_iso_utc(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def _in_range(value: Any, low: float, high: float) -> bool:
    if not _is_number(value):
        return False
    v = float(value)
    return low <= v <= high


def validate_feed_envelope(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload_not_object"]

    if "data" not in payload or not isinstance(payload.get("data"), dict):
        errors.append("data_missing_or_not_object")

    if "source_timestamp" not in payload or not _is_iso_utc(payload.get("source_timestamp")):
        errors.append("source_timestamp_missing_or_invalid_iso")

    quality_flags = payload.get("quality_flags")
    if not isinstance(quality_flags, list) or not all(isinstance(item, str) for item in quality_flags):
        errors.append("quality_flags_missing_or_invalid")

    warnings = payload.get("warnings")
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        errors.append("warnings_missing_or_invalid")

    return errors


def _validate_weather_data(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    team_weather = data.get("team_weather")
    if not isinstance(team_weather, dict):
        return ["weather.team_weather_missing_or_invalid"]

    for team_id, item in team_weather.items():
        if not isinstance(item, dict):
            errors.append(f"weather.team_weather.{team_id}_not_object")
            continue
        if not isinstance(item.get("is_dome"), bool):
            errors.append(f"weather.team_weather.{team_id}.is_dome_invalid")
        if not _is_number(item.get("wind_mph")):
            errors.append(f"weather.team_weather.{team_id}.wind_mph_invalid")
        if not _in_range(item.get("precip_prob"), 0.0, 1.0):
            errors.append(f"weather.team_weather.{team_id}.precip_prob_invalid")
    return errors


def _validate_market_data(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = [
        "projections",
        "usage_trend",
        "sentiment",
        "future_schedule_strength",
    ]
    for key in required:
        if not isinstance(data.get(key), dict):
            errors.append(f"market.{key}_missing_or_invalid")

    ownership = data.get("ownership_by_player")
    if ownership is not None:
        if not isinstance(ownership, dict):
            errors.append("market.ownership_by_player_missing_or_invalid")
        else:
            for player_id, value in ownership.items():
                if not _in_range(value, 0.0, 1.0):
                    errors.append(f"market.ownership_by_player.{player_id}_invalid")
    return errors


def _validate_odds_data(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = [
        "defense_vs_position",
        "spread_by_team",
        "implied_total_by_team",
        "schedule_strength_by_team",
    ]
    for key in required:
        if not isinstance(data.get(key), dict):
            errors.append(f"odds.{key}_missing_or_invalid")

    player_props = data.get("player_props_by_player")
    if player_props is not None:
        if not isinstance(player_props, dict):
            errors.append("odds.player_props_by_player_missing_or_invalid")
        else:
            for player_id, props in player_props.items():
                if not isinstance(props, dict):
                    errors.append(f"odds.player_props_by_player.{player_id}_not_object")
                    continue
                if not _is_number(props.get("line_open")):
                    errors.append(f"odds.player_props_by_player.{player_id}.line_open_invalid")
                if not _is_number(props.get("line_current")):
                    errors.append(f"odds.player_props_by_player.{player_id}.line_current_invalid")
                if not _in_range(props.get("sharp_over_pct"), 0.0, 1.0):
                    errors.append(f"odds.player_props_by_player.{player_id}.sharp_over_pct_invalid")

    win_probability_by_team = data.get("win_probability_by_team")
    if win_probability_by_team is not None:
        if not isinstance(win_probability_by_team, dict):
            errors.append("odds.win_probability_by_team_missing_or_invalid")
        else:
            for team_id, value in win_probability_by_team.items():
                if not _in_range(value, 0.0, 1.0):
                    errors.append(f"odds.win_probability_by_team.{team_id}_invalid")

    live_game_state_by_team = data.get("live_game_state_by_team")
    if live_game_state_by_team is not None:
        if not isinstance(live_game_state_by_team, dict):
            errors.append("odds.live_game_state_by_team_missing_or_invalid")
        else:
            for team_id, game_state in live_game_state_by_team.items():
                if not isinstance(game_state, dict):
                    errors.append(f"odds.live_game_state_by_team.{team_id}_not_object")
                    continue
                quarter = game_state.get("quarter")
                if not isinstance(quarter, int):
                    errors.append(f"odds.live_game_state_by_team.{team_id}.quarter_invalid")
                elif quarter < 1 or quarter > 5:
                    errors.append(f"odds.live_game_state_by_team.{team_id}.quarter_out_of_range")
                if not _is_number(game_state.get("time_remaining_sec")):
                    errors.append(f"odds.live_game_state_by_team.{team_id}.time_remaining_sec_invalid")
                if not _is_number(game_state.get("score_differential")):
                    errors.append(f"odds.live_game_state_by_team.{team_id}.score_differential_invalid")

    for key in ("opening_spread_by_team", "closing_spread_by_team"):
        optional_map = data.get(key)
        if optional_map is None:
            continue
        if not isinstance(optional_map, dict):
            errors.append(f"odds.{key}_missing_or_invalid")
            continue
        for team_id, value in optional_map.items():
            if not _is_number(value):
                errors.append(f"odds.{key}.{team_id}_invalid")
    return errors


def _validate_injury_data(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(data.get("injury_status"), dict):
        errors.append("injury_news.injury_status_missing_or_invalid")
    if not isinstance(data.get("team_injuries_by_position"), dict):
        errors.append("injury_news.team_injuries_by_position_missing_or_invalid")

    backup_projection_ratio = data.get("backup_projection_ratio_by_player")
    if backup_projection_ratio is not None:
        if not isinstance(backup_projection_ratio, dict):
            errors.append("injury_news.backup_projection_ratio_by_player_missing_or_invalid")
        else:
            for player_id, value in backup_projection_ratio.items():
                if not _in_range(value, 0.0, 1.0):
                    errors.append(f"injury_news.backup_projection_ratio_by_player.{player_id}_invalid")
    return errors


def _validate_nextgenstats_data(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    player_metrics = data.get("player_metrics")
    if not isinstance(player_metrics, dict):
        return ["nextgenstats.player_metrics_missing_or_invalid"]

    for player_id, metrics in player_metrics.items():
        if not isinstance(metrics, dict):
            errors.append(f"nextgenstats.player_metrics.{player_id}_not_object")
            continue
        numeric_fields = [
            "usage_over_expected",
            "route_participation",
            "avg_separation",
            "explosive_play_rate",
            "volatility_index",
            "red_zone_touch_trend",
            "snap_share_trend",
        ]
        for field in numeric_fields:
            if field in metrics and not _is_number(metrics.get(field)):
                errors.append(f"nextgenstats.player_metrics.{player_id}.{field}_invalid")

        for share_field in ("red_zone_touch_share", "snap_share"):
            if share_field in metrics and not _in_range(metrics.get(share_field), 0.0, 1.0):
                errors.append(f"nextgenstats.player_metrics.{player_id}.{share_field}_invalid")

    return errors


def validate_canonical_feed(domain: str, payload: Dict[str, Any]) -> List[str]:
    domain_key = str(domain or "").strip().lower()
    errors = validate_feed_envelope(payload)
    data = _as_dict(payload.get("data"))

    if domain_key == "weather":
        errors.extend(_validate_weather_data(data))
    elif domain_key == "market":
        errors.extend(_validate_market_data(data))
    elif domain_key == "odds":
        errors.extend(_validate_odds_data(data))
    elif domain_key in {"injury_news", "injury-news"}:
        errors.extend(_validate_injury_data(data))
    elif domain_key == "nextgenstats":
        errors.extend(_validate_nextgenstats_data(data))
    else:
        errors.append(f"unsupported_domain:{domain}")

    return errors


def build_empty_envelope() -> Dict[str, Any]:
    return {
        "data": {},
        "source_timestamp": datetime.now(timezone.utc).isoformat(),
        "quality_flags": [],
        "warnings": [],
    }

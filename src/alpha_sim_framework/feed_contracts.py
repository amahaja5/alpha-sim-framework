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
    return errors


def _validate_injury_data(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(data.get("injury_status"), dict):
        errors.append("injury_news.injury_status_missing_or_invalid")
    if not isinstance(data.get("team_injuries_by_position"), dict):
        errors.append("injury_news.team_injuries_by_position_missing_or_invalid")
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

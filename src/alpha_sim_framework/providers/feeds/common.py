import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict

from ...alpha_types import ExternalFeedConfig, ProviderRuntimeConfig


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _league_params(league: Any, week: int) -> Dict[str, str]:
    return {
        "league_id": str(getattr(league, "league_id", "")),
        "year": str(getattr(league, "year", "")),
        "week": str(int(week)),
    }


def _normalize_mapping(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        return data
    return {}


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), match.group(0)), value)


def _is_unresolved_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return text.startswith("${") and text.endswith("}")


def _merge_string_list(base: list, extra: Any) -> list:
    if not isinstance(extra, list):
        return base
    for item in extra:
        if isinstance(item, str) and item not in base:
            base.append(item)
    return base


def _is_feed_envelope(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    required = {"data", "source_timestamp", "quality_flags", "warnings"}
    return required.issubset(value.keys())


def _coerce_feed_envelope(value: Any, base_quality_flags: list, base_warnings: list) -> Dict[str, Any]:
    payload = {
        "data": {},
        "source_timestamp": _utc_now(),
        "quality_flags": list(base_quality_flags),
        "warnings": list(base_warnings),
    }

    if _is_feed_envelope(value):
        data = value.get("data")
        if isinstance(data, dict):
            payload["data"] = data
        elif data is not None:
            payload["data"] = {"value": data}
            payload["quality_flags"].append("data_wrapped_value")

        source_timestamp = value.get("source_timestamp")
        if isinstance(source_timestamp, str) and source_timestamp.strip():
            payload["source_timestamp"] = source_timestamp

        payload["quality_flags"] = _merge_string_list(payload["quality_flags"], value.get("quality_flags"))
        payload["warnings"] = _merge_string_list(payload["warnings"], value.get("warnings"))
        return payload

    if isinstance(value, dict):
        payload["data"] = value
        payload["quality_flags"].append("raw_payload_wrapped")
        return payload

    payload["data"] = {"value": value}
    payload["quality_flags"].append("non_object_payload_wrapped")
    return payload


class JSONFeedClient:
    def __init__(self, feed_name: str, config: ExternalFeedConfig, runtime: ProviderRuntimeConfig):
        self.feed_name = str(feed_name)
        self.config = config
        self.runtime = runtime

    def fetch(self, league: Any, week: int) -> Dict[str, Any]:
        payload = {
            "data": {},
            "source_timestamp": _utc_now(),
            "quality_flags": [],
            "warnings": [],
        }

        if not self.config.enabled:
            payload["quality_flags"].append("feed_disabled")
            return payload

        static_payloads = _normalize_mapping(self.config.static_payloads)
        if self.feed_name in static_payloads:
            return _coerce_feed_envelope(
                static_payloads[self.feed_name],
                base_quality_flags=["static_payload"],
                base_warnings=[],
            )

        endpoint_map = _normalize_mapping(self.config.endpoints)
        endpoint = _expand_env_string(endpoint_map.get(self.feed_name))
        if _is_unresolved_placeholder(endpoint):
            endpoint = None
        endpoint = endpoint or os.getenv(f"ALPHA_{self.feed_name.upper()}_ENDPOINT")
        if not endpoint:
            payload["quality_flags"].append("endpoint_not_configured")
            return payload

        headers = {
            str(key): str(_expand_env_string(value))
            for key, value in dict(_normalize_mapping(self.config.request_headers)).items()
        }
        api_keys = _normalize_mapping(self.config.api_keys)
        api_key = _expand_env_string(api_keys.get(self.feed_name))
        if _is_unresolved_placeholder(api_key):
            api_key = None
        api_key = api_key or os.getenv(f"ALPHA_{self.feed_name.upper()}_API_KEY")
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"

        params = _league_params(league, week)
        query = urllib.parse.urlencode(params)
        url = f"{endpoint}{'&' if '?' in endpoint else '?'}{query}"

        retries = max(0, int(getattr(self.runtime, "retries", 1)))
        timeout = float(getattr(self.runtime, "timeout_seconds", 2.0))
        backoff = float(getattr(self.runtime, "backoff_seconds", 0.2))

        last_error = ""
        for attempt in range(retries + 1):
            try:
                request = urllib.request.Request(url=url, headers=headers, method="GET")
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read().decode("utf-8")
                value = json.loads(raw)
                return _coerce_feed_envelope(
                    value,
                    base_quality_flags=["live_fetch"],
                    base_warnings=[],
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < retries and backoff > 0:
                    time.sleep(backoff)

        payload["quality_flags"].append("fetch_failed")
        payload["warnings"].append(f"{self.feed_name}_fetch_failed: {last_error}")
        return payload

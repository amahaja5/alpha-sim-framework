import json
import os
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
            payload["quality_flags"].append("static_payload")
            payload["data"] = static_payloads[self.feed_name]
            return payload

        endpoint_map = _normalize_mapping(self.config.endpoints)
        endpoint = endpoint_map.get(self.feed_name) or os.getenv(f"ALPHA_{self.feed_name.upper()}_ENDPOINT")
        if not endpoint:
            payload["quality_flags"].append("endpoint_not_configured")
            return payload

        headers = dict(_normalize_mapping(self.config.request_headers))
        api_keys = _normalize_mapping(self.config.api_keys)
        api_key = api_keys.get(self.feed_name) or os.getenv(f"ALPHA_{self.feed_name.upper()}_API_KEY")
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
                payload["data"] = value if isinstance(value, dict) else {"value": value}
                payload["quality_flags"].append("live_fetch")
                return payload
            except Exception as exc:
                last_error = str(exc)
                if attempt < retries and backoff > 0:
                    time.sleep(backoff)

        payload["quality_flags"].append("fetch_failed")
        payload["warnings"].append(f"{self.feed_name}_fetch_failed: {last_error}")
        return payload

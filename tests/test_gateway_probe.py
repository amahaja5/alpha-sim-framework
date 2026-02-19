import json
import tempfile
from unittest import TestCase, mock

from alpha_sim_framework.gateway_probe import run_gateway_probe, write_probe_outputs


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class GatewayProbeTest(TestCase):
    def _config(self):
        return {
            "context": {
                "league_id": 123,
                "year": 2025,
                "week": 4,
            },
            "runtime": {
                "attempts": 2,
                "timeout_seconds": 1.0,
            },
            "domains": {
                "weather": {
                    "candidates": [
                        {
                            "name": "ok-weather",
                            "url": "https://example.com/weather",
                            "canonical_domain": "weather",
                        },
                        {
                            "name": "bad-weather",
                            "url": "https://example.com/weather-bad",
                            "canonical_domain": "weather",
                        },
                    ]
                }
            },
        }

    def test_run_probe_promotes_primary_and_backup(self):
        good_payload = {
            "data": {
                "team_weather": {
                    "1": {
                        "is_dome": False,
                        "wind_mph": 12.0,
                        "precip_prob": 0.2,
                    }
                }
            },
            "source_timestamp": "2026-02-19T00:00:00+00:00",
            "quality_flags": ["live_fetch"],
            "warnings": [],
        }
        bad_payload = {
            "data": {},
            "source_timestamp": "2026-02-19T00:00:00+00:00",
            "quality_flags": ["live_fetch"],
            "warnings": [],
        }

        call_order = [
            _FakeResponse(good_payload),
            _FakeResponse(good_payload),
            _FakeResponse(bad_payload),
            _FakeResponse(bad_payload),
        ]

        with mock.patch("urllib.request.urlopen", side_effect=call_order):
            result = run_gateway_probe(self._config())

        promotions = result["promotions"]["weather"]
        self.assertEqual(promotions["primary"]["candidate"], "ok-weather")
        self.assertEqual(promotions["backup"]["candidate"], "bad-weather")

    def test_write_probe_outputs_creates_files(self):
        payload = {
            "generated_at_utc": "2026-02-19T00:00:00+00:00",
            "candidate_results": [],
            "promotions": {},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_probe_outputs(payload, temp_dir)
            with open(paths["json"], "r") as json_file:
                content = json.load(json_file)
            self.assertIn("generated_at_utc", content)
            with open(paths["markdown"], "r") as md_file:
                md = md_file.read()
            self.assertIn("Gateway Endpoint Probe Scorecard", md)

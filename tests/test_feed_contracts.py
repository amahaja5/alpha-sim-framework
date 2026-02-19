import os
from types import SimpleNamespace
from unittest import TestCase, mock

from alpha_sim_framework.alpha_types import ExternalFeedConfig, ProviderRuntimeConfig
from alpha_sim_framework.feed_contracts import build_empty_envelope, validate_canonical_feed, validate_feed_envelope
from alpha_sim_framework.providers.feeds.common import JSONFeedClient


class FeedContractsTest(TestCase):
    def test_validate_feed_envelope_success(self):
        payload = build_empty_envelope()
        payload["data"] = {}
        errors = validate_feed_envelope(payload)
        self.assertEqual(errors, [])

    def test_validate_weather_contract(self):
        payload = build_empty_envelope()
        payload["data"] = {
            "team_weather": {
                "1": {
                    "is_dome": False,
                    "wind_mph": 15.2,
                    "precip_prob": 0.4,
                }
            }
        }

        errors = validate_canonical_feed("weather", payload)
        self.assertEqual(errors, [])

    def test_validate_market_contract_failure(self):
        payload = build_empty_envelope()
        payload["data"] = {"projections": {"1": 10.0}}

        errors = validate_canonical_feed("market", payload)
        self.assertTrue(any("usage_trend" in err for err in errors))

    def test_validate_odds_contract(self):
        payload = build_empty_envelope()
        payload["data"] = {
            "defense_vs_position": {},
            "spread_by_team": {},
            "implied_total_by_team": {},
            "schedule_strength_by_team": {},
        }
        errors = validate_canonical_feed("odds", payload)
        self.assertEqual(errors, [])

    def test_validate_injury_contract(self):
        payload = build_empty_envelope()
        payload["data"] = {
            "injury_status": {},
            "team_injuries_by_position": {},
        }
        errors = validate_canonical_feed("injury_news", payload)
        self.assertEqual(errors, [])

    def test_validate_nextgenstats_contract(self):
        payload = build_empty_envelope()
        payload["data"] = {
            "player_metrics": {
                "101": {
                    "usage_over_expected": 1.1,
                    "route_participation": 0.82,
                    "avg_separation": 2.0,
                    "explosive_play_rate": 0.31,
                    "volatility_index": 5.6,
                }
            }
        }
        errors = validate_canonical_feed("nextgenstats", payload)
        self.assertEqual(errors, [])

    def test_validate_optional_extended_contract_fields(self):
        market_payload = build_empty_envelope()
        market_payload["data"] = {
            "projections": {},
            "usage_trend": {},
            "sentiment": {},
            "future_schedule_strength": {},
            "ownership_by_player": {"101": 0.22},
        }
        self.assertEqual(validate_canonical_feed("market", market_payload), [])

        odds_payload = build_empty_envelope()
        odds_payload["data"] = {
            "defense_vs_position": {},
            "spread_by_team": {"1": -4.5},
            "implied_total_by_team": {},
            "schedule_strength_by_team": {},
            "player_props_by_player": {"101": {"line_open": 74.5, "line_current": 78.5, "sharp_over_pct": 0.61}},
            "win_probability_by_team": {"1": 0.64},
            "live_game_state_by_team": {"1": {"quarter": 3, "time_remaining_sec": 420, "score_differential": 7}},
            "opening_spread_by_team": {"1": -3.0},
            "closing_spread_by_team": {"1": -4.5},
        }
        self.assertEqual(validate_canonical_feed("odds", odds_payload), [])

        injury_payload = build_empty_envelope()
        injury_payload["data"] = {
            "injury_status": {},
            "team_injuries_by_position": {},
            "backup_projection_ratio_by_player": {"101": 0.52},
        }
        self.assertEqual(validate_canonical_feed("injury_news", injury_payload), [])

        nextgen_payload = build_empty_envelope()
        nextgen_payload["data"] = {
            "player_metrics": {
                "101": {
                    "usage_over_expected": 1.1,
                    "route_participation": 0.82,
                    "avg_separation": 2.0,
                    "explosive_play_rate": 0.31,
                    "volatility_index": 5.6,
                    "red_zone_touch_share": 0.21,
                    "red_zone_touch_trend": 0.03,
                    "snap_share": 0.78,
                    "snap_share_trend": -0.02,
                }
            }
        }
        self.assertEqual(validate_canonical_feed("nextgenstats", nextgen_payload), [])

    def test_validate_optional_extended_contract_fields_rejects_invalid_types(self):
        market_payload = build_empty_envelope()
        market_payload["data"] = {
            "projections": {},
            "usage_trend": {},
            "sentiment": {},
            "future_schedule_strength": {},
            "ownership_by_player": {"101": 2.0},
        }
        self.assertTrue(any("ownership_by_player" in err for err in validate_canonical_feed("market", market_payload)))

        odds_payload = build_empty_envelope()
        odds_payload["data"] = {
            "defense_vs_position": {},
            "spread_by_team": {},
            "implied_total_by_team": {},
            "schedule_strength_by_team": {},
            "player_props_by_player": {"101": {"line_open": 74.5, "line_current": 78.5, "sharp_over_pct": 2.0}},
        }
        self.assertTrue(any("sharp_over_pct" in err for err in validate_canonical_feed("odds", odds_payload)))

        injury_payload = build_empty_envelope()
        injury_payload["data"] = {
            "injury_status": {},
            "team_injuries_by_position": {},
            "backup_projection_ratio_by_player": {"101": -0.1},
        }
        self.assertTrue(any("backup_projection_ratio_by_player" in err for err in validate_canonical_feed("injury_news", injury_payload)))

        nextgen_payload = build_empty_envelope()
        nextgen_payload["data"] = {
            "player_metrics": {
                "101": {
                    "snap_share": 1.3,
                }
            }
        }
        self.assertTrue(any("snap_share" in err for err in validate_canonical_feed("nextgenstats", nextgen_payload)))

    def test_json_feed_client_wraps_raw_static_payload(self):
        config = ExternalFeedConfig(
            enabled=True,
            static_payloads={
                "weather": {
                    "team_weather": {
                        "1": {
                            "is_dome": False,
                            "wind_mph": 10.0,
                            "precip_prob": 0.2,
                        }
                    }
                }
            },
        )
        runtime = ProviderRuntimeConfig()
        client = JSONFeedClient("weather", config, runtime)

        payload = client.fetch(SimpleNamespace(league_id=1, year=2025), week=3)

        self.assertIn("raw_payload_wrapped", payload["quality_flags"])
        self.assertIn("static_payload", payload["quality_flags"])
        self.assertIn("team_weather", payload["data"])

    def test_json_feed_client_expands_env_placeholders_for_endpoint_and_api_key(self):
        config = ExternalFeedConfig(
            enabled=True,
            endpoints={"weather": "${TEST_WEATHER_ENDPOINT}"},
            api_keys={"weather": "${TEST_WEATHER_KEY}"},
        )
        runtime = ProviderRuntimeConfig()
        client = JSONFeedClient("weather", config, runtime)

        class _Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"team_weather":{"1":{"is_dome":true,"wind_mph":0.0,"precip_prob":0.0}}}'

        seen = {}

        def _fake_urlopen(request, timeout=0):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            return _Resp()

        with mock.patch.dict(
            os.environ,
            {
                "TEST_WEATHER_ENDPOINT": "https://example.com/weather",
                "TEST_WEATHER_KEY": "secret-key",
            },
            clear=False,
        ):
            with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
                payload = client.fetch(SimpleNamespace(league_id=12, year=2025), week=7)

        self.assertEqual(seen["url"], "https://example.com/weather?league_id=12&year=2025&week=7")
        self.assertEqual(seen["auth"], "Bearer secret-key")
        self.assertIn("live_fetch", payload["quality_flags"])
        self.assertIn("raw_payload_wrapped", payload["quality_flags"])

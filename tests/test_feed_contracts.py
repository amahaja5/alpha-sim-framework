from unittest import TestCase

from alpha_sim_framework.feed_contracts import build_empty_envelope, validate_canonical_feed, validate_feed_envelope


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

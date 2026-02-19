import json
import os
import tempfile
from types import SimpleNamespace
from unittest import TestCase

from alpha_sim_framework.monte_carlo import MonteCarloSimulator
from alpha_sim_framework.providers import CompositeSignalProvider


class FakePlayer:
    def __init__(self, player_id, name, position, projected_avg, lineup_slot=None, percent_started=50.0):
        self.playerId = player_id
        self.name = name
        self.position = position
        self.projected_avg_points = projected_avg
        self.projected_total_points = projected_avg * 14
        self.avg_points = projected_avg
        self.lineupSlot = lineup_slot or position
        self.slot_position = self.lineupSlot
        self.eligibleSlots = [position, "FLEX"] if position in {"RB", "WR", "TE"} else [position]
        self.percent_started = percent_started
        self.injuryStatus = "NONE"
        self.injured = False
        self.stats = {
            1: {"points": projected_avg - 1.0},
            2: {"points": projected_avg + 1.0},
        }


class FakeTeam:
    def __init__(self, team_id, name, wins, scores, outcomes, roster):
        self.team_id = team_id
        self.team_name = name
        self.wins = wins
        self.losses = 0
        self.scores = scores
        self.outcomes = outcomes
        self.roster = roster
        self.schedule = []
        self.points_for = sum(score for score in scores if score is not None)


class FakeLeague:
    def __init__(self, teams):
        self.league_id = 999
        self.year = 2025
        self.current_week = 3
        self.teams = teams
        self.settings = SimpleNamespace(reg_season_count=14, playoff_team_count=2)

    def free_agents(self, week=None, size=50, position=None, position_id=None):
        return []


def _build_league():
    team1 = FakeTeam(
        1,
        "Team 1",
        1,
        [101.0, 99.0, None],
        ["W", "L", "U"],
        [
            FakePlayer(101, "QB-101", "QB", 20.0),
            FakePlayer(102, "RB-102", "RB", 15.0),
            FakePlayer(103, "RB-103", "RB", 14.0),
            FakePlayer(104, "WR-104", "WR", 15.0),
            FakePlayer(105, "WR-105", "WR", 13.0),
            FakePlayer(106, "TE-106", "TE", 11.0),
            FakePlayer(107, "K-107", "K", 8.0),
            FakePlayer(108, "DST-108", "D/ST", 8.0, lineup_slot="D/ST"),
            FakePlayer(109, "WR-109", "WR", 10.0),
        ],
    )

    team2 = FakeTeam(
        2,
        "Team 2",
        1,
        [97.0, 102.0, None],
        ["L", "W", "U"],
        [
            FakePlayer(201, "QB-201", "QB", 19.0),
            FakePlayer(202, "RB-202", "RB", 16.0),
            FakePlayer(203, "RB-203", "RB", 13.0),
            FakePlayer(204, "WR-204", "WR", 14.0),
            FakePlayer(205, "WR-205", "WR", 12.0),
            FakePlayer(206, "TE-206", "TE", 10.0),
            FakePlayer(207, "K-207", "K", 8.0),
            FakePlayer(208, "DST-208", "D/ST", 7.0, lineup_slot="D/ST"),
            FakePlayer(209, "WR-209", "WR", 9.0),
        ],
    )

    team1.schedule = [team2, team2, team2]
    team2.schedule = [team1, team1, team1]
    return FakeLeague([team1, team2])


def _provider_kwargs():
    return {
        "external_feeds": {
            "enabled": True,
            "static_payloads": {
                "market": {
                    "projections": {"101": 23.0, "102": 19.0, "201": 18.0},
                    "usage_trend": {"102": 2.5, "104": 1.8, "201": -1.0},
                    "sentiment": {"102": {"score": 0.8, "start_delta": 5.0}, "104": -0.4},
                    "future_schedule_strength": {"1": [1.0, 0.5, 0.4], "2": [-0.6, -0.3, -0.2]},
                },
                "odds": {
                    "defense_vs_position": {
                        "1": {"RB": -0.8, "WR": -0.6, "QB": -0.4},
                        "2": {"RB": 1.0, "WR": 0.8, "QB": 0.5},
                    },
                    "spread_by_team": {"1": -4.5, "2": 4.5},
                    "implied_total_by_team": {"1": 25.0, "2": 20.5},
                    "schedule_strength_by_team": {"1": [0.7, 0.5, 0.2], "2": [-0.5, -0.4, -0.2]},
                },
                "weather": {
                    "team_weather": {
                        "1": {"is_dome": False, "wind_mph": 19.0, "precip_prob": 0.55},
                        "2": {"is_dome": True, "wind_mph": 0.0, "precip_prob": 0.0},
                    }
                },
                "injury_news": {
                    "injury_status": {"203": "OUT", "106": "QUESTIONABLE"},
                    "team_injuries_by_position": {"2": {"RB": 1}},
                },
                "nextgenstats": {
                    "player_metrics": {
                        "101": {
                            "usage_over_expected": 0.9,
                            "route_participation": 0.68,
                            "avg_separation": 1.7,
                            "explosive_play_rate": 0.22,
                            "volatility_index": 4.1,
                        },
                        "104": {
                            "usage_over_expected": 1.4,
                            "route_participation": 0.84,
                            "avg_separation": 2.3,
                            "explosive_play_rate": 0.41,
                            "volatility_index": 6.2,
                        },
                    }
                },
            },
        },
        "runtime": {
            "cache_ttl_seconds": 300,
            "degrade_gracefully": True,
        },
    }


def _as_envelope(data, source_timestamp):
    return {
        "data": data,
        "source_timestamp": source_timestamp,
        "quality_flags": ["static_payload"],
        "warnings": [],
    }


def _provider_kwargs_extended():
    kwargs = _provider_kwargs()
    kwargs["enable_extended_signals"] = True
    static_payloads = kwargs["external_feeds"]["static_payloads"]

    static_payloads["market"]["projections"]["104"] = 21.0
    static_payloads["market"]["ownership_by_player"] = {
        "101": 0.68,
        "102": 0.34,
        "103": 0.52,
        "104": 0.12,
        "105": 0.60,
        "201": 0.55,
        "202": 0.28,
        "204": 0.40,
    }

    static_payloads["odds"]["player_props_by_player"] = {
        "102": {"line_open": 63.5, "line_current": 71.5, "sharp_over_pct": 0.64},
        "104": {"line_open": 74.5, "line_current": 81.5, "sharp_over_pct": 0.66},
    }
    static_payloads["odds"]["win_probability_by_team"] = {"1": 0.74, "2": 0.26}
    static_payloads["odds"]["live_game_state_by_team"] = {
        "1": {"quarter": 4, "time_remaining_sec": 120, "score_differential": 10},
        "2": {"quarter": 4, "time_remaining_sec": 120, "score_differential": -10},
    }
    static_payloads["odds"]["opening_spread_by_team"] = {"1": -2.5, "2": 2.5}
    static_payloads["odds"]["closing_spread_by_team"] = {"1": -5.5, "2": 5.5}

    static_payloads["injury_news"]["backup_projection_ratio_by_player"] = {
        "101": 0.90,
        "102": 0.32,
        "104": 0.72,
    }

    static_payloads["nextgenstats"]["player_metrics"]["102"] = {
        "red_zone_touch_share": 0.27,
        "red_zone_touch_trend": 0.05,
        "snap_share": 0.79,
        "snap_share_trend": 0.04,
    }
    static_payloads["nextgenstats"]["player_metrics"]["104"].update(
        {
            "red_zone_touch_share": 0.30,
            "red_zone_touch_trend": 0.06,
            "snap_share": 0.86,
            "snap_share_trend": 0.05,
        }
    )
    return kwargs


class CompositeSignalProviderTest(TestCase):
    def test_outputs_adjustments_matchups_and_diagnostics(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs())

        adjustments = provider.get_player_adjustments(league, week=3)
        matchups = provider.get_matchup_overrides(league, week=3)
        injuries = provider.get_injury_overrides(league, week=3)

        self.assertTrue(len(adjustments) >= 10)
        self.assertEqual(set(adjustments.keys()), set(matchups.keys()))
        self.assertIn(203, injuries)

        diagnostics = provider.last_diagnostics
        self.assertIn(101, diagnostics)
        self.assertIn("signals", diagnostics[101])
        self.assertIn("projection_residual", diagnostics[101]["signals"])

    def test_clipping_respects_total_and_matchup_bounds(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs())

        adjustments = provider.get_player_adjustments(league, week=3)
        matchups = provider.get_matchup_overrides(league, week=3)

        self.assertTrue(all(-6.0 <= value <= 6.0 for value in adjustments.values()))
        self.assertTrue(all(0.85 <= value <= 1.15 for value in matchups.values()))

    def test_deterministic_for_same_inputs(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs())

        first = provider.get_player_adjustments(league, week=3)
        second = provider.get_player_adjustments(league, week=3)

        self.assertEqual(first, second)

    def test_graceful_degradation_on_feed_failure(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs())

        def _explode(_league, _week):
            raise RuntimeError("feed down")

        provider._feeds["weather"].fetch = _explode

        adjustments = provider.get_player_adjustments(league, week=3)
        self.assertTrue(len(adjustments) > 0)
        self.assertTrue(any("weather_fetch_failed" in warning for warning in provider.last_warnings))

    def test_integration_with_monte_carlo_alpha_mode(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs())

        simulator = MonteCarloSimulator(
            league,
            num_simulations=40,
            seed=9,
            alpha_mode=True,
            provider=provider,
        )
        results = simulator.run_simulations()

        self.assertIn(1, results)
        self.assertIn("playoff_odds", results[1])

    def test_nextgenstats_payload_influences_adjustments(self):
        league = _build_league()

        base_kwargs = _provider_kwargs()
        with_nextgen = CompositeSignalProvider(**base_kwargs)

        without_nextgen_kwargs = _provider_kwargs()
        without_nextgen_kwargs["external_feeds"]["static_payloads"].pop("nextgenstats", None)
        without_nextgen = CompositeSignalProvider(**without_nextgen_kwargs)

        with_values = with_nextgen.get_player_adjustments(league, week=3)
        without_values = without_nextgen.get_player_adjustments(league, week=3)

        self.assertNotEqual(with_values.get(104), without_values.get(104))

    def test_contract_error_adds_warning_and_degrades_feed_payload(self):
        league = _build_league()
        bad_kwargs = _provider_kwargs()
        # Missing required keys for market canonical payload.
        bad_kwargs["external_feeds"]["static_payloads"]["market"] = {"projections": {"101": 22.0}}
        provider = CompositeSignalProvider(**bad_kwargs)

        provider.get_player_adjustments(league, week=3)
        payload = provider._get_week_payload(league, week=3)

        self.assertTrue(any("market_contract_error" in warning for warning in provider.last_warnings))
        self.assertIn("market:contract_invalid", payload["summary"]["quality_flags"])

    def test_as_of_cutoff_degrades_future_payload_to_prevent_leakage(self):
        league = _build_league()
        guarded_kwargs = _provider_kwargs()
        market_payload = guarded_kwargs["external_feeds"]["static_payloads"]["market"]
        guarded_kwargs["external_feeds"]["static_payloads"]["market"] = _as_envelope(
            market_payload, "2025-12-01T00:00:00+00:00"
        )
        guarded_kwargs["runtime"]["as_of_utc"] = "2025-10-01T00:00:00+00:00"
        guarded_kwargs["runtime"]["as_of_publication_lag_seconds_by_feed"] = {"market": 0}
        guarded_kwargs["runtime"]["as_of_snapshot_enabled"] = False

        provider = CompositeSignalProvider(**guarded_kwargs)
        provider.get_player_adjustments(league, week=3)
        payload = provider._get_week_payload(league, week=3)

        self.assertTrue(any("market_as_of_violation" in warning for warning in provider.last_warnings))
        self.assertIn("market:as_of_violation", payload["summary"]["quality_flags"])
        self.assertIn("market:as_of_degraded_to_empty", payload["summary"]["quality_flags"])

    def test_as_of_date_normalizes_to_utc_midnight(self):
        league = _build_league()
        guarded_kwargs = _provider_kwargs()
        market_payload = guarded_kwargs["external_feeds"]["static_payloads"]["market"]
        guarded_kwargs["external_feeds"]["static_payloads"]["market"] = _as_envelope(
            market_payload, "2025-10-01T00:00:00+00:00"
        )
        guarded_kwargs["runtime"]["as_of_date"] = "2025-10-01"
        guarded_kwargs["runtime"]["as_of_publication_lag_seconds_by_feed"] = {"market": 0}
        guarded_kwargs["runtime"]["as_of_snapshot_enabled"] = False

        provider = CompositeSignalProvider(**guarded_kwargs)
        provider.get_player_adjustments(league, week=3)
        payload = provider._get_week_payload(league, week=3)

        self.assertIn("market:as_of_date_normalized", payload["summary"]["quality_flags"])
        self.assertFalse(any("market_as_of_violation" in warning for warning in provider.last_warnings))

    def test_as_of_rejects_both_timestamp_and_date(self):
        guarded_kwargs = _provider_kwargs()
        guarded_kwargs["runtime"]["as_of_utc"] = "2025-10-01T00:00:00+00:00"
        guarded_kwargs["runtime"]["as_of_date"] = "2025-10-01"

        with self.assertRaises(ValueError):
            CompositeSignalProvider(**guarded_kwargs)

    def test_as_of_backward_selection_uses_latest_eligible_snapshot(self):
        league = _build_league()
        guarded_kwargs = _provider_kwargs()
        market_payload = guarded_kwargs["external_feeds"]["static_payloads"]["market"]
        guarded_kwargs["external_feeds"]["static_payloads"]["market"] = _as_envelope(
            market_payload, "2025-10-01T13:00:00+00:00"
        )
        guarded_kwargs["runtime"]["as_of_utc"] = "2025-10-01T12:00:00+00:00"
        guarded_kwargs["runtime"]["as_of_publication_lag_seconds_by_feed"] = {"market": 0}
        guarded_kwargs["runtime"]["as_of_snapshot_retention_days"] = 365

        with tempfile.TemporaryDirectory() as temp_dir:
            guarded_kwargs["runtime"]["as_of_snapshot_root"] = temp_dir
            snapshot_file = (
                f"{temp_dir}/{league.league_id}/{league.year}/week_3/market.jsonl"
            )
            os.makedirs(os.path.dirname(snapshot_file), exist_ok=True)
            old_record = {
                "schema_version": "1.0",
                "observed_at_utc": "2025-10-01T09:00:00+00:00",
                "league_id": league.league_id,
                "year": league.year,
                "week": 3,
                "feed_name": "market",
                "source_timestamp": "2025-10-01T10:00:00+00:00",
                "availability_timestamp": "2025-10-01T10:00:00+00:00",
                "payload": _as_envelope(
                    {
                        "projections": {"101": 11.0},
                        "usage_trend": market_payload["usage_trend"],
                        "sentiment": market_payload["sentiment"],
                        "future_schedule_strength": market_payload["future_schedule_strength"],
                    },
                    "2025-10-01T10:00:00+00:00",
                ),
            }
            new_record = {
                "schema_version": "1.0",
                "observed_at_utc": "2025-10-01T10:30:00+00:00",
                "league_id": league.league_id,
                "year": league.year,
                "week": 3,
                "feed_name": "market",
                "source_timestamp": "2025-10-01T11:00:00+00:00",
                "availability_timestamp": "2025-10-01T11:00:00+00:00",
                "payload": _as_envelope(
                    {
                        "projections": {"101": 19.0},
                        "usage_trend": market_payload["usage_trend"],
                        "sentiment": market_payload["sentiment"],
                        "future_schedule_strength": market_payload["future_schedule_strength"],
                    },
                    "2025-10-01T11:00:00+00:00",
                ),
            }
            with open(snapshot_file, "w", encoding="utf-8") as file_obj:
                file_obj.write(f"{json.dumps(old_record)}\n")
                file_obj.write(f"{json.dumps(new_record)}\n")

            provider = CompositeSignalProvider(**guarded_kwargs)
            provider.get_player_adjustments(league, week=3)
            market_feed = provider._fetch_feed("market", league, 3)

        self.assertEqual(market_feed["data"]["projections"]["101"], 19.0)
        self.assertIn("as_of_snapshot_selected", market_feed["quality_flags"])

    def test_as_of_lag_can_block_recent_source_until_available(self):
        league = _build_league()
        guarded_kwargs = _provider_kwargs()
        market_payload = guarded_kwargs["external_feeds"]["static_payloads"]["market"]
        guarded_kwargs["external_feeds"]["static_payloads"]["market"] = _as_envelope(
            market_payload, "2025-09-30T23:30:00+00:00"
        )
        guarded_kwargs["runtime"]["as_of_utc"] = "2025-10-01T00:00:00+00:00"
        guarded_kwargs["runtime"]["as_of_snapshot_enabled"] = False

        provider = CompositeSignalProvider(**guarded_kwargs)
        provider.get_player_adjustments(league, week=3)
        payload = provider._get_week_payload(league, week=3)

        self.assertIn("market:as_of_violation", payload["summary"]["quality_flags"])
        self.assertIn("market:as_of_degraded_to_empty", payload["summary"]["quality_flags"])

    def test_as_of_staleness_degrades_old_candidate(self):
        league = _build_league()
        guarded_kwargs = _provider_kwargs()
        market_payload = guarded_kwargs["external_feeds"]["static_payloads"]["market"]
        guarded_kwargs["external_feeds"]["static_payloads"]["market"] = _as_envelope(
            market_payload, "2025-10-01T00:00:00+00:00"
        )
        guarded_kwargs["runtime"]["as_of_utc"] = "2025-10-10T00:00:00+00:00"
        guarded_kwargs["runtime"]["as_of_publication_lag_seconds_by_feed"] = {"market": 0}
        guarded_kwargs["runtime"]["as_of_max_staleness_seconds_by_feed"] = {"market": 86400}
        guarded_kwargs["runtime"]["as_of_snapshot_enabled"] = False

        provider = CompositeSignalProvider(**guarded_kwargs)
        provider.get_player_adjustments(league, week=3)
        payload = provider._get_week_payload(league, week=3)

        self.assertIn("market:as_of_stale", payload["summary"]["quality_flags"])
        self.assertIn("market:as_of_degraded_to_empty", payload["summary"]["quality_flags"])

    def test_as_of_missing_snapshot_degrades_with_warning(self):
        league = _build_league()
        guarded_kwargs = _provider_kwargs()
        market_payload = guarded_kwargs["external_feeds"]["static_payloads"]["market"]
        guarded_kwargs["external_feeds"]["static_payloads"]["market"] = _as_envelope(market_payload, "")
        guarded_kwargs["runtime"]["as_of_utc"] = "2025-10-10T00:00:00+00:00"
        guarded_kwargs["runtime"]["as_of_snapshot_enabled"] = False

        provider = CompositeSignalProvider(**guarded_kwargs)
        provider.get_player_adjustments(league, week=3)
        payload = provider._get_week_payload(league, week=3)

        self.assertIn("market:as_of_missing_snapshot", payload["summary"]["quality_flags"])
        self.assertIn("market:as_of_degraded_to_empty", payload["summary"]["quality_flags"])
        self.assertTrue(any("market_as_of_missing_snapshot" in warning for warning in provider.last_warnings))

    def test_extended_signals_disabled_preserves_legacy_weight_behavior(self):
        league = _build_league()
        baseline_provider = CompositeSignalProvider(**_provider_kwargs())
        baseline_adjustments = baseline_provider.get_player_adjustments(league, week=3)

        disabled_kwargs = _provider_kwargs()
        disabled_kwargs["enable_extended_signals"] = False
        disabled_kwargs["weights"] = {
            "player_tilt_leverage": 25.0,
            "vegas_props": 25.0,
            "win_probability_script": 25.0,
            "backup_quality_adjustment": 25.0,
            "red_zone_opportunity": 25.0,
            "snap_count_percentage": 25.0,
            "line_movement": 25.0,
        }
        provider = CompositeSignalProvider(**disabled_kwargs)
        test_adjustments = provider.get_player_adjustments(league, week=3)

        self.assertEqual(baseline_adjustments, test_adjustments)

    def test_extended_signals_enabled_emits_new_signal_keys(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())

        provider.get_player_adjustments(league, week=3)
        diagnostics = provider.last_diagnostics
        self.assertIn(101, diagnostics)

        signal_names = diagnostics[101]["signals"].keys()
        for signal in (
            "player_tilt_leverage",
            "vegas_props",
            "win_probability_script",
            "backup_quality_adjustment",
            "red_zone_opportunity",
            "snap_count_percentage",
            "line_movement",
        ):
            self.assertIn(signal, signal_names)

    def test_player_tilt_leverage_directional(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())
        provider.get_player_adjustments(league, week=3)

        self.assertGreater(provider.last_diagnostics[104]["signals"]["player_tilt_leverage"], 0.0)

    def test_vegas_props_directional(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())
        provider.get_player_adjustments(league, week=3)

        self.assertGreater(provider.last_diagnostics[104]["signals"]["vegas_props"], 0.0)

    def test_win_probability_script_directional(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())
        provider.get_player_adjustments(league, week=3)

        self.assertGreater(provider.last_diagnostics[102]["signals"]["win_probability_script"], 0.0)

    def test_backup_quality_adjustment_directional(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())
        provider.get_player_adjustments(league, week=3)

        self.assertGreater(provider.last_diagnostics[102]["signals"]["backup_quality_adjustment"], 0.0)

    def test_red_zone_opportunity_directional(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())
        provider.get_player_adjustments(league, week=3)

        self.assertGreater(provider.last_diagnostics[104]["signals"]["red_zone_opportunity"], 0.0)

    def test_snap_count_percentage_directional(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())
        provider.get_player_adjustments(league, week=3)

        self.assertGreater(provider.last_diagnostics[104]["signals"]["snap_count_percentage"], 0.0)

    def test_line_movement_directional(self):
        league = _build_league()
        provider = CompositeSignalProvider(**_provider_kwargs_extended())
        provider.get_player_adjustments(league, week=3)

        self.assertGreater(provider.last_diagnostics[102]["signals"]["line_movement"], 0.0)

    def test_missing_extended_fields_degrade_to_neutral_not_failure(self):
        league = _build_league()
        kwargs = _provider_kwargs()
        kwargs["enable_extended_signals"] = True
        provider = CompositeSignalProvider(**kwargs)

        adjustments = provider.get_player_adjustments(league, week=3)
        self.assertTrue(len(adjustments) > 0)
        signals = provider.last_diagnostics[101]["signals"]
        self.assertEqual(signals["vegas_props"], 0.0)
        self.assertEqual(signals["win_probability_script"], 0.0)
        self.assertEqual(signals["backup_quality_adjustment"], 0.0)
        self.assertEqual(signals["red_zone_opportunity"], 0.0)
        self.assertEqual(signals["snap_count_percentage"], 0.0)
        self.assertEqual(signals["line_movement"], 0.0)

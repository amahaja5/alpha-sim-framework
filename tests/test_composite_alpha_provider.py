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
            },
        },
        "runtime": {
            "cache_ttl_seconds": 300,
            "degrade_gracefully": True,
        },
    }


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

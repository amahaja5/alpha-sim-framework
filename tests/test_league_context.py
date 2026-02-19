import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from alpha_sim_framework.historical_backtest import run_historical_backtest
from alpha_sim_framework.league_context import build_league_context, load_league_context, resolve_context_years


class FakePlayer:
    def __init__(self, player_id, name, position, week_points):
        self.playerId = player_id
        self.name = name
        self.position = position
        self.lineupSlot = position
        self.slot_position = position
        self.stats = {week: {"points": points} for week, points in week_points.items()}
        self.projected_total_points = 0.0
        self.projected_avg_points = 0.0
        self.avg_points = 0.0
        self.injuryStatus = "NONE"
        self.injured = False
        self.percent_started = 50.0
        self.pro_pos_rank = 0.0


class FakeTeam:
    def __init__(self, team_id, team_name, scores):
        self.team_id = team_id
        self.team_name = team_name
        self.wins = sum(1 for score in scores if score is not None and score >= 100)
        self.losses = sum(1 for score in scores if score is not None and score < 100)
        self.scores = scores
        self.outcomes = ["W" if score is not None and score >= 100 else "L" for score in scores]
        self.schedule = []
        self.roster = []
        self.points_for = float(sum(score for score in scores if score is not None))


class FakeMatchup:
    def __init__(self, home_team, away_team, home_lineup, away_lineup, home_score, away_score):
        self.home_team = home_team
        self.away_team = away_team
        self.home_lineup = home_lineup
        self.away_lineup = away_lineup
        self.home_score = home_score
        self.away_score = away_score


class FakeActivity:
    def __init__(self, date_ms, actions):
        self.date = date_ms
        self.actions = actions


class FakeLeague:
    def __init__(self, year):
        self.league_id = 9999
        self.year = year
        self.current_week = 2
        self.settings = SimpleNamespace(reg_season_count=2, playoff_team_count=2)

        t1 = FakeTeam(1, "Team 1", [110.0, 92.0])
        t2 = FakeTeam(2, "Team 2", [95.0, 101.0])
        t1.schedule = [2, 2]
        t2.schedule = [1, 1]
        t1.roster = [FakePlayer(11, "T1-RB", "RB", {1: 18.0, 2: 9.0})]
        t2.roster = [FakePlayer(21, "T2-RB", "RB", {1: 10.0, 2: 20.0})]
        self.teams = [t1, t2]
        self._team_map = {1: t1, 2: t2}

        self._box_scores = {
            1: [FakeMatchup(t1, t2, t1.roster, t2.roster, 110.0, 95.0)],
            2: [FakeMatchup(t1, t2, t1.roster, t2.roster, 92.0, 101.0)],
        }
        self._activities = [
            FakeActivity(
                1757000000000,
                [
                    (t1, "FA ADDED", FakePlayer(31, "New Player", "WR", {2: 12.0}), 0),
                    (t1, "DROPPED", FakePlayer(32, "Old Player", "WR", {2: 0.0}), 0),
                ],
            )
        ]

    def box_scores(self, week=None):
        return list(self._box_scores.get(week, []))

    def recent_activity(self, size=25, msg_type=None, offset=0):
        if offset >= len(self._activities):
            return []
        return self._activities[offset:offset + size]


class LeagueContextTest(TestCase):
    def test_resolve_years_default_includes_current_plus_lookback(self):
        cfg = SimpleNamespace(start_year=None, end_year=None, lookback_seasons=3)
        self.assertEqual(resolve_context_years(2025, cfg), [2022, 2023, 2024, 2025])

    def test_build_and_load_context_manifest_tables_and_features(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_league_context(
                {
                    "league_id": 9999,
                    "year": 2025,
                    "lookback_seasons": 0,
                    "context_dir": temp_dir,
                    "league_loader": lambda year: FakeLeague(year),
                }
            )
            self.assertEqual(result["sync_mode"], "full")
            self.assertEqual(result["seasons_synced"], [2025])
            context_root = Path(result["context_root"])
            self.assertTrue((context_root / "context_manifest.json").exists())
            self.assertTrue((context_root / "derived" / "league_behavior_summary.json").exists())

            loaded = load_league_context(str(context_root))
            self.assertIn("manifest", loaded)
            self.assertIn("2025", loaded["tables"])
            self.assertTrue(len(loaded["tables"]["2025"]["teams"]) >= 2)
            self.assertTrue(len(loaded["tables"]["2025"]["team_behavior_features"]) >= 2)

    def test_incremental_mode_uses_existing_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = build_league_context(
                {
                    "league_id": 9999,
                    "year": 2025,
                    "lookback_seasons": 0,
                    "context_dir": temp_dir,
                    "league_loader": lambda year: FakeLeague(year),
                }
            )
            self.assertEqual(first["sync_mode"], "full")

            second = build_league_context(
                {
                    "league_id": 9999,
                    "year": 2025,
                    "lookback_seasons": 0,
                    "context_dir": temp_dir,
                    "league_loader": lambda year: FakeLeague(year),
                }
            )
            self.assertEqual(second["sync_mode"], "incremental")

    def test_historical_backtest_context_fallback_to_live_loader(self):
        simulator = SimpleNamespace(_team_map={1: SimpleNamespace(team_name="Team 1")}, league=SimpleNamespace())
        out = run_historical_backtest(
            simulator,
            config={
                "league_id": 9999,
                "team_id": 1,
                "year": 2025,
                "start_year": 2025,
                "end_year": 2025,
                "context_path": "/tmp/missing-context-path",
                "league_loader": lambda year: FakeLeague(year),
            },
        )
        self.assertIn("warnings", out)
        self.assertTrue(any("context_load_failed" in warning for warning in out["warnings"]))
        self.assertTrue(len(out["opponents"]) >= 1)

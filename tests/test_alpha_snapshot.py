from types import SimpleNamespace
from unittest import TestCase

from alpha_sim_framework.alpha_snapshot import build_week_snapshot


class DummyPlayer:
    def __init__(self, name, lineup_slot="BE"):
        self.name = name
        self.lineupSlot = lineup_slot


class DummyTeam:
    def __init__(self, team_id, roster):
        self.team_id = team_id
        self.roster = roster


class DummyBoxScore:
    def __init__(self, home_team, away_team, home_lineup, away_lineup):
        self.home_team = home_team
        self.away_team = away_team
        self.home_lineup = home_lineup
        self.away_lineup = away_lineup


class LeagueWithBox:
    def __init__(self):
        self.current_week = 3
        self.teams = [
            DummyTeam(1, [DummyPlayer("A", "QB"), DummyPlayer("B", "BE")]),
            DummyTeam(2, [DummyPlayer("C", "RB"), DummyPlayer("D", "BE")]),
        ]

    def box_scores(self, week=None):
        return [
            DummyBoxScore(
                home_team=SimpleNamespace(team_id=1),
                away_team=SimpleNamespace(team_id=2),
                home_lineup=[DummyPlayer("A", "QB"), DummyPlayer("X", "BE")],
                away_lineup=[DummyPlayer("C", "RB")],
            )
        ]

    def free_agents(self, week=None, size=50):
        return [DummyPlayer("FA1"), DummyPlayer("FA2")]


class LeagueNoBox(LeagueWithBox):
    def box_scores(self, week=None):
        raise Exception("no box")


class AlphaSnapshotTest(TestCase):
    def test_snapshot_uses_box_scores_when_available(self):
        league = LeagueWithBox()
        snapshot = build_week_snapshot(league, week=3, candidate_pool_size=2)

        self.assertEqual(snapshot["week"], 3)
        self.assertEqual(len(snapshot["lineups"][1]), 1)
        self.assertEqual(snapshot["lineups"][1][0].name, "A")
        self.assertEqual(len(snapshot["free_agents"]), 2)

    def test_snapshot_falls_back_to_roster_when_box_unavailable(self):
        league = LeagueNoBox()
        snapshot = build_week_snapshot(league, week=3, candidate_pool_size=2)

        self.assertEqual(len(snapshot["lineups"][1]), 1)
        self.assertEqual(snapshot["lineups"][1][0].name, "A")

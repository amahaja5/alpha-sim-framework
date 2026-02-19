from types import SimpleNamespace
from unittest import TestCase

from alpha_sim_framework.monte_carlo import MonteCarloSimulator


class FakePlayer:
    def __init__(self, player_id, position, week_points):
        self.playerId = player_id
        self.name = f"{position}-{player_id}"
        self.position = position
        self.lineupSlot = position
        self.slot_position = position
        self.stats = {week: {"points": points} for week, points in week_points.items()}


class FakeTeam:
    def __init__(self, team_id, team_name, scores):
        self.team_id = team_id
        self.team_name = team_name
        self.scores = scores
        self.outcomes = ["W" if score and score >= 100 else "L" for score in scores]
        self.roster = []
        self.schedule = []


class FakeMatchup:
    def __init__(self, home_team, away_team, home_lineup, away_lineup):
        self.home_team = home_team
        self.away_team = away_team
        self.home_lineup = home_lineup
        self.away_lineup = away_lineup


class FakeLeague:
    def __init__(self, teams, box_scores_by_week):
        self.teams = teams
        self.settings = SimpleNamespace(reg_season_count=2, playoff_team_count=2)
        self.current_week = 2
        self._box_scores_by_week = box_scores_by_week

    def box_scores(self, week=None):
        return list(self._box_scores_by_week.get(week, []))


class SimPlayer:
    def __init__(self, player_id, position, projected_total_points, projected_avg_points):
        self.playerId = player_id
        self.position = position
        self.projected_total_points = projected_total_points
        self.projected_avg_points = projected_avg_points
        self.avg_points = projected_avg_points
        self.name = f"{position}-{player_id}"
        self.lineupSlot = position
        self.eligibleSlots = [position, "FLEX"] if position in ("RB", "WR", "TE") else [position]
        self.injuryStatus = "NONE"
        self.injured = False
        self.percent_started = 50.0
        self.stats = {1: {"points": projected_avg_points}}


class SimTeam:
    def __init__(self, team_id, team_name, wins, scores):
        self.team_id = team_id
        self.team_name = team_name
        self.wins = wins
        self.losses = 0
        self.scores = scores
        self.outcomes = ["W" if score is not None else "U" for score in scores]
        self.roster = [
            SimPlayer(team_id * 10 + 1, "QB", 280, 20.0),
            SimPlayer(team_id * 10 + 2, "RB", 220, 15.5),
            SimPlayer(team_id * 10 + 3, "WR", 210, 14.5),
            SimPlayer(team_id * 10 + 4, "TE", 150, 10.5),
            SimPlayer(team_id * 10 + 5, "K", 110, 8.0),
            SimPlayer(team_id * 10 + 6, "D/ST", 105, 7.5),
        ]
        self.schedule = []
        self.points_for = sum(score for score in scores if score is not None)


class SimLeague:
    def __init__(self, teams):
        self.teams = teams
        self.current_week = 2
        self.settings = SimpleNamespace(playoff_team_count=2, reg_season_count=2)

    def free_agents(self, week=None, size=50, position=None, position_id=None):
        return []


def _build_simulator_league():
    team1 = SimTeam(1, "Team 1", 1, [101.0, None])
    team2 = SimTeam(2, "Team 2", 0, [90.0, None])
    team1.schedule = [team2, team2]
    team2.schedule = [team1, team1]
    return SimLeague([team1, team2])


def _build_season(year, target_team_id):
    you = FakeTeam(target_team_id, "Team 1", [95.0, 88.0])
    rival_id = 200 + year
    rival = FakeTeam(rival_id, "Rivals", [120.0, 72.0])

    you.schedule = [rival, rival]
    rival.schedule = [you, you]

    you_lineup_w1 = [FakePlayer(11, "RB", {1: 12.0}), FakePlayer(12, "WR", {1: 8.0})]
    rival_lineup_w1 = [FakePlayer(21, "RB", {1: 30.0}), FakePlayer(22, "WR", {1: 5.0})]
    you_lineup_w2 = [FakePlayer(13, "RB", {2: 10.0}), FakePlayer(14, "WR", {2: 6.0})]
    rival_lineup_w2 = [FakePlayer(21, "RB", {2: 8.0}), FakePlayer(22, "WR", {2: 7.0})]

    box_scores = {
        1: [FakeMatchup(you, rival, you_lineup_w1, rival_lineup_w1)],
        2: [FakeMatchup(you, rival, you_lineup_w2, rival_lineup_w2)],
    }
    return FakeLeague([you, rival], box_scores)


class HistoricalBacktestTest(TestCase):
    def test_default_lookback_uses_last_three_years(self):
        simulator = MonteCarloSimulator(_build_simulator_league(), num_simulations=20, seed=1)
        seasons = {
            2023: _build_season(2023, 1),
            2024: _build_season(2024, 1),
            2025: _build_season(2025, 1),
        }

        backtest = simulator.run_historical_opponent_backtest(
            config={
                "league_id": 1234,
                "team_id": 1,
                "year": 2025,
                "league_loader": lambda year: seasons[year],
            }
        )

        self.assertEqual(backtest["analysis_window"]["years_requested"], [2023, 2024, 2025])
        self.assertEqual(backtest["analysis_window"]["years_skipped"], [])

    def test_returns_quant_and_qual_fields(self):
        simulator = MonteCarloSimulator(_build_simulator_league(), num_simulations=20, seed=1)
        seasons = {
            2023: _build_season(2023, 1),
            2024: _build_season(2024, 99),
            2025: _build_season(2025, 1),
        }

        backtest = simulator.run_historical_opponent_backtest(
            config={
                "league_id": 4321,
                "team_id": 1,
                "year": 2025,
                "league_loader": lambda year: seasons[year],
            }
        )

        self.assertGreaterEqual(len(backtest["opponents"]), 1)
        report = backtest["opponents"][0]
        self.assertIn("quant_metrics", report)
        self.assertIn("qualitative_tags", report)
        self.assertIn("narrative_summary", report)
        self.assertIn("confidence", report)
        self.assertIn("games_sampled", report["quant_metrics"])
        self.assertIn("position_pressure_index", report["quant_metrics"])
        self.assertTrue(len(report["qualitative_tags"]) >= 1)
        self.assertTrue(any("team_id_mismatch" in warning for warning in backtest["warnings"]))

    def test_skips_unavailable_seasons_and_records_warning(self):
        simulator = MonteCarloSimulator(_build_simulator_league(), num_simulations=20, seed=1)
        seasons = {
            2023: _build_season(2023, 1),
            2025: _build_season(2025, 1),
        }

        def loader(year):
            if year not in seasons:
                raise RuntimeError("access denied")
            return seasons[year]

        backtest = simulator.run_historical_opponent_backtest(
            config={
                "league_id": 9999,
                "team_id": 1,
                "year": 2025,
                "league_loader": loader,
            }
        )

        self.assertIn(2024, backtest["analysis_window"]["years_skipped"])
        self.assertTrue(any("load_failed" in warning for warning in backtest["warnings"]))

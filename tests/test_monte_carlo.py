import copy
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from alpha_sim_framework.monte_carlo import MonteCarloSimulator


class DummyPlayer:
    _counter = 0

    def __init__(self, position, projected_total_points, projected_avg_points=0, avg_points=0, lineup_slot="BE"):
        DummyPlayer._counter += 1
        self.playerId = DummyPlayer._counter
        self.position = position
        self.projected_total_points = projected_total_points
        self.projected_avg_points = projected_avg_points
        self.avg_points = avg_points
        self.name = f"{position}-player-{self.playerId}"
        self.lineupSlot = lineup_slot
        self.eligibleSlots = [position, "FLEX"] if position in ("RB", "WR", "TE") else [position]
        self.injuryStatus = "NONE"
        self.injured = False
        self.percent_started = 50.0
        self.stats = {
            0: {"projected_points": projected_total_points, "projected_avg_points": projected_avg_points},
            1: {"points": max(0.0, projected_total_points / 14.0)},
        }
        self.active_status = "active"


class DummyTeam:
    def __init__(self, team_id, team_name, wins, losses, scores, outcomes, roster):
        self.team_id = team_id
        self.team_name = team_name
        self.wins = wins
        self.losses = losses
        self.scores = scores
        self.outcomes = outcomes
        self.roster = roster
        self.schedule = []
        self.points_for = sum(score for score in scores if score is not None)


class DummyLeague:
    def __init__(self, teams, current_week=2, playoff_team_count=4, reg_season_count=14):
        self.teams = teams
        self.current_week = current_week
        self.settings = SimpleNamespace(
            playoff_team_count=playoff_team_count,
            reg_season_count=reg_season_count,
        )

    def get_team_data(self, team_id):
        for team in self.teams:
            if team.team_id == team_id:
                return team
        return None

    def free_agents(self, week=None, size=50, position=None, position_id=None):
        return []


class DummyNonNflTeam:
    def __init__(self):
        self.team_id = 99
        self.team_name = "NonNFL"
        self.wins = 0
        self.losses = 0
        self.roster = []
        self.scores = []
        self.outcomes = []
        self.points_for = 0
        self.schedule = [SimpleNamespace(week=1, home_team=1, away_team=2)]


class DummyNonNflLeague:
    def __init__(self):
        self.teams = [DummyNonNflTeam()]
        self.current_week = 1
        self.settings = SimpleNamespace(playoff_team_count=4, reg_season_count=14)


def build_league():
    team1 = DummyTeam(
        1,
        "Team 1",
        1,
        0,
        [110.0, None, None],
        ["W", "U", "U"],
        [
            DummyPlayer("QB", 320, projected_avg_points=22.0, lineup_slot="QB"),
            DummyPlayer("RB", 240, projected_avg_points=16.0, lineup_slot="RB"),
            DummyPlayer("WR", 210, projected_avg_points=15.0, lineup_slot="WR"),
            DummyPlayer("TE", 180, projected_avg_points=13.0, lineup_slot="TE"),
            DummyPlayer("K", 120, projected_avg_points=8.0, lineup_slot="K"),
            DummyPlayer("D/ST", 110, projected_avg_points=7.0, lineup_slot="D/ST"),
        ],
    )
    team2 = DummyTeam(
        2,
        "Team 2",
        0,
        1,
        [92.0, None, None],
        ["L", "U", "U"],
        [
            DummyPlayer("QB", 300, projected_avg_points=21.0, lineup_slot="QB"),
            DummyPlayer("RB", 180, projected_avg_points=12.0, lineup_slot="RB"),
            DummyPlayer("WR", 230, projected_avg_points=16.5, lineup_slot="WR"),
            DummyPlayer("K", 115, projected_avg_points=8.0, lineup_slot="K"),
            DummyPlayer("D/ST", 108, projected_avg_points=7.0, lineup_slot="D/ST"),
        ],
    )
    team3 = DummyTeam(
        3,
        "Team 3",
        1,
        0,
        [104.0, None, None],
        ["W", "U", "U"],
        [
            DummyPlayer("QB", 290, projected_avg_points=20.0, lineup_slot="QB"),
            DummyPlayer("RB", 250, projected_avg_points=17.0, lineup_slot="RB"),
            DummyPlayer("TE", 160, projected_avg_points=11.5, lineup_slot="TE"),
            DummyPlayer("WR", 190, projected_avg_points=13.0, lineup_slot="WR"),
            DummyPlayer("K", 112, projected_avg_points=8.0, lineup_slot="K"),
            DummyPlayer("D/ST", 105, projected_avg_points=7.0, lineup_slot="D/ST"),
        ],
    )
    team4 = DummyTeam(
        4,
        "Team 4",
        0,
        1,
        [88.0, None, None],
        ["L", "U", "U"],
        [
            DummyPlayer("QB", 275, projected_avg_points=19.0, lineup_slot="QB"),
            DummyPlayer("RB", 200, projected_avg_points=14.0, lineup_slot="RB"),
            DummyPlayer("WR", 185, projected_avg_points=13.0, lineup_slot="WR"),
            DummyPlayer("TE", 140, projected_avg_points=10.0, lineup_slot="TE"),
            DummyPlayer("K", 109, projected_avg_points=7.0, lineup_slot="K"),
            DummyPlayer("D/ST", 98, projected_avg_points=7.0, lineup_slot="D/ST"),
        ],
    )

    # Week 1: 1v2, 3v4 (played)
    # Week 2: 1v3, 2v4 (remaining)
    # Week 3: 1v4, 2v3 (remaining)
    team1.schedule = [team2, team3, team4]
    team2.schedule = [team1, team4, team3]
    team3.schedule = [team4, team1, team2]
    team4.schedule = [team3, team2, team1]

    return DummyLeague([team1, team2, team3, team4])


class MonteCarloSimulatorTest(TestCase):
    def test_rejects_non_nfl_league_shape(self):
        with self.assertRaises(ValueError):
            MonteCarloSimulator(DummyNonNflLeague(), num_simulations=10)

    def test_remaining_schedule_handles_football_shape(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=10, seed=1)

        # Weeks 2 and 3 contain 4 unique games total.
        self.assertEqual(len(simulator.schedule), 4)
        self.assertTrue(all(game["week"] in (2, 3) for game in simulator.schedule))

    def test_run_simulations_output_shape_and_ranges(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=200, seed=2)

        results = simulator.run_simulations()

        self.assertEqual(set(results.keys()), {1, 2, 3, 4})
        for team_id in results:
            team_result = results[team_id]
            self.assertIn("avg_wins", team_result)
            self.assertIn("playoff_odds", team_result)
            self.assertIn("championship_odds", team_result)
            self.assertGreaterEqual(team_result["playoff_odds"], 0.0)
            self.assertLessEqual(team_result["playoff_odds"], 100.0)
            self.assertGreaterEqual(team_result["championship_odds"], 0.0)
            self.assertLessEqual(team_result["championship_odds"], 100.0)

    def test_run_simulations_explain_adds_meta_only(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=50, seed=2, alpha_mode=True)

        results = simulator.run_simulations(explain=True)

        self.assertIn("_meta", results)
        self.assertTrue(results["_meta"]["alpha_mode"])
        self.assertIn(1, results)
        self.assertIn("avg_wins", results[1])

    def test_seed_reproducibility(self):
        league1 = build_league()
        league2 = build_league()

        simulator1 = MonteCarloSimulator(league1, num_simulations=150, seed=42)
        simulator2 = MonteCarloSimulator(league2, num_simulations=150, seed=42)

        self.assertEqual(simulator1.run_simulations(), simulator2.run_simulations())

    def test_different_seed_changes_outputs(self):
        league1 = build_league()
        league2 = build_league()

        simulator1 = MonteCarloSimulator(league1, num_simulations=120, seed=101)
        simulator2 = MonteCarloSimulator(league2, num_simulations=120, seed=202)

        self.assertNotEqual(simulator1.run_simulations(), simulator2.run_simulations())

    def test_analyze_draft_strategy_structure(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=50, preseason=True, seed=3)

        strategy_results = simulator.analyze_draft_strategy()

        self.assertEqual(set(strategy_results.keys()), {"Zero RB", "RB Heavy", "Balanced"})
        for strategy in strategy_results:
            self.assertTrue(len(strategy_results[strategy]) > 0)
            first_result = strategy_results[strategy][0]
            self.assertIn("composition", first_result)
            self.assertIn("star_players", first_result)
            self.assertIn("total_projection", first_result)

    def test_get_optimal_moves_handles_missing_position_starter(self):
        league = build_league()
        # Team 2 has no TE on roster; adding one should not crash.
        free_agents = [DummyPlayer("TE", 190)]

        simulator = MonteCarloSimulator(league, num_simulations=20, seed=10)
        moves = simulator.get_optimal_moves(team_id=2, free_agents=free_agents)

        add_moves = [move for move in moves if move["type"] == "add"]
        self.assertTrue(len(add_moves) >= 1)

    def test_get_optimal_moves_explain_contains_factors(self):
        league = build_league()
        free_agents = [DummyPlayer("TE", 900, projected_avg_points=64.0)]
        simulator = MonteCarloSimulator(league, num_simulations=20, seed=10, alpha_mode=True)

        moves = simulator.get_optimal_moves(team_id=2, free_agents=free_agents, explain=True)
        add_moves = [move for move in moves if move["type"] == "add" and move["player"].playerId == free_agents[0].playerId]

        self.assertTrue(len(add_moves) >= 1)
        self.assertIn("factors", add_moves[0])
        self.assertIn("confidence_band", add_moves[0])

    def test_recommend_lineup_returns_expected_structure(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=25, seed=15, alpha_mode=True)

        lineup = simulator.recommend_lineup(team_id=1, explain=True)
        self.assertIn("recommended_lineup", lineup)
        self.assertIn("current_lineup", lineup)
        self.assertIn("projected_delta", lineup)
        self.assertIn("details", lineup)

    def test_recommend_lineup_uses_requested_week_for_alpha(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=25, seed=15, alpha_mode=True)

        simulator.recommend_lineup(team_id=1, week=3, explain=True)

        self.assertEqual(simulator._alpha_week_cache, 3)

    def test_recommend_lineup_explain_without_alpha_does_not_call_alpha_pipeline(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=25, seed=15, alpha_mode=False)

        def _raise_if_called(*args, **kwargs):
            raise AssertionError("alpha projection pipeline should not run when alpha_mode=False")

        simulator._get_alpha_projection_map = _raise_if_called  # type: ignore[method-assign]
        lineup = simulator.recommend_lineup(team_id=1, explain=True)
        self.assertIn("details", lineup)

    def test_provider_adjustment_changes_alpha_value(self):
        class TestProvider:
            def get_player_adjustments(self, league, week):
                return {}

            def get_injury_overrides(self, league, week):
                return {}

            def get_matchup_overrides(self, league, week):
                return {}

        league = build_league()
        target_player = DummyPlayer("TE", 420, projected_avg_points=30.0)
        free_agents = [target_player]
        simulator_without = MonteCarloSimulator(league, num_simulations=20, seed=4, alpha_mode=True)
        simulator_without._get_alpha_projection_map(extra_players=free_agents)
        baseline_value = simulator_without._calculate_player_alpha_value(target_player, simulator_without._team_map[2])

        class BoostProvider(TestProvider):
            def get_player_adjustments(self, league, week):
                return {target_player.playerId: 7.0}

        simulator_with = MonteCarloSimulator(
            build_league(),
            num_simulations=20,
            seed=4,
            alpha_mode=True,
            provider=BoostProvider(),
        )
        simulator_with._get_alpha_projection_map(extra_players=free_agents)
        boosted_value = simulator_with._calculate_player_alpha_value(target_player, simulator_with._team_map[2])

        self.assertGreater(boosted_value, baseline_value)

    def test_backtest_alpha_returns_metrics(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=30, seed=18, alpha_mode=True)
        backtest = simulator.backtest_alpha()
        self.assertIn("ev_delta", backtest)
        self.assertIn("brier_score", backtest)

    def test_run_historical_opponent_backtest_returns_window_and_opponents(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=30, seed=18, alpha_mode=True)
        season_map = {
            2023: build_league(),
            2024: build_league(),
            2025: build_league(),
        }

        backtest = simulator.run_historical_opponent_backtest(
            config={
                "league_id": 12345,
                "team_id": 1,
                "year": 2025,
                "league_loader": lambda year: season_map[year],
            }
        )

        self.assertEqual(backtest["analysis_window"]["years_requested"], [2023, 2024, 2025])
        self.assertIn("opponents", backtest)

    def test_run_historical_opponent_backtest_context_path_parity_with_live_loader(self):
        def build_small_league():
            team1 = DummyTeam(1, "Team 1", 1, 0, [105.0, 90.0], ["W", "L"], [DummyPlayer("RB", 200, 14.0)])
            team2 = DummyTeam(2, "Team 2", 1, 0, [95.0, 101.0], ["L", "W"], [DummyPlayer("RB", 210, 15.0)])
            team1.schedule = [team2, team2]
            team2.schedule = [team1, team1]

            class Matchup:
                def __init__(self, home_team, away_team, home_lineup, away_lineup, home_score, away_score):
                    self.home_team = home_team
                    self.away_team = away_team
                    self.home_lineup = home_lineup
                    self.away_lineup = away_lineup
                    self.home_score = home_score
                    self.away_score = away_score

            class Lg:
                def __init__(self):
                    self.league_id = 1
                    self.year = 2025
                    self.current_week = 2
                    self.settings = SimpleNamespace(reg_season_count=2, playoff_team_count=2)
                    self.teams = [team1, team2]

                def box_scores(self, week=None):
                    if week == 1:
                        return [Matchup(team1, team2, team1.roster, team2.roster, 105.0, 95.0)]
                    if week == 2:
                        return [Matchup(team1, team2, team1.roster, team2.roster, 90.0, 101.0)]
                    return []

            return Lg()

        simulator = MonteCarloSimulator(build_league(), num_simulations=20, seed=22, alpha_mode=True)
        live = simulator.run_historical_opponent_backtest(
            config={
                "league_id": 1,
                "team_id": 1,
                "year": 2025,
                "start_year": 2025,
                "end_year": 2025,
                "league_loader": lambda year: build_small_league(),
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "raw" / "2025" / "box_scores").mkdir(parents=True, exist_ok=True)
            manifest = {
                "league_id": 1,
                "seasons": [2025],
                "last_sync_utc": "2026-01-01T00:00:00+00:00",
                "sync_mode": "full",
                "record_counts": {},
                "data_quality_flags": [],
                "schema_version": "1.0",
                "endpoint_watermarks": {"2025": {"last_activity_offset": 0, "last_completed_week": 2}},
            }
            (root / "context_manifest.json").write_text(json.dumps(manifest))
            snapshot = {
                "league_id": 1,
                "year": 2025,
                "current_week": 2,
                "reg_season_count": 2,
                "playoff_team_count": 2,
                "teams": [
                    {
                        "team_id": 1,
                        "team_name": "Team 1",
                        "wins": 1,
                        "losses": 1,
                        "scores": [105.0, 90.0],
                        "outcomes": ["W", "L"],
                        "schedule": [2, 2],
                        "roster": [
                            {
                                "playerId": 1,
                                "name": "RB-1",
                                "position": "RB",
                                "lineupSlot": "RB",
                                "slot_position": "RB",
                                "stats": {1: {"points": 15.0}, 2: {"points": 11.0}},
                            }
                        ],
                    },
                    {
                        "team_id": 2,
                        "team_name": "Team 2",
                        "wins": 1,
                        "losses": 1,
                        "scores": [95.0, 101.0],
                        "outcomes": ["L", "W"],
                        "schedule": [1, 1],
                        "roster": [
                            {
                                "playerId": 2,
                                "name": "RB-2",
                                "position": "RB",
                                "lineupSlot": "RB",
                                "slot_position": "RB",
                                "stats": {1: {"points": 10.0}, 2: {"points": 20.0}},
                            }
                        ],
                    },
                ],
            }
            (root / "raw" / "2025" / "league_snapshot.json").write_text(json.dumps(snapshot))
            wk1 = {
                "year": 2025,
                "week": 1,
                "matchups": [
                    {
                        "home_team_id": 1,
                        "away_team_id": 2,
                        "home_score": 105.0,
                        "away_score": 95.0,
                        "home_lineup": snapshot["teams"][0]["roster"],
                        "away_lineup": snapshot["teams"][1]["roster"],
                    }
                ],
            }
            wk2 = {
                "year": 2025,
                "week": 2,
                "matchups": [
                    {
                        "home_team_id": 1,
                        "away_team_id": 2,
                        "home_score": 90.0,
                        "away_score": 101.0,
                        "home_lineup": snapshot["teams"][0]["roster"],
                        "away_lineup": snapshot["teams"][1]["roster"],
                    }
                ],
            }
            (root / "raw" / "2025" / "box_scores" / "week_1.json").write_text(json.dumps(wk1))
            (root / "raw" / "2025" / "box_scores" / "week_2.json").write_text(json.dumps(wk2))

            from_context = simulator.run_historical_opponent_backtest(
                config={
                    "league_id": 1,
                    "team_id": 1,
                    "year": 2025,
                    "start_year": 2025,
                    "end_year": 2025,
                    "context_path": str(root),
                }
            )

        self.assertEqual(len(live["opponents"]), len(from_context["opponents"]))
        self.assertEqual(
            live["opponents"][0]["quant_metrics"]["games_sampled"],
            from_context["opponents"][0]["quant_metrics"]["games_sampled"],
        )

    def test_analyze_draft_strategy_does_not_mutate_baseline_ratings(self):
        league = build_league()
        simulator = MonteCarloSimulator(league, num_simulations=40, preseason=True, seed=9)
        baseline = copy.deepcopy(simulator.team_ratings)

        simulator.analyze_draft_strategy()

        self.assertEqual(baseline, simulator.team_ratings)

    def test_preseason_mode_handles_no_observed_scores(self):
        league = build_league()
        for team in league.teams:
            team.scores = [None, None, None]
            team.outcomes = ["U", "U", "U"]
            team.wins = 0
            team.losses = 0

        simulator = MonteCarloSimulator(league, num_simulations=20, preseason=True, seed=11)
        results = simulator.run_simulations()

        self.assertEqual(set(results.keys()), {1, 2, 3, 4})
        self.assertTrue(all("avg_wins" in value for value in results.values()))

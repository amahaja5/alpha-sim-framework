import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock

from alpha_sim_framework.ab_evaluation import (
    _decision,
    _resolve_config,
    resolve_ab_config,
    run_ab_evaluation,
)
from alpha_sim_framework.alpha_types import ABDecisionGateConfig
from alpha_sim_framework.fantasy_decision_maker import load_alpha_provider, main, run_ab_eval_from_cli


class FakePlayer:
    def __init__(self, player_id, position, projected_avg_points=10.0):
        self.playerId = player_id
        self.name = f"{position}-{player_id}"
        self.position = position
        self.lineupSlot = position
        self.slot_position = position
        self.eligibleSlots = [position, "FLEX"] if position in ("RB", "WR", "TE") else [position]
        self.projected_total_points = projected_avg_points * 14
        self.projected_avg_points = projected_avg_points
        self.avg_points = projected_avg_points
        self.injuryStatus = "NONE"
        self.injured = False
        self.percent_started = 50.0
        self.stats = {1: {"points": projected_avg_points}}


class FakeTeam:
    def __init__(self, team_id, name, wins, scores):
        self.team_id = team_id
        self.team_name = name
        self.wins = wins
        self.losses = 0
        self.scores = scores
        self.outcomes = ["W" if score is not None else "U" for score in scores]
        self.points_for = sum(score for score in scores if score is not None)
        self.roster = [
            FakePlayer(team_id * 100 + 1, "QB", 20.0),
            FakePlayer(team_id * 100 + 2, "RB", 15.0),
            FakePlayer(team_id * 100 + 3, "RB", 14.0),
            FakePlayer(team_id * 100 + 4, "WR", 14.0),
            FakePlayer(team_id * 100 + 5, "WR", 13.0),
            FakePlayer(team_id * 100 + 6, "TE", 11.0),
            FakePlayer(team_id * 100 + 7, "K", 8.0),
            FakePlayer(team_id * 100 + 8, "D/ST", 8.0),
        ]
        self.schedule = []


class FakeLeague:
    def __init__(self):
        self.league_id = 123
        self.year = 2025
        self.current_week = 4
        self.settings = SimpleNamespace(reg_season_count=3, playoff_team_count=2)

        team1 = FakeTeam(1, "Team 1", 1, [101.0, 98.0, None])
        team2 = FakeTeam(2, "Team 2", 1, [95.0, 100.0, None])
        team1.schedule = [team2, team2, team2]
        team2.schedule = [team1, team1, team1]
        self.teams = [team1, team2]

    def box_scores(self, week=None):
        return []

    def free_agents(self, week=None, size=50, position=None, position_id=None):
        return []


class ABEvaluationTest(TestCase):
    def test_gate_outcomes_pass_fail_inconclusive(self):
        gate = ABDecisionGateConfig(min_weekly_points_lift=0.0, max_downside_probability=0.4, min_successful_seeds=3)

        passed = _decision(
            {"mean": 0.4, "downside_probability": 0.2, "p05": 0.1, "p95": 0.8},
            successful_seeds=5,
            gate=gate,
        )
        self.assertEqual(passed["status"], "pass")

        failed = _decision(
            {"mean": -0.3, "downside_probability": 0.9, "p05": -0.9, "p95": -0.1},
            successful_seeds=5,
            gate=gate,
        )
        self.assertEqual(failed["status"], "fail")

        inconclusive = _decision(
            {"mean": 0.0, "downside_probability": 0.35, "p05": -0.2, "p95": 0.6},
            successful_seeds=5,
            gate=gate,
        )
        self.assertEqual(inconclusive["status"], "inconclusive")

    def test_config_resolution_uses_profile_defaults_and_overrides(self):
        merged = resolve_ab_config(
            {"profile": "quick", "league": {"league_id": 10, "team_id": 3, "year": 2025}},
            {"simulations": 3333},
        )

        resolved = _resolve_config(merged)
        self.assertEqual(resolved.profile, "quick")
        self.assertEqual(resolved.seeds, 3)
        self.assertEqual(resolved.simulations, 3333)

    def test_ab_parity_baseline_vs_alpha_uses_identical_non_alpha_inputs(self):
        league = FakeLeague()
        captured = []
        provider = object()

        class FakeSim:
            def __init__(self, league, num_simulations, seed, alpha_mode, alpha_config=None, provider=None):
                captured.append(
                    {
                        "league_id": id(league),
                        "num_simulations": num_simulations,
                        "seed": seed,
                        "alpha_mode": alpha_mode,
                        "provider": provider,
                    }
                )
                self.alpha_mode = alpha_mode

            def run_simulations(self, explain=False):
                return {
                    1: {"playoff_odds": 55.0, "championship_odds": 20.0},
                    2: {"playoff_odds": 45.0, "championship_odds": 10.0},
                }

            def backtest_alpha(self, config=None):
                return {"weekly_points_delta": 0.8, "brier_score": 0.21}

        with mock.patch("alpha_sim_framework.ab_evaluation.MonteCarloSimulator", FakeSim):
            run_ab_evaluation(
                {
                    "league_id": 123,
                    "team_id": 1,
                    "year": 2025,
                    "profile": "quick",
                    "output_dir": tempfile.mkdtemp(),
                },
                league=league,
                provider=provider,
            )

        self.assertGreaterEqual(len(captured), 2)
        first = captured[0]
        second = captured[1]
        self.assertEqual(first["league_id"], second["league_id"])
        self.assertEqual(first["num_simulations"], second["num_simulations"])
        self.assertEqual(first["seed"], second["seed"])
        self.assertNotEqual(first["alpha_mode"], second["alpha_mode"])
        self.assertIsNone(first["provider"])
        self.assertIs(second["provider"], provider)

    def test_load_alpha_provider_supports_module_colon_class(self):
        provider = load_alpha_provider("alpha_sim_framework.alpha_provider:NullSignalProvider")
        self.assertTrue(hasattr(provider, "get_player_adjustments"))

    def test_context_fallback_warning_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch(
                "alpha_sim_framework.ab_evaluation.run_historical_backtest",
                return_value={
                    "analysis_window": {"years_analyzed": [2025]},
                    "warnings": ["context_load_failed:missing"],
                    "opponents": [],
                },
            ):
                result = run_ab_evaluation(
                    {
                        "league_id": 123,
                        "team_id": 1,
                        "year": 2025,
                        "profile": "quick",
                        "output_dir": temp_dir,
                        "use_context": True,
                        "context_path": "/tmp/does-not-exist",
                    },
                    league=FakeLeague(),
                )

        self.assertTrue(any("fallback" in warning.lower() for warning in result["warnings"]))

    def test_writes_expected_artifacts_and_unique_run_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result1 = run_ab_evaluation(
                {
                    "league_id": 123,
                    "team_id": 1,
                    "year": 2025,
                    "profile": "quick",
                    "output_dir": temp_dir,
                },
                league=FakeLeague(),
            )
            result2 = run_ab_evaluation(
                {
                    "league_id": 123,
                    "team_id": 1,
                    "year": 2025,
                    "profile": "quick",
                    "output_dir": temp_dir,
                },
                league=FakeLeague(),
            )

            self.assertNotEqual(result1["run_id"], result2["run_id"])
            run_dir = Path(result1["output_dir"])
            self.assertTrue((run_dir / "run_manifest.json").exists())
            self.assertTrue((run_dir / "metrics_per_seed.csv").exists())
            self.assertTrue((run_dir / "metrics_summary.json").exists())
            self.assertTrue((run_dir / "decision_report.md").exists())
            self.assertTrue((run_dir / "warnings.json").exists())

            manifest = json.loads((run_dir / "run_manifest.json").read_text())
            self.assertIn("run_id", manifest)
            self.assertIn("timestamp_utc", manifest)
            self.assertIn("git_sha", manifest)
            self.assertIn("config_hash", manifest)

    def test_cli_ab_eval_invocation_path(self):
        with mock.patch(
            "alpha_sim_framework.fantasy_decision_maker.run_ab_eval_from_cli",
            return_value={"run_id": "ab_test"},
        ) as runner:
            argv = [
                "fantasy-decision-maker",
                "--league-id",
                "123",
                "--team-id",
                "1",
                "--year",
                "2025",
                "--ab-eval",
                "--ab-profile",
                "quick",
                "--ab-provider-class",
                "alpha_sim_framework.alpha_provider:NullSignalProvider",
            ]
            with mock.patch("sys.argv", argv):
                rc = main()

        self.assertEqual(rc, 0)
        runner.assert_called_once()

    def test_cli_ab_eval_loads_ab_config_without_provider_kwargs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ab_config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "league": {
                            "league_id": 987,
                            "team_id": 3,
                            "year": 2025,
                        }
                    }
                )
            )

            with mock.patch(
                "alpha_sim_framework.fantasy_decision_maker.run_ab_eval_from_cli",
                return_value={"run_id": "ab_test"},
            ) as runner:
                argv = [
                    "fantasy-decision-maker",
                    "--ab-config",
                    str(config_path),
                    "--ab-eval",
                ]
                with mock.patch("sys.argv", argv):
                    rc = main()

            self.assertEqual(rc, 0)
            runner.assert_called_once()
            kwargs = runner.call_args.kwargs
            self.assertEqual(kwargs["league_id"], 987)
            self.assertEqual(kwargs["team_id"], 3)
            self.assertEqual(kwargs["year"], 2025)

    def test_ab_eval_cli_wires_provider_kwargs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            captured = {}

            def _fake_run_ab_evaluation(*, config, provider):
                captured["config"] = config
                captured["provider"] = provider
                return {
                    "run_id": "ab_test",
                    "output_dir": temp_dir,
                    "metrics_summary": {"weekly_points_lift": {"mean": 0.2, "p05": -0.1, "p95": 0.5, "downside_probability": 0.3}},
                    "decision": {"status": "pass", "reasons": ["ok"]},
                    "warnings": [],
                }

            with mock.patch("alpha_sim_framework.fantasy_decision_maker.run_ab_evaluation", side_effect=_fake_run_ab_evaluation):
                run_ab_eval_from_cli(
                    league_id=123,
                    team_id=1,
                    year=2025,
                    swid=None,
                    espn_s2=None,
                    context_dir="data/league_context",
                    ab_base_config=None,
                    ab_profile="quick",
                    ab_output_dir=temp_dir,
                    ab_seeds=3,
                    ab_simulations=1200,
                    ab_weeks="auto",
                    ab_use_context=False,
                    ab_provider_class="alpha_sim_framework.alpha_provider:NullSignalProvider",
                    ab_provider_kwargs={},
                )

            self.assertIsNotNone(captured.get("provider"))
            self.assertEqual(
                captured["config"].get("alpha_provider", {}).get("class_path"),
                "alpha_sim_framework.alpha_provider:NullSignalProvider",
            )

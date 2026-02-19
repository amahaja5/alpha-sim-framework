from unittest import TestCase

from alpha_sim_framework.alpha_model import project_players
from alpha_sim_framework.alpha_types import AlphaConfig


class DummyPlayer:
    _counter = 0

    def __init__(self, name, position, projected_avg_points, recent_points, injury_status="NONE", pro_pos_rank=0):
        DummyPlayer._counter += 1
        self.playerId = DummyPlayer._counter
        self.name = name
        self.position = position
        self.projected_avg_points = projected_avg_points
        self.projected_total_points = projected_avg_points * 14
        self.avg_points = projected_avg_points
        self.injuryStatus = injury_status
        self.injured = injury_status not in ("NONE", "ACTIVE")
        self.percent_started = 55.0
        self.pro_pos_rank = pro_pos_rank
        self.stats = {
            idx + 1: {"points": float(points)} for idx, points in enumerate(recent_points)
        }


class AlphaModelTest(TestCase):
    def test_recent_form_changes_projection(self):
        config = AlphaConfig(recent_weeks=4, shrinkage_k=2.0)
        hot = DummyPlayer("Hot", "WR", 12.0, [20, 18, 19, 17])
        cold = DummyPlayer("Cold", "WR", 12.0, [7, 8, 6, 9])

        projections = project_players([hot, cold], config, {}, {}, {})

        self.assertGreater(projections[hot.playerId].weekly_mean, projections[cold.playerId].weekly_mean)

    def test_injury_penalty_reduces_mean(self):
        config = AlphaConfig()
        healthy = DummyPlayer("Healthy", "RB", 14.0, [13, 14, 15], injury_status="NONE")
        hurt = DummyPlayer("Hurt", "RB", 14.0, [13, 14, 15], injury_status="DOUBTFUL")

        projections = project_players([healthy, hurt], config, {}, {}, {})

        self.assertGreater(projections[healthy.playerId].weekly_mean, projections[hurt.playerId].weekly_mean)

    def test_matchup_proxy_directional_effect(self):
        config = AlphaConfig(matchup_scale=0.10)
        easy = DummyPlayer("Easy", "TE", 10.0, [9, 10, 11], pro_pos_rank=28)
        hard = DummyPlayer("Hard", "TE", 10.0, [9, 10, 11], pro_pos_rank=2)

        projections = project_players([easy, hard], config, {}, {}, {})

        self.assertGreater(projections[easy.playerId].weekly_mean, projections[hard.playerId].weekly_mean)

from dataclasses import dataclass, field
from typing import Any, Dict, Protocol


@dataclass
class AlphaConfig:
    recent_weeks: int = 4
    shrinkage_k: float = 4.0
    matchup_scale: float = 0.08
    simulations_decision: int = 1200
    candidate_pool_size: int = 30
    alpha_blend: float = 0.35
    injury_penalties: Dict[str, float] = field(
        default_factory=lambda: {
            "OUT": 0.0,
            "DOUBTFUL": 0.55,
            "QUESTIONABLE": 0.85,
            "P": 0.85,
            "SUSPENSION": 0.0,
            "IR": 0.0,
            "ACTIVE": 1.0,
            "NONE": 1.0,
        }
    )


@dataclass
class PlayerProjection:
    player_id: Any
    weekly_mean: float
    weekly_std: float
    components: Dict[str, float]
    confidence: float


class ExternalSignalProvider(Protocol):
    def get_player_adjustments(self, league: Any, week: int) -> Dict[Any, float]:
        ...

    def get_injury_overrides(self, league: Any, week: int) -> Dict[Any, str]:
        ...

    def get_matchup_overrides(self, league: Any, week: int) -> Dict[Any, float]:
        ...

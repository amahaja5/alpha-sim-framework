from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


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


@dataclass
class HistoricalBacktestConfig:
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    lookback_seasons: int = 3
    min_weeks_per_opponent: int = 2
    include_playoffs: bool = False
    narrative_mode: str = "rule_based"


@dataclass
class LeagueContextConfig:
    league_id: int
    year: int
    swid: Optional[str] = None
    espn_s2: Optional[str] = None
    context_dir: str = "data/league_context"
    lookback_seasons: int = 3
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    full_refresh: bool = False
    include_playoffs: bool = False


@dataclass
class ContextSyncResult:
    context_root: str
    sync_mode: str
    seasons_requested: List[int]
    seasons_synced: List[int]
    seasons_skipped: List[int]
    warnings: List[str] = field(default_factory=list)
    record_counts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextManifest:
    league_id: int
    seasons: List[int]
    last_sync_utc: str
    sync_mode: str
    record_counts: Dict[str, Any]
    data_quality_flags: List[str]
    schema_version: str
    endpoint_watermarks: Dict[str, Dict[str, int]]


class ExternalSignalProvider(Protocol):
    def get_player_adjustments(self, league: Any, week: int) -> Dict[Any, float]:
        ...

    def get_injury_overrides(self, league: Any, week: int) -> Dict[Any, str]:
        ...

    def get_matchup_overrides(self, league: Any, week: int) -> Dict[Any, float]:
        ...

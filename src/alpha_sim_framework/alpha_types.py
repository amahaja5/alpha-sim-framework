from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple


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


@dataclass
class ABDecisionGateConfig:
    min_weekly_points_lift: float = 0.0
    max_downside_probability: float = 0.4
    min_successful_seeds: int = 3


@dataclass
class ABEvaluationConfig:
    league_id: int
    team_id: int
    year: int
    swid: Optional[str] = None
    espn_s2: Optional[str] = None
    profile: str = "default"
    simulations: int = 5000
    seeds: int = 7
    weeks: str = "auto"
    use_context: bool = False
    context_path: Optional[str] = None
    lookback_seasons: int = 3
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    include_playoffs: bool = False
    alpha_config: Dict[str, Any] = field(default_factory=dict)
    output_dir: str = "reports/ab_runs"
    gate: ABDecisionGateConfig = field(default_factory=ABDecisionGateConfig)


@dataclass
class ABSeedMetric:
    seed: int
    weekly_points_lift: float
    playoff_odds_lift: float
    championship_odds_lift: float
    calibration_brier: float
    status: str = "ok"
    error: str = ""


@dataclass
class ABMetricSummary:
    metric: str
    n: int
    mean: float
    median: float
    std: float
    p05: float
    p95: float
    downside_probability: float


@dataclass
class SignalWeights:
    projection_residual: float = 0.20
    usage_trend: float = 0.12
    injury_opportunity: float = 0.14
    matchup_unit: float = 0.10
    game_script: float = 0.09
    volatility_aware: float = 0.08
    weather_venue: float = 0.07
    market_sentiment_contrarian: float = 0.07
    waiver_replacement_value: float = 0.06
    short_term_schedule_cluster: float = 0.07
    player_tilt_leverage: float = 0.08
    vegas_props: float = 0.10
    win_probability_script: float = 0.07
    backup_quality_adjustment: float = 0.04
    red_zone_opportunity: float = 0.05
    snap_count_percentage: float = 0.05
    line_movement: float = 0.04


@dataclass
class SignalCaps:
    projection_residual: Tuple[float, float] = (-2.5, 2.5)
    usage_trend: Tuple[float, float] = (-2.0, 2.0)
    injury_opportunity: Tuple[float, float] = (-3.0, 3.0)
    matchup_unit: Tuple[float, float] = (-1.25, 1.25)
    game_script: Tuple[float, float] = (-1.5, 1.5)
    volatility_aware: Tuple[float, float] = (-1.5, 0.5)
    weather_venue: Tuple[float, float] = (-1.5, 0.75)
    market_sentiment_contrarian: Tuple[float, float] = (-1.0, 1.0)
    waiver_replacement_value: Tuple[float, float] = (-1.0, 2.0)
    short_term_schedule_cluster: Tuple[float, float] = (-1.5, 1.5)
    player_tilt_leverage: Tuple[float, float] = (-1.5, 1.5)
    vegas_props: Tuple[float, float] = (-2.0, 2.0)
    win_probability_script: Tuple[float, float] = (-1.75, 1.75)
    backup_quality_adjustment: Tuple[float, float] = (-0.75, 0.75)
    red_zone_opportunity: Tuple[float, float] = (-1.25, 1.25)
    snap_count_percentage: Tuple[float, float] = (-1.0, 1.0)
    line_movement: Tuple[float, float] = (-1.25, 1.25)
    total_adjustment: Tuple[float, float] = (-6.0, 6.0)
    matchup_signal_multiplier: Tuple[float, float] = (0.92, 1.10)
    matchup_multiplier: Tuple[float, float] = (0.85, 1.15)


@dataclass
class ExternalFeedConfig:
    enabled: bool = True
    endpoints: Dict[str, str] = field(default_factory=dict)
    api_keys: Dict[str, str] = field(default_factory=dict)
    request_headers: Dict[str, str] = field(default_factory=dict)
    static_payloads: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderRuntimeConfig:
    timeout_seconds: float = 2.0
    retries: int = 1
    backoff_seconds: float = 0.2
    cache_ttl_seconds: int = 300
    degrade_gracefully: bool = True
    canonical_contract_mode: str = "warn"
    canonical_contract_domains: List[str] = field(
        default_factory=lambda: ["weather", "market", "odds", "injury_news", "nextgenstats"]
    )


@dataclass
class CompositeAlphaConfig:
    weights: SignalWeights = field(default_factory=SignalWeights)
    caps: SignalCaps = field(default_factory=SignalCaps)
    external_feeds: ExternalFeedConfig = field(default_factory=ExternalFeedConfig)
    runtime: ProviderRuntimeConfig = field(default_factory=ProviderRuntimeConfig)
    residual_scale: float = 0.35
    usage_scale: float = 0.25
    schedule_horizon_weeks: int = 4
    min_recent_points: int = 2
    enable_extended_signals: bool = False

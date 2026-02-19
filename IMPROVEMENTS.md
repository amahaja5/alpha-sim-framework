# Improvements Roadmap

For a robust fantasy decision-making framework used by fantasy league participants, this document prioritizes critical enhancements needed to ensure correctness, transparency, and operational reliability.

---

## Priority 1: Input Validation Layer (CRITICAL)

Robust validation prevents silent failures and catches misconfigured leagues early.

### 1.1 League Shape Validation

**Status**: Partial (only NFL check exists)

Currently validates:
- `team.outcomes` and `team.scores` exist
- Rejects non-NFL object shapes

**Missing validations**:
- League size: 4–16 teams (configurable)
- Required settings fields: `reg_season_count`, `playoff_bracket_id`, `final_rank_final_sort_id`
- Scoring format validation (PPR vs non-PPR implied by settings)
- Number of roster slots matches expected position counts
- All teams have 18 weeks of schedule (or whatever current season length is)

**Implementation approach**:
```python
# src/alpha_sim_framework/validation.py
class LeagueValidator:
    def validate(league: LeagueLike) -> ValidationResult:
        """Strict validation with error/warning/info levels."""
        # Check league size
        if not (4 <= len(league.teams) <= 16):
            raise ValueError(f"Unsupported league size: {len(league.teams)}")

        # Check required settings
        required_settings = ["reg_season_count", "playoff_bracket_id"]
        for field in required_settings:
            if not hasattr(league.settings, field):
                raise ValueError(f"Missing required setting: {field}")

        # Validate schedule consistency
        for team in league.teams:
            schedule_len = len(team.schedule)
            if schedule_len != 18:
                raise ValueError(f"Team {team.team_id} schedule length {schedule_len} != 18")

        return ValidationResult(valid=True, warnings=[])
```

### 1.2 Player Object Validation

**Status**: None (fields accessed defensively with `getattr` but not validated)

**Required validations**:
- Player IDs are unique within team roster
- Projected points ≥ 0
- Avg points ≥ 0
- Stats dict has valid week keys (positive integers, ≤ current week)
- Position is one of {QB, RB, WR, TE, K, DEF}
- Injury status is one of {NONE, ACTIVE, QUESTIONABLE, DOUBTFUL, OUT, IR, P, SUSPENSION}
- `percent_started` in [0, 100]
- Player not on multiple teams' rosters

**Implementation approach**:
```python
class PlayerValidator:
    def validate_roster(team) -> List[ValidationWarning]:
        """Check all players in roster for correctness."""
        warnings = []
        seen_ids = set()

        for player in team.roster:
            pid = getattr(player, "playerId", None)
            if pid in seen_ids:
                warnings.append(f"Duplicate player ID {pid} in team {team.team_id}")
            seen_ids.add(pid)

            pos = str(getattr(player, "position", "")).upper()
            if pos not in {"QB", "RB", "WR", "TE", "K", "DEF"}:
                warnings.append(f"Unknown position for {pid}: {pos}")

            # Validate projections
            proj = float(getattr(player, "projected_avg_points", 0) or 0)
            if proj < 0:
                warnings.append(f"Negative projection for {pid}: {proj}")

        return warnings
```

### 1.3 Config Validation

**Status**: Minimal (some flags checked but not comprehensive)

**Required validations**:
- `num_simulations` ∈ [100, 10000]
- `ratings_blend` ∈ [0.0, 1.0]
- `alpha_config` values within sensible ranges:
  - `recent_weeks` ≥ 1
  - `shrinkage_k` > 0
  - `alpha_blend` ∈ [0.0, 1.0]
  - Injury penalties are floats ∈ [0.0, 1.0]
- Provider config has valid endpoints (if external feeds enabled)
- Feed contract mode ∈ {off, warn, strict}

**Implementation approach**:
```python
class ConfigValidator:
    def validate_alpha_config(config: AlphaConfig) -> None:
        """Raise ValueError if config is invalid."""
        if not (1 <= config.recent_weeks <= 18):
            raise ValueError(f"recent_weeks must be 1–18, got {config.recent_weeks}")

        if not (0.0 < config.shrinkage_k < 100.0):
            raise ValueError(f"shrinkage_k must be > 0, got {config.shrinkage_k}")

        if not (0.0 <= config.alpha_blend <= 1.0):
            raise ValueError(f"alpha_blend must be [0.0, 1.0], got {config.alpha_blend}")

        for status, penalty in config.injury_penalties.items():
            if not (0.0 <= penalty <= 1.0):
                raise ValueError(f"Injury penalty for {status} invalid: {penalty}")
```

---

## Priority 5: Full Signal Observability (CRITICAL)

Fantasy users need to understand **why** a recommendation changed, what signals contributed, and whether to trust it.

### 5.1 Per-Player Signal Diagnostics

**Status**: Partial (composite provider has `last_diagnostics` but limited detail)

**Missing**:
- Individual signal contributions to adjustment (currently only have total adjustment)
- Confidence score per player per signal (0.0–1.0)
- Data quality flags per player (stale projection? missing injury status? anomalous recent form?)
- Reason codes for zero adjustments (no external feed? position-specific opt-out?)

**Implementation approach**:
```python
# Modify alpha_types.py
@dataclass
class SignalContribution:
    signal_name: str  # "usage_trend", "weather_venue", etc.
    raw_value: float  # Before clipping
    clipped_value: float  # After bounds applied
    weight: float  # 0.0–1.0
    confidence: float  # How much to trust this signal
    source: str  # "espn", "nextgenstats", "weather_api", "fallback"
    data_quality: List[str]  # ["stale_data", "high_variance", "missing_context"]

@dataclass
class PlayerSignalDetails:
    player_id: Any
    position: str
    baseline_projection: float
    total_adjustment: float
    signal_contributions: List[SignalContribution]
    overall_confidence: float
    warnings: List[str]

# In CompositeSignalProvider
def get_player_signal_details(player, league, week) -> PlayerSignalDetails:
    """Detailed breakdown of all signals for a player."""
    contributions = []
    for signal_name, signal_func in self._signal_funcs.items():
        raw = signal_func(player, league, week)
        confidence = self._compute_signal_confidence(player, signal_name, week)
        quality_flags = self._assess_data_quality(player, signal_name)

        contributions.append(SignalContribution(
            signal_name=signal_name,
            raw_value=raw,
            clipped_value=self._clip_signal(raw, signal_name),
            weight=self.config.weights[signal_name],
            confidence=confidence,
            source=self._determine_signal_source(player, signal_name),
            data_quality=quality_flags,
        ))

    return PlayerSignalDetails(
        player_id=_player_id(player),
        position=_position(player),
        baseline_projection=_player_baseline(player),
        total_adjustment=sum(c.clipped_value * c.weight for c in contributions),
        signal_contributions=contributions,
        overall_confidence=np.mean([c.confidence for c in contributions]),
        warnings=self._last_warnings,
    )
```

### 5.2 Audit Trail for Lineup Recommendations

**Status**: None

**What's needed**:
- For each recommended lineup:
  - Which players were considered for each position
  - What alternatives were rejected and why
  - Total projected score with and without alpha adjustments
  - Confidence in the recommendation (consensus across simulation runs? or divergent?)

**Implementation approach**:
```python
@dataclass
class PositionRecommendation:
    position: str
    recommended_player_id: Any
    recommended_player_name: str
    baseline_proj: float
    alpha_adjusted_proj: float
    bench_alternatives: List[Dict]  # [{player_id, name, proj_baseline, proj_alpha}]
    reasoning: str  # "High confidence: consistent alpha signal + favorable matchup"

@dataclass
class LineupRecommendationAudit:
    team_id: int
    week: int
    timestamp: str  # ISO UTC
    total_baseline_proj: float
    total_alpha_proj: float
    alpha_lift: float
    positions: List[PositionRecommendation]
    confidence_level: str  # "high", "medium", "low"
    decision_factors: List[str]  # ["recent_form_positive", "weather_favorable", "matchup_favorable"]

# Modify MonteCarloSimulator
def recommend_lineup_with_audit(
    self, team_id: int, week: Optional[int] = None, explain: bool = False
) -> Tuple[Dict, LineupRecommendationAudit]:
    """Return both the recommendation dict and detailed audit trail."""
    # ... existing logic ...
    audit = LineupRecommendationAudit(
        team_id=team_id,
        week=week or self.league.current_week,
        timestamp=datetime.utcnow().isoformat() + "Z",
        total_baseline_proj=baseline_score,
        total_alpha_proj=alpha_score,
        alpha_lift=alpha_score - baseline_score,
        positions=[...],  # PositionRecommendation for each slot
        confidence_level=self._assess_confidence(explain_data),
        decision_factors=[...],
    )
    return recommendation_dict, audit
```

### 5.3 Per-Team Historical Accuracy Tracking

**Status**: None (backtests exist but no running accuracy measurement)

**What's needed**:
- Track projected vs. actual scores for recommendations made
- Build historical accuracy by signal family (which signals predict best?)
- Flag when historical accuracy drops (data quality issue? league rule change?)

**Implementation approach**:
```python
class AccuracyTracker:
    """Track accuracy of projections vs. actual results over time."""

    def record_recommendation(
        self,
        team_id: int,
        week: int,
        lineup: List[int],  # player IDs
        projections: List[float],  # baseline
        alpha_adjustments: List[float],
    ) -> None:
        """Store a recommendation for later validation."""
        self.pending[team_id][week] = {
            "lineup": lineup,
            "baseline_proj": projections,
            "alpha_adj": alpha_adjustments,
        }

    def record_actual_scores(
        self,
        team_id: int,
        week: int,
        actual_scores: List[float],  # per player
    ) -> AccuracyMetrics:
        """Compare actual scores to what was projected."""
        stored = self.pending[team_id].get(week)
        if not stored:
            return None

        baseline_proj = np.array(stored["baseline_proj"])
        alpha_proj = baseline_proj + np.array(stored["alpha_adj"])
        actual = np.array(actual_scores)

        return AccuracyMetrics(
            week=week,
            baseline_mae=np.mean(np.abs(baseline_proj - actual)),
            alpha_mae=np.mean(np.abs(alpha_proj - actual)),
            baseline_r2=r2_score(actual, baseline_proj),
            alpha_r2=r2_score(actual, alpha_proj),
        )
```

### 5.4 Confidence Scores on Signals

**Status**: Mentioned in TODO, not implemented

**What's needed**:
- Signal confidence reflects data quality:
  - Recent form: high confidence if ≥4 weeks of data; low if <2 weeks
  - Injury: high confidence if ESPN confirms; lower if inferred from miss
  - Matchup: high for top-10 defenses; lower for mid-tier
  - Weather: high if feed was recent; lower if stale (>4 hours old)
  - Nextgenstats: high if available; zero if unavailable

**Implementation approach**:
```python
class SignalConfidence:
    """Compute confidence in individual signals."""

    def recent_form_confidence(player, current_week: int) -> float:
        """Higher if more weeks of data available."""
        stats = getattr(player, "stats", {})
        week_count = sum(1 for k in stats.keys() if _is_valid_week(k, current_week))

        if week_count >= 4:
            return 0.95
        elif week_count >= 2:
            return 0.75
        elif week_count == 1:
            return 0.40
        else:
            return 0.0  # No data

    def injury_status_confidence(player) -> float:
        """High if ESPN explicitly confirmed; lower if inferred."""
        status = getattr(player, "injuryStatus", None)
        if status in {"OUT", "DOUBTFUL", "QUESTIONABLE", "IR", "P"}:
            return 0.95

        injured = getattr(player, "injured", False)
        if injured:
            return 0.70  # Inferred from flag, not status

        return 0.95  # Explicitly healthy
```

### 5.5 Data Quality Flags per Player

**Status**: Mentioned in TODO, not implemented

**What's needed**:
- Flag stale projections (ESPN hasn't updated in >24h?)
- Flag missing injury status (player queried but no injury field?)
- Flag anomalous recent form (one 45-point game vs. 8-point average?)
- Flag missing stats (rookie or just called up?)
- Flag position ambiguity (eligible at 3 positions; which did we assume?)

**Implementation approach**:
```python
@dataclass
class PlayerDataQualityReport:
    player_id: Any
    player_name: str
    flags: List[str]  # "stale_projection", "missing_injury_status", etc.
    severity: str  # "info", "warning", "error"
    recommendation: str  # "use with caution", "skip recommendation", etc.

def assess_player_data_quality(player, league, week: int) -> PlayerDataQualityReport:
    """Check for data quality issues that affect recommendation confidence."""
    flags = []

    # Check projection staleness
    proj_ts = getattr(player, "projection_updated_at", None)
    if proj_ts and (datetime.utcnow() - proj_ts).total_seconds() > 86400:
        flags.append("stale_projection")

    # Check for missing injury status
    if not hasattr(player, "injuryStatus") and not hasattr(player, "injured"):
        flags.append("missing_injury_status")

    # Check for recent form anomalies
    recent_scores = _recent_points(player, 4)
    if recent_scores and np.std(recent_scores) > 15.0:
        flags.append("high_variance_recent_form")

    # Check for missing stats
    stats = getattr(player, "stats", {})
    if not stats:
        flags.append("no_historical_stats")

    severity = "error" if "missing_injury_status" in flags else "warning" if flags else "info"

    return PlayerDataQualityReport(
        player_id=_player_id(player),
        player_name=getattr(player, "name", "Unknown"),
        flags=flags,
        severity=severity,
        recommendation="use with caution" if flags else "ok",
    )
```

---

## Priority 2: Comprehensive Test Suite (OPTIONAL BUT RECOMMENDED)

If robustness is critical for fantasy users, expand tests to catch edge cases and prevent regressions.

### 2.1 Edge Case Tests
- Single-team leagues (backtest only)
- All players at a position injured
- League mid-season (week 15+)
- All playoff spots clinched / all teams eliminated
- Player with zero stats
- Division with only 1 team

### 2.2 Integration Tests
- Real ESPN league loading (gated: only run with explicit flag)
- End-to-end: load league → build context → recommend lineup → check output shape
- Feed contract validation against sample payloads (weather, odds, nextgenstats)

### 2.3 Stress Tests
- 20-team league simulation
- 10,000 Monte Carlo simulations (memory + time)
- Large backtest window (5 years of historical data)

### 2.4 CLI Error Handling
- Invalid league ID (404)
- Missing team ID (KeyError)
- Stale/invalid cookies (401)
- Malformed config JSON
- Missing required fields in config

---

## Implementation Priority

### Phase 1 (Must-Have for Fantasy Users)
1. **League Shape Validation** (1.1) — 2 days
2. **Player Object Validation** (1.2) — 2 days
3. **Per-Player Signal Diagnostics** (5.1) — 3 days
4. **Audit Trail for Recommendations** (5.2) — 2 days

**Outcome**: Fantasy users can trust recommendations and debug when something looks off.

### Phase 2 (Should-Have for Production)
5. **Config Validation** (1.3) — 1 day
6. **Per-Team Accuracy Tracking** (5.3) — 2 days
7. **Signal Confidence Scoring** (5.4) — 2 days

**Outcome**: Framework surfaces signal reliability and learns from historical accuracy.

### Phase 3 (Nice-To-Have)
8. **Data Quality Flags** (5.5) — 1 day
9. **Comprehensive Test Suite** (2.x) — 5–10 days

**Outcome**: Minimal surprises, easier debugging, better coverage.

---

## Integration Points

### CLI Output Changes
```bash
uv run fantasy-decision-maker --league-id 123 --team-id 1 --year 2025 --detailed-diagnostics
```

Should include in report:
```json
{
  "recommended_lineup": [...],
  "diagnostics": {
    "players": [
      {
        "player_id": 12345,
        "position": "WR",
        "baseline_proj": 14.5,
        "alpha_adjusted_proj": 15.2,
        "alpha_lift": 0.7,
        "signals": [
          {
            "name": "recent_form",
            "contribution": 0.8,
            "confidence": 0.92,
            "source": "espn",
            "quality_flags": []
          },
          {
            "name": "matchup_unit",
            "contribution": -0.1,
            "confidence": 0.85,
            "source": "espn",
            "quality_flags": []
          }
        ],
        "overall_confidence": 0.88,
        "warnings": []
      }
    ],
    "validation": {
      "league_valid": true,
      "data_quality_warnings": []
    },
    "accuracy_metrics": {
      "recent_weeks_baseline_mae": 3.2,
      "recent_weeks_alpha_mae": 2.9,
      "trend": "improving"
    }
  }
}
```

### Python API Changes
```python
from alpha_sim_framework import MonteCarloSimulator

sim = MonteCarloSimulator(league, num_simulations=2000, alpha_mode=True)

# Get recommendation with full audit trail
recommendation, audit = sim.recommend_lineup_with_audit(team_id=1, week=10, explain=True)

print(audit.total_alpha_lift)  # 2.3 points
print(audit.confidence_level)  # "high"

# Get per-player signal breakdown
for signal_detail in audit.signal_details:
    print(f"{signal_detail.player_id}: confidence={signal_detail.overall_confidence}")
```

---

## Documentation Updates Needed

- **Data Model Spec**: Document required fields on player/team/league objects (separate doc)
- **Signal Details**: Explain what each of the 10 signals does, how confidence is calculated
- **Validation Guide**: When validation fails, what does the error mean and how to fix it
- **Troubleshooting**: Common issues (stale ESPN data, missing injury status, etc.) and solutions
- **Accuracy Benchmarks**: Published accuracy rates from historical backtests (once implemented)

---

## Success Criteria

✅ **Phase 1 complete**: Fantasy users never get a silent error. Framework always explains why a recommendation changed.

✅ **Phase 2 complete**: Framework learns from accuracy and flags data quality issues proactively.

✅ **Phase 3 complete**: Framework handles edge cases gracefully and catches regressions in testing.

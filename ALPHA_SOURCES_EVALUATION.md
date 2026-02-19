# Alpha Sources Evaluation

This document reviews the 10 current alpha signals and identifies high-value additional sources that would improve recommendation quality for fantasy users.

---

## Current 10 Signals (Implemented)

### Tier 1: Core Signals (Strong Alpha)

#### 1. **Projection Residual** (0.2 weight)
- **What it does**: Compares external market projections to ESPN baseline
- **Signal strength**: Very high (catches consensus misses)
- **Data source**: Market feed + NextGen stats (explosive play rate, separation)
- **Current implementation**:
  ```
  residual = external_projection - espn_baseline
  + 0.20 * explosive_play_rate
  + 0.10 * avg_separation
  ```
- **Gaps**: Only uses two NextGen features; ignores snap count, route participation efficiency

---

#### 2. **Game Script** (0.09 weight)
- **What it does**: Adjusts expectations based on game context (spread, implied total)
- **Position-specific**:
  - QB/WR/TE: negative if favored (less passing), positive if underdog
  - RB: opposite (game script game benefits from leading)
  - K/DEF: minimal effect
- **Signal strength**: High (models actual NFL tendencies)
- **Current implementation**:
  ```
  script_base = -0.30 (favorite) or +0.35 (underdog) for pass-heavy
  + 0.08 * ((implied_total - 22.0) / 3.0)  # higher totals = more scoring
  ```
- **Gaps**:
  - ❌ Doesn't account for **in-game dynamics** (real-time score, time remaining)
  - ❌ No **win probability context** (locked-in win vs desperate catch-up)
  - ❌ Static spread at prediction time; doesn't use **line movement** (sharp money shifting?)

---

#### 3. **Injury Opportunity** (0.14 weight)
- **What it does**: Identifies backup benefit when starters are out
- **Current implementation**:
  ```
  -3.0 for OUT/IR
  -1.8 for DOUBTFUL
  -0.8 for QUESTIONABLE
  + 0.8 per teammate out (if healthy)
  ```
- **Signal strength**: Very high (directly impacts playing time)
- **Gaps**:
  - ❌ **No backup quality adjustment** (is replacement elite or third-stringer?)
  - ❌ **Position-agnostic penalties** (OUT at QB ≠ OUT at RB)
  - ❌ **No practice participation tracking** (limited/full participation signals)
  - ❌ **No return probability** (is player likely to return mid-game?)

---

#### 4. **Matchup Unit (DVP)** (0.10 weight)
- **What it does**: Compares opponent defense rank vs position
- **Current implementation**:
  ```
  matchup_unit = 0.2 * defense_vs_position_rank
  matchup_multiplier = 1.0 + (0.025 * dvp)
  ```
- **Signal strength**: Medium-high (historical correlation exists)
- **Gaps**:
  - ❌ **Static season average** (not accounting for recent form)
  - ❌ **No scheme matching** (zone vs man coverage vs player specialty)
  - ❌ **No key injury impact** (top corner out changes DVP meaningfully)
  - ❌ **No secondary depth** (weak backups vs strong reserves)

---

#### 5. **Usage Trend** (0.12 weight)
- **What it does**: Recent trajectory of snap/target share
- **Current implementation**:
  ```
  usage_value = recent_avg (3 wks) - older_avg (wks 4-6)
  + 0.30 * usage_over_expected  (NextGen)
  + position_scale_factor
  ```
- **Signal strength**: Very high (predictive of opportunity)
- **Gaps**:
  - ❌ **No snap count adjustment** (targets ≠ snaps)
  - ❌ **No red zone focus** (high-value touches underweighted)
  - ❌ **No in-game situation tracking** (garbage time targets)

---

#### 6. **Weather Venue** (0.07 weight)
- **What it does**: Dome vs outdoor, wind, precipitation effects
- **Current implementation**:
  ```
  +0.15 (dome, pass-heavy positions)
  -0.5 to -0.9 (high wind, field kickers hit hardest)
  -0.4 to -0.45 (heavy rain, pass-heavy positions)
  ```
- **Signal strength**: Medium (real effect but noise-prone)
- **Gaps**:
  - ❌ **No humidity** (swamp conditions affect ball control)
  - ❌ **No wind direction** (tailwind vs headwind vs crosswind)
  - ❌ **No cold weather muscle impact** (cold weather = RB > WR?)
  - ❌ **No forecast uncertainty** (is rain 40% likely or 90%?)

---

#### 7. **Volatility Aware** (0.08 weight)
- **What it does**: Penalizes high-variance players
- **Current implementation**:
  ```
  volatility_proxy = 0.55 * recent_std + 0.45 * nextgen_volatility_index
  volatility_aware = -0.08 * volatility_proxy + (0.25 if volatility < 4.0 else 0.0)
  ```
- **Signal strength**: Low-medium (variance is noise, not alpha)
- **Gaps**:
  - ❌ **No situation-adjusted variance** (high variance in close games is good)
  - ❌ **No time-of-season adjustment** (playoff variance different from week 3)
  - ❌ **Overly pessimistic** (penalizes boom/bust players who can win leagues)

---

### Tier 2: Market/External Signals (Moderate)

#### 8. **Market Sentiment Contrarian** (0.07 weight)
- **What it does**: Fade overowned/underowned consensus
- **Current implementation**:
  ```
  market_sentiment_contrarian = -0.5 * sentiment_score
  + logic for fading chalk (high %_started + negative residual)
  + logic for fading contrarian (low %_started + positive residual)
  ```
- **Signal strength**: Medium (works in subset games, edge fades fast)
- **Gaps**:
  - ❌ **No cash vs tourney split** (overownership means different things)
  - ❌ **No lineup position tracking** (FLEX ownership ≠ WR-slot ownership)
  - ❌ **No stacking detection** (paired players have correlated ownership)

---

#### 9. **Market Sentiment (via start %)**
- This is implicit in #8 above; conflated with contrarian logic

---

### Tier 3: Value & Schedule Signals

#### 10. **Waiver Replacement Value** (0.06 weight)
- **What it does**: Upside relative to replaceable alternatives
- **Current implementation**:
  ```
  replacement_value = 35th percentile of position (waiver wire floor)
  starter_value = team's current starter at position
  waiver_replacement_value = 0.03 * (proj - replacement)
                            + 0.08 * (proj - starter)
  ```
- **Signal strength**: Low (mostly re-ranks within teams)
- **Gaps**:
  - ❌ **No actual waiver wire scanning** (replacement pool changes weekly)
  - ❌ **No bench depth** (backup quality at position)
  - ❌ **No team salary/roster constraints** (unrealistic upgrades)

---

#### 11. **Short-Term Schedule Cluster** (0.07 weight)
- **What it does**: Next 3-4 weeks of schedule difficulty
- **Current implementation**:
  ```
  schedule_strength = avg(dvp_rank for next_horizon weeks)
  short_term_schedule_cluster = 0.25 * schedule_strength + 0.05 * dvp
  ```
- **Signal strength**: Low (forward-looking but week-level is too short)
- **Gaps**:
  - ❌ **No bye week impact** (upcoming bye week = lower projection?)
  - ❌ **No time-of-season adjustment** (playoff schedules easier)
  - ❌ **No playoff path implications** (clinching impacts play-calling)

---

## Missing High-Value Alpha Sources

### A. Player Tilt / Leverage (HIGH PRIORITY)

**What it is**: How a player's ownership diverges from their EV impact.

**Why it matters**:
- In cash games: underowned good plays are pure +EV
- In tournaments: ownership determines variance value
- Different players have different ownership patterns (studs overowned, sleepers underowned)

**Current status**: ❌ Not implemented
- We have `%_started` but don't calculate:
  - Salary cap + ownership correlation
  - Implied ownership from Vegas props
  - Salary-adjusted leverage

**Implementation approach**:
```python
@dataclass
class OwnershipContext:
    game_type: str  # "cash", "tournament", "best_ball"
    field_size: int  # 50 players (cash) vs 100k (tournament)
    avg_ownership: float  # 0-1
    player_ownership: float  # 0-1
    salary: int

def calculate_leverage(player_ownership, avg_ownership, game_type) -> float:
    """Higher = more valuable in tournaments (differentiation)."""
    if game_type == "cash":
        # Ownership doesn't matter in cash; only EV matters
        return 0.0

    # Tournament: ownership is key
    if player_ownership < avg_ownership * 0.7:
        # Underowned good player = huge leverage upside
        return (avg_ownership - player_ownership) / avg_ownership
    elif player_ownership > avg_ownership * 1.3:
        # Overowned = negative leverage
        return -(player_ownership - avg_ownership) / avg_ownership
    else:
        return 0.0
```

**Data needed**:
- Actual ownership from DFS sites (FanDuel, DraftKings)
- Game context (cash vs tournament, field size)
- Salary impact on ownership patterns

---

### B. In-Game Game Script / Win Probability (HIGH PRIORITY)

**What it is**: Real-time or pre-game win probability and how it evolves.

**Why it matters**: Current game_script signal is static; actual play-calling changes based on:
- Score differential
- Time remaining
- Win probability
- Timeout situation

**Current status**: ⚠️ Partially implemented (game_script exists but static)

**Example gaps**:
- Underdog trailing by 20 in Q4 passes constantly (RB value drops, WR/TE spike)
- Favorite up 20 with 2 min left runs out clock (opposite effect)
- Static spread doesn't capture real-time momentum

**Implementation approach**:
```python
def calculate_win_probability_adjusted_script(
    quarter: int,
    time_remaining: int,  # seconds in quarter
    score_differential: int,
    spread: float,
    implied_total: float,
) -> Dict[str, float]:
    """Adjust game script based on time and score."""

    # Compute win probability (from historical data)
    win_prob = compute_wp(score_differential, quarter, time_remaining)

    # Position-specific multipliers
    if win_prob > 0.75:
        # Heavy favorite, running out clock
        return {
            "QB": -0.25, "RB": +0.30, "WR": -0.15, "TE": -0.10
        }
    elif win_prob < 0.25:
        # Heavy underdog, chasing game
        return {
            "QB": +0.40, "RB": -0.25, "WR": +0.35, "TE": +0.25
        }
    else:
        # Close game; use implied total
        return {
            "QB": (implied_total - 22.0) * 0.05,
            "RB": -(implied_total - 22.0) * 0.03,
            "WR": (implied_total - 22.0) * 0.04,
            "TE": (implied_total - 22.0) * 0.03,
        }
```

**Data needed**:
- Real-time score, time remaining, quarter (requires live API)
- Historical WP model (or use external API like nflscrapR)

---

### C. Vegas Props & Line Movement (HIGH PRIORITY)

**What it is**: Player props (passing yards, rushing yards, receptions, TDs) and how lines move.

**Why it matters**:
- Props are more granular than team projections (e.g., "O/U 300 passing yards" not "QB scores 22 pts")
- Line movement indicates sharp money (sharp bettors move lines early)
- Prop totals can differ from projections by +/- 2-3x

**Current status**: ❌ Not implemented
- We have `spread` and `implied_total` but not player props

**Implementation approach**:
```python
@dataclass
class VegasProp:
    prop_type: str  # "passing_yards", "rushing_yards", "receptions", "touchdowns"
    over_under: float  # The line (e.g., 24.5 for passing yards)
    open_line: float  # Opening line
    current_line: float  # Current line
    moneyline_over: float  # -110 implies -110 to win $100
    moneyline_under: float
    volume: int  # Bet count
    sharp_percentage: float  # % of handle from sharp bettors
    public_percentage: float  # % of handle from public

def calculate_props_adjustment(player, props_data) -> float:
    """Consensus across props tells us market confidence."""

    if not props_data:
        return 0.0

    adjustments = []
    for prop in props_data:
        # Where is the line relative to projection?
        # E.g., if we project 270 passing yards but line is 300.5 O/U
        # that's a bearish signal (+0.5 to -0.5 adjustment)

        if prop.sharp_percentage > 0.60:
            # Sharp money on the over = signal
            line_miss = (prop.over_under - baseline_projection) / baseline_projection
            adjustments.append(0.30 * line_miss)

    return float(np.mean(adjustments)) if adjustments else 0.0
```

**Data needed**:
- Vegas props API (ESPN, DraftKings, FanDuel historical props)
- Line movement history (opening vs closing)
- Sharp money indicators (Covers, ESPN betting insights)

---

### D. Backup Quality & Injury Replacement Value (MEDIUM PRIORITY)

**What it is**: Who's the backup if starter goes down? How good are they?

**Why it matters**:
- Backup is elite (Mahomes 2.0): starter injury risk increases value
- Backup is practice squad call-up: starter stays upside-heavy despite injury risk
- Different for each position (QB backup value ≠ RB backup value)

**Current status**: ⚠️ Partially implemented (we boost healthy backups but don't quality-adjust)

**Implementation approach**:
```python
def calculate_backup_quality_adjustment(
    starter: Player,
    backup: Player,
    position: str,
) -> float:
    """How much does backup quality affect starter valuation?"""

    starter_proj = get_projection(starter)
    backup_proj = get_projection(backup)

    # Backup as % of starter
    backup_ratio = backup_proj / starter_proj if starter_proj > 0 else 0.0

    # Position-specific: QB backups matter most
    position_weight = {
        "QB": 1.0,      # Backup QB could be bad (hurts starter value if injured)
        "RB": 0.4,      # Backup RB often capable
        "WR": 0.2,      # WR depth usually decent
        "TE": 0.3,
    }.get(position, 0.0)

    # If backup is bad (< 40% of starter), starter carries injury risk premium
    if backup_ratio < 0.40:
        return 0.15 * position_weight  # +15% to starter for being safer
    elif backup_ratio > 0.80:
        return -0.10 * position_weight  # -10% to starter if backup is elite

    return 0.0
```

**Data needed**:
- Backup roster for each team/position
- Backup player projections (next-men-up analysis)

---

### E. Red Zone Opportunity & Target Share (MEDIUM PRIORITY)

**What it is**: High-value touches (RZ targets, goal-line carries) vs all touches.

**Why it matters**:
- RZ target is worth 2-3x air yards target
- Goal-line carry is worth 3-5x mid-field carry
- Player A: 8 targets (2 in RZ) ≠ Player B: 8 targets (6 in RZ)

**Current status**: ⚠️ Partially via NextGen stats
- We use `route_participation` but not actual RZ distribution

**Implementation approach**:
```python
def calculate_red_zone_adjustment(player, rz_touches_history) -> float:
    """Recent RZ touch trend."""

    total_touches = sum(t.total for t in rz_touches_history[-4:])
    rz_touches = sum(t.red_zone for t in rz_touches_history[-4:])

    if total_touches == 0:
        return 0.0

    rz_percentage = rz_touches / total_touches

    # Trend: is RZ usage increasing or decreasing?
    recent_rz_pct = rz_touches_history[-1].red_zone / rz_touches_history[-1].total
    older_rz_pct = np.mean([
        (t.red_zone / t.total) for t in rz_touches_history[-4:-1]
    ])

    rz_trend = recent_rz_pct - older_rz_pct

    # Higher RZ % = higher upside (but noisier)
    return (0.20 * rz_percentage) + (0.30 * rz_trend)
```

**Data needed**:
- Play-by-play: which plays were RZ (within 20 yards)
- Player involvement per play (touches, targets, snaps)

---

### F. Snap Count Percentage (MEDIUM PRIORITY)

**What it is**: % of snaps played relative to team offensive snaps.

**Why it matters**:
- Snap count > 80% = primary role (high floor)
- Snap count 40-60% = role player (high variance)
- Snap count < 20% = occasional role (floor play only)

**Current status**: ❌ Not explicitly implemented
- We infer from targets/touches but don't track explicit snap %

**Implementation approach**:
```python
def calculate_snap_percentage_adjustment(player, snaps_history) -> float:
    """Is player getting more or less snaps?"""

    recent_snaps = snaps_history[-3:]  # Last 3 weeks
    older_snaps = snaps_history[-6:-3]  # Weeks 4-6

    recent_avg = np.mean(recent_snaps)
    older_avg = np.mean(older_snaps)

    snap_trend = recent_avg - older_avg

    # Increasing snaps = positive signal
    # Decreasing snaps = negative signal
    return 0.15 * np.clip(snap_trend / 30.0, -1.0, 1.0)  # -100% to +100% change
```

**Data needed**:
- Play-by-play snap counts (ESPN, NFL.com, nflscrapR)

---

### G. Target Share / Air Yards Distribution (MEDIUM PRIORITY)

**What it is**: What % of team passing is directed to this player?

**Why it matters**:
- Target share > 30% = primary (high floor, high ceiling)
- Target share 15-25% = secondary (medium floor, medium ceiling)
- Target share < 10% = depth chart (low floor, low ceiling)

**Current status**: ⚠️ Partially via NextGen `route_participation`

**Implementation approach**:
```python
def calculate_target_share_adjustment(player, stats_history) -> float:
    """Is player getting target share spike?"""

    targets_recent = sum(s.targets for s in stats_history[-3:])
    total_targets_recent = sum(s.team_targets for s in stats_history[-3:])

    targets_older = sum(s.targets for s in stats_history[-6:-3])
    total_targets_older = sum(s.team_targets for s in stats_history[-6:-3])

    recent_share = targets_recent / total_targets_recent if total_targets_recent > 0 else 0.0
    older_share = targets_older / total_targets_older if total_targets_older > 0 else 0.0

    share_trend = recent_share - older_share

    # Target share increasing = positive
    return 0.20 * np.clip(share_trend / 0.10, -1.0, 1.0)  # -10% to +10% shift
```

**Data needed**:
- Team target distribution per game

---

### H. Vegas Closing Line Movement (MEDIUM PRIORITY)

**What it is**: Did the line move in favor of this team's game? (Spread tightening/expanding)

**Why it matters**:
- Sharp money moved line (opening vs closing) = signal
- RB that moved line in their favor is likely to get carries in positive script
- WR that moved line against them is likely in negative script

**Current status**: ❌ Not implemented

**Implementation approach**:
```python
def calculate_line_movement_adjustment(team_id, opening_spread, closing_spread) -> Dict[str, float]:
    """Did sharp money move line in favor of this team?"""

    line_move = closing_spread - opening_spread

    # If spread moved toward this team, they're favored by sharp money
    # (closer to 0 = more favored)
    sharp_confidence = abs(line_move)
    sharp_direction = 1.0 if line_move < 0 else -1.0

    # Position-specific impact
    return {
        "QB": 0.15 * sharp_direction * sharp_confidence,
        "RB": 0.20 * sharp_direction * sharp_confidence,
        "WR": 0.15 * sharp_direction * sharp_confidence,
        "TE": 0.10 * sharp_direction * sharp_confidence,
    }
```

**Data needed**:
- Opening vs closing spread (sportsbooks)
- Total moneyline handle (sharp vs public split)

---

### I. Player Consistency / Ceiling vs Floor (LOW PRIORITY)

**What it is**: Upside cap vs downside floor (not just average variance).

**Why it matters**:
- Player A: 5-35 points (ceiling play, high variance)
- Player B: 12-18 points (floor play, low variance)
- Same mean but different leverage profiles

**Current status**: We penalize variance but don't differentiate ceiling vs floor

**Implementation approach**:
```python
def calculate_ceiling_floor_profile(points_history) -> Dict[str, float]:
    """Separate upside from downside."""

    mean = np.mean(points_history)
    std = np.std(points_history)

    ceiling = np.percentile(points_history, 90)
    floor = np.percentile(points_history, 10)

    # Ceiling premium (upside) vs floor discount (downside)
    ceiling_relative = (ceiling - mean) / mean if mean > 0 else 0.0
    floor_relative = (floor - mean) / mean if mean > 0 else 0.0

    return {
        "ceiling": ceiling,
        "floor": floor,
        "ceiling_premium": ceiling_relative,
        "floor_discount": floor_relative,
    }
```

---

### J. Team Pace / Pass vs Run Ratio (LOW PRIORITY)

**What it is**: How fast does this team play? How balanced is their offense?

**Why it matters**:
- High-pace team = more plays = more opportunity
- Pass-heavy team = more WR/TE value, less RB value
- Run-heavy team = opposite

**Current status**: ❌ Not implemented (would require historical data)

**Implementation approach**:
```python
def calculate_pace_and_balance_adjustment(team, season_stats) -> Dict[str, float]:
    """Pace and play-calling tendencies."""

    plays_per_game = season_stats.total_plays / season_stats.games_played
    pass_plays = season_stats.passing_plays
    rush_plays = season_stats.rushing_plays

    pass_ratio = pass_plays / (pass_plays + rush_plays)

    pace_above_avg = (plays_per_game - 30.0) / 30.0  # NFL avg ~30 plays/game

    return {
        "pace_adjustment": 0.10 * pace_above_avg,
        "pass_ratio_adjustment": {
            "QB": 0.05 * (pass_ratio - 0.55),
            "RB": -0.10 * (pass_ratio - 0.55),
            "WR": 0.08 * (pass_ratio - 0.55),
            "TE": 0.06 * (pass_ratio - 0.55),
        }
    }
```

---

## Recommended Implementation Priorities

### Phase 1: High Impact, Medium Effort
1. **Player Tilt / Leverage** (2-3 days)
   - Requires: DFS ownership data integration
   - Impact: Separates cash from tournament strategies
   - Alpha gain: +2-3% in tournament contexts

2. **Vegas Props & Line Movement** (3-4 days)
   - Requires: Vegas props API integration
   - Impact: Much more granular than team spreads
   - Alpha gain: +3-5% (props are predictive)

3. **In-Game Game Script / Win Probability** (2 days)
   - Requires: Win probability model (can use external API)
   - Impact: Real game dynamics vs static spread
   - Alpha gain: +1-2%

### Phase 2: Medium Impact, Medium Effort
4. **Red Zone Opportunity** (1-2 days)
   - Requires: Play-by-play RZ classification
   - Impact: Captures high-value touches
   - Alpha gain: +1-2%

5. **Backup Quality Adjustment** (1 day)
   - Requires: Backup roster + projections
   - Impact: Refines injury risk premium
   - Alpha gain: +0.5-1%

6. **Snap Count Tracking** (1-2 days)
   - Requires: Play-by-play snap counts
   - Impact: Operationality signal
   - Alpha gain: +1-2%

### Phase 3: Lower Priority
7. Target Share (implicit in usage_trend + NextGen)
8. Pace & Pass Ratio (low predictive power, high noise)
9. Ceiling vs Floor (relevant for DFS, less for season projection)

---

## Data Integration Points

To implement these signals, we need to wire in:

```python
@dataclass
class ExternalAlphaFeeds:
    # Current
    weather: WeatherFeedClient
    market: MarketFeedClient  # projections, usage_trend, sentiment
    odds: OddsFeedClient  # spread, dvp, implied_total
    injury_news: InjuryNewsFeedClient
    nextgenstats: NextGenStatsFeedClient

    # Missing (Priority 1)
    dfs_ownership: DFSOwnershipFeedClient  # FanDuel, DraftKings
    vegas_props: VegasPropsClient  # Props + line movement
    win_probability: WinProbabilityClient  # Real-time WP model

    # Missing (Priority 2)
    play_by_play: PlayByPlayClient  # RZ, snap counts, target share
    backup_projections: BackupProjectionClient  # Next-men-up analysis
    team_stats: TeamStatsClient  # Pace, pass ratio
```

Each feed should conform to the canonical feed contract (data, source_timestamp, quality_flags, warnings).

---

## Validation & Backtest Strategy

Before integrating new signals:

1. **Backtest historical accuracy**:
   - Does the signal correlate with actual production?
   - What's the time lag (is it predictive or coincidental)?
   - Is there position-specific variation?

2. **Correlation with existing signals**:
   - Is it orthogonal to current 10 signals or redundant?
   - What's the optimal weight if added?

3. **Robustness checks**:
   - Does it work across different eras (2015-2024)?
   - Does it work in different cap environments (before/after salary explosion)?
   - Does it degrade gracefully if feed is unavailable?

4. **Operational validation**:
   - How stale can the data be before signal degrades?
   - What's the cost of the data integration?

---

## Summary Table

| Signal | Status | Priority | Effort | Impact | Recommended |
|--------|--------|----------|--------|--------|-------------|
| Projection Residual | ✅ | Core | - | Very High | Yes |
| Game Script | ✅ | Core | - | High | Yes |
| Injury Opportunity | ✅ | Core | - | Very High | Yes |
| Matchup Unit (DVP) | ✅ | Core | - | High | Yes |
| Usage Trend | ✅ | Core | - | Very High | Yes |
| Weather Venue | ✅ | Core | - | Medium | Yes |
| Volatility Aware | ✅ | Core | - | Low | Keep (don't weight high) |
| Market Sentiment | ✅ | Core | - | Medium | Yes |
| Waiver Value | ✅ | Core | - | Low | Keep (don't weight high) |
| Schedule Cluster | ✅ | Core | - | Low | Keep (don't weight high) |
| **Player Tilt** | ❌ | 1 | 2-3d | High | **ADD** |
| **Vegas Props** | ❌ | 1 | 3-4d | Very High | **ADD** |
| **Game Script (Real-Time)** | ⚠️ | 1 | 2d | High | **ADD** |
| **Red Zone Opportunity** | ❌ | 2 | 1-2d | Medium | ADD |
| **Snap Count %** | ❌ | 2 | 1-2d | Medium | ADD |
| **Backup Quality** | ⚠️ | 2 | 1d | Medium | ADD |
| **Target Share Trend** | ⚠️ | 3 | 0.5d | Low | Optional |
| **Line Movement** | ❌ | 2 | 1d | Medium | ADD |
| **Pace & Pass Ratio** | ❌ | 3 | 1d | Low | Optional |
| **Ceiling vs Floor** | ❌ | 3 | 0.5d | Low | Optional |

---

## Conclusion

The current 10-signal framework is solid but conservative. The biggest gaps are:

1. **Vegas props** (very predictive, not yet connected)
2. **Player tilt / leverage** (essential for DFS/tournaments)
3. **Real-time game dynamics** (static game script misses momentum)

Adding the 3 Priority 1 signals would likely improve accuracy by 5-8% and unlock tournament/cash differentiation. The 3 Priority 2 signals would add another 3-4%.

Start with **Vegas props** (highest ROI) and **player tilt** (differentiation), then move to **real-time game script** if live API access is available.

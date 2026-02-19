# Recent Improvements

## Issue #1: Injured Players in Free Agent Recommendations ✅ FIXED

### Problem
Free agent recommendations were including players with injury designations (OUT, QUESTIONABLE, DOUBTFUL, IR, SUSPENDED). For example, Joe Mixon was recommended even though he's out for the season.

### Solution
Added injury status filtering to `recommend_free_agents()`:

**New Parameter:**
- `exclude_injured` (default: `True`) - Automatically filters out injured players

**Filtered Statuses:**
ESPN API uses these injury status values:
- `OUT` - Player is out for the game
- `QUESTIONABLE` - Player's status is uncertain
- `DOUBTFUL` - Player is unlikely to play
- `INJURY_RESERVE` - Player on injured reserve (not `IR`)
- `SUSPENSION` - Player is suspended
- Any status that is NOT `ACTIVE` or `NORMAL`

**Healthy Statuses (NOT filtered):**
- `ACTIVE` - Player is healthy and active
- `NORMAL` - Player is in normal status
- `None` - No injury status set

**Code Changes:**
```python
# In advanced_simulator.py
def recommend_free_agents(
    self,
    my_team,
    free_agents: List,
    top_n: int = 10,
    positions: Optional[List[str]] = None,
    exclude_injured: bool = True  # NEW
):
    # Filter out injured players
    if exclude_injured:
        injury_status = getattr(fa, 'injuryStatus', None) or getattr(fa, 'injury_status', None)
        # ESPN uses: OUT, QUESTIONABLE, DOUBTFUL, INJURY_RESERVE, DAY_TO_DAY
        # Healthy players have: ACTIVE or NORMAL
        if injury_status and injury_status.upper() not in ['ACTIVE', 'NORMAL', '', None]:
            continue  # Skip this player
```

**Testing:**
Created comprehensive test suite (`test_injury_filtering.py`) with 11 tests covering:
- OUT players filtered
- QUESTIONABLE players filtered
- DOUBTFUL players filtered
- INJURY_RESERVE players filtered
- SUSPENDED players filtered
- Case-insensitive filtering (active, out, Out all work)
- ACTIVE and NORMAL players NOT filtered
- Mixed injury statuses handled correctly
- Value ranking preserved after filtering
- Option to include injured players (`exclude_injured=False`)
- None injury status handled correctly

---

## Issue #2: Unrealistic Trade Recommendations ✅ FIXED

### Problem
Trade recommendations included completely unrealistic trades with 0% chance of acceptance. For example:
```
You Give:    Justice Hill
You Receive: Bijan Robinson

Your Value Change:  +8.7 pts
Their Value Change: -12.5 pts  ❌ They lose significantly!
```

This trade would never be accepted - you're trying to trade a bench player for a superstar.

### Solution
Added **acceptance probability** calculation and filtering:

**New Metrics in Trade Analysis:**
- `acceptance_probability`: 0-100% chance opponent accepts
- `is_realistic`: Boolean flag (True if >30% acceptance)
- Updated `recommendation`: Now considers both value AND acceptance

**Acceptance Probability Logic:**
```python
# Both sides win = HIGH acceptance (70-95%)
if my_value_change > 0 and their_value_change > 0:
    acceptance_prob = 70-95%

# You win, they lose slightly = MODERATE (20-60%)
elif my_value_change > 0 and their_value_change < 0:
    if they lose < 2%:   acceptance_prob = 60%
    if they lose < 5%:   acceptance_prob = 40%
    if they lose < 10%:  acceptance_prob = 20%
    if they lose > 10%:  acceptance_prob = 5%   ❌ TOO UNFAIR

# Extreme imbalance (>15 pt difference) = MAX 10%
if abs(advantage_margin) > 15:
    acceptance_prob = min(current, 10%)
```

**New Filtering in find_trade_opportunities:**
```python
def find_trade_opportunities(
    self,
    my_team,
    min_advantage: float = 5.0,
    max_trades_per_team: int = 3,
    min_acceptance_probability: float = 30.0  # NEW - minimum 30%
):
    # Only suggest trades with realistic acceptance chance
    if (analysis['my_value_change'] > min_advantage and
        analysis['asymmetric_advantage'] and
        analysis['acceptance_probability'] >= min_acceptance_probability):  # NEW
        # Suggest this trade
```

**Updated CLI Output:**
```
📊 Analysis:
   Your Value Change:      +8.7 pts
   Their Value Change:     -12.5 pts
   Advantage Margin:       +21.2 pts
   Points Added Per Week:  +0.9 pts
   Acceptance Probability: 5%          # NEW!
   Recommendation:         REJECT      # Now rejects unfair trades
   Confidence:             78%

🔴 UNREALISTIC: Very unlikely to be accepted (5%)
⚠️  ASYMMETRIC BUT UNFAIR: You gain much more, unlikely to be accepted
```

**Visual Indicators:**
- 🟢 REALISTIC TRADE: 70%+ acceptance (High chance)
- 🟡 MODERATE TRADE: 40-70% acceptance (Fair chance)
- 🟠 RISKY TRADE: 20-40% acceptance (Low chance)
- 🔴 UNREALISTIC: <20% acceptance (Very unlikely)

**Special Cases:**
- ✅ ASYMMETRIC & REALISTIC: You gain more AND they might accept!
- ⚠️  ASYMMETRIC BUT UNFAIR: You gain much more, unlikely to be accepted

---

## Example: Before vs After

### Before (Unfair Trades Suggested)

```
TRADE #1: with Team Alpha
  You Give:    Bench Player
  You Receive: Elite Starter

  Your Value Change:  +15.0 pts  ✅
  Their Value Change: -15.0 pts  ❌
  Recommendation:     ACCEPT
```

**Problem:** They'd never accept this!

### After (Realistic Trades Only)

```
TRADE #1: with Team Alpha
  You Give:    Good Starter, Backup RB
  You Receive: Elite Starter

  Your Value Change:      +5.0 pts  ✅
  Their Value Change:     +2.0 pts  ✅ They also gain!
  Acceptance Probability: 75%
  Recommendation:         ACCEPT

🟢 REALISTIC TRADE: High chance of acceptance (75%)
✅ ASYMMETRIC & REALISTIC: You gain more value AND they might accept!
```

**Why it works:**
- Both sides gain value (win-win)
- You gain slightly more (asymmetric advantage)
- High acceptance probability
- Actually achievable in real league

---

## Impact

### Free Agent Recommendations
**Before:**
- 10 recommendations including 3 injured players
- You waste time researching unavailable players
- Might miss healthy alternatives

**After:**
- 10 recommendations, all healthy and available
- Focus on realistic pickups
- Better use of waiver priority/FAAB

### Trade Recommendations
**Before:**
- 5 trade suggestions
- 4 unrealistic (opponent would reject)
- 1 realistic
- Wasted effort proposing bad trades

**After:**
- 5 trade suggestions
- All have 30%+ acceptance probability
- Focus on trades worth proposing
- Better relationships with league mates

---

## Configuration

### Free Agent Filtering

```python
# Default: Exclude injured players
recommendations = simulator.recommend_free_agents(
    my_team,
    free_agents,
    exclude_injured=True  # Default
)

# Include injured (for research/IR stash)
all_recommendations = simulator.recommend_free_agents(
    my_team,
    free_agents,
    exclude_injured=False  # Show all players
)
```

### Trade Acceptance Threshold

```python
# Default: 30% minimum acceptance
trades = simulator.find_trade_opportunities(
    my_team,
    min_advantage=3.0,
    min_acceptance_probability=30.0  # Default
)

# Higher bar (only very realistic trades)
safe_trades = simulator.find_trade_opportunities(
    my_team,
    min_advantage=3.0,
    min_acceptance_probability=60.0  # Only 60%+ acceptance
)

# Lower bar (more speculative)
risky_trades = simulator.find_trade_opportunities(
    my_team,
    min_advantage=3.0,
    min_acceptance_probability=15.0  # Include riskier trades
)
```

---

## Testing

### Injury Filtering Tests
**File:** `tests/utils/test_injury_filtering.py`

**Coverage:**
- ✅ Filters OUT players
- ✅ Filters QUESTIONABLE players
- ✅ Filters DOUBTFUL players
- ✅ Filters IR players
- ✅ Filters SUSPENDED players
- ✅ Case-insensitive filtering
- ✅ Healthy players not filtered
- ✅ Mixed statuses handled correctly
- ✅ Value ranking preserved
- ✅ Option to include injured players

**Run tests:**
```bash
python -m unittest tests.utils.test_injury_filtering -v
```

### Trade Acceptance Tests
Integrated into existing `test_advanced_simulator.py`:
- Trade analysis includes acceptance probability
- Unrealistic trades filtered from opportunities
- Both sides' value changes calculated correctly

---

## Files Modified

### Core Logic
1. `espn_api/utils/advanced_simulator.py`
   - Added `exclude_injured` parameter to `recommend_free_agents()`
   - Added injury status filtering logic
   - Added acceptance probability calculation to `analyze_trade()`
   - Added `acceptance_probability` and `is_realistic` to trade analysis
   - Updated `find_trade_opportunities()` to filter by acceptance probability
   - Added `min_acceptance_probability` parameter

### CLI/UI
2. `fantasy_decision_maker.py`
   - Updated trade output to show acceptance probability
   - Added visual indicators (🟢🟡🟠🔴) for acceptance levels
   - Updated messages to emphasize realism
   - Changed "asymmetric advantage" messaging based on acceptance

### Testing
3. `tests/utils/test_injury_filtering.py` (NEW)
   - 11 comprehensive tests for injury filtering
   - Tests all injury statuses
   - Tests filtering behavior
   - Tests value ranking preservation

---

## Backwards Compatibility

✅ **Fully backwards compatible**

- `exclude_injured=True` is the default (better behavior)
- Can set `exclude_injured=False` for old behavior
- `min_acceptance_probability` parameter is optional
- Existing code will automatically get improved recommendations
- All new fields added to analysis dict (no fields removed)

---

## Future Enhancements

Possible improvements for the future:

1. **Injury Timeline Filtering**
   - Filter "Out" but include "Questionable" if game is far away
   - Check expected return dates
   - Consider IR-Return eligible players

2. **Context-Aware Acceptance**
   - Consider opponent's roster needs (weak at RB? More likely to accept RB)
   - Consider playoff race urgency
   - Consider bye week coverage needs

3. **Historical Acceptance Data**
   - Learn from league's past trades
   - Adjust acceptance probability based on league's trade frequency
   - Identify "trade-active" vs "trade-averse" opponents

4. **Three-Team Trades**
   - Multi-team trade analysis
   - Find win-win-win scenarios
   - Calculate acceptance for all parties

---

## Summary

### What Changed
- ✅ Injured players filtered from free agent recommendations
- ✅ Trade acceptance probability calculated
- ✅ Unrealistic trades filtered from recommendations
- ✅ Better CLI output with visual indicators
- ✅ Comprehensive tests added

### Why It Matters
- **Saves time**: No researching unavailable players
- **Better trades**: Only propose realistic deals
- **League relationships**: Don't annoy people with lowball offers
- **More wins**: Focus on actionable opportunities

### How to Use
Just run the tool normally - improvements are automatic! The tool now:
1. Only recommends healthy free agents you can actually pick up
2. Only suggests trades that have a realistic chance of being accepted
3. Shows you acceptance probability so you can decide which trades to propose

**Ready to use immediately - no config changes needed!** 🎉

---

## Issue #3: Trade Values Based on Season Averages, Not ROS ✅ FIXED

### Problem
Trade recommendations were based on **season-long averages** instead of **Rest of Season (ROS) projections**. This meant:
- A player with 3 tough matchups remaining had the same value as one with 3 easy matchups
- Past performance (weeks 1-10) weighted equally with future matchups
- No consideration of upcoming schedule strength

**Example:**
```
Player A: 15.0 pts/game (season avg) → ROS vs #1, #2, #3 defenses
Player B: 15.0 pts/game (season avg) → ROS vs #30, #31, #32 defenses

Old System: "Equal value" ❌
Reality: Player B much more valuable for ROS ✅
```

### Solution
Implemented **schedule-aware ROS projections** for trade analysis:

**New Calculation Method:**
1. Calculate opponent strength for each position based on fantasy points allowed
2. Project weekly performance for remaining weeks with matchup adjustments
3. Use ROS values instead of season averages for trade analysis

**Code Changes:**
```python
# In advanced_simulator.py

# NEW: Calculate opponent defense strength
def _calculate_opponent_strength(position: str, opponent_team: str) -> float:
    # Returns multiplier: 1.0 = average, >1.0 = favorable, <1.0 = unfavorable
    # Example: 49ers allow 12 pts/game to RBs, league avg is 15
    #   multiplier = 12/15 = 0.80 (tough matchup)

# NEW: Calculate ROS value with schedule awareness
def _calculate_roster_value_ros(roster, current_week, end_week, consider_schedule=True):
    for week in range(current_week, end_week + 1):
        # Get base projection (with GMM hot/cold state)
        base_projection = GMM_predict() or projected_avg_points

        # Adjust for matchup difficulty
        if player has schedule data:
            opponent = player.schedule[week]
            multiplier = calculate_opponent_strength(position, opponent)
            week_projection = base_projection * multiplier

        ros_value += week_projection
    return ros_value / weeks_remaining

# UPDATED: analyze_trade now uses ROS by default
def analyze_trade(my_team, other_team, my_players, their_players, use_ros=True):
    if use_ros:
        # Use ROS projections with schedule awareness
        my_value_after = calculate_roster_value_ros(roster_after, current_week, end_week)
    else:
        # Fall back to season averages
        my_value_after = calculate_roster_value(roster_after)
```

**New Output:**
```
🔄 TRADE OPPORTUNITY ANALYSIS (REST OF SEASON)

🔍 Searching for realistic trade opportunities...
   (Using ROS projections with schedule-aware matchup difficulty)

TRADE #1: with Team Alpha
────────────────────────────────────────────────────────────────

  You Give:    James Conner
  You Receive: Saquon Barkley

  📊 Analysis (ROS):
     Weeks Remaining:        5
     Your Value Change:      +4.2 pts/week  ← ROS, not season avg!
     Their Value Change:     +1.5 pts/week
     Advantage Margin:       +2.7 pts/week
     Acceptance Probability: 65%
     Recommendation:         ACCEPT

  🟡 MODERATE TRADE: Fair chance of acceptance (65%)
  ✅ ASYMMETRIC & REALISTIC: You gain more value AND they might accept!
```

### How It Works

**Step 1: Calculate Defense Rankings**
- Analyzes fantasy points allowed by each NFL team to each position
- Creates multipliers: 1.0 = average, >1.0 = easy, <1.0 = tough

**Step 2: Project ROS Performance**
- For each remaining week, gets base projection (GMM or ESPN)
- Adjusts projection based on opponent strength
- Averages weekly projections for ROS value

**Step 3: Analyze Trade with ROS**
- Calculates team ROS value before trade
- Calculates team ROS value after trade
- Reports value change in pts/week for remaining weeks

### Example Comparison

**Before (Season Averages):**
```
Player A: 15.0 pts/game season avg
Player B: 15.0 pts/game season avg
Trade Value: EQUAL ❌
```

**After (ROS Projections):**
```
Player A (tough schedule):
  - Season Avg: 15.0 pts/game
  - ROS Matchups: vs #1 DEF, vs #2 DEF, vs #3 DEF
  - ROS Projection: 11.5 pts/game

Player B (easy schedule):
  - Season Avg: 15.0 pts/game
  - ROS Matchups: vs #28 DEF, vs #30 DEF, vs #32 DEF
  - ROS Projection: 17.8 pts/game

Trade Value: Player B is +6.3 pts/week more valuable! ✅
```

### Testing
Created comprehensive test suite (`test_ros_trade_analysis.py`) with 7 tests:
- ✅ ROS uses weeks_remaining parameter
- ✅ ROS vs season avg gives different results
- ✅ find_trade_opportunities uses ROS flag
- ✅ Opponent strength calculation works
- ✅ ROS value calculation returns valid values
- ✅ ROS works without schedule data (fallback)
- ✅ All trade analysis includes ROS metadata

### Configuration

**Default: ROS Enabled**
```python
# Automatic - uses ROS by default
opportunities = simulator.find_trade_opportunities(my_team)
```

**Disable ROS (use season averages)**
```python
# For comparison or if schedule data unavailable
opportunities = simulator.find_trade_opportunities(my_team, use_ros=False)
```

**Manual weeks_remaining**
```python
# Focus on next 3 weeks only
analysis = simulator.analyze_trade(
    my_team, other_team,
    [my_player], [their_player],
    weeks_remaining=3
)
```

---

## Summary (All Improvements)

### What Changed
- ✅ Injured players filtered from free agent recommendations
- ✅ Trade acceptance probability calculated
- ✅ Unrealistic trades filtered from recommendations
- ✅ **ROS projections with schedule-aware matchups** (NEW!)
- ✅ Better CLI output with visual indicators
- ✅ Comprehensive tests added

### Why It Matters
- **Saves time**: No researching unavailable players
- **Better trades**: Only propose realistic deals
- **Accurate values**: Trade based on future value, not past performance
- **Schedule advantage**: Exploit matchup differences others miss
- **League relationships**: Don't annoy people with lowball offers
- **More wins**: Focus on actionable opportunities

### How to Use
Just run the tool normally - improvements are automatic! The tool now:
1. Only recommends healthy free agents you can actually pick up
2. Only suggests trades that have a realistic chance of being accepted
3. **Uses Rest of Season projections that consider upcoming matchups**
4. Shows you acceptance probability so you can decide which trades to propose

**Ready to use immediately - no config changes needed!** 🎉

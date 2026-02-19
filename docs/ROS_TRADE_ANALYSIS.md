# Rest of Season (ROS) Analysis - Implementation Complete ✅

## Overview

**Trade analysis** and **free agent recommendations** now use **Rest of Season (ROS) projections** with **schedule-aware matchup difficulty** instead of season averages. This gives you accurate values based on upcoming matchups for the weeks that actually matter.

## What Changed

### Before (Season Averages) ❌
```
Player A: 15.0 pts/game (season average)
Player B: 15.0 pts/game (season average)
Trade Value: EQUAL

Problem: Ignores that Player A has tough matchups and Player B has easy matchups
```

### After (ROS Projections) ✅
```
Player A:
  - Season Avg: 15.0 pts/game
  - ROS Matchups: vs #1 DEF, vs #2 DEF, vs #3 DEF
  - ROS Projection: 11.5 pts/game (adjusted for tough schedule)

Player B:
  - Season Avg: 15.0 pts/game
  - ROS Matchups: vs #28 DEF, vs #30 DEF, vs #32 DEF
  - ROS Projection: 17.8 pts/game (adjusted for easy schedule)

Trade Value: Player B is +6.3 pts/week more valuable!
```

## How It Works

### 1. Opponent Strength Calculation

Calculates how each NFL team's defense performs against each position:

```python
def _calculate_opponent_strength(position: str, opponent_team: str) -> float:
    # Returns multiplier: 1.0 = average, >1.0 = favorable, <1.0 = unfavorable
    # Example: If 49ers allow 12 pts/game to RBs and league avg is 15:
    #   multiplier = 12/15 = 0.80 (tough matchup)
```

**Data Source:** Analyzes actual fantasy points allowed to each position across all league teams

### 2. ROS Value Calculation

For each player, projects weekly performance for remaining weeks:

```python
def _calculate_roster_value_ros(roster, current_week, end_week):
    for player in roster:
        for week in range(current_week, end_week + 1):
            # Step 1: Get base projection
            if using_GMM:
                base_projection = GMM_predict()  # Accounts for hot/cold state
            else:
                base_projection = projected_avg_points

            # Step 2: Adjust for matchup difficulty
            if player has schedule data for this week:
                opponent = player.schedule[week]
                matchup_multiplier = calculate_opponent_strength(position, opponent)
                week_projection = base_projection * matchup_multiplier

            # Step 3: Sum weekly projections
            ros_value += week_projection

    return ros_value / weeks_remaining  # Average per week
```

### 3. Trade Analysis with ROS

```python
def analyze_trade(my_team, other_team, my_players, their_players, use_ros=True):
    # Calculate current week and weeks remaining
    current_week = league.current_week
    weeks_remaining = reg_season_end - current_week + 1

    # Before trade (ROS values)
    my_ros_before = calculate_roster_value_ros(my_team.roster, current_week, end_week)
    their_ros_before = calculate_roster_value_ros(their_team.roster, current_week, end_week)

    # After trade (ROS values)
    my_roster_after = my_team.roster - my_players + their_players
    my_ros_after = calculate_roster_value_ros(my_roster_after, current_week, end_week)

    # Value change based on ROS, not season averages!
    my_value_change = my_ros_after - my_ros_before
```

## Features

### ✅ Schedule-Aware Projections
- Adjusts player values based on actual upcoming opponents
- Considers defensive strength by position (QB, RB, WR, TE)
- Updates automatically as schedule progresses

### ✅ GMM Integration
- Accounts for hot/cold streaks in ROS projections
- Uses current player state to bias future predictions
- More accurate than simple averages

### ✅ Automatic Calculation
- Calculates weeks remaining automatically from current week
- Uses regular season end week from league settings
- No manual configuration needed

### ✅ Backward Compatible
- Optional `use_ros` parameter (default: True)
- Can fall back to season averages if needed
- Works even if schedule data is unavailable

## Usage

### CLI (Automatic)

**Trades:**
```bash
python fantasy_decision_maker.py --league-id XXX --team-id X
# Select: "4. Analyze trades"
```

**Free Agents:**
```bash
python fantasy_decision_maker.py --league-id XXX --team-id X
# Select: "2. Analyze free agents"
```

**Trade Output:**
```
🔄 TRADE OPPORTUNITY ANALYSIS (REST OF SEASON)

🔍 Searching for realistic trade opportunities...
   (Using ROS projections with schedule-aware matchup difficulty)

TRADE #1: with Team Alpha
────────────────────────────────────────────────────────────────────────────────

  You Give:    James Conner
  You Receive: Saquon Barkley

  📊 Analysis (ROS):
     Weeks Remaining:        5
     Your Value Change:      +4.2 pts/week  ← ROS projection
     Their Value Change:     +1.5 pts/week
     Advantage Margin:       +2.7 pts/week
     Points Added Per Week:  +4.2 pts
     Acceptance Probability: 65%
     Recommendation:         ACCEPT
     Confidence:             82%

  🟡 MODERATE TRADE: Fair chance of acceptance (65%)
  ✅ ASYMMETRIC & REALISTIC: You gain more value AND they might accept!
```

**Free Agent Output:**
```
🆓 FREE AGENT ANALYSIS (REST OF SEASON)

📥 Fetching free agents...
🔍 Analyzing 100 free agents with ROS schedule awareness...

🎯 TOP FREE AGENT RECOMMENDATIONS (ROS):
   (ROS values shown, season avg in parentheses if significantly different)

   Rank  Player            Pos  Value Added  ROS Avg       Drop                 Drop ROS     Priority  Own %
      1  Jaylen Warren     RB         +5.2   14.3 (12.1)  James Conner         9.1 (13.5)   HIGH      45.2%
      2  Tank Bigsby       RB         +4.8   13.2 (11.8)  Tony Pollard         8.4 (10.2)   HIGH      38.7%
      3  Jaxon Smith-Njigba WR        +3.9   11.5 (10.2)  Tyler Lockett        7.6 (8.9)    HIGH      52.1%
```

**What This Shows:**
- Jaylen Warren: 14.3 ROS (was 12.1 season avg) → easy schedule!
- James Conner: 9.1 ROS (was 13.5 season avg) → tough schedule!
- Net gain: +5.2 pts/week by making the pickup

### Programmatic Usage

```python
from espn_api.football import League
from espn_api.utils.advanced_simulator import AdvancedFantasySimulator

league = League(league_id=XXX, year=2024, espn_s2='...', swid='...')
simulator = AdvancedFantasySimulator(league)

# Find trades using ROS projections
opportunities = simulator.find_trade_opportunities(
    my_team,
    min_advantage=3.0,
    use_ros=True  # Default, uses ROS with schedule awareness
)

# Analyze specific trade with ROS
analysis = simulator.analyze_trade(
    my_team,
    other_team,
    my_players=[conner],
    their_players=[barkley],
    weeks_remaining=5,  # Auto-calculated from league.current_week
    use_ros=True  # Use ROS projections
)

print(f"Value change (ROS): {analysis['my_value_change']} pts/week")
print(f"Uses ROS: {analysis['uses_ros_projections']}")
print(f"Weeks remaining: {analysis['weeks_remaining']}")

# Find free agents using ROS projections
free_agents = league.free_agents(size=100)
recommendations = simulator.recommend_free_agents(
    my_team,
    free_agents,
    top_n=10,
    use_ros=True  # Default, uses ROS with schedule awareness
)

for rec in recommendations:
    print(f"{rec['player'].name}: {rec['fa_projected_avg']:.1f} ROS (was {rec['fa_season_avg']:.1f})")
    print(f"  Value added: +{rec['value_added']:.1f} pts/week")
```

### Disable ROS (Use Season Averages)

```python
# For comparison or if schedule data is unavailable
opportunities = simulator.find_trade_opportunities(
    my_team,
    use_ros=False  # Use season averages instead
)

analysis = simulator.analyze_trade(
    my_team, other_team,
    [my_player], [their_player],
    use_ros=False
)

# Free agents without ROS
recommendations = simulator.recommend_free_agents(
    my_team,
    free_agents,
    use_ros=False
)
```

## Example Scenarios

### Scenario 1: Playoff Push

**Situation:** Week 10, need to make playoffs

```python
# Current week: 10
# Regular season ends: Week 14
# Weeks remaining: 5
```

**Player A:**
- Season Avg: 14.2 pts/game
- ROS Schedule: vs DEN (tough), vs KC (tough), vs SF (tough), vs BAL (tough), vs MIA (avg)
- **ROS Projection: 11.8 pts/game** ❌

**Player B:**
- Season Avg: 14.0 pts/game
- ROS Schedule: vs ARI (easy), vs CAR (easy), vs NYG (easy), vs LV (easy), vs JAX (easy)
- **ROS Projection: 17.2 pts/game** ✅

**Trade Recommendation:**
```
Trade Player A for Player B
Value Gain: +5.4 pts/week for 5 weeks = +27.0 total points
```

### Scenario 2: Championship Schedule

**Situation:** Week 12, locked into playoffs, optimizing for championship weeks

```python
# Current week: 12
# Regular season ends: Week 14
# Playoffs: Weeks 15-17
# Focus on playoff schedule!
```

**Player A:**
- Weeks 15-17: vs MIN (6th best DEF), vs DAL (8th), vs PHI (3rd)
- **Playoff ROS: 12.5 pts/game** ❌

**Player B:**
- Weeks 15-17: vs CAR (32nd worst DEF), vs CHI (28th), vs ARI (30th)
- **Playoff ROS: 19.8 pts/game** ✅

**Trade Recommendation:**
```
Trade for Player B before playoffs
Championship weeks value: +7.3 pts/week
```

## Configuration

### Adjust ROS Time Horizon

Modify weeks_remaining to focus on different periods:

```python
# Focus on next 3 weeks only
analysis = simulator.analyze_trade(
    my_team, other_team,
    [my_player], [their_player],
    weeks_remaining=3  # Only next 3 weeks
)

# Focus on playoff weeks (manual)
playoff_start = 15
playoff_end = 17
current_week = 12
playoff_weeks = playoff_end - playoff_start + 1

# Would need custom calculation - feature request!
```

### Customize Opponent Strength Calculation

The opponent strength calculation is automatic, but you can extend it:

```python
# Currently uses league data to calculate defense strength
# Future: Could integrate external defense rankings (ESPN, FanGraphs, etc.)
```

## Benefits

### 1. Better Trade Decisions
- ✅ Know which players have favorable upcoming schedules
- ✅ Avoid players facing tough defenses
- ✅ Maximize points in critical weeks (playoffs)

### 2. Competitive Advantage
- ✅ Most managers trade based on season averages
- ✅ You trade based on future value
- ✅ Exploit schedule differences others miss

### 3. Accurate Projections
- ✅ Accounts for actual upcoming opponents
- ✅ Integrates GMM hot/cold states
- ✅ More realistic than season-long averages

## Testing

Run ROS-specific tests:

```bash
# Test ROS trade analysis
python -m unittest tests.utils.test_ros_trade_analysis -v

# All tests
python run_tests.py
```

**Test Coverage:**
- ✅ ROS uses weeks_remaining parameter
- ✅ ROS vs season avg gives different results
- ✅ find_trade_opportunities uses ROS flag
- ✅ Opponent strength calculation works
- ✅ ROS value calculation returns valid values
- ✅ ROS works without schedule data (fallback)

## Files Modified

### Core Implementation
1. **espn_api/utils/advanced_simulator.py**
   - `_calculate_opponent_strength()` - NEW: Calculate defense rankings
   - `_calculate_roster_value_ros()` - NEW: ROS value with schedule awareness
   - `analyze_trade()` - MODIFIED: Added `use_ros` parameter
   - `find_trade_opportunities()` - MODIFIED: Added `use_ros` parameter

### CLI
2. **fantasy_decision_maker.py**
   - Updated trade analysis header to show "REST OF SEASON"
   - Added "(ROS)" indicator in output
   - Shows weeks remaining
   - Labels values as "pts/week" for clarity

### Testing
3. **tests/utils/test_ros_trade_analysis.py** - NEW
   - Comprehensive ROS testing suite
   - 7 tests covering all ROS features

### Documentation
4. **TRADE_VALUE_ANALYSIS.md** - Analysis document
5. **ROS_TRADE_ANALYSIS.md** - This file
6. **IMPROVEMENTS.md** - Will update with ROS feature

## Limitations & Future Enhancements

### Current Limitations
1. **Defense rankings calculated from league data only**
   - Could integrate external rankings (ESPN, PFF, etc.)
   - Could consider defensive trends (improving/declining)

2. **No injury/suspension awareness in ROS**
   - Could check player.injuryStatus for future weeks
   - Could project return dates for IR players

3. **No weather/home-away adjustments**
   - Could factor in dome games, weather conditions
   - Could adjust for home/road splits

### Future Enhancements
1. **Playoff-Specific ROS**
   - Separate ROS calculation for playoff weeks
   - Focus on championship matchups

2. **Dynamic Defense Rankings**
   - Update defense strength as season progresses
   - Account for defensive injuries/trades

3. **Multi-Week Trade Analysis**
   - Show week-by-week value changes
   - Identify when trade pays off most

4. **Schedule Visualization**
   - Display upcoming matchups in trade analysis
   - Show defense rankings visually

## Summary

✅ **Implemented:** Schedule-aware ROS trade analysis
✅ **Testing:** 7 comprehensive tests passing
✅ **Integration:** Automatic in CLI and API
✅ **Documentation:** Complete with examples

**Your trades now consider:**
- Remaining weeks in season
- Upcoming opponent difficulty
- Position-specific defense strength
- Player hot/cold states (GMM)

**No more trading based on past performance - trade based on future value!** 🎯

# Trade Value Analysis: Current vs Rest of Season (ROS)

## Current Implementation

### ❌ Problem: Trade Values Use **Season Averages**, Not ROS

The current trade analysis calculates player values using **entire season statistics**, which includes:
- All weeks already played
- Historical averages that may not reflect current performance
- No consideration of upcoming schedule/matchups

### How It Currently Works

**File:** `espn_api/utils/advanced_simulator.py`

**Step 1: Calculate Team Value** (line 284-323)
```python
def _calculate_roster_value(self, roster: List) -> float:
    for player in starters:
        if self.use_gmm and player.playerId in self.player_model.player_states:
            # Uses GMM season_avg (entire season)
            value = state['season_avg']  # ❌ SEASON AVERAGE
        else:
            # Uses ESPN projected_avg_points (entire season)
            value = getattr(player, 'projected_avg_points', 0)  # ❌ SEASON AVERAGE
```

**Step 2: Analyze Trade** (line 198-279)
```python
def analyze_trade(self, my_team, other_team, my_players, their_players, weeks_remaining=10):
    # Calculate value before trade
    my_current_value = self._calculate_team_value(my_team)  # ❌ Uses season avg

    # Calculate value after trade
    my_value_after = self._calculate_roster_value(my_roster_after)  # ❌ Uses season avg

    # Project wins added
    avg_points_per_week = my_value_change / weeks_remaining  # ❌ Just divides season avg
```

**Problem:**
- Player averaging 15 pts/game with 3 tough matchups remaining gets same value as player with 3 easy matchups
- Doesn't account for trends (hot streaks, cold streaks, injuries returning)
- Doesn't use actual ROS projections

## What You Need: ROS-Based Trade Values

### ✅ Ideal Implementation

Trade values should be based on:
1. **Rest of Season (ROS) Projections** - only weeks remaining
2. **Upcoming Matchups** - opponent strength for player's position
3. **Current Form** - recent performance trends (GMM already does this with hot/cold states)
4. **Playoff Schedule** - especially important for playoff-bound teams

### Example Scenario

**Current (Wrong):**
```
Player A: 15.0 pts/game season average
Player B: 15.0 pts/game season average
Trade Value: EQUAL ❌
```

**ROS-Based (Correct):**
```
Player A:
  - Season Avg: 15.0 pts/game
  - ROS Matchups: vs #1 DEF, vs #2 DEF, vs #3 DEF
  - ROS Projection: 11.0 pts/game ❌ TOUGH SCHEDULE

Player B:
  - Season Avg: 15.0 pts/game
  - ROS Matchups: vs #28 DEF, vs #30 DEF, vs #32 DEF
  - ROS Projection: 18.0 pts/game ✅ EASY SCHEDULE

Trade Value: Player B >> Player A ✅
```

## Available Data

### ✅ Data We Have Access To

1. **Player Schedule** (espn_api/football/player.py:19)
   ```python
   player.schedule = {
       week_number: {
           'team': 'Opponent',
           'date': datetime(...)
       }
   }
   ```

2. **Week-by-Week Stats** (espn_api/football/player.py:18)
   ```python
   player.stats = {
       week_number: {
           'points': ...,
           'avg_points': ...,
           'projected_points': ...
       }
   }
   ```

3. **GMM Performance States** (espn_api/utils/player_performance.py)
   - Hot/Normal/Cold state detection
   - Recent form trends
   - Performance prediction with bias

4. **League Information**
   ```python
   league.current_week  # Current week
   league.settings.reg_season_count  # Regular season end week
   league.settings.playoff_team_count  # Playoff info
   ```

## Proposed Fix

### Option 1: Simple ROS Projection (Recommended for Quick Fix)

Use current GMM predictions for remaining weeks:

```python
def _calculate_roster_value_ros(self, roster: List, weeks_remaining: int) -> float:
    """Calculate roster value for rest of season only"""
    total_value = 0

    for player in roster:
        if self.use_gmm and player.playerId in self.player_model.player_states:
            # Use GMM to predict future performance (already biased by current state)
            predictions = self.player_model.predict_performance(
                player,
                n_samples=weeks_remaining,
                use_state_bias=True  # Accounts for hot/cold streaks
            )
            ros_avg = np.mean(predictions)
        else:
            # Fall back to projected points
            ros_avg = getattr(player, 'projected_avg_points', 0)

        total_value += ros_avg

    return total_value
```

### Option 2: Schedule-Aware ROS Projection (Advanced)

Consider opponent strength for remaining matchups:

```python
def _calculate_roster_value_ros_with_schedule(
    self,
    roster: List,
    current_week: int,
    end_week: int
) -> float:
    """Calculate ROS value considering matchup difficulty"""
    total_value = 0

    for player in roster:
        ros_value = 0
        weeks_remaining = end_week - current_week + 1

        # Get player's upcoming schedule
        for week in range(current_week, end_week + 1):
            if week in player.schedule:
                opponent = player.schedule[week]['team']

                # Adjust projection based on opponent strength
                # (Would need opponent defense rankings)
                matchup_difficulty = self._get_matchup_difficulty(
                    player.position,
                    opponent
                )

                if self.use_gmm:
                    base_projection = self.player_model.predict_performance(
                        player,
                        n_samples=1,
                        use_state_bias=True
                    )[0]
                else:
                    base_projection = getattr(player, 'projected_avg_points', 0)

                # Adjust for matchup
                week_projection = base_projection * matchup_difficulty
                ros_value += week_projection

        # Average over remaining weeks
        if weeks_remaining > 0:
            total_value += ros_value / weeks_remaining

    return total_value
```

### Option 3: Monte Carlo ROS Simulation (Most Accurate)

Simulate each remaining week individually:

```python
def analyze_trade_ros(
    self,
    my_team,
    other_team,
    my_players: List,
    their_players: List,
    current_week: int,
    end_week: int
) -> Dict:
    """Analyze trade using ROS simulation"""

    # Simulate rest of season BEFORE trade
    my_ros_before = self._simulate_ros(my_team, current_week, end_week)
    their_ros_before = self._simulate_ros(other_team, current_week, end_week)

    # Simulate rest of season AFTER trade
    my_roster_after = [p for p in my_team.roster if p not in my_players] + their_players
    their_roster_after = [p for p in other_team.roster if p not in their_players] + my_players

    my_ros_after = self._simulate_ros_roster(my_roster_after, current_week, end_week)
    their_ros_after = self._simulate_ros_roster(their_roster_after, current_week, end_week)

    # Calculate ROS value change
    my_ros_value_change = my_ros_after - my_ros_before
    their_ros_value_change = their_ros_after - their_ros_before

    # ... rest of analysis
```

## Recommendation

### Immediate Fix (Option 1)

**Pros:**
- ✅ Quick to implement (1 hour)
- ✅ Uses existing GMM state bias (hot/cold)
- ✅ Better than season averages
- ✅ No external data needed

**Cons:**
- ❌ Doesn't consider matchup difficulty
- ❌ Assumes uniform projection across weeks

### Medium-Term Enhancement (Option 2)

**Pros:**
- ✅ Considers actual upcoming opponents
- ✅ More accurate for schedule-dependent value
- ✅ Critical for playoff-bound teams

**Cons:**
- ❌ Needs opponent defense rankings (would need to calculate)
- ❌ More complex implementation

### Long-Term Goal (Option 3)

**Pros:**
- ✅ Most accurate
- ✅ Leverages existing Monte Carlo infrastructure
- ✅ Accounts for all variables

**Cons:**
- ❌ Computationally expensive
- ❌ Takes longer to implement

## Implementation Priority

1. **Phase 1 (Immediate):** Update `analyze_trade()` to use weeks_remaining parameter
   - Currently accepts `weeks_remaining` but doesn't use it properly
   - Line 204: `weeks_remaining: int = 10`
   - Line 239: `avg_points_per_week = my_value_change / weeks_remaining` ← Only used for display

2. **Phase 2 (Quick Win):** Add `_calculate_roster_value_ros()` using GMM predictions
   - Use GMM `predict_performance()` for future weeks
   - Already accounts for hot/cold states
   - No schedule data needed

3. **Phase 3 (Enhancement):** Add schedule-aware adjustments
   - Calculate opponent strength rankings
   - Adjust projections based on matchup difficulty
   - Particularly important for RBs and WRs

## Current vs Proposed Behavior

### Current
```python
# Trade: My Bench RB (15 ppg season avg, tough ROS)
#    for: Their WR2 (15 ppg season avg, easy ROS)

analyze_trade(my_team, their_team, [bench_rb], [their_wr])
# Result: Equal value (both 15 ppg) ❌ WRONG
```

### Proposed
```python
# Trade: My Bench RB (15 ppg season avg, 11 ppg ROS projection)
#    for: Their WR2 (15 ppg season avg, 18 ppg ROS projection)

analyze_trade_ros(my_team, their_team, [bench_rb], [their_wr])
# Result: Their WR2 has +7 ppg ROS value ✅ CORRECT
```

## Files to Modify

1. **espn_api/utils/advanced_simulator.py**
   - Add `_calculate_roster_value_ros()` method
   - Update `analyze_trade()` to use ROS calculations
   - Add optional `use_ros` parameter (default True)

2. **fantasy_decision_maker.py**
   - Pass current_week and playoff_start_week to trade analyzer
   - Display ROS vs season averages in output

3. **tests/utils/test_advanced_simulator.py**
   - Add tests for ROS trade calculations
   - Verify ROS projections differ from season averages

## Summary

**Current Status:** ❌ Trade values use season averages (entire season)

**What You Want:** ✅ Trade values based on Rest of Season (ROS) projections

**Quick Fix:** Implement Option 1 - use GMM predictions for remaining weeks

**Best Solution:** Implement Option 2 - schedule-aware ROS projections

**Next Step:** Should I implement the ROS-based trade analysis? I recommend starting with Option 1 for immediate improvement.

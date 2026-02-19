# Quick Start Guide

Get started with the Fantasy Football Decision Maker in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Find Your League Info

### League ID
1. Go to your ESPN Fantasy Football league
2. Look at the URL: `https://fantasy.espn.com/football/league?leagueId=123456`
3. Your league ID is `123456`

### Team ID
1. Click on your team
2. Look at the URL: `https://fantasy.espn.com/football/team?leagueId=123456&teamId=1`
3. Your team ID is `1`

### ESPN Cookies (Private Leagues Only)

If your league is private:

1. Log into ESPN Fantasy Football in Chrome/Firefox
2. Press `F12` to open Developer Tools
3. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
4. Click **Cookies** → **https://fantasy.espn.com**
5. Find and copy these values:
   - `SWID` (include the curly braces `{...}`)
   - `espn_s2` (long string)

## Step 3: Run Your First Analysis

### Option A: Using Config File (Easier)

**1. Copy the template:**
```bash
cp config.template.json config.json
```

**2. Edit `config.json` with your league info:**
```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1,
    "year": 2024,
    "swid": null,
    "espn_s2": null
  }
}
```

For private leagues, add your cookies:
```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1,
    "swid": "{YOUR-SWID-HERE}",
    "espn_s2": "YOUR-ESPN-S2-HERE"
  }
}
```

**3. Run:**
```bash
python fantasy_decision_maker.py --config config.json
```

See [CONFIG_USAGE.md](CONFIG_USAGE.md) for more config options.

### Option B: Using Command Line

**Public League:**
```bash
python fantasy_decision_maker.py --league-id 123456 --team-id 1
```

**Private League:**
```bash
python fantasy_decision_maker.py \
  --league-id 123456 \
  --team-id 1 \
  --swid "{YOUR-SWID-HERE}" \
  --espn-s2 "YOUR-ESPN-S2-HERE"
```

## Step 4: Choose Your Analysis

You'll see a menu:

```
🏈 FANTASY FOOTBALL DECISION MAKER

What would you like to analyze?
  1. Current Week Matchup       ← Check your win probability
  2. Free Agent Recommendations ← See who to pick up
  3. Trade Opportunities        ← Find asymmetric trades
  4. Rest of Season Outlook     ← Playoff odds
  5. Generate Full Weekly Report
  6. Exit
```

### Recommended First Analysis

Start with **Option 1: Current Week Matchup**

This will:
- Show your win probability for this week
- Project your score range
- Give you confidence in your lineup

## Step 5: Weekly Routine

### Every Monday/Tuesday (After Waivers)

```bash
python fantasy_decision_maker.py --league-id XXX --team-id X --report-only
```

This generates a comprehensive report with:
- Matchup analysis
- Free agent recommendations
- Trade opportunities
- Season outlook

Save the report and use it to make decisions!

### During the Week

Run interactive mode to check specific scenarios:

```bash
python fantasy_decision_maker.py --league-id XXX --team-id X
```

## Common First-Time Issues

### ❌ "Team ID not found"
**Fix**: Double-check your team ID. It's in the URL when you view your team.

### ❌ "401 Unauthorized"
**Fix**: Your league is private. Add `--swid` and `--espn-s2` cookies.

### ❌ "Insufficient data for player"
**Fix**: This is normal for new players. System uses fallback predictions automatically.

### ⏰ First run is slow (1-3 minutes)
**Fix**: This is expected! The system is training AI models for all players. Subsequent runs will be fast (5-15 seconds).

## What to Expect

### First Run (Training)
```
📊 Loading league...
✅ Found team: Your Team Name
🔬 Initializing advanced simulator...
   Training player performance models (this may take a minute)...
   [Progress updates...]
✅ Simulator ready!
```

**Time**: 1-3 minutes

### Subsequent Runs (Cached)
```
📊 Loading league...
✅ Found team: Your Team Name
🔬 Initializing advanced simulator...
   Loading cached models...
✅ Simulator ready!
```

**Time**: 5-15 seconds

## Understanding Results

### Matchup Win Probability

| Probability | Meaning | Strategy |
|------------|---------|----------|
| > 70% | Strong favorite | Play safe, high floor players |
| 55-70% | Slight favorite | Play your studs |
| 45-55% | Toss-up | Balanced approach |
| 30-45% | Underdog | Take calculated risks |
| < 30% | Long shot | Swing for ceiling, not floor |

### Free Agent Value Added

| Value Added | Priority | Action |
|------------|----------|--------|
| +3.0 or more | HIGH | Use waiver priority/FAAB |
| +1.0 to +3.0 | MEDIUM | Free agent after waivers |
| +0.5 to +1.0 | LOW | Only if roster space |

### Trade Advantage Margin

| Margin | Meaning | Action |
|--------|---------|--------|
| +5.0 or more | Huge win | Strongly pursue |
| +3.0 to +5.0 | Good trade | Try to execute |
| +1.0 to +3.0 | Minor upgrade | Situational |
| < +1.0 | Lateral move | Not worth it |

## Next Steps

1. **Read the full README**: [FANTASY_DECISION_MAKER_README.md](FANTASY_DECISION_MAKER_README.md)
2. **Check examples**: See `examples/advanced_decision_making.py` for code samples
3. **Customize settings**: Copy `config.template.json` to `config.json` and modify

## Tips for Your First Week

1. **Run matchup analysis** before setting your lineup
2. **Check free agents** for any obvious pickups you missed
3. **Review trade opportunities** but don't force trades early
4. **Check season outlook** to understand your playoff path

## Need Help?

- **Documentation**: See [FANTASY_DECISION_MAKER_README.md](FANTASY_DECISION_MAKER_README.md)
- **Examples**: See [examples/advanced_decision_making.py](examples/advanced_decision_making.py)
- **ESPN API Docs**: https://github.com/cwendt94/espn-api

## Success Indicators

After your first run, you should see:

✅ Win probability for current matchup
✅ Top 5-10 free agent recommendations
✅ 2-5 trade opportunities (if any exist)
✅ Playoff odds and projected wins

If you see all of these, you're ready to start making data-driven fantasy decisions!

---

**Good luck this season! 🏈🏆**

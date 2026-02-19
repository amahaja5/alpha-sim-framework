# Using Configuration Files

The Fantasy Football Decision Maker now supports loading settings from a JSON configuration file, making it easier to manage your league settings and preferences.

## Quick Start

### 1. Create Your Config File

Copy the template:
```bash
cp config.template.json config.json
```

Or use the example:
```bash
cp config.example.json config.json
```

### 2. Edit Your Config

Open `config.json` and add your league details:

```json
{
  "league": {
    "league_id": 123456,      // Your ESPN league ID
    "team_id": 1,             // Your team ID
    "year": 2024,             // Season year
    "swid": null,             // SWID cookie (for private leagues)
    "espn_s2": null           // ESPN_S2 cookie (for private leagues)
  },
  "simulation": {
    "num_simulations": 10000,
    "cache_dir": ".cache"
  }
}
```

### 3. Run with Config File

```bash
python fantasy_decision_maker.py --config config.json
```

That's it! Much simpler than typing all the arguments every time.

## Config File Structure

### League Settings

```json
{
  "league": {
    "league_id": 123456,           // Required: Your ESPN league ID
    "team_id": 1,                  // Required: Your team ID
    "year": 2024,                  // Season year (default: current year)
    "swid": "{YOUR-SWID}",         // Optional: For private leagues
    "espn_s2": "YOUR-ESPN-S2"      // Optional: For private leagues
  }
}
```

**Finding Your IDs:**
- **league_id**: In URL when viewing your league
  - `https://fantasy.espn.com/football/league?leagueId=123456`
- **team_id**: In URL when viewing your team
  - `https://fantasy.espn.com/football/team?leagueId=123456&teamId=1`

### Simulation Settings

```json
{
  "simulation": {
    "num_simulations": 10000,      // Number of Monte Carlo simulations
    "use_gmm": true,               // Use Gaussian Mixture Models
    "cache_dir": ".cache",         // Directory for caching player models
    "cache_ttl_hours": 24          // Cache time-to-live in hours
  }
}
```

**Recommendations:**
- **10,000 simulations**: Fast, good accuracy (default)
- **50,000 simulations**: Slower, high accuracy
- **100,000 simulations**: Very slow, maximum accuracy

### Analysis Settings

```json
{
  "analysis": {
    "free_agents": {
      "fetch_size": 100,           // Number of FAs to fetch from ESPN
      "top_n_recommendations": 10, // Top N to show
      "positions_filter": null     // Filter by positions (e.g., ["RB", "WR"])
    },
    "trades": {
      "min_advantage": 3.0,        // Minimum point advantage for trade
      "max_trades_per_team": 2,    // Max suggestions per opponent
      "max_total_opportunities": 10 // Max total trade suggestions
    }
  }
}
```

### Output Settings

```json
{
  "output": {
    "report_directory": "reports",  // Where to save reports
    "include_timestamp": true,      // Add timestamp to filenames
    "format": "text"                // Report format (text, json, html)
  }
}
```

## Usage Examples

### Basic Usage (Public League)

**config.json:**
```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1,
    "year": 2024
  }
}
```

**Run:**
```bash
python fantasy_decision_maker.py --config config.json
```

### Private League with Cookies

**config.json:**
```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1,
    "year": 2024,
    "swid": "{12345-6789-ABCD-EF01-234567890ABC}",
    "espn_s2": "AEBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx%3D"
  }
}
```

**Run:**
```bash
python fantasy_decision_maker.py --config config.json
```

### High-Accuracy Simulations

**config.json:**
```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1
  },
  "simulation": {
    "num_simulations": 50000,
    "cache_dir": "/tmp/ff_cache"
  }
}
```

**Run:**
```bash
python fantasy_decision_maker.py --config config.json
```

### Generate Report Only

```bash
python fantasy_decision_maker.py --config config.json --report-only
```

## Overriding Config with CLI Arguments

CLI arguments **override** config file values:

```bash
# Use config but override simulations
python fantasy_decision_maker.py --config config.json --simulations 50000

# Use config but different team
python fantasy_decision_maker.py --config config.json --team-id 2

# Use config but different year
python fantasy_decision_maker.py --config config.json --year 2023
```

This is useful for:
- Testing different simulation counts
- Analyzing different teams in same league
- Looking at past seasons

## Multiple Configurations

You can maintain different config files for different scenarios:

```bash
# Different leagues
config.league1.json
config.league2.json

# Different analysis settings
config.quick.json      # 1,000 simulations for quick checks
config.accurate.json   # 50,000 simulations for important decisions

# Different years
config.2024.json
config.2023.json
```

**Usage:**
```bash
python fantasy_decision_maker.py --config config.league1.json
python fantasy_decision_maker.py --config config.quick.json
python fantasy_decision_maker.py --config config.2023.json
```

## Configuration for Weekly Workflow

### Setup Once

Create `config.json` with your league details:

```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1,
    "year": 2024,
    "swid": "{YOUR-SWID}",
    "espn_s2": "YOUR-ESPN-S2"
  },
  "simulation": {
    "num_simulations": 10000,
    "cache_dir": ".cache"
  }
}
```

### Use Weekly

```bash
# Monday morning: Generate report
python fantasy_decision_maker.py --config config.json --report-only

# Mid-week: Interactive analysis
python fantasy_decision_maker.py --config config.json
```

No need to remember league IDs, team IDs, or cookies!

## Security Best Practices

### Don't Commit Secrets

Add `config.json` to `.gitignore`:

```bash
echo "config.json" >> .gitignore
```

This prevents accidentally committing your ESPN cookies to version control.

### Use Template for Sharing

Share the template instead:
- ✅ Commit: `config.template.json` (no real values)
- ✅ Commit: `config.example.json` (example values)
- ❌ Don't commit: `config.json` (your actual credentials)

### Environment Variables (Advanced)

For extra security, you can use environment variables:

```bash
export ESPN_SWID="{YOUR-SWID}"
export ESPN_S2="YOUR-ESPN-S2"
```

Then in your config:
```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1,
    "swid": null,
    "espn_s2": null
  }
}
```

And pass them via CLI:
```bash
python fantasy_decision_maker.py \
  --config config.json \
  --swid "$ESPN_SWID" \
  --espn-s2 "$ESPN_S2"
```

## Troubleshooting

### "Config file not found"

**Problem:**
```
❌ Error: Config file not found: config.json
```

**Solution:**
- Check file exists: `ls config.json`
- Use absolute path: `--config /full/path/to/config.json`
- Check you're in the right directory

### "Invalid JSON in config file"

**Problem:**
```
❌ Error: Invalid JSON in config file: ...
```

**Solution:**
- Remove trailing commas (JSON doesn't allow them)
- Check quotes are balanced
- Use a JSON validator: https://jsonlint.com/
- Common issues:
  ```json
  // BAD - trailing comma
  {
    "league_id": 123,
    "team_id": 1,
  }

  // GOOD
  {
    "league_id": 123,
    "team_id": 1
  }
  ```

### "league-id is required"

**Problem:**
```
❌ Error: --league-id is required (or specify --config)
```

**Solution:**
- Make sure your config has `league_id` field
- Check spelling: `league_id` not `leagueId`
- Ensure config is valid JSON

### Config Not Loading

**Debug:**
```bash
# Check if config loads
python fantasy_decision_maker.py --config config.json

# Should see:
# 📄 Loaded config from: config.json
```

If you don't see this message, the config isn't loading.

## Sample Configurations

### Minimal Config (Public League)

```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1
  }
}
```

### Complete Config (Private League)

```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1,
    "year": 2024,
    "swid": "{12345-6789-ABCD-EF01-234567890ABC}",
    "espn_s2": "AEBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx%3D"
  },
  "simulation": {
    "num_simulations": 10000,
    "use_gmm": true,
    "cache_dir": ".cache",
    "cache_ttl_hours": 24
  },
  "analysis": {
    "free_agents": {
      "fetch_size": 100,
      "top_n_recommendations": 10,
      "positions_filter": null
    },
    "trades": {
      "min_advantage": 3.0,
      "max_trades_per_team": 2,
      "max_total_opportunities": 10
    }
  }
}
```

### Quick Analysis Config

```json
{
  "league": {
    "league_id": 123456,
    "team_id": 1
  },
  "simulation": {
    "num_simulations": 1000,
    "cache_dir": ".cache"
  }
}
```

## Benefits of Using Config Files

✅ **Convenience**: Set up once, use all season
✅ **No typing**: Don't remember league IDs every time
✅ **Security**: Keep credentials in one place
✅ **Version control**: Track changes to settings
✅ **Multiple leagues**: Easy to switch between leagues
✅ **Consistency**: Same settings every week

## Summary

```bash
# 1. Copy template
cp config.template.json config.json

# 2. Edit with your values
# Add league_id, team_id, and optionally swid/espn_s2

# 3. Run with config
python fantasy_decision_maker.py --config config.json

# 4. Done! Use weekly
```

Much easier than:
```bash
python fantasy_decision_maker.py \
  --league-id 123456 \
  --team-id 1 \
  --year 2024 \
  --swid "{12345-6789-ABCD-EF01-234567890ABC}" \
  --espn-s2 "AEBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx%3D" \
  --simulations 10000 \
  --cache-dir .cache
```

Enjoy your config files! 🏈

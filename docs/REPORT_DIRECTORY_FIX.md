# Report Directory Fix

## Problem
Weekly reports were being saved to the current working directory (`.`) instead of the `./reports/` directory.

## Solution
Updated `generate_weekly_report()` in `fantasy_decision_maker.py` to:

1. **Create reports directory if it doesn't exist**
   ```python
   import os
   reports_dir = "reports"
   os.makedirs(reports_dir, exist_ok=True)
   ```

2. **Save reports to the reports directory**
   ```python
   output_file = os.path.join(reports_dir, f"weekly_report_week{self.league.current_week}_{datetime.now().strftime('%Y%m%d')}.txt")
   ```

## Changes Made

### Files Modified
1. **fantasy_decision_maker.py** (line 279-287)
   - Added automatic creation of `./reports/` directory
   - Changed default output path from `.` to `./reports/`

2. **README.md** (line 144-150)
   - Updated documentation to specify reports are saved to `./reports/`
   - Added example of report filename format

### Files Already Configured
- **.gitignore** already includes `reports/` (no changes needed)

## Behavior

### Before
```bash
python fantasy_decision_maker.py --league-id XXX --team-id X --report-only
# Saved to: ./weekly_report_week12_20241128.txt  ❌
```

### After
```bash
python fantasy_decision_maker.py --league-id XXX --team-id X --report-only
# Saved to: ./reports/weekly_report_week12_20241128.txt  ✅
```

## Features
- ✅ Reports automatically saved to `./reports/` directory
- ✅ Directory is created automatically if it doesn't exist
- ✅ Reports are already in `.gitignore` (won't be committed)
- ✅ Full path displayed in success message
- ✅ Backward compatible - custom paths still work if provided

## Custom Output Path
You can still specify a custom path if needed:
```python
# In code
decision_maker.generate_weekly_report(output_file="/custom/path/report.txt")
```

## Directory Structure
```
espn-api/
├── fantasy_decision_maker.py
├── reports/                          ← NEW: Reports saved here
│   ├── weekly_report_week12_20241128.txt
│   ├── weekly_report_week13_20241205.txt
│   └── ...
├── .cache/                           ← Player model cache
│   └── player_*.pkl
└── config.json                       ← User config
```

All generated files are in `.gitignore` and won't clutter your repository!

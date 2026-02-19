# League Context

## Purpose

`league_context` builds a persistent, local ESPN data store for league-wide historical analysis.
It is optimized for behavior analytics (lineup churn, waiver style, volatility, trend drift).

## Default Scope

- Team scope: all league teams
- Year scope: last 3 seasons + current season
- Sync mode:
  - incremental by default
  - full refresh every 7+ days (or via explicit full-refresh flag)

## CLI

Build or update context:

```bash
uv run fantasy-decision-maker --config config.json --build-context
```

Force full rebuild:

```bash
uv run fantasy-decision-maker --config config.json --build-context --context-full-refresh
```

Choose year window:

```bash
uv run fantasy-decision-maker --config config.json --build-context \
  --context-start-year 2023 --context-end-year 2025
```

Write context sync summary:

```bash
uv run fantasy-decision-maker --config config.json --build-context \
  --context-output-summary-json reports/context_summary.json
```

Use context for historical backtest:

```bash
uv run fantasy-decision-maker --config config.json --historical-backtest --use-context
```

## Data Layout

Root:

`data/league_context/<league_id>/`

Artifacts:

- `context_manifest.json`
- `raw/<year>/league_snapshot.json`
- `raw/<year>/box_scores/week_<n>.json`
- `raw/<year>/activity/activity_offset_<k>.json`
- `tables/<year>/teams.parquet`
- `tables/<year>/weekly_team_scores.parquet`
- `tables/<year>/lineups.parquet`
- `tables/<year>/transactions.parquet`
- `tables/<year>/team_behavior_features.parquet`
- `derived/league_behavior_summary.json`
- `derived/team_reactivity_rankings.json`

## Manifest Fields

- `league_id`
- `seasons`
- `last_sync_utc`
- `sync_mode`
- `record_counts`
- `data_quality_flags`
- `schema_version`
- `endpoint_watermarks`

## Python API

```python
from alpha_sim_framework import build_league_context, load_league_context

result = build_league_context({
    "league_id": 1769126,
    "year": 2025,
    "swid": "...",
    "espn_s2": "...",
})

payload = load_league_context(result["context_root"])
print(payload["manifest"]["seasons"])
```

Historical backtest with context:

```python
from alpha_sim_framework import MonteCarloSimulator

backtest = simulator.run_historical_opponent_backtest({
    "league_id": 1769126,
    "team_id": 9,
    "year": 2025,
    "context_path": "data/league_context/1769126",
})
```

## Fallback Behavior

When `context_path` is provided:

- historical backtest tries local context first
- if context cannot be loaded, it records a warning and falls back to live ESPN loading

## Notes

- Parquet write requires a parquet engine (`pyarrow` recommended).
- If parquet write fails, table output falls back to JSON and a warning is recorded.

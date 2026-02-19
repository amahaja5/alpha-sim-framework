# Alpha Provider Guide

## CompositeSignalProvider

`CompositeSignalProvider` is the built-in multi-signal alpha generator with:

- 10 base signal families (residual, usage, injury, matchup, script, volatility, weather, sentiment, waiver value, schedule cluster)
- optional extended mode with 7 additional signals (`player_tilt_leverage`, `vegas_props`, `win_probability_script`, `backup_quality_adjustment`, `red_zone_opportunity`, `snap_count_percentage`, `line_movement`)
- static weighted blending
- per-signal clipping + total caps
- graceful degradation when external feeds fail
- diagnostics via `last_diagnostics` and `last_warnings`

Extended signals are gated by `enable_extended_signals` and default to `False`.

Module path for CLI loading:

- `alpha_sim_framework.providers:CompositeSignalProvider`

## Python Usage

```python
from alpha_sim_framework import CompositeSignalProvider, MonteCarloSimulator

provider = CompositeSignalProvider(
    enable_extended_signals=False,
    weights={
        "projection_residual": 0.2,
        "usage_trend": 0.12,
        "injury_opportunity": 0.14,
        "matchup_unit": 0.1,
        "game_script": 0.09,
        "volatility_aware": 0.08,
        "weather_venue": 0.07,
        "market_sentiment_contrarian": 0.07,
        "waiver_replacement_value": 0.06,
        "short_term_schedule_cluster": 0.07,
        "player_tilt_leverage": 0.08,
        "vegas_props": 0.10,
        "win_probability_script": 0.07,
        "backup_quality_adjustment": 0.04,
        "red_zone_opportunity": 0.05,
        "snap_count_percentage": 0.05,
        "line_movement": 0.04,
    },
    caps={
        "player_tilt_leverage": (-1.5, 1.5),
        "vegas_props": (-2.0, 2.0),
        "win_probability_script": (-1.75, 1.75),
        "backup_quality_adjustment": (-0.75, 0.75),
        "red_zone_opportunity": (-1.25, 1.25),
        "snap_count_percentage": (-1.0, 1.0),
        "line_movement": (-1.25, 1.25),
        "total_adjustment": (-6.0, 6.0),
        "matchup_multiplier": (0.85, 1.15),
    },
    runtime={
        "timeout_seconds": 2.0,
        "retries": 1,
        "cache_ttl_seconds": 300,
    },
    external_feeds={
        "enabled": True,
        "endpoints": {
            "weather": "https://example.com/weather",
            "market": "https://example.com/market",
            "odds": "https://example.com/odds",
            "injury_news": "https://example.com/injury",
            "nextgenstats": "https://example.com/nextgenstats",
        },
    },
)

sim = MonteCarloSimulator(league, num_simulations=5000, alpha_mode=True, provider=provider)
results = sim.run_simulations(explain=True)
```

## A/B CLI Usage

Using a template config:

```bash
uv run fantasy-decision-maker --ab-config config.ab.template.json --ab-eval
```

Or explicit provider flags:

```bash
uv run fantasy-decision-maker \
  --league-id 123456 --team-id 1 --year 2025 \
  --ab-eval \
  --ab-provider-class alpha_sim_framework.providers:CompositeSignalProvider \
  --ab-provider-kwargs '{"runtime":{"timeout_seconds":2.0}}'
```

## As-Of V2 Leakage Guard

`CompositeSignalProvider` supports backward as-of merge controls in runtime config:

- `as_of_utc`: exact ISO timestamp cutoff (UTC).
- `as_of_date`: date-only cutoff (`YYYY-MM-DD`) normalized to `00:00:00+00:00`.
- `as_of_snapshot_enabled`: enable persisted snapshot history.
- `as_of_snapshot_root`: snapshot storage root (default `data/feed_snapshots`).
- `as_of_mode`: currently `backward_publish_time` only.
- `as_of_missing_policy`: currently `degrade_warn` only.
- `as_of_publication_lag_seconds_by_feed`: per-feed publish delay.
- `as_of_max_staleness_seconds_by_feed`: per-feed stale threshold.
- `as_of_snapshot_retention_days`: retention window for snapshot pruning.

Validation rules:

- Setting both `as_of_utc` and `as_of_date` raises a `ValueError`.
- Invalid `as_of_date` format raises a `ValueError`.
- Unknown `as_of_mode` / `as_of_missing_policy` values raise a `ValueError`.
- Negative lag/staleness values raise a `ValueError`.

Snapshot path layout:

- `data/feed_snapshots/{league_id}/{year}/week_{week}/{feed_name}.jsonl`

## Feed Adapter Contract

Feed adapters return:

- `data`: normalized payload (dict)
- `source_timestamp`: ISO UTC timestamp
- `quality_flags`: list of quality indicators
- `warnings`: list of warning strings

Built-in adapters:

- `weather`
- `market`
- `odds`
- `injury_news`
- `nextgenstats`

If a feed is unavailable, the provider defaults that signal to neutral and continues.

### Optional extended feed keys

- `market.data.ownership_by_player`
- `odds.data.player_props_by_player`
- `odds.data.win_probability_by_team`
- `odds.data.live_game_state_by_team`
- `odds.data.opening_spread_by_team`
- `odds.data.closing_spread_by_team`
- `injury_news.data.backup_projection_ratio_by_player`
- `nextgenstats.data.player_metrics[*].red_zone_touch_share`
- `nextgenstats.data.player_metrics[*].red_zone_touch_trend`
- `nextgenstats.data.player_metrics[*].snap_share`
- `nextgenstats.data.player_metrics[*].snap_share_trend`

### `nextgenstats` canonical payload (expected)

```json
{
  "data": {
    "player_metrics": {
      "12345": {
        "usage_over_expected": 1.2,
        "route_participation": 0.78,
        "avg_separation": 2.1,
        "explosive_play_rate": 0.35,
        "volatility_index": 5.4,
        "red_zone_touch_share": 0.23,
        "red_zone_touch_trend": 0.04,
        "snap_share": 0.81,
        "snap_share_trend": 0.03
      }
    }
  },
  "source_timestamp": "2026-02-19T00:00:00+00:00",
  "quality_flags": ["live_fetch"],
  "warnings": []
}
```

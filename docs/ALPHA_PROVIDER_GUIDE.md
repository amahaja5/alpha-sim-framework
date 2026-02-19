# Alpha Provider Guide

## CompositeSignalProvider

`CompositeSignalProvider` is the built-in multi-signal alpha generator with:

- 10 signal families (residual, usage, injury, matchup, script, volatility, weather, sentiment, waiver value, schedule cluster)
- static weighted blending
- per-signal clipping + total caps
- graceful degradation when external feeds fail
- diagnostics via `last_diagnostics` and `last_warnings`

Module path for CLI loading:

- `alpha_sim_framework.providers:CompositeSignalProvider`

## Python Usage

```python
from alpha_sim_framework import CompositeSignalProvider, MonteCarloSimulator

provider = CompositeSignalProvider(
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
    },
    caps={
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
        "volatility_index": 5.4
      }
    }
  },
  "source_timestamp": "2026-02-19T00:00:00+00:00",
  "quality_flags": ["live_fetch"],
  "warnings": []
}
```

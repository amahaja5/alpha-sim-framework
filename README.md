# Alpha Sim Framework

Standalone NFL decision/simulation framework that integrates with `espn_api` league objects.

## What It Includes

- `AdvancedFantasySimulator` for matchup, trade, and free-agent analysis
- `MonteCarloSimulator` for season/playoff simulation plus alpha-mode workflows
- Alpha utility modules (`alpha_model`, `alpha_snapshot`, `alpha_backtest`, `alpha_provider`, `alpha_types`)
- Composite provider (`CompositeSignalProvider`) with 10-signal blend, feed adapters, and diagnostics
- League context pipeline (`league_context`) for persistent ESPN history + derived behavior analytics
- League adapter (`from_espn_league`) to convert live ESPN objects into a stable internal shape
- CLI entrypoint: `fantasy-decision-maker`

## Install

```bash
uv sync
```

## Quick Run

```bash
uv run fantasy-decision-maker --league-id <LEAGUE_ID> --team-id <TEAM_ID> --year <YEAR>
```

## Python Usage (Adapter + Simulator)

```python
from espn_api.football import League
from alpha_sim_framework import MonteCarloSimulator, from_espn_league

espn_league = League(league_id=123, year=2026, espn_s2="...", swid="...")
league_ctx = from_espn_league(espn_league)

sim = MonteCarloSimulator(league_ctx, num_simulations=2000, alpha_mode=True)
results = sim.run_simulations(explain=True)
```

## A/B With Composite Provider

```bash
uv run fantasy-decision-maker \
  --ab-config config.ab.template.json \
  --ab-eval
```

## Docs Index

- [Getting Started](docs/GETTING_STARTED.md)
- [League Context](docs/LEAGUE_CONTEXT.md)
- [Features](docs/FEATURES.md)
- [Alpha Provider Guide](docs/ALPHA_PROVIDER_GUIDE.md)
- [Testing](docs/TESTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)

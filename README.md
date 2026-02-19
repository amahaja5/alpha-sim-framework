# Alpha Sim Framework

Standalone extraction of the NFL decision/simulation utilities with `espn_api` as an external dependency.

## Includes

- `AdvancedFantasySimulator` (GMM + matchup/trade/free-agent analysis)
- `MonteCarloSimulator` (alpha mode, explainability, backtest)
- Alpha utility modules (`alpha_*`, provider, snapshot, contracts)
- `fantasy_decision_maker` CLI

## Install

```bash
pip install -e .
```

## Usage

```bash
fantasy-decision-maker --league-id <LEAGUE_ID> --team-id <TEAM_ID> --year 2024
```

This package expects league/team/player objects from `espn_api.football.League`.

## League Adapter Template

Use `from_espn_league` to freeze live ESPN objects into a stable `LeagueLike` shape:

```python
from espn_api.football import League
from alpha_sim_framework import MonteCarloSimulator, from_espn_league

espn_league = League(league_id=123, year=2026, espn_s2="...", swid="...")
league_ctx = from_espn_league(espn_league)

sim = MonteCarloSimulator(league_ctx, num_simulations=2000, alpha_mode=True)
results = sim.run_simulations(explain=True)
```

## Documentation Bundle

This repo now includes the copied documentation set:

- `/Users/amahajan/src/alpha-sim-framework/docs/`
- `/Users/amahajan/src/alpha-sim-framework/CHANGELOG.md`
- `/Users/amahajan/src/alpha-sim-framework/docs/README_espn_api.md`

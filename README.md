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

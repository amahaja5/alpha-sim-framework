# Architecture

## Package Layout

Core package path: `src/alpha_sim_framework/`

- `advanced_simulator.py`
  - `AdvancedFantasySimulator` for matchup/trade/free-agent workflows
- `monte_carlo.py`
  - `MonteCarloSimulator` for season/playoff simulation and alpha-mode APIs
- `alpha_model.py`
  - projection blending, uncertainty, and confidence logic
- `alpha_snapshot.py`
  - week snapshot extraction from league context
- `alpha_backtest.py`
  - backtest metric helpers (`run_backtest`)
- `alpha_provider.py`
  - provider wrappers (`NullSignalProvider`, `SafeSignalProvider`)
- `alpha_types.py`
  - `AlphaConfig`, `PlayerProjection`, provider protocol
- `league_adapter.py`
  - `from_espn_league` and adapter dataclasses
- `sim_contracts.py`
  - `LeagueLike` protocol contract

## Data Flow

1. Build or fetch a live ESPN league object (`espn_api.football.League`).
2. Convert via `from_espn_league(...)` into adapter-backed `LeagueLike` context.
3. Initialize simulator (`AdvancedFantasySimulator` or `MonteCarloSimulator`).
4. Execute analysis/simulation APIs.
5. Consume outputs in CLI or Python workflows.

## Interfaces and Contracts

- External dependency boundary:
  - `espn_api` provides live league/team/player objects.
- Internal simulator boundary:
  - `LeagueLike` protocol defines minimum shape required by simulators.
- Optional extension boundary:
  - external signals via provider protocol and safe wrappers.

External object details for `espn_api` types are documented in:

- [ESPN API Reference](ESPN_API_REFERENCE.md)

## CLI Entry

- Script mapping in `pyproject.toml`:
  - `fantasy-decision-maker = alpha_sim_framework.fantasy_decision_maker:main`
- Runtime CLI implementation:
  - `src/alpha_sim_framework/fantasy_decision_maker.py`

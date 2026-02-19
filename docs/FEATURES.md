# Features

## Simulators

### `AdvancedFantasySimulator`

Implemented in `src/alpha_sim_framework/advanced_simulator.py`.

Primary capabilities:
- Matchup simulation (`simulate_matchup`)
- Trade analysis (`analyze_trade`, `find_trade_opportunities`)
- Free-agent recommendation (`recommend_free_agents`)

### `MonteCarloSimulator`

Implemented in `src/alpha_sim_framework/monte_carlo.py`.

Primary capabilities:
- Season and playoff simulation (`simulate_season`, `simulate_playoffs`, `run_simulations`)
- Move optimization (`get_optimal_moves`)
- Draft strategy analysis (`analyze_draft_strategy`)
- Alpha APIs (`recommend_lineup`, `backtest_alpha`)
- League context APIs (`build_league_context`, `load_league_context`)

## Alpha Mode, Explainability, and Provider Hooks

- Alpha mode is opt-in through `MonteCarloSimulator(..., alpha_mode=True, alpha_config=..., provider=...)`.
- Explainability is available through:
  - `run_simulations(explain=True)`
  - `get_optimal_moves(..., explain=True)`
  - `recommend_lineup(..., explain=True)`
- External signal providers are supported through `alpha_provider` wrappers for safe fallback behavior.
- Built-in `CompositeSignalProvider` supports:
  - 10 signal families (projection residual, usage trend, injury opportunity, matchup unit, game script, volatility, weather, sentiment, waiver value, schedule cluster)
  - static weighted blending
  - strict clipping/cap controls
  - graceful external-feed fallback
  - per-player diagnostics (`last_diagnostics`) and warnings (`last_warnings`)

## Persistent League Context

- `league_context.py` provides:
  - local ESPN context build/sync
  - normalized yearly tables (teams, weekly scores, lineups, transactions)
  - derived behavior summaries and reactivity rankings
- Historical backtest can optionally consume local context (`context_path`) before live ESPN fallback.

## Gateway Discovery Toolkit

- Endpoint discovery docs and scorecard templates live under `docs/gateway/`.
- `gateway-probe` CLI (`src/alpha_sim_framework/gateway_probe.py`) can probe candidate endpoints and rank primary/backup choices by reliability + schema conformity.
- Feed contract validation utilities (`src/alpha_sim_framework/feed_contracts.py`) provide canonical schema checks for weather/market/odds/injury domains.

## League Adapter Usage

`from_espn_league(...)` (in `src/alpha_sim_framework/league_adapter.py`) converts a live `espn_api.football.League` object into the internal `LeagueLike` simulator context.

## Notable Changes

- Added alpha-layer modules and APIs for lineup recommendation and backtesting.
- Improved NFL schedule handling and deterministic simulation support.
- Added stronger test coverage around alpha model behavior and snapshot fallbacks.

## Limits and Non-Goals

- This package does not reimplement `espn_api`; it consumes `espn_api` objects.
- Historical deep-dive fix narratives were consolidated into this feature summary and `CHANGELOG.md`.
- No backward-compat documentation for old script-style commands is maintained.

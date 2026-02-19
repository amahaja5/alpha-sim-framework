# Changelog

## V2 - February 19, 2026

### Alpha Layer (NFL decision engine)
- Added opt-in alpha mode support to `MonteCarloSimulator` via constructor options:
  - `alpha_mode`
  - `alpha_config`
  - `provider`
- Added optional explainability output:
  - `run_simulations(explain=True)` includes `_meta` diagnostics
  - `get_optimal_moves(..., explain=True)` includes compact factor/context data
- Added new alpha-facing APIs:
  - `recommend_lineup(team_id, week=None, explain=False)`
  - `backtest_alpha(config=None)`
- Added alpha-driven lineup optimization and rating translation for simulation blending while preserving default behavior when `alpha_mode=False`.
- Added optional external signal adapter plumbing with safe provider fallback behavior.

### New utility modules
- Added `src/alpha_sim_framework/alpha_types.py`:
  - `AlphaConfig`
  - `PlayerProjection`
  - `ExternalSignalProvider`
- Added `src/alpha_sim_framework/alpha_provider.py` for null/safe provider wrappers.
- Added `src/alpha_sim_framework/alpha_snapshot.py` for week snapshot extraction with box-score and roster fallbacks.
- Added `src/alpha_sim_framework/alpha_model.py` for ESPN-first feature blending, uncertainty estimation, and confidence scoring.
- Added `src/alpha_sim_framework/alpha_backtest.py` for EV-delta and calibration-oriented backtest summaries.

### Tests
- Extended `tests/test_monte_carlo.py` with alpha API coverage:
  - explain metadata in simulation output
  - explainable move recommendations
  - lineup recommendation shape and week selection behavior
  - provider adjustment impact
  - alpha backtest return structure
- Added `tests/test_alpha_model.py` coverage for:
  - recent-form sensitivity
  - injury penalty effect
  - matchup directional behavior
- Added `tests/test_alpha_snapshot.py` coverage for:
  - box-score snapshot extraction
  - roster fallback behavior

### Notable changes
- Condensed historical deep-dive docs into core docs + changelog summaries for this standalone repository.

## V1 - February 18, 2026

### Monte Carlo simulator reliability pass (NFL-first)
- Reworked `MonteCarloSimulator` to support football schedule shape (`team.schedule` as opponents) and avoid runtime crashes from nonexistent matchup fields.
- Replaced broken schedule parsing with remaining-game extraction using week index and undecided outcomes.
- Added deterministic simulation support with optional `seed`.
- Added optional `ratings_blend` to combine observed in-season performance with preseason priors.
- Corrected projection field usage to align with available player model fields.
- Added safer team rating construction with variance floors and sparse-data fallback behavior.
- Removed dependency on missing internal methods in draft strategy analysis and implemented a working strategy simulation path.
- Fixed mutation bleed during strategy runs by deep-copying rating payloads.
- Hardened move recommendation logic to handle positions with no current starter.
- Maintained compatibility for:
  - `run_simulations()`
  - `simulate_season()`
  - `simulate_playoffs()`
  - `analyze_draft_strategy()`
  - `get_optimal_moves()`

### Tests
- Added baseline simulator coverage in `tests/test_monte_carlo.py` for:
  - remaining schedule extraction
  - output shape/range checks
  - seed reproducibility
  - draft-strategy result structure
  - missing-starter handling in move recommendations

### Project setup
- Added standalone package metadata in `pyproject.toml`.
- Synced environment and lockfile via `uv`, producing `uv.lock`.
- Updated `.gitignore` for local environment/editor cache artifacts.

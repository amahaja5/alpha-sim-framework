# Changelog

## V2 - February 19, 2026

### Alpha Layer (NFL decision engine)
- Added an opt-in alpha mode to `MonteCarloSimulator` with constructor support for:
  - `alpha_mode`
  - `alpha_config`
  - `provider`
- Added optional explainability output to simulation and move APIs:
  - `run_simulations(explain=True)` now includes `_meta` diagnostics
  - `get_optimal_moves(..., explain=True)` can include compact factors and confidence bands
- Added new alpha-facing methods:
  - `recommend_lineup(team_id, week=None, explain=False)`
  - `backtest_alpha(config=None)`
- Added alpha-driven lineup optimization and team-rating translation for simulation blending while preserving default behavior when `alpha_mode=False`.
- Added optional external signal adapter plumbing with safe-fallback behavior for provider failures.

### New utility modules
- Added `/Users/amahajan/src/espn-api/espn_api/utils/alpha_types.py` for:
  - `AlphaConfig`
  - `PlayerProjection`
  - `ExternalSignalProvider` protocol
- Added `/Users/amahajan/src/espn-api/espn_api/utils/alpha_provider.py` for null/safe provider wrappers.
- Added `/Users/amahajan/src/espn-api/espn_api/utils/alpha_snapshot.py` for week snapshot extraction with box-score and roster fallbacks.
- Added `/Users/amahajan/src/espn-api/espn_api/utils/alpha_model.py` for ESPN-first feature blending, uncertainty estimation, and confidence scoring.
- Added `/Users/amahajan/src/espn-api/espn_api/utils/alpha_backtest.py` for EV delta and calibration-oriented backtest summaries.

### Examples
- Updated `/Users/amahajan/src/espn-api/examples/season_strategy.py` with CLI flags:
  - `--alpha`
  - `--explain`
  - `--backtest`
- Added `/Users/amahajan/src/espn-api/examples/alpha_backtest.py` as a runnable alpha backtest example.

### Tests
- Extended `/Users/amahajan/src/espn-api/tests/football/unit/test_monte_carlo.py` with alpha API coverage:
  - explain metadata in simulation output
  - explainable move recommendations
  - lineup recommendation shape
  - provider adjustment impact
  - alpha backtest return structure
- Added `/Users/amahajan/src/espn-api/tests/football/unit/test_alpha_model.py` for:
  - recent-form sensitivity
  - injury penalty effect
  - matchup directional behavior
- Added `/Users/amahajan/src/espn-api/tests/football/unit/test_alpha_snapshot.py` for:
  - box-score snapshot extraction
  - roster fallback behavior

## V1 - February 18, 2026

### Monte Carlo Simulator (NFL-first reliability pass)
- Reworked `MonteCarloSimulator` to support football's real schedule shape (`team.schedule` as opponents) and avoid runtime crashes from nonexistent matchup fields.
- Replaced broken schedule parsing with remaining-game extraction using week index and undecided outcomes.
- Added deterministic simulation support with optional `seed`.
- Added optional `ratings_blend` to combine observed in-season performance with preseason priors.
- Fixed projection field usage to align with player models (`projected_total_points`, `projected_avg_points`, `avg_points`), replacing invalid field assumptions.
- Added safer team rating construction with score variance floors and fallback behavior when data is sparse.
- Removed dependency on missing internal methods in draft strategy analysis and implemented a working strategy simulation path.
- Fixed mutation bleed during strategy runs by using deep-copied rating payloads.
- Hardened move recommendation logic to handle positions with no current starter.
- Kept public method compatibility for:
  - `run_simulations()`
  - `simulate_season()`
  - `simulate_playoffs()`
  - `analyze_draft_strategy()`
  - `get_optimal_moves()`

### Tests
- Added `/Users/amahajan/src/espn-api/tests/football/unit/test_monte_carlo.py` covering:
  - remaining-schedule extraction
  - output shape/range checks
  - seed reproducibility
  - draft-strategy result structure
  - missing-starter handling in move recommendations

### Project and environment setup
- Updated `/Users/amahajan/src/espn-api/pyproject.toml` to include:
  - `[project]` metadata
  - `requires-python`
  - runtime dependencies (`requests`, `urllib3`, `numpy`, `pandas`)
  - dynamic version config from `espn_api._version.__version__`
- Synced environment with `uv`, producing `uv.lock`.
- Updated `.gitignore` to ignore local environment and macOS/editor cache artifacts:
  - `.venv/`
  - `.DS_Store`
  - `.pytest_cache/`
  - `.mypy_cache/`

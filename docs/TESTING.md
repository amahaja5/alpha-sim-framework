# Testing

## Test Files

Current test suite files:

- `tests/test_alpha_model.py`
- `tests/test_alpha_snapshot.py`
- `tests/test_monte_carlo.py`
- `tests/test_ab_evaluation.py`
- `tests/test_composite_alpha_provider.py`
- `tests/test_feed_contracts.py`
- `tests/test_gateway_probe.py`

## Run All Tests

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

## Run Individual Test Modules

```bash
uv run python -m unittest tests.test_alpha_model -v
uv run python -m unittest tests.test_alpha_snapshot -v
uv run python -m unittest tests.test_monte_carlo -v
uv run python -m unittest tests.test_feed_contracts -v
uv run python -m unittest tests.test_gateway_probe -v
```

## What Is Covered

- Alpha model behavior:
  - recent-form sensitivity
  - injury penalty effect
  - matchup directional behavior
- Snapshot extraction:
  - box-score path
  - roster fallback path
- Monte Carlo simulator:
  - output shape/ranges
  - seed reproducibility
  - schedule handling
  - move/draft APIs
  - alpha-mode methods
- Feed contracts and gateway probe:
  - canonical schema validation behavior
  - endpoint probe scoring/promotions
  - scorecard output generation

## Documentation Guard Check

Run the docs reference guard to catch stale pre-split references:

```bash
./scripts/check_docs_references.sh
```

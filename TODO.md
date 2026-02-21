# TODO

Consolidated modeling and product gaps backlog (updated 2026-02-21).

## Trade Modeling

- [ ] [P0] Replace rule-based trade acceptance heuristics with a learned acceptance model using league history.
- [ ] [P0] Add opponent-specific trade utility features (roster needs, standings pressure, positional scarcity, playoff schedule).
- [ ] [P0] Move from one-sided value delta to two-sided utility optimization (filter for deals that are acceptable to both teams and still +EV for us).
- [ ] [P1] Add package-level search constraints and realistic counter-offer simulation (1-for-1, 2-for-1, 2-for-2 with roster-balance rules).
- [ ] [P1] Add correlation-aware trade valuation (avoid over-concentrated weekly outcome risk unless intentional for upside).
- [ ] [P1] Add playoff-window weighted trade objective (weeks 14-17 weighted higher than regular weeks).
- [ ] [P2] Integrate manager behavior features (`reactivity_index`, transaction cadence, lineup churn) directly into trade partner targeting and acceptance prediction.

## Free Agency And Waivers

- [ ] [P0] Implement `WaiverAlphaScore` that combines mean EV, uncertainty, downside risk, opportunity shock, and acquisition cost.
- [ ] [P0] Add FAAB/waiver-priority bid recommendation model (bid-to-win probability, expected surplus by bid level).
- [ ] [P0] Add injury/opportunity shock features (starter-out impact, backup quality delta, depth chart promotions).
- [ ] [P1] Add weekly opponent-contest dynamics (block adds, deny opponent upgrades, streaming race effects).
- [ ] [P1] Add covariance-aware add/drop optimization (evaluate roster portfolio impact, not only individual deltas).
- [ ] [P1] Add schedule-window weighting for waiver decisions (next 1, 3, and 6 weeks with playoffs emphasis).
- [ ] [P2] Add explicit bench slot utility and optional roster expansion constraints in add/drop recommendations.

## Draft Strategy

- [ ] [P0] Build true snake draft simulation with pick-order dynamics, available-player set changes, and replacement-level cliffs.
- [ ] [P0] Add ADP and tier-drop modeling to capture positional runs and scarcity timing.
- [ ] [P1] Add uncertainty-aware draft optimization (mean-variance and upside/floor portfolio controls).
- [ ] [P1] Add playoff-week schedule weighting during draft value estimation.
- [ ] [P2] Replace coarse strategy presets (`Zero RB`, `RB Heavy`, `Balanced`) with policy search over round-by-round decision rules.

## Lineup Optimization

- [ ] [P0] Add portfolio lineup optimization with covariance terms (not just per-player risk-adjusted scores).
- [ ] [P1] Add matchup-context objective switching (protect floor when favored, maximize ceiling when underdog).
- [ ] [P1] Add late-news/late-swap aware re-optimization workflow.
- [ ] [P2] Generalize lineup slot templates from hardcoded defaults to per-league settings.

## Data Sources And Feed Quality

- [ ] [P0] Replace heuristic free-feed proxies for key domains with canonical, production-grade gateway feeds where possible.
- [ ] [P0] Upgrade odds ingestion to richer markets (player props, opening/closing lines, line movement by book) with robust normalization.
- [ ] [P0] Add robust ID crosswalks across ESPN/Sleeper/Odds/NextGen identifiers.
- [ ] [P1] Add richer injury/news source fusion (transactional statuses plus narrative news and expected return windows).
- [ ] [P1] Add venue/game-location resolution for weather accuracy and dome/open-air handling per game.
- [ ] [P1] Add source reliability scoring and per-feed confidence weights in alpha blending.
- [ ] [P2] Add social and expert sentiment ingestion pipeline as optional market-sentiment enrichment.

## Modeling And Evaluation

- [ ] [P0] Add probability calibration tracking for projections (reliability curves, Brier-style diagnostics, interval coverage).
- [ ] [P0] Add uncertainty backtests and decision-quality metrics (regret vs oracle, downside hit rate).
- [ ] [P1] Add signal ablation framework to quantify marginal value of each alpha component.
- [ ] [P1] Add stress tests for stale/missing feeds and controlled degradation performance.
- [ ] [P1] Add out-of-time validation slices with strict as-of publication-time guards and snapshot replay.
- [ ] [P2] Add simulation realism checks for transaction constraints and weekly operational timing.

## Explainability And Output Contracts

- [ ] [P0] Add `player_uncertainty_overrides` output (variance-level adjustments, not only mean shifts).
- [ ] [P0] Add per-player `confidence_scores` for downstream gating and risk control.
- [ ] [P1] Add `feature_attribution` output for transparent alpha contribution auditing.
- [ ] [P1] Add per-player `data_quality_flags` for stale/missing/low-quality feed inputs.
- [ ] [P2] Add decision trace artifacts for trade/waiver/lineup recommendation reproducibility.

## Product And Workflow

- [ ] [P1] Add automated weekly report that summarizes actionable adds, starts, and trade targets with confidence and risk bands.
- [ ] [P1] Add configuration profiles for league archetypes (redraft, keeper, dynasty, superflex, TE premium).
- [ ] [P2] Add policy toggles for manager style (aggressive upside, balanced, conservative floor) and map to objective weights.

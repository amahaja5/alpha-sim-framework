from typing import Any, Dict


def _team_projection_sum(players, projection_map):
    total = 0.0
    for player in players:
        pid = getattr(player, "playerId", getattr(player, "name", id(player)))
        proj = projection_map.get(pid)
        if proj:
            total += proj.weekly_mean
    return total


def run_backtest(simulator: Any, config: Dict = None) -> Dict[str, Any]:
    config = config or {}
    sample_weeks = max(1, int(config.get("sample_weeks", 3)))

    projections = simulator._get_alpha_projection_map()
    baseline_total = 0.0
    alpha_total = 0.0
    brier_terms = []

    for team in simulator.teams:
        baseline_lineup = simulator._current_lineup(team)
        alpha_lineup = simulator._optimize_lineup(team)

        baseline_pts = _team_projection_sum(baseline_lineup, projections)
        alpha_pts = _team_projection_sum(alpha_lineup, projections)

        baseline_total += baseline_pts
        alpha_total += alpha_pts

        denom = max(1.0, baseline_pts + alpha_pts)
        p_win = alpha_pts / denom
        pseudo_outcome = 1.0 if alpha_pts >= baseline_pts else 0.0
        brier_terms.append((p_win - pseudo_outcome) ** 2)

    per_week_delta = (alpha_total - baseline_total) / max(1, len(simulator.teams))
    ev_delta = per_week_delta * sample_weeks

    baseline_results = simulator.run_simulations(explain=False)
    alpha_results = simulator.run_simulations(explain=False, ratings=simulator._alpha_team_ratings_for_sim())

    champ_baseline = sum(v["championship_odds"] for v in baseline_results.values()) / max(1, len(baseline_results))
    champ_alpha = sum(v["championship_odds"] for v in alpha_results.values()) / max(1, len(alpha_results))

    return {
        "ev_delta": ev_delta,
        "weekly_points_delta": per_week_delta,
        "playoff_equity_delta": (
            sum(v["playoff_odds"] for v in alpha_results.values())
            - sum(v["playoff_odds"] for v in baseline_results.values())
        )
        / max(1, len(alpha_results)),
        "championship_equity_delta": champ_alpha - champ_baseline,
        "brier_score": sum(brier_terms) / max(1, len(brier_terms)),
        "sample_weeks": sample_weeks,
    }

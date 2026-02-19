import csv
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np

from .alpha_types import ABDecisionGateConfig, ABEvaluationConfig
from .historical_backtest import run_historical_backtest
from .monte_carlo import MonteCarloSimulator


AB_PROFILES: Dict[str, Dict[str, int]] = {
    "quick": {"simulations": 1200, "seeds": 3},
    "default": {"simulations": 5000, "seeds": 7},
    "deep": {"simulations": 12000, "seeds": 15},
}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_gate(raw: Optional[Dict[str, Any]]) -> ABDecisionGateConfig:
    raw = raw or {}
    gate = ABDecisionGateConfig()
    if "min_weekly_points_lift" in raw:
        gate.min_weekly_points_lift = float(raw["min_weekly_points_lift"])
    if "max_downside_probability" in raw:
        gate.max_downside_probability = float(raw["max_downside_probability"])
    if "min_successful_seeds" in raw:
        gate.min_successful_seeds = max(1, _safe_int(raw["min_successful_seeds"], gate.min_successful_seeds))
    return gate


def _parse_weeks(weeks: Any, current_week: int) -> List[int]:
    if weeks is None or str(weeks).strip().lower() == "auto":
        completed = max(0, int(current_week) - 1)
        if completed <= 0:
            return []
        start = max(1, completed - 3)
        return list(range(start, completed + 1))

    text = str(weeks).strip().lower()
    if "," in text:
        parsed = []
        for token in text.split(","):
            token = token.strip()
            if not token:
                continue
            parsed.append(max(1, int(token)))
        return sorted(set(parsed))

    if "-" in text:
        left, right = text.split("-", 1)
        start = max(1, int(left.strip()))
        end = max(start, int(right.strip()))
        return list(range(start, end + 1))

    return [max(1, int(text))]


def _git_sha() -> str:
    try:
        output = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return output.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.array(values, dtype=float), q))


def _metric_summary(name: str, values: List[float], downside_threshold: float = 0.0) -> Dict[str, Any]:
    if not values:
        return {
            "metric": name,
            "n": 0,
            "mean": 0.0,
            "median": 0.0,
            "std": 0.0,
            "p05": 0.0,
            "p95": 0.0,
            "downside_probability": 1.0,
        }

    arr = np.array(values, dtype=float)
    downside_prob = float(np.mean(arr < downside_threshold))
    return {
        "metric": name,
        "n": int(len(values)),
        "mean": float(np.mean(arr)),
        "median": float(median(values)),
        "std": float(np.std(arr, ddof=1)) if len(values) >= 2 else 0.0,
        "p05": _percentile(values, 5),
        "p95": _percentile(values, 95),
        "downside_probability": downside_prob,
    }


def _decision(summary: Dict[str, Any], successful_seeds: int, gate: ABDecisionGateConfig) -> Dict[str, Any]:
    reasons: List[str] = []

    if successful_seeds < gate.min_successful_seeds:
        reasons.append(
            f"Insufficient successful seeds ({successful_seeds}) < min_successful_seeds ({gate.min_successful_seeds})"
        )
        return {"status": "inconclusive", "reasons": reasons}

    mean_lift = float(summary.get("mean", 0.0))
    downside_prob = float(summary.get("downside_probability", 1.0))
    p05 = float(summary.get("p05", 0.0))
    p95 = float(summary.get("p95", 0.0))

    if mean_lift > gate.min_weekly_points_lift and downside_prob <= gate.max_downside_probability:
        reasons.append(
            f"Mean weekly points lift {mean_lift:.3f} > {gate.min_weekly_points_lift:.3f} and downside_probability {downside_prob:.3f} <= {gate.max_downside_probability:.3f}"
        )
        return {"status": "pass", "reasons": reasons}

    if p95 <= gate.min_weekly_points_lift or downside_prob > gate.max_downside_probability:
        reasons.append(
            f"Lift profile did not clear gate: p95={p95:.3f}, mean={mean_lift:.3f}, downside_probability={downside_prob:.3f}"
        )
        return {"status": "fail", "reasons": reasons}

    if p05 <= gate.min_weekly_points_lift <= p95:
        reasons.append(
            f"Confidence band overlaps threshold: p05={p05:.3f}, p95={p95:.3f}, threshold={gate.min_weekly_points_lift:.3f}"
        )
    else:
        reasons.append("Signal is mixed across seeds; additional data is required")

    return {"status": "inconclusive", "reasons": reasons}


def _resolve_config(config: Dict[str, Any]) -> ABEvaluationConfig:
    profile = str(config.get("profile", "default")).lower()
    profile_defaults = AB_PROFILES.get(profile, AB_PROFILES["default"])

    league = config.get("league", {})
    simulation = config.get("simulation", {})
    evaluation = config.get("evaluation", {})
    output = config.get("output", {})

    gate = _to_gate(config.get("gate"))

    payload = ABEvaluationConfig(
        league_id=_safe_int(config.get("league_id", league.get("league_id")), 0),
        team_id=_safe_int(config.get("team_id", league.get("team_id")), 0),
        year=_safe_int(config.get("year", league.get("year")), datetime.now().year),
        swid=config.get("swid", league.get("swid")),
        espn_s2=config.get("espn_s2", league.get("espn_s2")),
        profile=profile,
        simulations=max(1, _safe_int(config.get("simulations", simulation.get("simulations")), profile_defaults["simulations"])),
        seeds=max(1, _safe_int(config.get("seeds", simulation.get("seeds")), profile_defaults["seeds"])),
        weeks=str(config.get("weeks", evaluation.get("weeks", "auto"))),
        use_context=bool(config.get("use_context", evaluation.get("use_context", False))),
        context_path=config.get("context_path", evaluation.get("context_path")),
        lookback_seasons=max(1, _safe_int(config.get("lookback_seasons", evaluation.get("lookback_seasons")), 3)),
        start_year=config.get("start_year", evaluation.get("start_year")),
        end_year=config.get("end_year", evaluation.get("end_year")),
        include_playoffs=bool(config.get("include_playoffs", evaluation.get("include_playoffs", False))),
        alpha_config=dict(config.get("alpha_config", simulation.get("alpha_config", {})) or {}),
        output_dir=str(config.get("output_dir", output.get("output_dir", "reports/ab_runs"))),
        gate=gate,
    )

    if payload.league_id <= 0:
        raise ValueError("A/B evaluation requires a valid league_id")
    if payload.team_id <= 0:
        raise ValueError("A/B evaluation requires a valid team_id")

    if payload.context_path is None and payload.use_context:
        payload.context_path = str(Path("data/league_context") / str(payload.league_id))

    return payload


def _resolve_seed_list(seed_count: int) -> List[int]:
    return list(range(1, int(seed_count) + 1))


def _simulate_for_seed(league: Any, config: ABEvaluationConfig, seed: int, provider: Optional[Any] = None) -> Dict[str, Any]:
    baseline = MonteCarloSimulator(
        league=league,
        num_simulations=config.simulations,
        seed=seed,
        alpha_mode=False,
    )
    alpha = MonteCarloSimulator(
        league=league,
        num_simulations=config.simulations,
        seed=seed,
        alpha_mode=True,
        alpha_config=config.alpha_config,
        provider=provider,
    )

    baseline_results = baseline.run_simulations(explain=False)
    alpha_results = alpha.run_simulations(explain=False)

    baseline_team = baseline_results[int(config.team_id)]
    alpha_team = alpha_results[int(config.team_id)]

    alpha_backtest = alpha.backtest_alpha(config={"sample_weeks": max(1, len(_parse_weeks(config.weeks, getattr(league, "current_week", 1))))})

    return {
        "seed": seed,
        "weekly_points_lift": float(alpha_backtest.get("weekly_points_delta", 0.0)),
        "playoff_odds_lift": float(alpha_team.get("playoff_odds", 0.0) - baseline_team.get("playoff_odds", 0.0)),
        "championship_odds_lift": float(
            alpha_team.get("championship_odds", 0.0) - baseline_team.get("championship_odds", 0.0)
        ),
        "calibration_brier": float(alpha_backtest.get("brier_score", 0.0)),
        "status": "ok",
        "error": "",
    }


def _context_quality(config: ABEvaluationConfig, league: Any, warnings: List[str]) -> Dict[str, Any]:
    payload = {
        "context_requested": bool(config.use_context),
        "context_path": config.context_path,
        "context_used": False,
        "years_analyzed": [],
        "quality_flags": [],
        "warnings": [],
    }

    if not config.use_context:
        return payload

    runtime = {
        "league_id": config.league_id,
        "team_id": config.team_id,
        "year": config.year,
        "lookback_seasons": config.lookback_seasons,
        "start_year": config.start_year,
        "end_year": config.end_year,
        "include_playoffs": config.include_playoffs,
        "context_path": config.context_path,
    }

    try:
        result = run_historical_backtest(
            simulator=MonteCarloSimulator(league=league, num_simulations=10, seed=1, alpha_mode=False),
            config=runtime,
        )
        window = result.get("analysis_window", {})
        payload["years_analyzed"] = list(window.get("years_analyzed", []))
        payload["warnings"] = list(result.get("warnings", []))
        payload["context_used"] = not any("context_load_failed" in item for item in payload["warnings"])

        quality_flags = set()
        for report in result.get("opponents", []):
            confidence = report.get("confidence", {})
            for flag in confidence.get("data_quality_flags", []):
                quality_flags.add(flag)
        payload["quality_flags"] = sorted(quality_flags)

        if not payload["context_used"]:
            warnings.append("Requested context, but loader failed and ESPN fallback was used")
    except Exception as exc:
        warnings.append(f"Context quality check failed: {exc}")

    return payload


def _write_outputs(
    root: Path,
    run_manifest: Dict[str, Any],
    per_seed: List[Dict[str, Any]],
    summary: Dict[str, Any],
    decision: Dict[str, Any],
    warnings: List[str],
) -> None:
    root.mkdir(parents=True, exist_ok=False)

    (root / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, sort_keys=True))
    (root / "metrics_summary.json").write_text(
        json.dumps({"summary": summary, "decision": decision}, indent=2, sort_keys=True)
    )
    (root / "warnings.json").write_text(json.dumps({"warnings": warnings}, indent=2, sort_keys=True))

    with open(root / "metrics_per_seed.csv", "w", newline="") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=[
                "seed",
                "weekly_points_lift",
                "playoff_odds_lift",
                "championship_odds_lift",
                "calibration_brier",
                "status",
                "error",
            ],
        )
        writer.writeheader()
        for row in per_seed:
            writer.writerow(row)

    primary = summary.get("weekly_points_lift", {})
    report = [
        "# Alpha A/B Decision Report",
        "",
        f"- Status: **{decision.get('status', 'inconclusive')}**",
        f"- Mean weekly points lift: `{primary.get('mean', 0.0):.4f}`",
        f"- 90% empirical interval (p05, p95): `({primary.get('p05', 0.0):.4f}, {primary.get('p95', 0.0):.4f})`",
        f"- Downside probability P(lift < 0): `{primary.get('downside_probability', 1.0):.4f}`",
        "",
        "## Rationale",
    ]
    for reason in decision.get("reasons", []):
        report.append(f"- {reason}")

    if warnings:
        report.extend(["", "## Warnings"])
        for item in warnings:
            report.append(f"- {item}")

    (root / "decision_report.md").write_text("\n".join(report) + "\n")


def run_ab_evaluation(
    config: Dict[str, Any],
    *,
    league: Optional[Any] = None,
    league_loader: Optional[Any] = None,
    provider: Optional[Any] = None,
) -> Dict[str, Any]:
    resolved = _resolve_config(config)
    warnings: List[str] = []

    if league is None:
        if league_loader is not None:
            league = league_loader(resolved.year)
        else:
            from espn_api.football import League

            league = League(
                league_id=resolved.league_id,
                year=resolved.year,
                swid=resolved.swid,
                espn_s2=resolved.espn_s2,
            )

    week_window = _parse_weeks(resolved.weeks, getattr(league, "current_week", 1))
    if not week_window:
        warnings.append("No completed weeks in scope; using sample_weeks=1 for alpha backtest")

    context_quality = _context_quality(resolved, league, warnings)

    seeds = _resolve_seed_list(resolved.seeds)
    per_seed: List[Dict[str, Any]] = []
    for seed in seeds:
        try:
            per_seed.append(_simulate_for_seed(league, resolved, seed, provider=provider))
        except Exception as exc:
            per_seed.append(
                {
                    "seed": seed,
                    "weekly_points_lift": 0.0,
                    "playoff_odds_lift": 0.0,
                    "championship_odds_lift": 0.0,
                    "calibration_brier": 0.0,
                    "status": "error",
                    "error": str(exc),
                }
            )
            warnings.append(f"Seed {seed} failed: {exc}")

    ok_rows = [row for row in per_seed if row.get("status") == "ok"]

    weekly_values = [float(row["weekly_points_lift"]) for row in ok_rows]
    playoff_values = [float(row["playoff_odds_lift"]) for row in ok_rows]
    champ_values = [float(row["championship_odds_lift"]) for row in ok_rows]
    brier_values = [float(row["calibration_brier"]) for row in ok_rows]

    summary = {
        "weekly_points_lift": _metric_summary("weekly_points_lift", weekly_values, downside_threshold=0.0),
        "playoff_odds_lift": _metric_summary("playoff_odds_lift", playoff_values, downside_threshold=0.0),
        "championship_odds_lift": _metric_summary("championship_odds_lift", champ_values, downside_threshold=0.0),
        "calibration_brier": _metric_summary("calibration_brier", brier_values, downside_threshold=0.0),
        "seed_success_rate": float(len(ok_rows) / max(1, len(seeds))),
    }

    decision = _decision(summary["weekly_points_lift"], len(ok_rows), resolved.gate)

    timestamp = datetime.now(timezone.utc)
    run_id = f"ab_{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    config_payload = asdict(resolved)
    config_hash = hashlib.sha256(json.dumps(config_payload, sort_keys=True).encode("utf-8")).hexdigest()

    run_manifest = {
        "run_id": run_id,
        "timestamp_utc": timestamp.isoformat(),
        "git_sha": _git_sha(),
        "config_hash": config_hash,
        "effective_config": config_payload,
        "profile_defaults": AB_PROFILES.get(resolved.profile, AB_PROFILES["default"]),
        "seeds": seeds,
        "week_window": week_window,
        "context_quality": context_quality,
    }

    output_root = Path(resolved.output_dir) / run_id
    _write_outputs(output_root, run_manifest, per_seed, summary, decision, warnings)

    return {
        "run_id": run_id,
        "output_dir": str(output_root),
        "run_manifest": run_manifest,
        "metrics_per_seed": per_seed,
        "metrics_summary": summary,
        "decision": decision,
        "warnings": warnings,
    }


def resolve_ab_config(base_config: Optional[Dict[str, Any]], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base_config or {})
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        merged[key] = value
    return merged

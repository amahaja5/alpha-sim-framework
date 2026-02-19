import argparse
import json
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .feed_contracts import validate_canonical_feed


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _extract_dot_path(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for token in str(path or "").split("."):
        if not token:
            continue
        if isinstance(current, dict) and token in current:
            current = current[token]
        else:
            return None
    return current


def _attempt_request(candidate: Dict[str, Any], context: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    base_url = str(candidate.get("url", "")).strip()
    if not base_url:
        return {
            "ok": False,
            "latency_ms": 0.0,
            "status_code": None,
            "response_bytes": 0,
            "json": {},
            "error": "missing_url",
            "schema_ok": False,
            "schema_errors": ["missing_url"],
            "refresh_lag_seconds": None,
        }

    params = dict(candidate.get("params", {}) or {})
    params.setdefault("league_id", context.get("league_id"))
    params.setdefault("year", context.get("year"))
    params.setdefault("week", context.get("week"))

    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    full_url = f"{base_url}{'&' if '?' in base_url else '?'}{query}" if query else base_url

    headers = dict(candidate.get("headers", {}) or {})
    started = datetime.now(timezone.utc)
    status_code = None
    body_bytes = b""
    parsed: Dict[str, Any] = {}
    error = ""

    try:
        request = urllib.request.Request(full_url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", None)
            body_bytes = response.read()
        parsed_obj = json.loads(body_bytes.decode("utf-8"))
        parsed = parsed_obj if isinstance(parsed_obj, dict) else {"value": parsed_obj}
    except Exception as exc:
        error = str(exc)

    finished = datetime.now(timezone.utc)
    latency_ms = (finished - started).total_seconds() * 1000.0

    schema_errors: List[str] = []
    schema_ok = False
    canonical_domain = str(candidate.get("canonical_domain", "")).strip()
    if parsed and canonical_domain:
        schema_errors = validate_canonical_feed(canonical_domain, parsed)
        schema_ok = len(schema_errors) == 0
    elif parsed:
        required_paths = list(candidate.get("required_paths", []) or [])
        path_errors = []
        for path in required_paths:
            if _extract_dot_path(parsed, path) is None:
                path_errors.append(f"missing_path:{path}")
        schema_errors = path_errors
        schema_ok = len(path_errors) == 0

    refresh_lag_seconds = None
    freshness_path = str(candidate.get("freshness_path", "")).strip()
    if freshness_path and parsed:
        stamp = _extract_dot_path(parsed, freshness_path)
        if isinstance(stamp, (int, float)):
            refresh_lag_seconds = max(0.0, datetime.now(timezone.utc).timestamp() - float(stamp))
        elif isinstance(stamp, str) and stamp:
            try:
                dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                refresh_lag_seconds = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
            except Exception:
                schema_errors.append("invalid_freshness_timestamp")

    ok = error == "" and status_code is not None and int(status_code) < 400 and bool(parsed)
    return {
        "ok": ok,
        "latency_ms": latency_ms,
        "status_code": status_code,
        "response_bytes": len(body_bytes),
        "json": parsed,
        "error": error,
        "schema_ok": schema_ok,
        "schema_errors": schema_errors,
        "refresh_lag_seconds": refresh_lag_seconds,
    }


def _summarize_attempts(domain: str, candidate_name: str, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    successes = [a for a in attempts if a.get("ok")]
    latencies = [float(a.get("latency_ms", 0.0)) for a in attempts if a.get("latency_ms") is not None]
    sizes = [int(a.get("response_bytes", 0)) for a in attempts if a.get("response_bytes") is not None]
    schema_hits = [a for a in attempts if a.get("schema_ok")]
    lag_values = [float(a.get("refresh_lag_seconds")) for a in attempts if isinstance(a.get("refresh_lag_seconds"), (int, float))]

    return {
        "domain": domain,
        "candidate": candidate_name,
        "attempts": len(attempts),
        "success_rate": (len(successes) / max(1, len(attempts))) * 100.0,
        "median_latency_ms": statistics.median(latencies) if latencies else None,
        "median_response_bytes": statistics.median(sizes) if sizes else None,
        "schema_conformity_rate": (len(schema_hits) / max(1, len(attempts))) * 100.0,
        "refresh_lag_seconds_median": statistics.median(lag_values) if lag_values else None,
        "errors": [a.get("error") for a in attempts if a.get("error")],
        "schema_errors": [err for a in attempts for err in a.get("schema_errors", [])],
    }


def _score(summary: Dict[str, Any]) -> float:
    success = _safe_float(summary.get("success_rate"), 0.0)
    schema = _safe_float(summary.get("schema_conformity_rate"), 0.0)
    latency = _safe_float(summary.get("median_latency_ms"), 99999.0)
    latency_component = max(0.0, 100.0 - min(100.0, latency / 10.0))
    return (0.45 * success) + (0.40 * schema) + (0.15 * latency_component)


def run_gateway_probe(config: Dict[str, Any]) -> Dict[str, Any]:
    context = dict(config.get("context", {}) or {})
    context.setdefault("league_id", None)
    context.setdefault("year", None)
    context.setdefault("week", None)

    runtime = dict(config.get("runtime", {}) or {})
    default_attempts = max(1, _safe_int(runtime.get("attempts", 3), 3))
    timeout_seconds = max(0.2, _safe_float(runtime.get("timeout_seconds", 3.0), 3.0))

    domains = dict(config.get("domains", {}) or {})
    candidate_results: List[Dict[str, Any]] = []

    for domain, domain_cfg in domains.items():
        candidates = list((domain_cfg or {}).get("candidates", []) or [])
        for candidate in candidates:
            name = str(candidate.get("name", candidate.get("url", "unknown")))
            attempts = max(1, _safe_int(candidate.get("attempts", default_attempts), default_attempts))
            trial_rows = []
            for _ in range(attempts):
                trial_rows.append(_attempt_request(candidate, context, timeout=timeout_seconds))
            summary = _summarize_attempts(domain=domain, candidate_name=name, attempts=trial_rows)
            summary["score"] = _score(summary)
            summary["metadata"] = {
                "url": candidate.get("url"),
                "notes": candidate.get("notes", ""),
                "auth": candidate.get("auth", ""),
                "cost": candidate.get("cost", ""),
                "update_cadence": candidate.get("update_cadence", ""),
            }
            candidate_results.append(summary)

    by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for row in candidate_results:
        by_domain.setdefault(row["domain"], []).append(row)

    promotions = {}
    for domain, rows in by_domain.items():
        ranked = sorted(rows, key=lambda r: (r["score"], r["success_rate"], r["schema_conformity_rate"]), reverse=True)
        promotions[domain] = {
            "primary": ranked[0] if ranked else None,
            "backup": ranked[1] if len(ranked) > 1 else None,
            "ranked": ranked,
        }

    return {
        "generated_at_utc": _now_utc(),
        "context": context,
        "runtime": {
            "attempts": default_attempts,
            "timeout_seconds": timeout_seconds,
        },
        "candidate_results": candidate_results,
        "promotions": promotions,
    }


def _markdown_report(payload: Dict[str, Any]) -> str:
    lines = [
        "# Gateway Endpoint Probe Scorecard",
        "",
        f"Generated: {payload.get('generated_at_utc')}",
        "",
        "## Promotions",
    ]

    promotions = payload.get("promotions", {}) or {}
    for domain, entry in promotions.items():
        primary = (entry or {}).get("primary")
        backup = (entry or {}).get("backup")
        lines.append(f"- `{domain}`")
        lines.append(f"  - primary: `{(primary or {}).get('candidate', 'n/a')}`")
        lines.append(f"  - backup: `{(backup or {}).get('candidate', 'n/a')}`")

    lines.extend(["", "## Candidate Metrics", "", "| Domain | Candidate | Success % | Schema % | Median Latency (ms) | Median Size (bytes) | Score |", "|---|---:|---:|---:|---:|---:|---:|"])

    for row in payload.get("candidate_results", []):
        lines.append(
            "| {domain} | {candidate} | {success:.1f} | {schema:.1f} | {latency} | {size} | {score:.2f} |".format(
                domain=row.get("domain", ""),
                candidate=row.get("candidate", ""),
                success=_safe_float(row.get("success_rate"), 0.0),
                schema=_safe_float(row.get("schema_conformity_rate"), 0.0),
                latency="n/a" if row.get("median_latency_ms") is None else f"{_safe_float(row.get('median_latency_ms')):.1f}",
                size="n/a" if row.get("median_response_bytes") is None else int(_safe_float(row.get("median_response_bytes"), 0.0)),
                score=_safe_float(row.get("score"), 0.0),
            )
        )

    lines.extend(["", "## Notes", "- Success and schema conformity are measured across repeated probe attempts.", "- Promote primary + backup per domain based on score and reliability."])
    return "\n".join(lines) + "\n"


def write_probe_outputs(payload: Dict[str, Any], output_dir: str) -> Dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    json_path = root / "gateway_probe_scorecard.json"
    md_path = root / "gateway_probe_scorecard.md"

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    md_path.write_text(_markdown_report(payload))

    return {
        "json": str(json_path),
        "markdown": str(md_path),
    }


def load_probe_config(path: str) -> Dict[str, Any]:
    with open(path, "r") as file_obj:
        return json.load(file_obj)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Probe candidate gateway endpoints and rank primaries/backups.")
    parser.add_argument("--config", required=True, help="Path to gateway probe config JSON")
    parser.add_argument("--output-dir", default="reports/gateway_probe", help="Output directory for scorecard files")
    args = parser.parse_args(argv)

    config = load_probe_config(args.config)
    payload = run_gateway_probe(config)
    outputs = write_probe_outputs(payload, args.output_dir)

    print(f"Probe JSON: {outputs['json']}")
    print(f"Probe Markdown: {outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SNAPSHOT_SCHEMA_VERSION = "1.0"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def snapshot_path(
    *,
    root: str,
    league_id: int,
    year: int,
    week: int,
    feed_name: str,
) -> Path:
    return (
        Path(root)
        / str(int(league_id))
        / str(int(year))
        / f"week_{int(week)}"
        / f"{str(feed_name).strip().lower()}.jsonl"
    )


def load_snapshot_records(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not path.exists():
        return [], []

    records: List[Dict[str, Any]] = []
    warnings: List[str] = []

    try:
        lines = path.read_text().splitlines()
    except Exception as exc:
        return [], [f"snapshot_read_failed:{path}:{exc}"]

    for line_number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except Exception:
            warnings.append(f"snapshot_malformed_line:{path}:{line_number}")
            continue
        if not isinstance(parsed, dict):
            warnings.append(f"snapshot_invalid_record_type:{path}:{line_number}")
            continue
        records.append(parsed)

    return records, warnings


def append_snapshot_record(
    *,
    path: Path,
    record: Dict[str, Any],
    retention_days: int,
) -> List[str]:
    warnings: List[str] = []
    try:
        existing, load_warnings = load_snapshot_records(path)
        warnings.extend(load_warnings)
        all_records = list(existing) + [dict(record)]

        cutoff = _utc_now() - timedelta(days=max(0, int(retention_days)))
        retained: List[Dict[str, Any]] = []
        for row in all_records:
            observed = _parse_iso_utc(row.get("observed_at_utc"))
            if observed is None:
                warnings.append(f"snapshot_observed_at_invalid:{path}")
                retained.append(row)
                continue
            if observed >= cutoff:
                retained.append(row)

        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as file_obj:
            for row in retained:
                file_obj.write(json.dumps(row, sort_keys=True))
                file_obj.write("\n")
        temp.replace(path)
        return warnings
    except Exception as exc:
        warnings.append(f"snapshot_append_failed:{path}:{exc}")
        return warnings


def make_snapshot_record(
    *,
    league_id: int,
    year: int,
    week: int,
    feed_name: str,
    source_timestamp: str,
    availability_timestamp: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "observed_at_utc": _utc_now_iso(),
        "league_id": int(league_id),
        "year": int(year),
        "week": int(week),
        "feed_name": str(feed_name).strip().lower(),
        "source_timestamp": str(source_timestamp or ""),
        "availability_timestamp": str(availability_timestamp or ""),
        "payload": dict(payload or {}),
    }

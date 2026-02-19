import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase

from alpha_sim_framework.providers.feeds.snapshot_store import (
    append_snapshot_record,
    load_snapshot_records,
    make_snapshot_record,
    snapshot_path,
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class SnapshotStoreTest(TestCase):
    def test_snapshot_path_layout(self):
        path = snapshot_path(
            root="data/feed_snapshots",
            league_id=999,
            year=2025,
            week=3,
            feed_name="market",
        )
        self.assertEqual(str(path), "data/feed_snapshots/999/2025/week_3/market.jsonl")

    def test_append_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "999/2025/week_3/market.jsonl"
            record = make_snapshot_record(
                league_id=999,
                year=2025,
                week=3,
                feed_name="market",
                source_timestamp="2025-10-01T10:00:00+00:00",
                availability_timestamp="2025-10-01T12:00:00+00:00",
                payload={
                    "data": {"projections": {"101": 19.0}, "usage_trend": {}, "sentiment": {}, "future_schedule_strength": {}},
                    "source_timestamp": "2025-10-01T10:00:00+00:00",
                    "quality_flags": ["live_fetch"],
                    "warnings": [],
                },
            )
            warnings = append_snapshot_record(path=path, record=record, retention_days=365)
            self.assertEqual(warnings, [])

            rows, load_warnings = load_snapshot_records(path)
            self.assertEqual(load_warnings, [])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["feed_name"], "market")
            self.assertEqual(rows[0]["payload"]["data"]["projections"]["101"], 19.0)

    def test_prune_old_records_during_append(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "999/2025/week_3/market.jsonl"
            old_dt = datetime.now(timezone.utc) - timedelta(days=5)
            fresh_dt = datetime.now(timezone.utc)
            old_record = {
                "schema_version": "1.0",
                "observed_at_utc": _iso(old_dt),
                "league_id": 999,
                "year": 2025,
                "week": 3,
                "feed_name": "market",
                "source_timestamp": "2025-10-01T10:00:00+00:00",
                "availability_timestamp": "2025-10-01T12:00:00+00:00",
                "payload": {},
            }
            fresh_record = {
                "schema_version": "1.0",
                "observed_at_utc": _iso(fresh_dt),
                "league_id": 999,
                "year": 2025,
                "week": 3,
                "feed_name": "market",
                "source_timestamp": "2025-10-01T11:00:00+00:00",
                "availability_timestamp": "2025-10-01T13:00:00+00:00",
                "payload": {},
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as file_obj:
                file_obj.write(json.dumps(old_record) + "\n")

            warnings = append_snapshot_record(path=path, record=fresh_record, retention_days=1)
            self.assertEqual(warnings, [])

            rows, _ = load_snapshot_records(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_timestamp"], "2025-10-01T11:00:00+00:00")

    def test_load_tolerates_malformed_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "999/2025/week_3/market.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as file_obj:
                file_obj.write("{bad json}\n")
                file_obj.write(json.dumps({"ok": True}) + "\n")

            rows, warnings = load_snapshot_records(path)
            self.assertEqual(len(rows), 1)
            self.assertTrue(any("snapshot_malformed_line" in warning for warning in warnings))

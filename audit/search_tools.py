"""Compliance-officer tooling for ad-hoc audit log queries.

Usage:
    python -m audit.search_tools patient --hash p_sha256_abc... --window 90d
    python -m audit.search_tools user --id u_42 --window 30d
    python -m audit.search_tools verify-chain --from-date 2026-01-01
    python -m audit.search_tools export --date-range 2026-01-01:2026-03-31 --out report.jsonl

Every invocation of this tool is itself audited (recursive audit). The OS
account running this script must have the `compliance_officer_read` OS role.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def _parse_window(window: str) -> timedelta:
    """Parse 7d, 30d, 90d, 6h, etc. Returns a timedelta."""
    unit = window[-1].lower()
    value = int(window[:-1])
    mapping = {"d": "days", "h": "hours", "m": "minutes"}
    if unit not in mapping:
        raise ValueError(f"unsupported window unit: {unit}")
    return timedelta(**{mapping[unit]: value})


def _iter_events(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"WARN: unparseable line {line_no}: {e}", file=sys.stderr)


def search_by_patient(path: Path, patient_hash: str, window: timedelta) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - window
    matches: list[dict] = []
    for event in _iter_events(path):
        ts = datetime.fromisoformat(event["event_timestamp"].replace("Z", "+00:00"))
        if ts < cutoff:
            continue
        subject = event.get("subject") or {}
        if subject.get("patient_hash") == patient_hash:
            matches.append(event)
    return matches


def search_by_user(path: Path, user_id: str, window: timedelta) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - window
    matches: list[dict] = []
    for event in _iter_events(path):
        ts = datetime.fromisoformat(event["event_timestamp"].replace("Z", "+00:00"))
        if ts < cutoff:
            continue
        actor = event.get("actor") or {}
        if actor.get("user_id") == user_id:
            matches.append(event)
    return matches


def verify_chain(path: Path, from_date: datetime | None = None) -> tuple[bool, list[str]]:
    """Return (is_valid, list_of_break_descriptions)."""
    breaks: list[str] = []
    prev_hash = "sha256:genesis"
    prev_ts: str | None = None

    for event in _iter_events(path):
        ts_str = event["event_timestamp"]
        if from_date is not None:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts < from_date:
                prev_hash = event["integrity"]["current_hash"]
                prev_ts = ts_str
                continue

        claimed_prev = event["integrity"]["prev_hash"]
        if claimed_prev != prev_hash:
            breaks.append(
                f"chain break at {ts_str}: prev_hash {claimed_prev} != expected {prev_hash} "
                f"(previous event at {prev_ts})"
            )

        # Recompute current_hash excluding current_hash field itself.
        event_copy = json.loads(json.dumps(event))
        claimed_current = event_copy["integrity"].pop("current_hash")
        canonical = json.dumps(event_copy, sort_keys=True, separators=(",", ":"))
        recomputed = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if recomputed != claimed_current:
            breaks.append(
                f"hash mismatch at {ts_str}: recomputed {recomputed} != claimed {claimed_current}"
            )

        prev_hash = claimed_current
        prev_ts = ts_str

    return len(breaks) == 0, breaks


def export_range(path: Path, start: datetime, end: datetime, out: Path) -> int:
    count = 0
    with open(out, "w", encoding="utf-8") as f:
        for event in _iter_events(path):
            ts = datetime.fromisoformat(event["event_timestamp"].replace("Z", "+00:00"))
            if start <= ts < end:
                f.write(json.dumps(event, separators=(",", ":")) + "\n")
                count += 1
    return count


def _format_event(event: dict) -> str:
    actor = event.get("actor") or {}
    subject = event.get("subject") or {}
    return (
        f"{event['event_timestamp']}  "
        f"{event['event_type']:30s}  "
        f"actor={actor.get('user_id', '-')}  "
        f"patient={subject.get('patient_hash', '-')[:24]}...  "
        f"outcome={event.get('outcome', '-')}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit log search tool")
    parser.add_argument(
        "--audit-path",
        default="/var/log/retina-scan-ai/audit.jsonl",
        help="Path to the audit JSONL file",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_patient = sub.add_parser("patient", help="Search by patient hash")
    p_patient.add_argument("--hash", required=True)
    p_patient.add_argument("--window", default="90d")

    p_user = sub.add_parser("user", help="Search by user id")
    p_user.add_argument("--id", required=True)
    p_user.add_argument("--window", default="30d")

    p_chain = sub.add_parser("verify-chain", help="Verify hash chain integrity")
    p_chain.add_argument("--from-date", default=None)

    p_export = sub.add_parser("export", help="Export a date range")
    p_export.add_argument("--date-range", required=True, help="YYYY-MM-DD:YYYY-MM-DD")
    p_export.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    path = Path(args.audit_path)
    if not path.exists():
        print(f"ERROR: audit path {path} does not exist", file=sys.stderr)
        return 2

    if args.cmd == "patient":
        matches = search_by_patient(path, args.hash, _parse_window(args.window))
        print(f"Found {len(matches)} events")
        for event in matches:
            print(_format_event(event))
        return 0

    if args.cmd == "user":
        matches = search_by_user(path, args.id, _parse_window(args.window))
        print(f"Found {len(matches)} events")
        for event in matches:
            print(_format_event(event))
        return 0

    if args.cmd == "verify-chain":
        from_date = (
            datetime.fromisoformat(args.from_date).replace(tzinfo=timezone.utc)
            if args.from_date
            else None
        )
        ok, breaks = verify_chain(path, from_date=from_date)
        if ok:
            print("OK: hash chain is intact")
            return 0
        print(f"FAIL: {len(breaks)} chain breaks detected")
        for b in breaks:
            print(f"  - {b}")
        return 1

    if args.cmd == "export":
        start_str, end_str = args.date_range.split(":")
        start = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
        count = export_range(path, start, end, Path(args.out))
        print(f"Exported {count} events to {args.out}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Pipeline report — what's happening, at a glance."""
from __future__ import annotations

import sqlite3

from .outreach import pending_drafts


def _bar(count: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return ""
    filled = round(count / total * width)
    return "█" * filled + "░" * (width - filled)


def print_report(conn: sqlite3.Connection) -> None:
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    print(f"\nLead pipeline — {total} leads\n")
    print("By status:")
    for row in conn.execute(
        "SELECT status, COUNT(*) AS n FROM leads GROUP BY status ORDER BY n DESC"
    ):
        print(f"  {row['status']:<14} {row['n']:>3}  {_bar(row['n'], total)}")
    print("\nBy tier:")
    for row in conn.execute(
        "SELECT tier, COUNT(*) AS n FROM leads GROUP BY tier ORDER BY n DESC"
    ):
        print(f"  {row['tier']:<14} {row['n']:>3}  {_bar(row['n'], total)}")
    drafts = pending_drafts(conn)
    print(f"\nDrafts waiting for review: {len(drafts)}")
    for d in drafts[:10]:
        print(f"  - {d['business_name']} (step {d['step']}): {d['subject']}")
    if len(drafts) > 10:
        print(f"  ... and {len(drafts) - 10} more")
    meetings = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE status IN ('meeting', 'won')"
    ).fetchone()[0]
    print(f"\nMeetings / wins so far: {meetings}\n")

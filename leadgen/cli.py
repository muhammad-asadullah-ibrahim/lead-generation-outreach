"""Command-line interface for the Lead Generation + Outreach System.

Usage:
    python -m leadgen.cli import data/sample_leads.csv
    python -m leadgen.cli enrich
    python -m leadgen.cli draft [--ai]
    python -m leadgen.cli report
    python -m leadgen.cli status <email> <replied|meeting|won|lost|do-not-contact>
    python -m leadgen.cli demo [--ai]

Everything runs on the standard library — no pip installs. The only
optional service is a free cloud AI (Groq or Gemini) for --ai rewrites.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadgen import __version__  # noqa: E402
from leadgen.enrich import enrich  # noqa: E402
from leadgen.leads import import_csv  # noqa: E402
from leadgen.outreach import (  # noqa: E402
    connect, due_leads, generate_drafts, get_leads, set_status, upsert_leads,
)
from leadgen.report import print_report  # noqa: E402

DEFAULT_DB = "leads.db"
DEFAULT_SENDER = "Muhammad Asadullah Ibrahim"


def _db(args) -> object:
    return connect(args.db)


def cmd_import(args) -> int:
    leads, errors = import_csv(args.csv)
    conn = _db(args)
    inserted, skipped = upsert_leads(conn, leads)
    print(f"Imported {inserted} leads ({skipped} already in database).")
    for err in errors:
        print(f"  ! {err}")
    return 0


def cmd_enrich(args) -> int:
    conn = _db(args)
    leads = get_leads(conn)
    for row in leads:
        conn.execute(
            "UPDATE leads SET score = ?, tier = ? WHERE id = ?",
            (row["score"], row["tier"], row["id"]),
        )
    conn.commit()
    hot = sum(1 for r in leads if r["tier"] == "Hot")
    warm = sum(1 for r in leads if r["tier"] == "Warm")
    print(f"Scored {len(leads)} leads: {hot} Hot, {warm} Warm, "
          f"{len(leads) - hot - warm} Cold.")
    return 0


def cmd_draft(args) -> int:
    conn = _db(args)
    drafted = generate_drafts(conn, args.sender, use_ai=args.ai)
    if not drafted:
        print("No leads are due for a message right now.")
        return 0
    print(f"Drafted {len(drafted)} message(s) — review them before sending:\n")
    for d in drafted:
        print(f"--- {d['business']} (step {d['step']}) — {d['subject']}")
        print(d["body"])
        print()
    return 0


def cmd_report(args) -> int:
    print_report(_db(args))
    return 0


def cmd_status(args) -> int:
    conn = _db(args)
    ok = set_status(conn, args.email, args.status)
    print("Updated." if ok else f"No lead found with email {args.email}.")
    return 0 if ok else 1


def cmd_demo(args) -> int:
    """Full pipeline on the sample data, from scratch, in one command."""
    demo_db = "demo.db"
    if os.path.exists(demo_db):
        os.remove(demo_db)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base, "data", "sample_leads.csv")

    class A:
        db = demo_db
        csv = csv_path
        sender = args.sender
        ai = args.ai

    a = A()
    print("=== 1. Importing sample leads ===")
    cmd_import(a)
    print("\n=== 2. Scoring ===")
    cmd_enrich(a)
    print("\n=== 3. Drafting step-1 messages ===")
    cmd_draft(a)
    print("=== 4. Pipeline report ===")
    cmd_report(a)
    print("Demo database saved as demo.db (delete it any time).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="leadgen",
        description="Lead Generation + Outreach System — find leads, score "
                    "them, draft personal messages, follow up politely.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database file")
    parser.add_argument("--sender", default=DEFAULT_SENDER,
                        help="Your name, used to sign messages")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("import", help="Import leads from a CSV file")
    p.add_argument("csv", help="Path to the CSV file")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("enrich", help="Score all leads and set their tier")
    p.set_defaults(func=cmd_enrich)

    p = sub.add_parser("draft", help="Draft messages for leads whose next step is due")
    p.add_argument("--ai", action="store_true",
                   help="Rewrite drafts with Groq or Gemini (set GROQ_API_KEY or GEMINI_API_KEY; falls back to templates)")
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("report", help="Show the pipeline report")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("status", help="Move a lead to a new status")
    p.add_argument("email", help="Lead's email address")
    p.add_argument("status", choices=["replied", "meeting", "won", "lost",
                                      "do-not-contact"])
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("demo", help="Run the whole pipeline on sample data")
    p.add_argument("--ai", action="store_true", help="Use Groq/Gemini rewrites in the demo")
    p.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

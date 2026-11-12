"""Pipeline storage + the follow-up sequence (SQLite, stdlib only).

Two tables:

    leads     — one row per business, with score, tier, and status
    messages  — one row per outreach email (draft or sent)

The sequence is deliberately slow and polite: step 1 on day 0, step 2
after 3 days, step 3 after 7 days — then stop. A lead that replies, books
a meeting, or says no leaves the sequence immediately. Nobody gets a
4th email.

Nothing here sends an email. Drafts are drafts: a human reviews them,
and sending happens through the n8n workflow (Gmail) or by hand.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from .enrich import enrich
from .leads import Lead
from .personalize import personalize

# Days after the previous step before the next one is due.
STEP_GAPS = {1: 0, 2: 3, 3: 7}

# Statuses that leave the outreach sequence for good.
DONE_STATUSES = {"replied", "meeting", "won", "lost", "do-not-contact"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    website TEXT,
    industry TEXT,
    city TEXT,
    employees INTEGER DEFAULT 0,
    source TEXT,
    score INTEGER DEFAULT 0,
    tier TEXT,
    status TEXT DEFAULT 'new',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (date('now')),
    last_contacted_at TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    step INTEGER NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT (date('now')),
    sent_at TEXT,
    UNIQUE(lead_id, step)
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_leads(conn: sqlite3.Connection, leads: list[Lead]) -> tuple[int, int]:
    """Insert leads, skipping emails already in the database.

    Returns (inserted, skipped).
    """
    inserted = skipped = 0
    for lead in leads:
        enrich(lead)
        try:
            conn.execute(
                """INSERT INTO leads
                   (business_name, contact_name, email, phone, website,
                    industry, city, employees, source, score, tier, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')""",
                (lead.business_name, lead.contact_name, lead.email, lead.phone,
                 lead.website, lead.industry, lead.city, lead.employees,
                 lead.source, lead.score, lead.tier),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    return inserted, skipped


def get_leads(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM leads"
    args: list = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY score DESC, business_name"
    return conn.execute(sql, args).fetchall()


def _last_step_date(conn: sqlite3.Connection, lead_id: int) -> tuple[int, str | None]:
    """Highest step already drafted/sent for a lead, and its date."""
    row = conn.execute(
        "SELECT MAX(step) AS step, MAX(created_at) AS d FROM messages WHERE lead_id = ?",
        (lead_id,),
    ).fetchone()
    return (row["step"] or 0), row["d"]


def due_leads(conn: sqlite3.Connection, on: date | None = None) -> list[tuple[sqlite3.Row, int]]:
    """Leads whose next sequence step is due, with the step number.

    Step 1 is due immediately for untouched leads. Steps 2 and 3 are due
    once the gap (3 / 7 days) has passed since the previous step.
    """
    on = on or date.today()
    due: list[tuple[sqlite3.Row, int]] = []
    for lead in get_leads(conn):
        if lead["status"] in DONE_STATUSES:
            continue
        last_step, last_date = _last_step_date(conn, lead["id"])
        next_step = last_step + 1
        if next_step > 3:
            continue
        if last_step == 0:
            due.append((lead, 1))
            continue
        gap = STEP_GAPS[next_step]
        last = date.fromisoformat(last_date) if last_date else on
        if (on - last).days >= gap:
            due.append((lead, next_step))
    return due


def generate_drafts(
    conn: sqlite3.Connection,
    sender_name: str,
    use_ai: bool = False,
    on: date | None = None,
) -> list[dict]:
    """Create draft messages for every due lead. Returns what was drafted."""
    drafted: list[dict] = []
    for lead_row, step in due_leads(conn, on):
        lead = Lead(
            business_name=lead_row["business_name"],
            contact_name=lead_row["contact_name"] or "",
            email=lead_row["email"],
            phone=lead_row["phone"] or "",
            website=lead_row["website"] or "",
            industry=lead_row["industry"] or "",
            city=lead_row["city"] or "",
            employees=lead_row["employees"] or 0,
        )
        subject, body = personalize(lead, step, sender_name, use_ai=use_ai)
        conn.execute(
            "INSERT OR IGNORE INTO messages (lead_id, step, subject, body, status)"
            " VALUES (?, ?, ?, ?, 'draft')",
            (lead_row["id"], step, subject, body),
        )
        conn.execute(
            "UPDATE leads SET status = 'contacted', last_contacted_at = date('now')"
            " WHERE id = ? AND status = 'new'",
            (lead_row["id"],),
        )
        drafted.append(
            {"business": lead.business_name, "step": step,
             "subject": subject, "body": body}
        )
    conn.commit()
    return drafted


def set_status(conn: sqlite3.Connection, email: str, status: str) -> bool:
    """Move a lead to a new status (replied / meeting / won / lost /
    do-not-contact). Returns False if the email isn't in the database."""
    cur = conn.execute(
        "UPDATE leads SET status = ? WHERE email = ?", (status, email.lower())
    )
    conn.commit()
    return cur.rowcount > 0


def pending_drafts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT m.*, l.business_name, l.email FROM messages m
           JOIN leads l ON l.id = m.lead_id
           WHERE m.status = 'draft' ORDER BY m.created_at, l.score DESC"""
    ).fetchall()

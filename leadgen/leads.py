"""Lead model + CSV import.

A lead is one business that might need automation. Leads come in from a
CSV file (exported from any directory, form, or scraper) and are validated
and de-duplicated here — garbage in, garbage out is not a strategy.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Lead:
    business_name: str
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    industry: str = ""
    city: str = ""
    employees: int = 0
    source: str = ""
    # Filled in later by enrich.py / outreach.py
    score: int = 0
    tier: str = ""
    status: str = "new"  # new -> contacted -> replied -> meeting -> won / lost
    notes: str = ""


def _to_int(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def import_csv(path: str) -> tuple[list[Lead], list[str]]:
    """Read leads from a CSV file.

    Expected columns: business_name, contact_name, email, phone, website,
    industry, city, employees, source. Missing columns are tolerated;
    rows without a valid email are skipped and reported.

    Returns (leads, errors). Duplicates (same email) are dropped, first
    row wins.
    """
    leads: list[Lead] = []
    errors: list[str] = []
    seen_emails: set[str] = set()

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            name = row.get("business_name", "")
            email = row.get("email", "").lower()
            if not name:
                errors.append(f"line {line_no}: missing business_name — skipped")
                continue
            if not EMAIL_RE.match(email):
                errors.append(f"line {line_no}: '{name}' has no valid email — skipped")
                continue
            if email in seen_emails:
                errors.append(f"line {line_no}: duplicate email {email} — skipped")
                continue
            seen_emails.add(email)
            leads.append(
                Lead(
                    business_name=name,
                    contact_name=row.get("contact_name", ""),
                    email=email,
                    phone=row.get("phone", ""),
                    website=row.get("website", ""),
                    industry=row.get("industry", ""),
                    city=row.get("city", ""),
                    employees=_to_int(row.get("employees", "")),
                    source=row.get("source", ""),
                )
            )
    return leads, errors

"""Lead scoring + qualification.

Not every lead is worth the same effort. A business with a website, a
named contact, and a real team is far more likely to buy automation than
a listing with no email at all. Score 0–100, then tier:

    Hot  >= 70  — contact first, personal message, same week
    Warm 40–69  — contact in the normal sequence
    Cold < 40   — nurture later, don't burn the sequence on them
"""
from __future__ import annotations

from .leads import Lead

# How much each industry tends to need automation (follow-ups, bookings,
# inbox triage). Tune these to whatever niche you sell into.
INDUSTRY_POINTS = {
    "Real Estate": 20,
    "Dental": 20,
    "Healthcare": 18,
    "E-commerce": 18,
    "Legal": 16,
    "Veterinary": 14,
    "Fitness": 12,
    "Automotive": 12,
}

# The specific pain each industry feels — this is what the outreach
# message talks about. Never pitch a feature; pitch the pain going away.
PAIN_POINTS = {
    "Real Estate": "leads that message after hours and never hear back until the next day",
    "Dental": "missed appointment bookings and patients who don't show up",
    "Healthcare": "a front desk buried in calls and appointment requests",
    "E-commerce": "abandoned carts and order questions that wait hours for a reply",
    "Legal": "consultation requests that go unanswered and intake forms that pile up",
    "Veterinary": "appointment calls that go to voicemail while the team is with patients",
    "Fitness": "trial sign-ups that never get a follow-up call",
    "Automotive": "quote requests that sit in the inbox for days",
}
DEFAULT_PAIN = "repetitive emails and follow-ups eating hours every week"


def pain_point(industry: str) -> str:
    return PAIN_POINTS.get(industry, DEFAULT_PAIN)


def score_lead(lead: Lead) -> int:
    """Score a lead 0–100. Pure function — no database, no network."""
    score = 0
    if lead.email:
        score += 25
    if lead.website:
        score += 20
    if lead.contact_name:
        score += 10
    if lead.phone:
        score += 5
    score += INDUSTRY_POINTS.get(lead.industry, 5)
    if lead.employees >= 10:
        score += 15
    elif lead.employees >= 5:
        score += 10
    elif lead.employees >= 1:
        score += 5
    if lead.city:
        score += 5
    return min(score, 100)


def tier_for(score: int) -> str:
    if score >= 70:
        return "Hot"
    if score >= 40:
        return "Warm"
    return "Cold"


def enrich(lead: Lead) -> Lead:
    """Score a lead in place and set its tier. Returns the same lead."""
    lead.score = score_lead(lead)
    lead.tier = tier_for(lead.score)
    return lead

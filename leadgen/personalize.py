"""Outreach messages: templates + optional AI personalization.

Every lead gets a 3-step sequence:

    Step 1 (Day 0) — short intro + the pain point + a free 10-minute audit
    Step 2 (Day 3) — a useful observation, no pressure
    Step 3 (Day 7) — final nudge, then stop. No 4th email, ever.

Templates are the default. With --ai, each message is rewritten by a
free cloud AI in a natural tone, using the lead's details. The AI never
invents facts about the business — it only rewords the template.

The rewrite tries providers in order and uses the first one that
answers with a usable message:

    1. Groq openai/gpt-oss-20b — GROQ_API_KEY
    2. Groq openai/gpt-oss-120b — same key, stronger model
    3. Groq qwen/qwen3.8-27b — same key
    4. Google Gemini 2.0 Flash — GEMINI_API_KEY

Setup — Groq (recommended, 2 minutes, no card):
    1. Go to https://console.groq.com and sign up (Google se bhi hota hai).
    2. API Keys → Create API Key (key `gsk_...` se shuru hoti hai).
    3. Windows:  setx GROQ_API_KEY "paste-your-key-here"
       (then open a NEW terminal window)
    4. Run any draft command with --ai.

Free tiers: Groq 30 requests/minute (8b: 14,400/day, 70b: 1,000/day);
Gemini 15/minute, 1,500/day. Note: Gemini ka free tier kuch projects
par "unavailable" dikha sakta hai (Google ki taraf se project flag),
aur Groq kabhi kisi model par 403 de sakta hai (key valid, us resource
ki permission nahi) — is liye chain mein kayi providers hain. Koi key
na ho, ya sab fail hon, to plain template use hota hai. The pipeline
never breaks on AI.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

from .enrich import pain_point
from .leads import Lead

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
# Models this account can actually use (checked with /models on 12 Nov 2026).
GROQ_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b")
# Groq sits behind Cloudflare, which blocks Python's default User-Agent
# with HTTP 403 (error code 1010). A custom User-Agent fixes it.
USER_AGENT = "leadgen-cli/1.0"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

TEMPLATES = {
    1: {
        "subject": "Quick question about {business_name}",
        "body": (
            "Hi {contact_name},\n\n"
            "I help small businesses automate the work that quietly eats hours "
            "every week — things like {pain_point}.\n\n"
            "Would a free 10-minute audit be useful? I'll look at how "
            "{business_name} handles follow-ups today and tell you the one "
            "thing AI could take off your plate. No pitch, no obligation.\n\n"
            "Best,\n{sender_name}\nAI Automation Specialist"
        ),
    },
    2: {
        "subject": "Re: Quick question about {business_name}",
        "body": (
            "Hi {contact_name},\n\n"
            "Just floating this back up — most {industry} businesses I speak "
            "to lose enquiries the same way: {pain_point}. An AI assistant "
            "that replies in seconds usually fixes it in a week.\n\n"
            "Happy to show you what that looks like for {business_name} in "
            "10 minutes, if you're curious.\n\n"
            "Best,\n{sender_name}"
        ),
    },
    3: {
        "subject": "Closing the loop — {business_name}",
        "body": (
            "Hi {contact_name},\n\n"
            "Last note from me — I don't want to clutter your inbox. If "
            "automating follow-ups is on your list this year, I'm here for a "
            "quick chat. If not, no worries at all, and I wish {business_name} "
            "well.\n\n"
            "Best,\n{sender_name}"
        ),
    },
}


def render(lead: Lead, step: int, sender_name: str) -> tuple[str, str]:
    """Render a template for a lead. Returns (subject, body)."""
    tpl = TEMPLATES[step]
    ctx = {
        "contact_name": lead.contact_name or "there",
        "business_name": lead.business_name,
        "industry": lead.industry or "small business",
        "pain_point": pain_point(lead.industry),
        "sender_name": sender_name,
    }
    return tpl["subject"].format(**ctx), tpl["body"].format(**ctx)


def _clean_model_text(text: str) -> str:
    """Strip <think> blocks and markdown fences from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```[a-z]*\n?", "", text)
    return text.strip()


def _parse_rewrite(text: str, template_subject: str) -> tuple[str, str] | None:
    """Pull (subject, body) out of a model's rewrite.

    Tolerant by design: models often add a preamble ("Here is the
    rewritten email:"), bold the label ("**Subject:**"), or use a
    lowercase label. We search for the subject line anywhere in the
    text instead of demanding it be the first line. If there is no
    subject line but the body is a real rewrite, we keep the template
    subject and use the model's body. Returns None when the text is
    unusable, so the caller falls back to the template.
    """
    text = _clean_model_text(text)
    if not text:
        return None
    match = re.search(
        r"\*{0,2}subject:\*{0,2}\s*(.+?)\n+(.*)",
        text, flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        subject = match.group(1).strip().strip("*").strip()
        body = match.group(2).strip()
        if subject and body:
            return subject, body
    if len(text) >= 80:
        return template_subject, text
    return None


def _post_json(url: str, payload: dict, headers: dict,
               timeout: int = 30) -> dict | None:
    """POST JSON and parse the reply. None on any network/parse failure."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            **headers,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def _groq_rewrite(prompt: str, model: str) -> str | None:
    """Rewrite via Groq (free). Returns raw text or None."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        # Reasoning models spend tokens thinking first, so leave room.
        "max_tokens": 1500,
    }
    if model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"
    data = _post_json(
        GROQ_URL,
        payload,
        {"Authorization": f"Bearer {api_key}"},
    )
    if not data:
        return None
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def _gemini_rewrite(prompt: str) -> str | None:
    """Rewrite via Google Gemini (free). Returns raw text or None."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    data = _post_json(
        GEMINI_URL,
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400},
        },
        {"x-goog-api-key": api_key},
    )
    if not data:
        return None
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None


def ai_personalize(
    lead: Lead, step: int, sender_name: str, timeout: int = 30
) -> tuple[str, str] | None:
    """Ask a free cloud AI to rewrite the template in a natural tone.

    Tries Groq (small model, then big model), then Gemini. Returns
    (subject, body), or None if every provider fails — the caller
    falls back to the plain template.
    """
    subject, body = render(lead, step, sender_name)
    prompt = (
        "Rewrite this outreach email so it sounds like a real person wrote "
        "it — short, natural, no hype, no buzzwords. Keep every fact the "
        "same, keep it under 120 words, and keep the greeting and sign-off. "
        "Reply with the subject line on the first line starting with "
        "'Subject: ', then a blank line, then the email body. No thinking, "
        "no explanation.\n\n"
        f"Subject: {subject}\n\n{body}"
    )

    def _tries():
        for model in GROQ_MODELS:
            yield _groq_rewrite(prompt, model)
        yield _gemini_rewrite(prompt)

    for text in _tries():
        if not text:
            continue
        parsed = _parse_rewrite(text, subject)
        if parsed is not None:
            return parsed
    return None


_AI_WARNED = False


def personalize(
    lead: Lead, step: int, sender_name: str, use_ai: bool = False
) -> tuple[str, str]:
    """Best message for a lead: AI rewrite when available, else template."""
    global _AI_WARNED
    if use_ai:
        rewritten = ai_personalize(lead, step, sender_name)
        if rewritten is not None:
            return rewritten
        if not _AI_WARNED:
            _AI_WARNED = True
            print(
                "Note: AI se rewrite nahi hua (key, network ya jawab ka "
                "format) — templates use ho rahe hain.",
                file=sys.stderr,
            )
    return render(lead, step, sender_name)

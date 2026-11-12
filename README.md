# Lead Generation + Outreach System

Most small businesses don't lose customers because of bad service. They
lose them because nobody follows up. A lead messages after hours, asks
about a booking, or abandons a cart — and nobody replies for a day. By
then they've gone somewhere else.

This system fixes that. It finds leads, scores them so you talk to the
best ones first, writes each of them a personal message, and follows up
on a polite schedule — until they reply, book, or say no. Then it stops.

**Live demo:** [Lead Outreach Studio](https://legendary-rolypoly-c9a1de.netlify.app) — upload a CSV in your browser and watch it score every lead and draft the 3-email sequence. Same scoring rules as this pipeline.


## How it works

```
CSV leads → score + tier → personal message (template or Gemini AI)
         → 3-step sequence (day 0, 3, 7) → SQLite pipeline + report
```

1. **Import** — leads come in from a CSV (any directory, form, or
   scraper). Bad rows are reported, duplicates are dropped.
2. **Score** — each lead gets 0–100 based on email, website, contact
   name, team size, and industry. Hot (70+), Warm (40–69), Cold (under
   40). Talk to the Hot ones first.
3. **Draft** — every due lead gets a personal message. Templates by
   default; with `--ai` a free cloud AI (Groq, or Gemini as backup)
   rewrites each one in a natural tone (free API key, see below). If no
   key is set or the AI errors, templates are used — the pipeline
   never breaks.
4. **Follow up** — step 1 on day 0, step 2 after 3 days, step 3 after 7
   days. Then stop. A lead that replies, books a meeting, or says no
   leaves the sequence immediately. Nobody gets a 4th email.
5. **Report** — pipeline by status and tier, drafts waiting for review,
   meetings and wins so far.

Nothing here sends an email by itself. Drafts are drafts — a human
reviews them, and sending happens through the included n8n workflow
(Gmail) or by hand.

## Quickstart

```bash
# No installs needed — Python 3.10+ standard library only.
# (Gemini is optional, only for --ai rewrites.)

# See the whole thing work on sample data:
python -m leadgen.cli demo

# Or run it yourself:
python -m leadgen.cli import data/sample_leads.csv
python -m leadgen.cli enrich
python -m leadgen.cli draft            # templates
python -m leadgen.cli draft --ai       # Groq/Gemini rewrites, if a key is set
python -m leadgen.cli report
python -m leadgen.cli status sarah@sunsetrealtygroup.com replied
```

## AI setup (optional, 2 minutes, free)

`--ai` uses a free cloud AI — no local server, nothing to install, no
card needed.

**Groq (recommended):**
1. Go to https://console.groq.com → sign up (Google se bhi hota hai).
2. API Keys → **Create API Key** (key `gsk_...` se shuru hoti hai).
3. Set it once on your machine:
   - Windows: `setx GROQ_API_KEY "paste-your-key-here"` (then open a
     new terminal)
   - Mac/Linux: `export GROQ_API_KEY="paste-your-key-here"`
4. Run any draft command with `--ai`.

Free tier: 30 requests/minute, 1,000/day — roz ke outreach ke liye
bohat hai.

**Gemini (backup):** same thing with Google Gemini 2.0 Flash — key from
https://aistudio.google.com/app/apikey, set as `GEMINI_API_KEY` (free
tier: 15/minute, 1,500/day). Note: Gemini ka free tier kuch projects
par "unavailable" dikha sakta hai — Google ki taraf se project flag —
us surat mein Groq use karein.

No key, no problem — templates work on their own.

## The n8n workflow

`n8n/lead-outreach-workflow.json` runs the same sequence on a schedule —
every day at 9 AM it reads due leads from Google Sheets, builds the
message, optionally personalizes it with Groq (free API key), sends it
with Gmail, and logs it. Import it in n8n (Workflows → Import), paste
your Google Sheet ID where it says `PASTE_YOUR_GOOGLE_SHEET_ID_HERE`,
paste your Groq API key where it says `PASTE_YOUR_GROQ_API_KEY_HERE`,
and connect your Google account. The setup notes are inside the
workflow.

## Project layout

```
leadgen/
  leads.py        Lead model + CSV import (validate, de-duplicate)
  enrich.py       Scoring, tiers, and each industry's pain point
  personalize.py  Message templates + Groq/Gemini rewrites
  outreach.py     SQLite pipeline + the 3-step sequence
  report.py       Pipeline report
  cli.py          Command-line interface
data/
  sample_leads.csv    10 fictional leads (demo data — not real businesses)
  email_templates.md  The 3 message templates, documented
n8n/
  lead-outreach-workflow.json
```

## A note on the sample data

The 10 leads in `data/sample_leads.csv` are fictional businesses made
up for the demo. Don't email them — they're not real.

## Tech

Python (stdlib only) · SQLite · n8n · Groq / Gemini APIs (free tiers) · Gmail & Google Sheets APIs

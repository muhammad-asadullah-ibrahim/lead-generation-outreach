# Email templates

The three steps of the outreach sequence. Placeholders are filled in
from the lead's record: `{contact_name}`, `{business_name}`, `{industry}`,
`{pain_point}` (the industry's specific pain, from `enrich.py`), and
`{sender_name}`.

The templates live in code (`leadgen/personalize.py`) — this file
documents them so you can edit the words without touching Python.

## Step 1 — Day 0: the intro

**Subject:** Quick question about {business_name}

> Hi {contact_name},
>
> I help small businesses automate the work that quietly eats hours every
> week — things like {pain_point}.
>
> Would a free 10-minute audit be useful? I'll look at how {business_name}
> handles follow-ups today and tell you the one thing AI could take off
> your plate. No pitch, no obligation.
>
> Best,
> {sender_name}
> AI Automation Specialist

## Step 2 — Day 3: the nudge

**Subject:** Re: Quick question about {business_name}

> Hi {contact_name},
>
> Just floating this back up — most {industry} businesses I speak to lose
> enquiries the same way: {pain_point}. An AI assistant that replies in
> seconds usually fixes it in a week.
>
> Happy to show you what that looks like for {business_name} in 10 minutes,
> if you're curious.
>
> Best,
> {sender_name}

## Step 3 — Day 7: the close

**Subject:** Closing the loop — {business_name}

> Hi {contact_name},
>
> Last note from me — I don't want to clutter your inbox. If automating
> follow-ups is on your list this year, I'm here for a quick chat. If not,
> no worries at all, and I wish {business_name} well.
>
> Best,
> {sender_name}

No 4th email, ever. A lead that replies, books, or says no leaves the
sequence immediately.

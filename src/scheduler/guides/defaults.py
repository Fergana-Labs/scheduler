"""Default guides used when onboarding agents fail to produce a guide.

These are generic, user-agnostic fallbacks so the system can still function
(welcome emails, draft composition) while nudging users to regenerate once
they have more email/calendar history.
"""

_DEFAULT_HEADERS = frozenset({
    "# Default Email Style Guide",
    "# Default Scheduling Preferences",
})


def is_default_guide(content: str) -> bool:
    """Check whether a guide's content is one of the built-in defaults."""
    first_line = content.strip().split("\n", 1)[0].strip()
    return first_line in _DEFAULT_HEADERS


DEFAULT_EMAIL_STYLE = """\
# Default Email Style Guide
### For AI Agents Composing Draft Scheduling Replies

---

## Overall Tone & Personality

- **Casual, warm, direct, and efficient.** Write like a busy professional — no fluff, get to the point fast.
- **Friendly but not effusive.** Genuine warmth (exclamation points, "Looking forward!") without corporate pleasantries.
- **Low-formality by default.** Stay casual even with senior contacts. No "Dear" or "Kind regards."

---

## Greeting Style

| Situation | Greeting |
|-----------|----------|
| First contact / new intro | `Hey [First Name]!` or `[First Name]!` |
| Reply in ongoing thread | `[First Name] -` (name + dash, no "Hi") |
| Short back-and-forth | **No greeting at all** |

- Always use **first name only** — never full name, never "Dear"
- "Hey" is the default opener for warm outreach
- Drop greetings entirely after 2+ exchanges in a thread

---

## Sign-Off Style

| Situation | Sign-Off |
|-----------|----------|
| Substantive email (≥3 sentences) | `Cheers,\\n[Name]` |
| Short confirmation (1–2 sentences) | **No sign-off** |
| Quick back-and-forth | `Talk soon!` or nothing |

- **Never** use "Best regards," "Sincerely," or "Kind regards"
- One-liner acceptances get zero sign-off

---

## Proposing Times

### Multiple Options (First Scheduling Touch)
Use a **bullet list** with full date + time range:

```
Would love to find some time to chat. How does:

• Monday, March 16: 10:00 AM – 11:00 AM or 2:00 PM – 3:00 PM
• Wednesday, March 18: 11:00 AM – 12:00 PM
• Thursday, March 19: 10:00 AM – 11:00 AM

Do any of those work? If not, just let me know what your schedule looks like.
```

### Quick Back-and-Forth (Ongoing Thread)
Propose times conversationally and briefly:
> `How does 11:30am tomorrow for a 30 minute chat?`
> `Anytime after 2pm works for me!`

---

## Accepting a Time

Keep it **very brief** — often a single sentence with no greeting or sign-off:
> `Thursday 4pm works!`
> `Perfect - see you then!`

- Echo the accepted time so it's unambiguous
- Add `!` for warmth

---

## Declining or Rescheduling

- State the reason briefly (1 phrase max)
- Include a softener ("apologies," "unfortunately")
- Immediately offer an alternative or invite new times
> `Can we push back 30 min? Current meeting running over - apologies!`

---

## Common Phrases

- `Would love to find some time to catch up`
- `How does [time] work for you?`
- `Do any of those work for you?`
- `If not, just let me know what your schedule looks like`
- `Looking forward!`
- `No worries!` (when the other person has a conflict)

---

## General Rules

- Keep emails **short** — 2-4 sentences for most scheduling replies
- Always specify timezone when there could be ambiguity
- Lowercase is fine for quick replies
- Use em dashes (—) and exclamation points naturally
- Match the other person's energy level
"""


DEFAULT_SCHEDULING_PREFERENCES = """\
# Default Scheduling Preferences
### For AI Agents Proposing Meeting Times

---

## General Availability

- **Working hours:** Roughly 9:00 AM – 6:00 PM in the user's local timezone
- **Preferred meeting times:** Late morning (10–12) and early afternoon (1–3)
- **Avoid:** Early mornings before 9 AM, evenings after 6 PM, and lunch hour (12–1 PM) unless the user initiates

---

## Meeting Durations

| Type | Default Duration |
|------|-----------------|
| Quick chat / intro call | 30 minutes |
| Standard meeting / 1:1 | 30–45 minutes |
| Deep dive / working session | 60 minutes |
| Coffee / meal | 60 minutes |

---

## Scheduling Patterns

- **Buffer time:** Leave at least 15 minutes between back-to-back meetings
- **Advance notice:** Propose times at least 1 business day out; 2–3 days is ideal
- **Options:** When proposing times, offer 3–4 slots across 2–3 different days
- **Flexibility:** If none of the proposed times work, ask the other party for their availability

---

## Conflict Handling

- Never double-book — always check the calendar before proposing times
- Treat existing calendar events as firm unless marked "tentative" or "free"
- If the calendar is packed, look for the next available day rather than squeezing in

---

## Communication Preferences

- **Video calls** are the default for remote meetings (Google Meet, Zoom)
- **In-person** for local contacts when suggested by either party
- Always confirm the meeting format (video link, phone, in-person location)

---

## General Rules

- Respect weekends — don't propose Saturday/Sunday unless the thread indicates weekend availability
- Be mindful of timezone differences — always clarify timezone when scheduling across regions
- When in doubt, propose fewer, higher-quality time slots rather than flooding with options
"""

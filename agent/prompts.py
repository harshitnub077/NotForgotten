"""Prompt templates for the LangGraph agent nodes."""
from __future__ import annotations

SYSTEM_PROMPT = """\
You are NotForgotten, an adaptive learning assistant powered by spaced repetition science.

Your goals:
1. Explain concepts clearly using ONLY the retrieved context provided.
2. Connect ideas to what the user already knows.
3. Ask clarifying questions if the retrieved context is insufficient.
4. Be concise — aim for 3-5 paragraphs max per answer.
5. Always cite the source chunk(s) you drew from.

If the context doesn't contain enough information to answer, say so honestly and
suggest what the user should re-read. Never hallucinate facts.
"""

GENERATE_PROMPT = """\
## Retrieved Context
{context}

## User Query
{query}

Please answer the query using only the context above. At the end of your answer,
list the source files and page numbers you referenced in a compact format like:
  Sources: file.pdf p.3, notes.pdf p.7
"""

ASSESS_PROMPT = """\
Based on the explanation above, please rate your understanding:

  1 — I didn't understand anything
  2 — I got the gist but still confused
  3 — Understood, but not confident
  4 — Understood well
  5 — Completely clear, could explain it myself

Reply with a single digit (1–5).
"""

RETEACH_PROMPT = """\
I see you're still struggling with this concept. Let me approach it differently.

## Additional Context
{context}

Here's a simpler breakdown:
"""

SCHEDULE_PROMPT = """\
Great session! Here's your review schedule update:

{schedule_summary}

Keep it up — the key to long-term retention is consistent, spaced review. 🧠
"""

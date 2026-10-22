# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: university and competitive-exam students (e.g. JEE, NEET, MCAT, bar exams) who have
lecture PDFs, notes and web readings and a fixed exam date. Their job is to turn that material
into memory that is still there on exam day, with limited daily time and a tendency to cram
and re-read. Secondary (later): professionals and lifelong learners who read a lot and want to
retain it.

## Product Purpose

NotForgotten turns any study material into a personal memory system. It reads a document,
discovers its concepts, writes recall questions, and schedules each one at the moment the
learner is about to forget it. Success means higher measured recall on exam day for fewer
minutes of study per day, and a learner who trusts the plan instead of cramming.

## Positioning

Not another flashcard app: the unit of memory is the *concept*, modelled with FSRS-6 and
linked in a prerequisite knowledge graph where forgetting propagates. It grades typed recall
instead of honour-system flips, measures confidence calibration (the illusion of competence),
fits a personal forgetting curve from the learner's own reviews, and plans backwards from an
exam date. The AI tutor knows what the learner is forgetting and uses every conversation as
review.

## Operating Context

- Daily ritual: open the app, see what is due and how long it will take, do a short session.
- Study-time sessions are focused and often keyboard-driven on a laptop; quick reviews happen
  on a phone between classes.
- Inputs: PDFs (lecture slides, textbooks), Markdown/TXT notes, pasted text, web article URLs.
- Exams are the forcing function: a named exam with a date and a target recall.

## Capabilities and Constraints

- Backend: FastAPI + SQLite + ChromaDB, local sentence-transformer embeddings (MiniLM).
- Scheduling: FSRS-6 with personal parameter fitting; queue modes due / smart (time-boxed by
  retention-days gained per second) / cram / exam.
- Card kinds: qa, cloze, explain. Grading: LLM rubric or embedding + lexical fallback.
- Feynman mode, memory-aware streaming tutor (explain / socratic / quiz), knowledge graph with
  a time-machine projection, insights (heatmap, true retention, calibration, forecast).
- Every AI feature works offline with a deterministic fallback; an LLM key is optional.
- Single-user, local-first today. Accounts, sync and payments are undecided.

## Brand Commitments

- Name: NotForgotten (keep). Logo, colours and visual identity are open.
- Voice: a calm scientific coach — evidence-based, honest about forgetting, quietly
  encouraging; shows the maths when it builds trust. Not gamified hype.

## Evidence on Hand

- Original demo study texts in `assets/demo/` and a simulated two-month learner history.
- No real users, testimonials, customer logos, benchmarks, press or pricing exist. Do not
  fabricate any.

## Product Principles

1. Measure memory, don't assume it — every number shown is computed from the model or reviews.
2. Time is the scarce resource — always say how long today's work takes and what it buys.
3. Effortful recall over passive review — typing an answer beats flipping a card.
4. Honest feedback builds trust — show forgetting and overconfidence plainly, without shame.
5. Plan backwards from the exam — the date and target drive the schedule.

## Accessibility & Inclusion

Full keyboard operation of review sessions; readable in long study sessions (light and dark);
respects reduced motion; colour is never the only carrier of retention state.

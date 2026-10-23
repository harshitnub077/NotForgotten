# Deploying NotForgotten for beta students

NotForgotten runs as **one container** (API + web app on port 8080) plus **one Postgres database**. Passages, embeddings, cards, reviews and accounts all live in Postgres, so the app server is stateless. You can redeploy or scale it without losing data.

## 1. Create the database

Any managed Postgres 14+ works. Free tiers are enough for a beta:

| Provider | Notes |
|---|---|
| [Neon](https://neon.tech) | Serverless Postgres, generous free tier. Copy the *pooled* connection string. |
| [Supabase](https://supabase.com) | Use **Project settings → Database → Connection string (URI)**. |
| Render / Railway | Add a Postgres service next to the app. |

You'll get a URL like `postgresql://user:password@host/dbname?sslmode=require`. NotForgotten creates its tables on first start.

## 2. Deploy the container

The repo's `Dockerfile` builds everything. On **Render** / **Railway** / **Fly.io**, create a web service from the GitHub repo using the Dockerfile, and set:

| Variable | Value | Why |
|---|---|---|
| `DATABASE_URL` | your Postgres URL | Turns on hosted Postgres (otherwise SQLite on local disk) |
| `COOKIE_SECURE` | `1` | Session cookies only over HTTPS |
| `CORS_ORIGINS` | `https://your-domain.com` | The site's own origin (and any other front-end origin) |
| `BETA_INVITE_CODES` | e.g. `JEE2026,NEETBETA` | Only people with a code can sign up. Leave unset to allow anyone |
| `GROQ_API_KEY` *(or `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`)* | your key | AI questions, grading and tutor. Optional, since every feature has an offline fallback |
| `LLM_PROVIDER`, `LLM_MODEL` | optional | Choose provider/model explicitly |

**Instance size:** use at least **1 GB RAM**. The embedding model (MiniLM) and PyTorch use about 600 MB. The health check is `GET /api/health`.

## 3. Invite students

Share `https://your-domain.com/signup?invite=YOURCODE`. The invite field is pre-filled from the link.

Each student gets a private library:
- every query is scoped to their account;
- sessions are 30-day HttpOnly cookies;
- passwords are hashed with scrypt.

Students can export all their data or delete their account from **Settings → Account**.

## 4. Before going public

- **Password reset by email** isn't built yet. For the beta, reset a student's password manually or ask them to make a new account.
- **Privacy policy and terms.** Required before collecting student data. If you have users under 18 in India, the DPDP Act 2023 needs verifiable parental consent.
- **Backups.** Enable your Postgres provider's automatic backups.
- **Scale.** Ingestion runs on one background worker per instance. For more than ~50 concurrent uploads, move it to a job queue (e.g. a separate worker process).

## Local development

Without `DATABASE_URL` the app uses SQLite in `./data/memory.db`. The first account you create takes ownership of any library made before accounts existed.

```bash
.venv/bin/uvicorn api.main:app --port 8080
```

```bash
npm --prefix frontend run dev
```

To run the test suite against Postgres:

```bash
DATABASE_URL=postgresql://localhost/notforgotten_test .venv/bin/python -m pytest
```

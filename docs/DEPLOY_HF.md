# Free hosting: Hugging Face Space + Neon Postgres

NotForgotten runs free at `https://<hf-username>-<space-name>.hf.space`.

| Piece | Service | Cost |
|---|---|---|
| App (API + web app, one Docker container) | Hugging Face Space, CPU basic: 2 vCPU, 16 GB RAM | Free |
| Database (accounts, libraries, reviews) | Neon Postgres | Free (0.5 GB) |
| Deploys | GitHub Action `.github/workflows/deploy-hf.yml` | Free |

**You never configure the Space by hand.** On every run, the deploy:
- creates the Space if it doesn't exist (Docker, free CPU basic, public);
- fixes its hardware if it's wrong;
- copies your secrets in from GitHub;
- pushes the app and waits until the live site answers.

Every push to `main` redeploys.

---

## Step 1: Database on Neon

1. Sign up at **https://neon.tech**. You can sign in with GitHub.
2. Create a project named `notforgotten`, region **AWS US East (N. Virginia)** (close to Hugging Face's servers).
3. Click **Connect**, turn **off** "Connection pooling", and copy the connection string:
   ```
   postgresql://neondb_owner:XXXX@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```

## Step 2: Hugging Face account and token

1. Sign up at **https://huggingface.co/join** and **confirm your email**.
2. Note your username: it's in the menu under your avatar and in your profile address `huggingface.co/<username>`.
3. Go to **https://huggingface.co/settings/tokens**, click **Create new token**, choose the **Write** tab (not "Fine-grained"), name it `notforgotten-deploy`, and create it. Copy the `hf_…` value.

## Step 3: Settings in GitHub

Open **https://github.com/harshitnub077/NotForgotten/settings/secrets/actions**.

**Secrets** tab → **New repository secret**, once for each:

| Name | Value |
|---|---|
| `HF_TOKEN` | the `hf_…` Write token from Step 2 |
| `DATABASE_URL` | the Neon connection string from Step 1 |
| `GROQ_API_KEY` | your Groq key, from your local `.env` or https://console.groq.com/keys |
| `BETA_INVITE_CODES` | invite codes students must enter, comma-separated, e.g. `NF-BETA-7Q4K` (leave out to allow anyone) |

**Variables** tab → **New repository variable**:

| Name | Value |
|---|---|
| `HF_SPACE` | `<your-hf-username>/notforgotten-app` (the username **exactly** as on Hugging Face, including capitals) |

## Step 4: Deploy

1. Open **https://github.com/harshitnub077/NotForgotten/actions/workflows/deploy-hf.yml** and click **Run workflow** on branch `main`.
2. The first run creates the Space and builds it in about 10–15 minutes. It finishes with **"Live at https://…hf.space"** in the run summary.

## Step 5: Invite students

Open `https://<your-hf-username>-notforgotten-app.hf.space/signup?invite=<CODE>` (all lowercase) and create your own account first. Then share the same link.

Always use the `.hf.space` address. On the `huggingface.co/spaces/...` page the app runs inside a frame, and browsers block the login cookie there.

---

## If the deploy fails

The run prints the reason in plain words. The common ones:

| Message | Fix |
|---|---|
| `HF_TOKEN was rejected` / `token can't create Spaces` | Create a token with the **Write** role (Step 2) and update the `HF_TOKEN` secret |
| `owner '…' doesn't match the token's account '…'` | Set `HF_SPACE` to `<that account>/notforgotten-app` |
| `won't move this Space off 'zero-a10g' without a PRO plan` | The Space was created on ZeroGPU by hand. Change `HF_SPACE` to a new name (e.g. `…/notforgotten-web`) and rerun; the deploy creates a fresh free Space |
| `No DATABASE_URL secret` (warning) | Add the Neon URL as the `DATABASE_URL` secret, or accounts reset whenever the Space restarts |

Build and runtime logs are on the Space page under **Logs**.

## Good to know

- **Sleeping:** a free Space sleeps after 48 hours without visitors and wakes in 1–2 minutes on the next visit. Neon's free database pauses after 5 minutes idle and wakes in about a second. Data is never lost.
- **Changing settings:** update the GitHub secret, then rerun the workflow; it re-applies them to the Space.
- **Upgrading:** when you outgrow the free tier, run the same Docker image on Render, Railway or Fly.io ([DEPLOY.md](DEPLOY.md)) with the same Neon database.

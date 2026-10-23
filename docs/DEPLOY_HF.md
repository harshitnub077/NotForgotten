# Free hosting: Hugging Face Space + Neon Postgres

This gets NotForgotten live at `https://<your-hf-username>-notforgotten.hf.space` at no cost, and redeploys it automatically on every push to `main`.

| Piece | Service | Cost |
|---|---|---|
| App (API + web app, one Docker container) | Hugging Face Space, CPU basic: 2 vCPU, 16 GB RAM | Free |
| Database (accounts, libraries, reviews) | Neon Postgres | Free (0.5 GB) |
| Redeploy on push | GitHub Action `.github/workflows/deploy-hf.yml` | Free |

It takes about 15 minutes, most of it waiting for the first build.

---

## Step 1: Create the database on Neon

1. Go to **https://neon.tech** and sign up. You can sign in with GitHub.
2. Create a project:
   - **Project name:** `notforgotten`
   - **Postgres version:** the default (16 or 17)
   - **Region:** **AWS US East (N. Virginia)**. This keeps the database close to Hugging Face's servers, which matters more than distance to your students.
3. On the project dashboard, click **Connect**.
4. **Turn off "Connection pooling"** so you get the direct connection string, then copy it. It looks like:
   ```
   postgresql://neondb_owner:XXXXXXXX@ep-something-123456.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
   This is your **`DATABASE_URL`**. Keep it private: it contains the database password.

NotForgotten creates its tables automatically on first start.

## Step 2: Create the Space on Hugging Face

1. Go to **https://huggingface.co/join**, sign up, and confirm your email.
2. Open **https://huggingface.co/new-space** and fill in:
   - **Space name:** `notforgotten`
   - **License:** any (e.g. `other`)
   - **Select the Space SDK:** **Docker**, then the **Blank** template
   - **Space hardware:** **CPU basic · 2 vCPU · 16 GB · FREE**
   - **Visibility:** **Public**. Students can't open a private Space without a Hugging Face login.
3. Click **Create Space**. Leave it empty; GitHub will fill it.

## Step 3: Add the app's settings to the Space

In the Space, open **Settings → Variables and secrets**.

Add these as **New secret** (hidden values):

| Name | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string from Step 1 |
| `GROQ_API_KEY` | your Groq key. Copy it from your local `.env` file, or create one at https://console.groq.com/keys |
| `BETA_INVITE_CODES` | one or more codes students must enter to sign up, comma-separated, e.g. `NF-BETA-7Q4K` |

Add these as **New variable** (visible values):

| Name | Value |
|---|---|
| `COOKIE_SECURE` | `1` |
| `CORS_ORIGINS` | `https://<your-hf-username>-notforgotten.hf.space` (lowercase; `_` and `.` in your username become `-`) |
| `LLM_PROVIDER` | `groq` |
| `LLM_MODEL` | `openai/gpt-oss-120b` |

## Step 4: Create a Hugging Face token for GitHub

1. Go to **https://huggingface.co/settings/tokens** and click **Create new token**.
2. Choose the **Fine-grained** token type and name it `notforgotten-deploy`.
3. Under **Repositories permissions**, select your Space `spaces/<your-hf-username>/notforgotten` and tick **Write access to contents/settings of selected repos**.
4. Click **Create token** and copy it (it starts with `hf_`). You only see it once.

## Step 5: Connect GitHub to the Space

In **https://github.com/harshitnub077/NotForgotten/settings/secrets/actions**:

1. On the **Secrets** tab, click **New repository secret**:
   - Name: `HF_TOKEN`
   - Value: the `hf_…` token from Step 4
2. On the **Variables** tab, click **New repository variable**:
   - Name: `HF_SPACE`
   - Value: `<your-hf-username>/notforgotten`, e.g. `asha-k/notforgotten`

## Step 6: Deploy

1. Open **https://github.com/harshitnub077/NotForgotten/actions/workflows/deploy-hf.yml**.
2. Click **Run workflow** (branch `main`), then **Run workflow**.
3. The first build takes about 10–15 minutes (it installs PyTorch and bakes in the AI model). The run ends with **"Live at https://…hf.space"** in its summary.

From now on, every push to `main` redeploys automatically.

## Step 7: Create your account and invite students

1. Open `https://<your-hf-username>-notforgotten.hf.space/signup?invite=<YOUR-CODE>` and create your own account.
2. Share the same link with beta students. The invite code is pre-filled.

Always use the **`.hf.space` address**, not the `huggingface.co/spaces/...` page. That page shows the app inside a frame where browsers block the login cookie.

---

## Good to know

- **Sleeping:** a free Space sleeps after 48 hours without visitors, and the next visit wakes it in 1–2 minutes. Neon's free database also pauses after 5 minutes idle and wakes in about a second. Your data is never lost; it lives in Neon.
- **Source visibility:** a public Space shows its files on Hugging Face, the same code as your public GitHub repo. Secrets stay hidden.
- **Logs:** if a deploy fails, the Action prints a link. Build and runtime logs are under **Logs** on the Space page.
- **Upgrading later:** if students outgrow the free tier, move the same Docker image to Render, Railway or Fly.io (see [DEPLOY.md](DEPLOY.md)) and keep the same Neon database.

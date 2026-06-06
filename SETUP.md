# Setup Guide

## What you need (accounts to create)

1. **Anthropic** (for AI summaries): https://console.anthropic.com  
   Create an account, go to API Keys, and create a new key.

2. **Resend** (for sending emails): https://resend.com  
   Create an account, go to API Keys, and create a key.  
   Also go to Domains and add your domain (or use their free @resend.dev address to start).

3. **Railway** (for hosting): https://railway.app  
   Create an account. The free tier works; the $5/mo Hobby plan is recommended.

---

## Step 1: Get your API keys

Copy `.env.example` to `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...        ← from console.anthropic.com
RESEND_API_KEY=re_...               ← from resend.com
FROM_EMAIL=digest@yourdomain.com    ← must be verified in Resend
FROM_NAME=Investing Digest
APP_URL=https://your-app.railway.app  ← fill in after deploying
SECRET_KEY=pick-any-long-random-string
ADMIN_SECRET=another-random-string   ← for manually triggering digests
```

---

## Step 2: Deploy to Railway

1. Go to https://railway.app → New Project → Deploy from GitHub repo  
   (Push this folder to a GitHub repo first, then connect it)

2. In your Railway project:
   - Click **+ New** then **Database** then **PostgreSQL**. Railway will set `DATABASE_URL` automatically.
   - Go to your app service → **Variables** → add all your `.env` values

3. Once deployed, copy the public URL (e.g. `https://myapp.railway.app`)  
   and update `APP_URL` in Railway's variables.

4. Your app auto-restarts whenever you push new code.

---

## Step 3: Verify it works

1. Visit your Railway URL. You should see the landing page.
2. Sign up with your own email. You will get a welcome email with your dashboard link.
3. Open the dashboard and add a YouTube channel (e.g. `https://www.youtube.com/@InvestLikeTheBest`)
4. To test the digest manually, run:

```bash
curl -X POST https://your-app.railway.app/api/admin/trigger-digest \
  -H "X-Admin-Secret: your-ADMIN_SECRET-value"
```

This triggers the digest immediately for all users.

---

## How the weekly digest works

- Every **Saturday at 12:00 PM UTC** the app automatically:
  1. Fetches the last 7 days of videos from each user's subscribed YouTube channels
  2. Pulls transcripts (auto-generated captions)
  3. Sends each transcript to Claude for analysis
  4. Builds a combined email with the 3-section format
  5. Sends via Resend

- If a video has no transcript available, it's skipped
- If no new videos were found for a user that week, no email is sent

---

## Running locally (optional)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python main.py         # starts on http://localhost:8000
```

To run a test digest locally:
```bash
python scheduler.py
```

---

## Popular investing channels to add

| Channel | URL |
|---|---|
| Invest Like the Best | `https://www.youtube.com/@InvestLikeTheBest` |
| We Study Billionaires | `https://www.youtube.com/@theinvestorspodcast` |
| Macro Voices | `https://www.youtube.com/@macrovoices` |
| Real Vision | `https://www.youtube.com/@realvision` |
| Acquired | `https://www.youtube.com/@acquiredfm` |
| BG2 Pod (Chamath/Sacks) | `https://www.youtube.com/@bg2pod` |
| My First Million | `https://www.youtube.com/@MyFirstMillion` |

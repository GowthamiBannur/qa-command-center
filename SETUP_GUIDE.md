# QA Command Center — Setup Guide

## Zero-cost stack
| Service | Purpose | Free limit |
|---|---|---|
| Streamlit Cloud | App hosting | Unlimited |
| Supabase | Database | 500MB / unlimited rows |
| Groq | AI (LLaMA 3.3 70B) | Free tier |
| Gmail SMTP | Email notifications | Free |

---

## Step 1 — Supabase
1. Go to https://supabase.com → New project
2. SQL Editor → paste entire `schema.sql` → Run
3. After running, insert your admin account:
```sql
insert into users (name, email, role, status)
values ('Your Name', 'you@gmail.com', 'admin', 'approved');
```
4. Copy your **Project URL** and **anon key** from Settings → API

---

## Step 2 — Gmail App Password
1. Go to your Google Account → Security
2. Enable **2-Step Verification** (required)
3. Search "App Passwords" → Create one → name it "QA Center"
4. Copy the 16-character password (you only see it once)

---

## Step 3 — Groq API Key
1. Go to https://console.groq.com → API Keys → Create
2. Copy the key

---

## Step 4 — secrets.toml
Create `.streamlit/secrets.toml` locally:

```toml
SUPABASE_URL       = "https://xxxx.supabase.co"
SUPABASE_KEY       = "your-anon-key"
GROQ_API_KEY       = "gsk_xxxx"
GMAIL_ADDRESS      = "you@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
```

**On Streamlit Cloud:** Settings → Secrets → paste the same content.

---

## Step 5 — Deploy
1. Push to GitHub (public or private repo)
2. Go to https://share.streamlit.io → New app → connect repo
3. Add secrets in Streamlit Cloud settings
4. Deploy — your team URL is ready to share!

---

## How team access works
1. Share the app URL with your team
2. Teammate clicks **Request Access** → enters name + email
3. You get an email notification + see it in **👥 Team Access**
4. You click **Approve** → they get an email with login instructions
5. They log in with their email — that's it, no passwords

---

## How email notifications work
- When you mark a test case as **Fail** and create a bug report
- Enter the dev's email in the "Dev Email" field
- Click **🐛 Auto Bug Report** → a form appears to send the email
- Optional CC field for manager/lead
- The email contains: bug summary, severity, steps, expected vs actual, evidence link

## In-app notifications (🔔 bell)
- Every action (audit generated, TC marked fail, bug filed, user approved) creates a notification
- Visible to ALL logged-in users in the sidebar bell
- Blue dot = unread, click "Mark all read" to clear

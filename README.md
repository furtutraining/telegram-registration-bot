# Furtu Training Registration Bot

Trilingual Telegram bot (English / አማርኛ / Afaan Oromoo) for course registration.

---

## Deploy to Railway via GitHub

### 1. Push this repo to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Create a new Railway project
- Go to https://railway.app → **New Project** → **Deploy from GitHub repo**
- Select your repository

### 3. Set Environment Variables in Railway dashboard
Go to your service → **Variables** tab and add:

| Variable     | Required | Example value         | Notes                                      |
|--------------|----------|-----------------------|--------------------------------------------|
| `BOT_TOKEN`  | ✅ Yes   | `7123456789:AAF...`   | Get from @BotFather on Telegram            |
| `CHANNEL_ID` | ❌ No    | `-1001234567890`      | Your Telegram channel ID (negative number) |
| `ADMIN_IDS`  | ❌ No    | `123456,789012`       | Comma-separated Telegram user IDs          |

> ⚠️ **Never** put `BOT_TOKEN` in your code or `.env` file committed to GitHub.

### 4. Deploy
Railway will automatically build and start the bot using `python bot.py`.

---

## Running locally (for testing)

```bash
pip install -r requirements.txt
BOT_TOKEN=your_token_here python bot.py
```

---

## Commands
| Command   | Description                        |
|-----------|------------------------------------|
| `/start`  | Begin or restart registration      |
| `/cancel` | Cancel current registration        |
| `/myid`   | Show your Telegram user/chat ID    |
| `/admin`  | Show registration stats (admins)   |

---

## Notes on Railway storage
Railway's filesystem is **ephemeral** — `registrations.db` and `bot_persistence.pkl`
are recreated on each deploy. This means:
- Conversation state is reset on redeploy (users just need to `/start` again)
- Registration records are lost on redeploy

If you need persistent storage, add a **Railway PostgreSQL** plugin and migrate the DB code to use `psycopg2`.

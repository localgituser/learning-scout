# Learning Scout

A personal AI agent that finds conferences, courses, and learning opportunities tailored to your career goals — then delivers a weekly digest to your Telegram.

No dashboard. No SaaS subscription. Just a Monday morning nudge with things worth your attention — and a quick tap to tell it what to keep or skip.

---

## Setup

### 1. Create your Telegram bot

Open Telegram → search **@BotFather** → `/newbot` → follow the prompts.

You'll get a **bot token**. Also grab your **personal Telegram user ID** by sending `/start` to [@userinfobot](https://t.me/userinfobot).

### 2. Fork and configure

Fork this repo, then edit `config.yaml` with your profile:

```yaml
profile:
  current_role: "Senior Product Manager – Data Platforms"
  target_role: "Group PM / Head of Product"
  career_stage: mid-senior   # early | mid | mid-senior | senior | exec
  years_experience: 10
  topics_of_interest:
    - product strategy
    - AI/ML product management

budget_aud: 3000
regions: [australia, asia-pacific, online]
format_preference: [online, in-person]
commitment: [short, medium]
```

Pay particular attention to `budget_aud`, `regions`, and `format_preference` — these do the most work to improve result quality.

### 3. Add GitHub secrets

In your forked repo → **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | From BotFather |
| `TELEGRAM_CHAT_ID` | Your personal Telegram user ID |

`GITHUB_TOKEN` is provided automatically by Actions — no action needed.

### 4. Deploy the bot to Railway

The Telegram bot is a small always-on process that handles inline button callbacks and text commands.

```bash
railway login
railway init
railway up
```

Set these environment variables in your Railway project:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
GITHUB_TOKEN=<fine-grained PAT with contents:write on this repo>
GITHUB_REPO=your-username/learning-scout
```

> **Note on GITHUB_TOKEN**: For the bot on Railway you need a fine-grained Personal Access Token (not the Actions built-in token). Create one at GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens, scoped to **only this repo** with **Contents: Read and write**.

### 5. Enable the GitHub Actions workflow

The weekly scout runs every Monday at 08:00 Melbourne time (Sunday 22:00 UTC). Enable it under the **Actions** tab.

To test locally before the first live run:

```bash
pip install -e ".[dev]"
python -m learning_scout.main --dry-run
```

`seen.json` is created automatically on first run. Use `/reset` via the Telegram bot to clear history if needed.

---

## How it works

```
config.yaml  →  seen.json (filter)  →  Claude API + web_search
     ↓
Ranked digest (category mix enforced)
     ↓
Telegram: one message per item with [💾 Save] [⏭ Skip] buttons
     ↓
Button tap  →  Railway bot  →  GitHub API  →  seen.json committed
```

---

## Telegram commands

| Command | What it does |
|---|---|
| `/saved` | List everything you've saved |
| `/block <keyword>` | Permanently filter results matching that keyword |
| `/reset` | Clear seen history and start fresh |

---

## Cost

- **Claude API**: typically under $0.50/week for 8–10 search topics
- **Telegram Bot API**: free
- **Railway**: free tier comfortably covers the bot process
- **GitHub Actions**: free for public repos; ~2 minutes of compute per week

---

## Tech stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| AI | Claude API (Sonnet) with `web_search` tool |
| Scheduling | GitHub Actions |
| Config | `config.yaml` |
| Memory | `seen.json` (committed to repo) |
| Delivery | Telegram Bot API |
| Bot hosting | Railway (free tier) |
| Feedback write-back | GitHub Contents API |

---

## Contributing

Pull requests welcome — especially improvements to the prompt, scoring logic, or additional delivery channels (email, Discord).

---

Built by [Kunal Kalra](https://www.linkedin.com/in/kunalkalra).

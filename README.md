# Learning Scout

> **License:** [PolyForm Noncommercial 1.0.0](LICENSE) — free for personal use, no commercial derivatives.
> **Disclaimer:** This software is provided as-is, without warranty of any kind. The author accepts no liability for damages arising from its use, including account suspensions, data loss, or unintended messages. You are responsible for complying with the terms of service of any third-party platforms this bot interacts with (Telegram, Anthropic, etc.). Use at your own risk.

A personal AI agent that finds learning opportunities tailored to your career goals — conferences, courses, webinars, articles, podcasts, community spaces, and more — then delivers a weekly digest to your Telegram.

No dashboard. No SaaS subscription. Just a Monday morning nudge with things worth your attention — and a quick tap to tell it what to keep or skip.

A typical digest looks like:

> 🎯 **Mind the Product Leadership Summit**
> London · Oct 2026 · ~$1,800 AUD
> ⚠️ Early bird closes in 12 days
>
> Matches your goal of moving into a Group PM / Head of Product role.
>
> [💾 Save]   [⏭ Skip]

> 📚 **Reforge: Developing a Growth System**
> Online · Rolling cohorts · ~$2,500 AUD
>
> Relevant given your data platform background and interest in strategic thinking at scale.
>
> [💾 Save]   [⏭ Skip]

> 🎙️ **Locally Optimistic Slack Community**
> Free · Data analytics & data platform practitioners
>
> Active Slack workspace with practitioners from Airbnb, dbt Labs, and Shopify — strong signal-to-noise for senior data platform discussions.
>
> [💾 Save]   [⏭ Skip]

---

## Contents

- [How it works](#how-it-works)
- [Setup](#setup)
- [Configuring your profile](#configuring-your-profile)
- [Telegram commands](#telegram-commands)
- [Memory and feedback](#memory-and-feedback)
- [Cost](#cost)
- [Tech stack](#tech-stack)

---

## How it works

```
config.yaml (your profile, goals, budget)
        ↓
seen.json (everything ever recommended — filtered before scoring)
        ↓
Claude API (web search + relevance + timeliness scoring)
        ↓
Ranked digest (category mix enforced)
        ↓
Telegram: one message per item with [💾 Save] [⏭ Skip] buttons
        ↓
Button tap → Railway bot → GitHub API → seen.json updated and committed
```

GitHub Actions runs the weekly scout job. A small Telegram bot process (hosted free on Railway) handles delivery and button callbacks. No server you own, no database.

---

## Setup

### 1. Create your Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts — you'll get a **bot token** like `123456789:ABCdef...`
3. Grab your **personal Telegram user ID** by sending `/start` to [@userinfobot](https://t.me/userinfobot)

### 2. Fork and clone this repo

```bash
git clone https://github.com/your-username/learning-scout.git
cd learning-scout
```

### 3. Configure your profile

Copy the example config and fill in your details:

```bash
cp config.yaml.example config.yaml
```

`config.yaml` is gitignored — your personal data stays local and is never committed. Edit it with your own role, goals, and preferences. See [Configuring your profile](#configuring-your-profile) below for a full explanation of every field.

### 4. Create a private state repo

`seen.json` tracks every item you've been shown and whether you saved or skipped it. To keep your personal history out of this repo, create a separate **private** GitHub repository — e.g. `your-username/learning-scout-state`. It can be completely empty; the bot will create `seen.json` there on first use.

### 5. Add GitHub secrets

In your forked repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `TELEGRAM_BOT_TOKEN` | From @BotFather in step 1 |
| `TELEGRAM_CHAT_ID` | Your numeric user ID from @userinfobot |
| `CONFIG_YAML` | The full contents of your local `config.yaml` file (see below) |
| `GITHUB_STATE_REPO` | `your-username/learning-scout-state` (the private repo from step 4) |

`GITHUB_TOKEN` is provided automatically by Actions — no action needed for the scout job.

> **Setting `CONFIG_YAML`**: Because `config.yaml` is gitignored (your personal data stays off GitHub), the Actions workflow recreates it at runtime from this secret. Copy the entire contents of your local `config.yaml` and paste it as the secret value.

### 6. Deploy the Telegram bot to Railway

The bot is a small always-on process that listens for Save/Skip button taps and text commands. Railway's free tier is plenty.

```bash
npm install -g @railway/cli   # if you don't have it
railway login
railway init
railway up
```

In your Railway project dashboard, set these environment variables:

| Variable | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Same token as above |
| `TELEGRAM_CHAT_ID` | Same user ID as above |
| `GITHUB_TOKEN` | A fine-grained PAT (see below) |
| `GITHUB_REPO` | `your-username/learning-scout` |
| `GITHUB_STATE_REPO` | `your-username/learning-scout-state` |

> **Creating the Railway GITHUB_TOKEN**: Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token. Set repository access to **Both repositories** (the main repo and the state repo), and grant **Contents: Read and write** on both. This is separate from the Actions token — it lets the Railway bot commit `seen.json` to your state repo when you tap a button.

Every time you tap Save or Skip, the bot commits `seen.json` to your state repo. The included `railway.toml` already sets `watchPatterns` so Railway only redeploys when source code changes — `seen.json` updates are ignored automatically.

### 7. Test locally before the first live run

```bash
pip install -e ".[dev]"
python -m learning_scout.main --dry-run
```

This runs the full pipeline (real Claude API call, real web searches) but prints results to the terminal instead of sending to Telegram. Good way to check your profile produces sensible results before Monday.

### 8. Enable the GitHub Actions workflow

Go to the **Actions** tab in your forked repo and enable workflows. The scout runs automatically every Monday at 08:00 Melbourne time.

You can also trigger it manually any time via **Actions → Learning Scout → Run workflow**.

---

## Configuring your profile

All configuration lives in `config.yaml`. Here's the complete file with every field explained:

```yaml
# ── Who you are ──────────────────────────────────────────────────────────────
profile:
  current_role: "Senior Product Manager – Data Platforms"
  # Your actual job title. The more specific the better — "Senior PM" is less
  # useful than "Senior PM – B2B SaaS, 50-person startup".

  target_role: "Group PM / Head of Product"
  # Where you're trying to get to. Used to weight opportunities that are a
  # stepping stone toward this goal.

  career_stage: mid-senior
  # One of: early | mid | mid-senior | senior | exec
  # Controls the seniority level of content surfaced. "early" finds bootcamps
  # and entry-level conferences; "exec" finds board-level and C-suite content.

  years_experience: 10
  # Used together with career_stage for relevance scoring.

  topics_of_interest:
    - data platforms
    - product strategy
    - AI/ML product management
    - engineering leadership
  # The search engine runs one query per topic per week. Be specific — 
  # "data platforms" surfaces more relevant results than just "data".
  # 4–8 topics is a good range. You can add/remove topics any time.


# ── Budget and logistics ──────────────────────────────────────────────────────
budget_aud: 3000
# Maximum cost (AUD) per opportunity. Items above this are filtered out before
# scoring. Set to null (remove the line) to disable budget filtering.

format_preference:
  - online
  - in-person
# Which formats you'd actually attend. Options: online | in-person
# Remove a format to filter it out entirely — e.g. if you only want online,
# delete the "- in-person" line.

regions:
  - australia
  - asia-pacific
  - online
# Geographic scope. Common values: australia | asia-pacific | online |
# north-america | europe | global. Used as search context, not a hard filter —
# highly relevant global events may still appear.

commitment:
  - short
  - medium
# How much time you're willing to invest per opportunity:
#   short  = 1–2 days (a conference, a workshop)
#   medium = 1 week (an intensive, a short course)
#   long   = multi-week (Reforge cohort, extended program)


# ── Search behaviour ──────────────────────────────────────────────────────────
search:
  topics_per_run: 8
  # How many of your topics_of_interest to search each week. If you have more
  # topics than this, a rotating subset is used each run.

  results_per_topic: 5
  # How many candidates Claude fetches per search query. Higher = more
  # comprehensive but slower and slightly more expensive.

  min_relevance_score: 6
  # Items scored below this (1–10 scale) are dropped before building the
  # digest. 6 is a good default; lower it to 5 if your digests are too sparse.

  digest_size: 8
  # Maximum number of items in each weekly digest. The actual number may be
  # lower if not enough items pass the relevance threshold.


# ── Category mix ─────────────────────────────────────────────────────────────
digest:
  enforce_category_mix: true
  # When true, the digest includes a spread of opportunity types rather than
  # showing 8 Reforge courses. Set to false to rank purely by score.

  categories:
    in_person_events: 1    # physical conferences, summits, workshops
    online_events: 1       # virtual conferences, live webinars, vendor summits
    meetups: 1             # Meetup.com groups, Slack/Discord communities, user groups
    online_courses: 2      # self-paced courses, YouTube playlists, tutorials
    cohort_programs: 1     # Reforge, On Deck, structured cohorts
    books_or_resources: 1  # books, newsletters, articles, podcast episodes
    wildcard: 1            # open-source projects, frameworks, anything high-value
  # These are slot limits, not guarantees. Empty slots stay empty.


# ── Delivery ─────────────────────────────────────────────────────────────────
delivery:
  channel: telegram        # only telegram is supported currently

  send_day: monday
  send_time: "08:00"
  timezone: "Australia/Melbourne"
  # The GitHub Actions cron is set to match this. If you change timezone,
  # update .github/workflows/scout.yml accordingly.

  telegram_chat_id:        # optional — overrides the TELEGRAM_CHAT_ID env var
                           # leave blank to use the GitHub secret
```

### Tips for better results

**Be specific with `topics_of_interest`** — the topics are used directly as search queries. "Product strategy for B2B SaaS" surfaces better results than "strategy". Think about what you'd type into Google.

**Start with a lower `min_relevance_score`** (e.g. 5) for the first few runs, then raise it once you have a feel for what Claude finds. You can always `/skip` mediocre items.

**Use `regions` to reduce noise** — if you're based in Australia and only interested in online or APAC events, remove `north-america` and `europe` from the list. It narrows the search considerably.

**`budget_aud: 0` means free only** — the agent will return only items explicitly marked as free (no cost). Items with unknown pricing ("TBA") are excluded, not snuck through. Set to `null` (or remove the line) to see everything regardless of cost.

---

## Telegram commands

Once the Railway bot is running, you can send these commands directly to your bot in Telegram:

| Command | What it does |
|---|---|
| `/saved` | Shows everything you've saved so far — useful when you're ready to actually register for something |
| `/block <keyword>` | Permanently filters results matching that keyword. E.g. `/block MBA` stops MBA programs appearing in future digests |
| `/reset` | Clears your seen history and starts fresh — useful after a career change or long break |

The Save/Skip buttons in the digest are the main feedback mechanism — no commands needed for day-to-day use.

---

## Memory and feedback

Every item that appears in a digest is written to `seen.json` in your repo. Before the next run, the agent loads this file and filters out anything you've already seen — so you won't see the same Reforge cohort three weeks in a row.

Tapping **Save** or **Skip** in Telegram updates the status in `seen.json` and commits the change back to your repo automatically. You don't touch the file.

```json
{
  "items": [
    {
      "id": "a3f9c2...",
      "title": "Mind the Product Leadership Summit",
      "url": "https://...",
      "first_seen": "2026-06-02",
      "status": "saved"
    }
  ],
  "blocked_keywords": ["MBA"]
}
```

Saved items accumulate until you run `/reset`. Use `/saved` any time to see what you've flagged.

---

## Cost

| Service | Cost |
|---|---|
| Claude API | ~$0.50/week for 8–10 topics |
| Telegram Bot API | Free |
| Railway (bot hosting) | Free tier |
| GitHub Actions | Free for public repos (~2 min/week) |

Total: under $2/month.

---

## Tech stack

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Readable, widely understood |
| AI | Claude API (Sonnet) + `web_search` | Best reasoning + search combo |
| Scheduling | GitHub Actions | Free, version-controlled, no server |
| Config | `config.yaml` | Simple to edit, easy to understand |
| Memory | `seen.json` (in repo) | No external dependency; auditable history |
| Delivery | Telegram Bot API | Free, native inline buttons, two-way |
| Bot hosting | Railway (free tier) | Lightweight always-on process |
| Feedback write-back | GitHub Contents API | Bot commits directly to your repo |

---

## Contributing

Pull requests welcome — especially improvements to the prompt, scoring logic, or additional delivery channels (email, Discord).

If you fork it and adapt it for a different career stage or industry, I'd genuinely like to hear how it's working for you.

---

Built by [Kunal Kalra](https://www.linkedin.com/in/kunalkalra) — Senior Product Manager with a background in data platforms and consumer products.

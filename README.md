# Learning Scout

> **License:** [PolyForm Noncommercial 1.0.0](LICENSE) — free for personal use, no commercial derivatives.
> **Disclaimer:** This software is provided as-is, without warranty of any kind. The author accepts no liability for damages arising from its use, including account suspensions, data loss, or unintended messages. You are responsible for complying with the terms of service of any third-party platforms this bot interacts with (Telegram, Anthropic, Cloudflare, etc.). Use at your own risk.

A personal AI agent that finds learning opportunities tailored to your career goals — conferences, courses, webinars, meetups, and community spaces — then delivers a weekly digest to your Telegram. It also surfaces time-sensitive windows (early bird pricing, CFP deadlines, scholarship applications, cohort enrolments) so you know when to act.

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
> 📋 Enrolment closes: 2026-07-01
>
> Relevant given your data platform background and interest in strategic thinking at scale.
>
> [💾 Save]   [⏭ Skip]

> 👥 **Locally Optimistic Slack Community**
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
Claude API (web search + relevance + timeliness scoring)
        ↓
Ranked digest (category mix enforced)
        ↓
Telegram: one message per item with [💾 Save] [⏭ Skip] buttons
        ↓
Button tap → Cloudflare Worker → Cloudflare KV (seen state updated)
```

GitHub Actions runs the weekly scout job. A Cloudflare Worker (deployed once, runs serverless) handles Telegram webhook callbacks and stores state in Cloudflare KV. No always-on server, no database, no GitHub commits for every button tap.

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

`config.yaml` is gitignored — your personal data stays local and is never committed. See [Configuring your profile](#configuring-your-profile) for a full explanation of every field.

### 4. Deploy the Cloudflare Worker

The Worker receives Telegram button taps, handles commands, and stores your seen history in Cloudflare KV. You need a free [Cloudflare account](https://dash.cloudflare.com/sign-up).

```bash
cd worker
npm install
cp wrangler.toml.example wrangler.toml
```

**Create a KV namespace:**

```bash
npx wrangler kv namespace create STATE
```

Copy the `id` from the output and paste it into `worker/wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "STATE"
id = "paste-your-id-here"
```

**Set Worker secrets** (you'll be prompted to enter each value):

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN   # from @BotFather
npx wrangler secret put TELEGRAM_CHAT_ID     # your numeric user ID
npx wrangler secret put API_SECRET           # run: openssl rand -hex 32
npx wrangler secret put WEBHOOK_SECRET       # run: openssl rand -hex 32
```

**Deploy:**

```bash
npx wrangler deploy
```

Note the Worker URL from the output — it looks like `https://learning-scout-bot.your-subdomain.workers.dev`.

**Register the Telegram webhook** (replace the placeholders):

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<WORKER_URL>/webhook&secret_token=<WEBHOOK_SECRET>"
```

### 5. Add GitHub Actions secrets

In your forked repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com) |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | Your numeric user ID from @userinfobot |
| `CONFIG_YAML` | The full contents of your local `config.yaml` (see note below) |
| `CF_WORKER_URL` | Your Worker URL from step 4 |
| `CF_API_SECRET` | The same value you set as `API_SECRET` in Wrangler |

> **Setting `CONFIG_YAML`**: Because `config.yaml` is gitignored, the Actions workflow recreates it at runtime from this secret. Copy the entire contents of your local `config.yaml` and paste it as the secret value.

### 6. Test locally before the first live run

```bash
pip install -e ".[dev]"
python -m learning_scout.main --dry-run
```

This runs the full pipeline (real Claude API call, real web searches) but prints results to the terminal instead of sending to Telegram. Good way to verify your profile produces sensible results before Monday.

> **Local dry-run needs CF vars**: even in dry-run mode the script reads seen state from Cloudflare KV. Set `CF_WORKER_URL` and `CF_API_SECRET` as local environment variables, or export them in your shell before running.

### 7. Enable the GitHub Actions workflow

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
# Remove a format to filter it out entirely.

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
    in_person_events: 1  # physical conferences, summits, workshops
    online_events: 1     # virtual conferences, live webinars, vendor summits
    meetups: 1           # Meetup.com groups, Slack/Discord communities, user groups
    courses: 3           # self-paced courses, cohort programs, certifications
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

**Start with a lower `min_relevance_score`** (e.g. 5) for the first few runs, then raise it once you have a feel for what Claude finds. You can always skip mediocre items.

**Use `regions` to reduce noise** — if you're based in Australia and only interested in online or APAC events, remove `north-america` and `europe`. It narrows the search considerably.

**`budget_aud: 0` means free only** — the agent returns only items explicitly marked as free. Items with unknown pricing ("TBA") are excluded, not snuck through. Set to `null` (or remove the line) to see everything regardless of cost.

---

## Telegram commands

Send these commands directly to your bot in Telegram:

| Command | What it does |
|---|---|
| `/saved` | Shows everything you've saved — useful when you're ready to actually register for something |
| `/block <keyword>` | Permanently filters results matching that keyword. E.g. `/block MBA` stops MBA programs appearing in future digests |
| `/blocked` | Lists all currently blocked keywords |
| `/reset confirm` | Clears your seen history and starts fresh — useful after a career change or long break |

The Save/Skip buttons in the digest are the main feedback mechanism — no commands needed for day-to-day use.

---

## Memory and feedback

Every item that appears in a digest is stored in Cloudflare KV. Before the next run, the scout reads this state and filters out anything you've already seen — so you won't see the same Reforge cohort three weeks in a row.

Tapping **Save** or **Skip** in Telegram sends a webhook to the Cloudflare Worker, which updates the item's status in KV immediately. You don't touch any files.

The stored state looks like this:

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

Saved items accumulate until you run `/reset confirm`. Use `/saved` any time to see what you've flagged.

---

## Cost

| Service | Cost |
|---|---|
| Claude API | ~$0.50/week for 8–10 topics |
| Telegram Bot API | Free |
| Cloudflare Workers | Free tier (100k requests/day) |
| Cloudflare KV | Free tier (100k reads/day, 1k writes/day) |
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
| State | Cloudflare KV | Serverless, no database, free tier |
| Delivery | Telegram Bot API | Free, native inline buttons, two-way |
| Bot/webhook | Cloudflare Workers | Serverless, no always-on process needed |

---

## Contributing

Pull requests welcome — especially improvements to the prompt, scoring logic, or additional delivery channels (email, Discord).

If you fork it and adapt it for a different career stage or industry, I'd genuinely like to hear how it's working for you.

---

Built by [Kunal Kalra](https://www.linkedin.com/in/kunalkalra) — Senior Product Manager with a background in data platforms and consumer products.

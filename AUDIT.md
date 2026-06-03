# Codebase Audit Report: Learning Scout

Verified against source as of commit `1fac41d`.

---

## Executive Summary & Priority Matrix

| Issue ID | Category | Severity | Description |
| :--- | :--- | :--- | :--- |
| **SEC-01** | Security | **Critical** | Webhook endpoint unauthenticated when `WEBHOOK_SECRET` is unset — spoofed payloads can trigger admin commands. |
| **BUG-03** | Bug | **High** | Past/negative deadlines receive maximum timeliness boost (`+2.0`) due to unbounded `days <= 14` check. |
| **SEC-02** | Security | **High** | URL not HTML-escaped in Worker `/saved` `href` attribute; same gap exists in Python formatter. |
| **BUG-05** | Bug | **Medium** | State overwrite race: Python pipeline's PUT clobbers user saves and blocked-keyword additions made during a run. |
| **BUG-04** | Bug | **Medium** | Worker `/saved` handler has no message length cap, unlike the Python formatter which already limits to 20 items. |
| **REL-01** | Reliability | **Medium** | `callTelegram` silently swallows all Telegram API errors; failed deliveries are undetectable. |
| **SEC-03** | Security | **Medium** | `/state` PUT body accepted via TypeScript type assertion only — no runtime shape validation, malformed payloads can corrupt KV. |
| **BUG-02** | Bug | **Low** | `run_search` fallback `AsyncAnthropic()` client missing beta header — only affects direct/test callers bypassing `main.py`. |
| **BUG-06** | Bug | **Low** | Keyword blocking uses substring matching — "aws" blocks "flaws", "draw", etc. |
| **DUP-01** | Structure | **Low** | State serialization/deserialization logic duplicated between `cf_state_client.py` and `memory.py`. |
| **DX-01** | DX | **Low** | No `.env` auto-loading; developers must export variables manually before running locally. |

---

## Detailed Findings

### Security

#### [SEC-01] Critical: Unauthenticated Webhook Endpoint

**Location:** `worker/src/index.ts:287–292`

The webhook authentication block is conditional on the secret being set:

```typescript
if (env.WEBHOOK_SECRET) {
  const telegramToken = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
  if (telegramToken !== env.WEBHOOK_SECRET) {
    return new Response("Unauthorized", { status: 401 });
  }
}
```

If `WEBHOOK_SECRET` is omitted from production secrets, the entire check is skipped. `isAuthorised()` at lines 117 and 173 provides a secondary defence — it checks that `from.id` matches `TELEGRAM_CHAT_ID` — but Telegram user IDs are numeric and often not treated as secrets, so this cannot be relied on as a sole control.

**Impact:** An attacker who knows the target's Telegram user ID can POST crafted payloads directly to `/webhook` and execute any command including `/reset confirm`, which clears all KV history.

**Remediation:** Make `WEBHOOK_SECRET` mandatory in `wrangler.toml` (remove the `optional` annotation) and error loudly on startup if it is absent. Alternatively, embed the secret in the webhook URL path (`/webhook/<token>`) so the path itself acts as a bearer credential.

---

#### [SEC-02] High: URL Not HTML-Escaped in Anchor `href` Attributes

**Locations:**
- `worker/src/index.ts:193`
- `learning_scout/formatter.py:69`

**Worker (index.ts:193):**
```typescript
`• <a href="${item.url}">${escapeHtml(item.title)}</a>`
```
`item.url` is stored state that originated from LLM output. It is inserted raw into the `href` attribute without any escaping.

**Python formatter (formatter.py:69):**
```python
lines.append(f'<a href="{url}">More info</a>')
```
`url` here is already passed through `_safe_url()`, which rejects non-`https://` schemes by substituting `#`. This is a meaningful partial mitigation — non-HTTP URIs cannot be injected. However, the URL is still not run through `html.escape()`, so a URL containing a literal `"` character (e.g., from a malformed LLM output) would break the HTML attribute boundary and cause Telegram's strict HTML parser to reject the message.

**Remediation:**

Python — chain `html.escape` after `_safe_url`:
```python
url = html.escape(_safe_url(item.url))
```

Worker — add a minimal URL escaper before insertion:
```typescript
function escapeAttr(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}
// usage:
`• <a href="${escapeAttr(item.url)}">${escapeHtml(item.title)}</a>`
```

Note: the existing `escapeHtml` helper (`index.ts:252`) only escapes `&`, `<`, and `>` — it does not escape `"`. It is safe for text-node content but must not be used in attribute context without the `"` → `&quot;` replacement added above.

---

#### [SEC-03] Medium: `/state` PUT Body Has No Runtime Validation

**Location:** `worker/src/index.ts:277–279`

```typescript
const body = (await request.json()) as State;
await putState(env, body);
```

TypeScript type assertions are compile-time only. At runtime, `body` is an unvalidated `unknown`. A `PUT` with `{"items": null, "blocked_keywords": null}` would cause `putState` to crash inside `state.items.filter(...)` (line 84), and depending on error handling, could result in a 500 response while leaving KV in an unknown state. Sending `{"items": [], "blocked_keywords": []}` is a valid denial-of-service that wipes history without authentication beyond the `API_SECRET`.

**Remediation:** Add a runtime shape check before calling `putState`:

```typescript
if (!Array.isArray(body?.items) || !Array.isArray(body?.blocked_keywords)) {
  return new Response("Bad Request", { status: 400 });
}
```

---

### Functional & Logic Bugs

#### [BUG-03] High: Past Deadlines Receive Maximum Timeliness Score Boost

**Location:** `learning_scout/scorer.py:10–14`

```python
days = (item.deadline - today).days
if days <= 14:
    return 2.0
if days <= 30:
    return 1.0
```

When a deadline is in the past, `days` is a negative integer. The condition `days <= 14` is still `True`, so expired deadlines receive the maximum `+2.0` boost and sort to the top of the digest. The formatter's `_deadline_text` does suppress the deadline label for past dates (formatter.py:48–49), so the date won't appear in the message, but the score inflation is invisible to the user and promotes stale content.

**Remediation:**
```python
if 0 <= days <= 14:
    return 2.0
if 0 <= days <= 30:
    return 1.0
```

---

#### [BUG-04] Medium: Worker `/saved` Has No Message Length Cap

**Location:** `worker/src/index.ts:180–199`

The Worker sends all saved items in a single Telegram message. The Python formatter (`formatter.py:82`) already handles this:

```python
for i, item in enumerate(saved[-20:], 1):  # cap at 20 to stay under Telegram's 4096-char limit
```

The Worker port of the same command omits this cap entirely. A user with more than roughly 30–40 saved items will hit Telegram's 4096-character limit, causing message delivery to fail silently (no error is surfaced — see REL-01).

**Remediation:** Slice before mapping:
```typescript
const display = saved.slice(0, 20);
const lines = display.map((item) => `• <a href="${item.url}">${escapeHtml(item.title)}</a>`).join("\n");
```

---

#### [BUG-05] Medium: Full-State Overwrite Race Drops User Interactions

**Location:** `learning_scout/main.py:30–61`

The pipeline flow is:
1. `fetch_state()` — read full state from KV (~3 seconds)
2. `run_search()` — 2–3 minutes of concurrent searches
3. `push_state()` — write full state back to KV

During step 2, a user can tap Save/Skip on a digest item or send `/block <keyword>` via Telegram. These updates land in KV via the Worker. When step 3 executes, it sends the state snapshot taken in step 1 — overwriting and losing all mid-run interactions. This affects both item statuses (`saved`/`skipped`) and the `blocked_keywords` list.

**Remediation:** Add a merge step before pushing:

```python
fresh_seen, fresh_blocked = await fetch_state(_cf_config())
# Merge: let user interactions (fresh state) win over pipeline's new items
for item_id, item in seen.items():
    if item_id not in fresh_seen:
        fresh_seen[item_id] = item
for kw in fresh_blocked:
    if kw not in blocked:
        blocked.append(kw)
await push_state(fresh_seen, blocked, _cf_config())
```

A cleaner long-term fix is a delta endpoint (`POST /state/items/:id/status`) so the pipeline only writes new items and never touches existing ones.

---

#### [BUG-06] Low: Keyword Blocking Uses Substring Matching

**Location:** `learning_scout/memory.py:82–85`

```python
if not any(kw in i.title.lower() or kw in i.description.lower() for kw in blocked)
```

Plain substring matching means blocking `"aws"` also blocks items mentioning "flaws", "draws", "drawstring", etc. The same pattern applies to the Worker's `/block` storage — the Worker stores the keyword, and the Python side applies the filter.

**Remediation:** Wrap the check in a word-boundary regex:

```python
import re

def _is_blocked(text: str, keywords: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE) for kw in keywords)
```

---

### Reliability

#### [REL-01] Medium: Telegram API Errors Are Silently Dropped

**Location:** `worker/src/index.ts:91–101`

```typescript
async function callTelegram(token, method, body) {
  await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
```

The response is never inspected. A rate-limit (429), bad token (401), or message-too-long (400) all result in a silent no-op. This is why BUG-04 fails silently rather than surfacing an error. It also means that if `TELEGRAM_BOT_TOKEN` is misconfigured, the Worker will return `200 OK` to Telegram for every update while delivering nothing.

**Remediation:**

```typescript
async function callTelegram(token: string, method: string, body: Record<string, unknown>): Promise<void> {
  const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error(`Telegram ${method} failed ${res.status}: ${text}`);
  }
}
```

---

### Code Quality & Structure

#### [BUG-02] Low: `run_search` Fallback Client Missing Beta Header

**Location:** `learning_scout/scout.py:160–161`

```python
if client is None:
    client = AsyncAnthropic()
```

The `web_search_20250305` tool requires `"anthropic-beta": "web-search-2025-03-05"` on the client. The production path in `main.py:31–35` always constructs a correctly configured client and passes it in, so this is not a production bug. However, any test or script that calls `run_search(config)` directly without a client will crash at the Anthropic API level.

**Remediation:**
```python
if client is None:
    client = AsyncAnthropic(
        default_headers={"anthropic-beta": "web-search-2025-03-05"},
    )
```

---

#### [DUP-01] Low: State Serialization Duplicated Across Modules

**Locations:** `learning_scout/cf_state_client.py:22–37` and `learning_scout/memory.py:20–51`

Both modules implement identical logic for mapping the `{"items": [...], "blocked_keywords": [...]}` JSON structure to/from `dict[str, SeenItem]`. A change to the data format (e.g., adding a field to `SeenItem`) requires parallel edits in both files.

**Remediation:** Extract `_serialize` / `_deserialize` into `models.py` or a dedicated `state_serde.py`. Both `memory.save_seen`/`load_seen` and `cf_state_client.push_state`/`fetch_state` become thin wrappers around shared helpers.

---

#### [DX-01] Low: No `.env` Auto-Loading for Local Development

**Location:** `learning_scout/main.py`

Environment variables are consumed via `os.environ[...]` but the script does not load `.env` automatically. Developers must export all variables in their shell before running, which is error-prone and inconsistent with the `.env.example` provided.

**Remediation:** Add `python-dotenv` to the dev dependencies and call `load_dotenv()` near the top of `main.py`:

```python
from dotenv import load_dotenv
load_dotenv()
```

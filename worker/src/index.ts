/**
 * Cloudflare Worker — Learning Scout bot + state API
 *
 * Routes:
 *   GET  /state          Internal API for GitHub Actions scout to load seen state
 *   PUT  /state          Internal API for GitHub Actions scout to save seen state
 *   POST /webhook        Telegram webhook (button callbacks + text commands)
 *
 * KV layout:
 *   "seen_state"  →  JSON: { items: SeenItem[], blocked_keywords: string[] }
 */

interface Env {
  STATE: KVNamespace;
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
  API_SECRET: string;
  WEBHOOK_SECRET: string; // optional; set when registering the webhook
}

// ── State types (mirror learning_scout/models.py) ──────────────────────────

type ItemStatus = "saved" | "skipped" | "blocked";

interface SeenItem {
  id: string;
  title: string;
  url: string;
  first_seen: string;
  status: ItemStatus;
  saved_at?: string;
}

interface State {
  items: SeenItem[];
  blocked_keywords: string[];
}

// ── Telegram update types (minimal) ────────────────────────────────────────

interface TelegramUpdate {
  update_id: number;
  callback_query?: TelegramCallbackQuery;
  message?: TelegramMessage;
}

interface TelegramCallbackQuery {
  id: string;
  from?: { id: number };
  data?: string;
  message?: TelegramInlineMessage;
}

interface TelegramInlineMessage {
  message_id: number;
  chat: { id: number };
  text?: string;
}

interface TelegramMessage {
  message_id: number;
  from?: { id: number };
  chat: { id: number };
  text?: string;
}

// ── KV helpers ──────────────────────────────────────────────────────────────

async function getState(env: Env): Promise<State> {
  const raw = await env.STATE.get("seen_state");
  if (!raw) return { items: [], blocked_keywords: [] };
  try {
    return JSON.parse(raw) as State;
  } catch {
    return { items: [], blocked_keywords: [] };
  }
}

async function putState(env: Env, state: State): Promise<void> {
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() - 1);
  const pruned: State = {
    ...state,
    items: state.items.filter(item => new Date(item.first_seen) >= cutoff),
  };
  await env.STATE.put("seen_state", JSON.stringify(pruned));
}

// ── Telegram API helper ─────────────────────────────────────────────────────

async function callTelegram(
  token: string,
  method: string,
  body: Record<string, unknown>
): Promise<void> {
  await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ── Auth ─────────────────────────────────────────────────────────────────────

function isAuthorised(userId: number | undefined, allowedChatId: string): boolean {
  return String(userId) === String(allowedChatId);
}

// ── Callback query handler (Save / Skip buttons) ───────────────────────────

const HASH_LEN = 16;
const ALLOWED_ACTIONS = new Set(["save", "skip"]);
const ACTION_TO_STATUS: Record<string, ItemStatus> = { save: "saved", skip: "skipped" };
const ACTION_LABEL: Record<string, string> = { save: "💾 Saved!", skip: "⏭ Skipped" };

async function handleCallbackQuery(query: TelegramCallbackQuery, env: Env): Promise<void> {
  if (!isAuthorised(query.from?.id, env.TELEGRAM_CHAT_ID)) return;

  const data = query.data ?? "";
  const colonIdx = data.indexOf(":");
  if (colonIdx === -1) {
    await callTelegram(env.TELEGRAM_BOT_TOKEN, "answerCallbackQuery", { callback_query_id: query.id });
    return;
  }

  const action = data.slice(0, colonIdx);
  const hashPrefix = data.slice(colonIdx + 1, colonIdx + 1 + HASH_LEN);

  if (!ALLOWED_ACTIONS.has(action) || !hashPrefix) {
    await callTelegram(env.TELEGRAM_BOT_TOKEN, "answerCallbackQuery", { callback_query_id: query.id });
    return;
  }

  const state = await getState(env);
  const candidates = state.items.filter((item) => item.id.startsWith(hashPrefix));

  if (candidates.length !== 1) {
    await callTelegram(env.TELEGRAM_BOT_TOKEN, "editMessageText", {
      chat_id: query.message?.chat.id,
      message_id: query.message?.message_id,
      text: "⚠️ Item not found — it may have expired.",
    });
    await callTelegram(env.TELEGRAM_BOT_TOKEN, "answerCallbackQuery", { callback_query_id: query.id });
    return;
  }

  const matched = candidates[0];
  matched.status = ACTION_TO_STATUS[action];
  if (action === "save") {
    matched.saved_at = new Date().toISOString();
  }
  await putState(env, state);

  const label = ACTION_LABEL[action];
  const originalText = query.message?.text ?? "";
  await callTelegram(env.TELEGRAM_BOT_TOKEN, "editMessageText", {
    chat_id: query.message?.chat.id,
    message_id: query.message?.message_id,
    text: `${originalText}\n\n${label}`,
    disable_web_page_preview: true,
  });
  await callTelegram(env.TELEGRAM_BOT_TOKEN, "answerCallbackQuery", {
    callback_query_id: query.id,
    text: label,
  });
}

// ── Message handler (text commands) ────────────────────────────────────────

const MAX_KEYWORD_LEN = 100;

async function handleMessage(message: TelegramMessage, env: Env): Promise<void> {
  if (!isAuthorised(message.from?.id, env.TELEGRAM_CHAT_ID)) return;

  const text = message.text ?? "";
  const chatId = message.chat.id;

  if (text.startsWith("/saved")) {
    const state = await getState(env);
    const saved = state.items
      .filter((item) => item.status === "saved")
      .sort((a, b) => {
        const ta = a.saved_at ?? a.first_seen;
        const tb = b.saved_at ?? b.first_seen;
        return tb.localeCompare(ta);
      });
    if (saved.length === 0) {
      await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
        chat_id: chatId,
        text: "No saved items yet.",
      });
    } else {
      const lines = saved.map((item) => `• <a href="${item.url}">${escapeHtml(item.title)}</a>`).join("\n");
      await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
        chat_id: chatId,
        text: `<b>Saved items (${saved.length})</b>\n\n${lines}`,
        parse_mode: "HTML",
        disable_web_page_preview: true,
      });
    }
  } else if (text.startsWith("/block ")) {
    const keyword = text.slice("/block ".length).trim().slice(0, MAX_KEYWORD_LEN).toLowerCase();
    if (!keyword) {
      await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
        chat_id: chatId,
        text: "Usage: /block <keyword>",
      });
      return;
    }
    const state = await getState(env);
    if (!state.blocked_keywords.includes(keyword)) {
      state.blocked_keywords.push(keyword);
    }
    await putState(env, state);
    await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
      chat_id: chatId,
      text: `🚫 Blocked: "${keyword}". It won't appear in future digests.`,
    });
  } else if (text === "/blocked" || text.startsWith("/blocked ")) {
    const state = await getState(env);
    if (state.blocked_keywords.length === 0) {
      await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
        chat_id: chatId,
        text: "No blocked keywords.",
      });
    } else {
      const list = state.blocked_keywords.map((kw) => `• ${escapeHtml(kw)}`).join("\n");
      await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
        chat_id: chatId,
        text: `<b>Blocked keywords:</b>\n\n${list}`,
        parse_mode: "HTML",
      });
    }
  } else if (text === "/reset" || text.startsWith("/reset ")) {
    const args = text.split(" ").slice(1);
    if (args[0]?.toLowerCase() !== "confirm") {
      await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
        chat_id: chatId,
        text: "⚠️ This clears <b>all</b> seen history. To confirm, send:\n<code>/reset confirm</code>",
        parse_mode: "HTML",
      });
      return;
    }
    await putState(env, { items: [], blocked_keywords: [] });
    await callTelegram(env.TELEGRAM_BOT_TOKEN, "sendMessage", {
      chat_id: chatId,
      text: "♻️ History cleared. Next digest starts fresh.",
    });
  }
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── Main fetch handler ──────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Internal state API — used by GitHub Actions scout
    if (url.pathname === "/state") {
      const secret = request.headers.get("X-API-Secret");
      if (secret !== env.API_SECRET) {
        return new Response("Unauthorized", { status: 401 });
      }

      if (request.method === "GET") {
        const state = await getState(env);
        return new Response(JSON.stringify(state), {
          headers: { "Content-Type": "application/json" },
        });
      }

      if (request.method === "PUT") {
        const body = (await request.json()) as State;
        await putState(env, body);
        return new Response("OK");
      }

      return new Response("Method not allowed", { status: 405 });
    }

    // Telegram webhook
    if (url.pathname === "/webhook" && request.method === "POST") {
      if (env.WEBHOOK_SECRET) {
        const telegramToken = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
        if (telegramToken !== env.WEBHOOK_SECRET) {
          return new Response("Unauthorized", { status: 401 });
        }
      }

      const update = (await request.json()) as TelegramUpdate;

      if (update.callback_query) {
        await handleCallbackQuery(update.callback_query, env);
      } else if (update.message) {
        await handleMessage(update.message, env);
      }

      return new Response("OK");
    }

    return new Response("Not found", { status: 404 });
  },
};

# Security Policy

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities (exposed tokens, injection risks, etc.).

Email: kalrakunal@outlook.com

I will respond within 7 days. As a personal project with no commercial backing, fixes are made on a best-effort basis.

## Scope

The main risks in this project are:

- **Credentials in config**: `config.yaml` and `.env` are gitignored. Never commit them.
- **Telegram bot token exposure**: If your token is compromised, revoke it immediately via [@BotFather](https://t.me/BotFather).
- **GitHub Actions secrets**: Rotate via the repo Settings → Secrets page.

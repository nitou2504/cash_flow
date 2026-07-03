# Telegram Bot

A companion chatbot for tracking expenses on-the-go, with support for shared household finances via delegate users. Requires an [LLM provider](llm.md) since it parses natural language.

## Quick setup

1. **Get a bot token** from [@BotFather](https://t.me/BotFather) (`/newbot`).

2. **Add to `.env`**:

   ```bash
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_ALLOWED_USERS=123456789,987654321
   GEMINI_API_KEY=your_gemini_key_here
   ```

   `TELEGRAM_ALLOWED_USERS` is the allowlist — unauthorized users are rejected and logged. If empty, the bot is open to anyone, so always set it in production. Find your ID via [@userinfobot](https://t.me/userinfobot).

3. **Start**: `python3 bot.py`

### Docker deployment

```bash
python3 cli.py bot restart        # rebuild + restart container
# or
docker compose -f docker-compose.bot.yml up -d --build
```

The container mounts the project directory, sharing the same `cash_flow.db` as the CLI and web app. Local Ollama is reachable via `LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434`.

Management: `cli.py bot restart | logs [-f] | stop`.

## Usage

Send messages like:

- `"Spent 50 on groceries today"`
- `"Bought laptop for 1200 in 12 installments on Visa"`
- `"Split: 30 on groceries, 15 on snacks"`

The bot parses with the same LLM backend as the CLI, shows a preview with inline buttons, and lets you **Confirm** or **Revise** (in natural language) before saving.

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and reset state |
| `/help` | Usage instructions |
| `/summary` | Budget envelope view for the current month |
| `/summary October` | Budget view for a specific month |
| `/cancel` | Cancel current transaction |
| `/review` | Review flagged transactions (approve or edit with LLM) |
| `/lang` | Switch language (English / Spanish) |

`/summary` shows per-month budget envelopes with spent/remaining and navigation buttons to browse months or toggle a planning/pending view.

### Language

English and Spanish. Set a default with `TELEGRAM_DEFAULT_LANG=es`, or per-user at runtime with `/lang` (persisted in the database).

### Review flow

`/review` shows one flagged transaction at a time with inline buttons:

- **Approve** — clears the `needs_review` flag
- **Edit** — natural language editing (same flow as `cli.py edit <id> "..."`), with a before/after diff and confirmation
- **Skip** / **Done**

## Extra users (delegates)

Family members can log transactions through the same bot. Their transactions are tagged with a source and flagged for review.

```bash
# TELEGRAM_EXTRA_USER_<NAME>=telegram_user_id,default_account,default_budget_name[,no_budget_phrase]
TELEGRAM_EXTRA_USER_MOM=987654321,Visa Pichincha,Home Groceries
TELEGRAM_EXTRA_USER_DAD=222222,Cash,Personal
# With optional no-budget phrase (LLM fuzzy match handles dictation typos):
TELEGRAM_EXTRA_USER_MOM=987654321,Visa Pichincha,Home Groceries,de mateo
```

- `<NAME>` becomes the `source` tag on transactions (`MOM` → `mom`)
- Extra users are automatically authorized — no need to add them to `TELEGRAM_ALLOWED_USERS`
- The configured account is appended to the message for payment date resolution; the budget is resolved in code to the active period (not by the LLM — prevents category pollution)
- If `no_budget_phrase` is set, a parallel small-model LLM call checks for a fuzzy match — if found, the budget is omitted (e.g. "de mateo" / "de matteo" / "de mateos")

**How it works**:

1. Mom sends `supermaxi 25.50`
2. The bot appends her account, parses via the normal LLM flow, tags `source=mom`, `needs_review=1`
3. The transaction is **auto-saved** — she gets a compact reply with date, amount, and remaining budget
4. The owner gets a notification, then approves via `/review` in the bot, `cli.py review`, or the web Review page

**Simplified `/summary` for extra users**: shows only their configured budget, no planning toggle, defaults to the current payment month for their account.

### Auto-confirm behavior (`TELEGRAM_AUTO_CONFIRM`)

| Value | Behavior |
|---|---|
| `extra_users_only` (default) | Extra users auto-save; owner gets preview + confirm/revise |
| `all` | Everyone auto-saves |
| `none` | Everyone gets preview + confirm/revise |

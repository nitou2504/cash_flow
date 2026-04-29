# Cash Flow — Agent Guide

Personal finance CLI app. Budget envelopes, CC billing-cycle awareness, single timeline forecasting real cash position. SQLite backend, LLM-powered natural language input, Telegram bot, Gmail invoice pipeline.

## Project Layout

```
cli.py                  # Main CLI entry point (all commands)
bot.py                  # Telegram bot
cash_flow.db            # Single SQLite database (all tables)
llm_config.yaml         # LLM model routing config

cashflow/               # Core domain
  config.py             # Paths, backup settings, Telegram user config
  database.py           # Schema creation, migrations (all tables incl invoices/consumos)
  repository.py         # All SQL queries (CRUD)
  controller.py         # Business logic orchestration
  transactions.py       # Transaction factory functions
  backup.py             # Auto/manual backup with retention
  invoice_database.py   # Compatibility shim → database.py
  invoice_repository.py # Invoice CRUD
  consumo_database.py   # Compatibility shim → database.py
  consumo_repository.py # Consumo CRUD

llm/
  backend.py            # LLMBackend singleton (LiteLLM wrapper, per-function routing)
  parser.py             # All LLM parsing functions

ui/
  cli_display.py        # Rich table rendering for CLI
  interactive.py        # Interactive TUI prompts (no LLM needed)
  telegram_format.py    # Telegram Markdown formatters
  strings.py            # i18n strings (en/es)

gmail_sync/             # Gmail integration
  auth.py               # OAuth2 (gmail.readonly scope)
  client.py             # GmailClient wrapper
  parsers.py            # CC consumo email parsers (Pichincha/Diners/Produbanco/Cash)
  invoice.py            # SRI XML parser (3 schema families)
  ingest_consumos.py    # Consumos/* labels → consumos table
  ingest_invoices.py    # Facturas label → invoices table
  register_consumos.py  # Auto-register consumos → cash_flow.db transactions
  scheduled.py          # Scheduled Gmail sync job (PTB JobQueue)
  inspect_label.py      # Debug: eyeball email format
  verify.py             # Setup: test auth + list labels

tests/                  # 37 pytest files, use in-memory SQLite via create_test_db()
specs/                  # Design docs
extra/                  # Bank statements, utility scripts, invoice XML cache
backups/                # Auto + manual DB backups
```

## CLI Commands

Entry point: `python3 cli.py COMMAND`. All commands run `controller.run_monthly_rollover()` on startup.

### Adding transactions

```bash
# LLM natural language (uses Gemini/Ollama)
cli.py add "pichincha, apr 22, Coral groceries, home food home groc budget, 5.94" -y

# No-LLM explicit creation (preferred for automation/scripting)
cli.py create tx "Description" AMOUNT ACCOUNT -c CATEGORY -b BUDGET_ID -d YYYY-MM-DD
cli.py create tx "GMO lenses" 180.00 "Visa Pichincha" -c Home -b budget_home_mortgage -d 2026-04-24 -n 6

# Interactive guided entry (no LLM)
cli.py add -i

# CSV import
cli.py add --import file.csv
cli.py add --import installments.csv --installments
```

`create tx` flags: `-c` category, `-b` budget, `-d` date, `-n` installments, `--start-installment`, `--grace-period`, `--income`, `--pending`, `--planning`, `--source`, `--needs-review`

### Other commands

| Command | Aliases | Key flags |
|---------|---------|-----------|
| `view` | `v` | `-m` months, `-f` from, `-s` summary, `-c` created-view, `-p` include-planning |
| `edit` | `e` | `ID [instruction]`, `-d` desc, `-a` amount, `-D` date, `-c` cat, `-b` budget, `--all` group |
| `delete` | `del`, `d` | `ID`, `--all` group |
| `clear` | `cl` | `ID`, `--all` — commit pending/planning |
| `accounts` | `acc`, `a` | `list`, `add`, `adjust-billing ACCT YYYY-MM CUT_OFF -p PAY_DAY` |
| `categories` | `cat`, `c` | `list`, `add`, `edit`, `delete` |
| `subscriptions` | `sub`, `s` | `list [--all\|--budgets-only]`, `add`, `edit`, `delete` |
| `fix` | `f` | `--balance AMOUNT [--account]`, `--payment ACCOUNT [month] [amount]` |
| `liabilities` | `liab`, `owe` | `-m` months, `-d` detail, `-s` summary |
| `review` | `rv` | `[ls\|ID]`, `clear`, filter flags |
| `export` | `exp`, `x` | CSV export |
| `backup` | `bk` | `[name]`, `list`, `restore FILE` |

## Data Model

Single SQLite database (`cash_flow.db`) holds all tables: transactions, accounts, subscriptions, invoices, consumos, llm_decisions. On first run, if legacy `invoices.db` or `consumos.db` exist, they are auto-migrated and renamed to `.migrated`.

Consumos link directly to transactions via `consumos.registered_txn_id` column (no bridge table). Link metadata: `link_source`, `linked_at`, `matched_invoice_number`, `matched_at`.

### Accounts

| Account | Type | Cut-off | Payment | Cycle |
|---------|------|---------|---------|-------|
| Cash | cash | — | — | Same day |
| Visa Pichincha | credit_card | 13 | 1 | Purchase before 13th → pay 1st next month |
| Diners | credit_card | 18 | 3 | Purchase before 18th → pay 3rd next month |
| Visa Produbanco | credit_card | 30 | 15 | Purchase before 30th → pay 15th next month |

### Transaction fields

- `date_created`: purchase date
- `date_payed`: when money moves. Cash = same as created. CC = billing formula based on cut-off/payment days
- `amount`: negative = expense, positive = income
- `status`: `committed` (real), `pending` (unconfirmed, excluded from balance), `planning` (what-if), `forecast` (auto-generated, becomes committed on rollover)
- `budget`: FK to subscriptions.id — links expense to a budget envelope
- `origin_id`: groups installments/splits (UUID) or budget allocations (= subscription id)
- `source`: NULL for owner, name string for delegate users (e.g. "mom")

### Categories (12 active)

Dining-Snacks, Family Support, Health, Home, Home Food & Supplies, Income, Loans, Others, Personal, Personal Diet, Savings, Sister Education

## Budget Envelope System

Core concept: budgets are live transactions, not separate tracking.

1. Budget subscription created with `is_budget=1`, `monthly_amount`, `underspend_behavior` (keep/return)
2. Forecast generates allocation transaction each month: `amount = -monthly_amount`, `status = forecast`
3. When expense links to budget via `budget` field, **absorption** happens:
   - Allocation absorbs expense: `new_alloc = alloc + abs(expense)` (moves toward 0)
   - Capped at 0 (overspend doesn't go positive)
4. Running balance shows real disposable cash (money already earmarked doesn't count)

### Key budgets

| ID | Name | Amount | Account | Category |
|----|------|--------|---------|----------|
| `budget_home_mortgage` | Home Mortgage | $150/mo | Cash | Home |
| `budget_mercado_groceries` | Mercado | $80/mo | Cash | Home Food |
| `budget_home_food_supplies_*` | Home Food & Supplies | $220/mo | Cash | Home Food |
| `budget_personal_diet_*` | Personal Diet | $60/mo | Cash | Personal Diet |

Per-month budgets follow pattern: `budget_{name}_{month}_{year}` (auto-renamed when end_date set).

### Underspend behavior

- **keep**: leftover stays reserved (allocation stays negative)
- **return**: at month end, creates positive "Budget Release" transaction and zeroes allocation

## CC Billing Date Calculation

`_calculate_credit_card_payment_date(date_created, cut_off_day, payment_day)`:

All current accounts: payment_day < cut_off_day (next-month cycle):
- Purchase day ≤ cut_off → pay next month on payment_day
- Purchase day > cut_off → pay month+2 on payment_day

Grace period: shifts effective date forward N months before applying billing formula.

One-off adjustment: `cli.py accounts adjust-billing ACCOUNT YYYY-MM CUT_OFF -p PAY_DAY`

## Gmail Sync

### Labels → Parsers

| Gmail Label | Bank | Parser | Account |
|-------------|------|--------|---------|
| `Consumos/Pichincha` | Pichincha | `parse_pichincha()` | Visa Pichincha |
| `Consumos/Diners` | Diners | `parse_diners()` | Diners |
| `Consumos/Produbanco` | Produbanco | `parse_produbanco()` | Visa Produbanco |
| `Consumos/Cash` | — | Bank transfer notifications | Cash |
| `Facturas` | SRI invoices | `parse_sri_factura()` | — |

### Consumo email parsers (`parsers.py`)

Each returns `EmailTxn(msg_id, bank, account, purchased_at, amount, merchant, card_last, subject)` or None.

- Pichincha/Diners: structured labels (Valor, Fecha YYYY-MM-DD HH:MM, Establecimiento, Tarjeta)
- Produbanco: regex-based, two date formats (Spanish month `4/Abril/2026` or MM/DD/YYYY), skips reversals
- Cash (Consumos/Cash): Pichincha transfer notifications — parse Fecha, Cuenta acreditada, Beneficiario, Monto, Concepto

### Ingest workflows

```bash
# Consumo emails → consumos table
python3 -m gmail_sync.ingest_consumos --since-last
python3 -m gmail_sync.ingest_consumos --after 2025-01-01  # bulk
python3 -m gmail_sync.ingest_consumos --show-unparsed
python3 -m gmail_sync.ingest_consumos --rematch           # re-match invoices

# Facturas XML → invoices table
python3 -m gmail_sync.ingest_invoices --since-last
python3 -m gmail_sync.ingest_invoices --after 2025-01-01  # bulk
python3 -m gmail_sync.ingest_invoices --show-unparsed
```

### Invoice system

SRI electronic invoices (Ecuador). Parsed from XML attachments in Facturas label.
- 3 XML schema families: bare `<factura>`, `<autorizacion>` CDATA wrap, SOAP envelope
- Stores: invoice_number, vendor, issue_date, total, line items, taxes, forma_pago
- Supports `nota_credito` (credit notes / refunds)
- XML cache at `extra/invoices/`

## LLM Integration

### Model routing (`llm_config.yaml`)

| Function | Provider/Model | Purpose |
|----------|---------------|---------|
| `pre_parse_date_and_account` | ollama/llama3.2:3b | Quick date+account extraction (free, 0.8s) |
| `parse_transaction_string` | gemini/gemini-2.5-flash | Full transaction parsing |
| `parse_subscription_string` | gemini/gemini-2.5-flash | Budget/subscription creation |
| `parse_account_string` | gemini/gemini-2.5-flash | Account creation |
| `check_no_budget` | ollama/llama3.2:3b | Fuzzy phrase detection |

- Multiple Gemini API keys rotated randomly (`GEMINI_API_KEY_1` through `_4`)
- `_clean_llm_response()` strips `<think>` tags and markdown fencing from local models
- Two-step add: pre_parse extracts date+account cheaply, then full parse with budget filtering by payment month

## Telegram Bot

Commands: `/start`, `/help`, `/cancel`, `/summary [month]`, `/lang`, `/review`

User types:
- **Owner** (`TELEGRAM_ALLOWED_USERS`): full flow with confirm/revise/cancel
- **Extra users** (`TELEGRAM_EXTRA_USER_<NAME>`): auto-confirmed, tagged with source, needs_review=1
- Extra users have optional `no_budget_phrase` for purchases on behalf of others

## Testing

```bash
pytest tests/                    # all tests
pytest tests/test_budgets.py     # specific
```

Tests use `create_test_db()` (in-memory SQLite). Mock patches use full paths: `patch('cashflow.controller.date')`.

## Common Patterns

### Registering transactions from Gmail

Auto-registration pipeline (`gmail_sync/register_consumos.py`):
1. Scheduled sync runs at midnight+midday via `gmail_sync/scheduled.py` (PTB JobQueue)
2. Consumos matched to subscriptions/existing txns are linked (no new txn created)
3. Unmatched consumos: deterministic rules (`register_rules.yaml`) → LLM (gemma4:e2b, think=False)
4. LLM decisions logged in `llm_decisions` table (prompt, response, category)
5. Budget auto-assigned via `category_budget_map` in rules, resolved by payment month
6. All auto-registered txns get `needs_review=1`, `source="gmail"`

Manual registration: `python3 -m gmail_sync.register_consumos --after YYYY-MM-DD [--dry-run] [--no-llm] [--limit N]`
Manual per-txn: `python3 cli.py create tx` with `-n` for installments, `-b` for budget

### Known account mappings

- Father's account 6634 (Sanchez Rueda Pedro Jose) — real transfers, usually mercado/home budget
- Ana's account 2210 — transfers for various purposes
- Own accounts: 1057 (savings), 7788, 9911
- CC numbers: 4477 (Visa Pichincha), 3355 (Produbanco), 8811 (Diners)

### Interbank CC payment fees

Each interbank CC payment: $0.34 comision + $0.05 IVA = $0.39

### Subscription conventions

- Spotify: $8.04/mo (incl 15% IVA, uses ×1.15 all-inclusive convention)
- $20 transfers to father (6634) from budget_mercado_groceries

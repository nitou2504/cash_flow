# Architecture

## Technology stack

- **Backend**: Python 3.10+, FastAPI + uvicorn (web API), SQLite (single `cash_flow.db`)
- **Frontend**: React 19 + TypeScript + Vite (built output committed to `static/`)
- **CLI**: `argparse` + `rich`
- **Telegram bot**: `python-telegram-bot`
- **LLM**: [LiteLLM](https://github.com/BerriAI/litellm) — Gemini, Ollama, OpenAI, Anthropic, …
- **Gmail**: Google API client, OAuth2 read-only scope
- **Testing**: pytest, in-memory SQLite
- **Deployment**: Docker Compose (web app and bot as separate services)

## Project layout

```
cash_flow/
├── cli.py                      # CLI entry point
├── bot.py                      # Telegram bot entry point
├── api/                        # FastAPI backend for the web app
│   ├── app.py                  #   App factory, SPA static serving, lifespan (rollover + scheduler)
│   ├── auth.py                 #   Password login, JWT session cookie, rate limiting
│   └── routers/                #   dashboard, transactions, accounts, categories, budgets,
│                               #   subscriptions, review, invoices, settings, gmail, fixes
├── web/                        # React frontend source (Vite)
│   └── src/pages/              #   Dashboard, Transactions, Review, Invoices, Subscriptions, Settings
├── static/                     # Built frontend (committed; served by FastAPI)
├── sync/scheduler.py           # In-process scheduled Gmail sync (midnight + midday)
├── cashflow/                   # Core domain
│   ├── controller.py           #   Orchestration (transaction processing, rollover, budgets)
│   ├── transactions.py         #   Transaction factory functions (installments, splits, CC dates)
│   ├── repository.py           #   Data access layer (all SQL)
│   ├── database.py             #   Schema, migrations, test DB factory
│   ├── backup.py               #   Auto/manual backups with retention
│   └── config.py               #   Env config
├── llm/
│   ├── backend.py              #   LLMBackend singleton (LiteLLM, key rotation, fallbacks)
│   └── parser.py               #   NL→JSON parsing prompts
├── gmail_sync/                 # Gmail ingest pipeline
│   ├── client.py               #   Gmail API wrapper
│   ├── parsers.py              #   Bank consumo email parsers (Pichincha/Diners/Produbanco/Cash)
│   ├── invoice.py              #   SRI XML parser (factura + nota de crédito, 3 wrappings)
│   ├── ingest_consumos.py      #   Consumos/* labels → consumos table
│   ├── ingest_invoices.py      #   Facturas label → invoices tables
│   ├── register_consumos.py    #   Rules + LLM auto-registration → transactions
│   ├── scheduled.py            #   Scheduled sync job
│   └── verify.py               #   Setup helper: test auth + list labels
├── ui/                         # Presentation layer (CLI tables, Telegram formatting, i18n)
├── tests/                      # pytest suite (in-memory SQLite)
└── specs/                      # Design documents
```

## Database schema

One SQLite file holds everything. Legacy `invoices.db`/`consumos.db` are auto-migrated on first run.

### Core tables

```sql
CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    account_type TEXT NOT NULL,        -- 'cash' | 'credit_card'
    cut_off_day INTEGER,
    payment_day INTEGER
);

CREATE TABLE subscriptions (           -- recurring subscriptions AND budget envelopes
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    monthly_amount REAL NOT NULL,
    payment_account_id TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    is_budget BOOLEAN DEFAULT 0,
    is_income BOOLEAN DEFAULT 0,
    underspend_behavior TEXT DEFAULT 'keep'   -- 'keep' | 'return'
);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_created DATE NOT NULL,        -- purchase date
    date_payed DATE NOT NULL,          -- cash impact date (CC billing formula)
    description TEXT NOT NULL,
    account TEXT,
    amount REAL NOT NULL,              -- negative = expense
    category TEXT,
    budget TEXT,                       -- FK to subscriptions.id (envelope link)
    status TEXT NOT NULL,              -- committed | pending | planning | forecast
    origin_id TEXT,                    -- groups installments/splits; = subscription id for allocations
    source TEXT DEFAULT NULL,          -- NULL = owner; 'gmail', 'mom', ... = automated/delegate
    needs_review INTEGER DEFAULT 0
);
```

Plus `categories`, `settings`, and `llm_examples` (confirmed natural-language inputs paired with their parse results — future few-shot/training data).

### Gmail pipeline tables

- **`consumos`** — one row per parsed bank notification email: bank, account, merchant, amount, timestamp, card digits; link metadata (`registered_txn_id`, `link_source`, `matched_invoice_number`).
- **`invoices`** / **`invoice_lines`** / **`invoice_taxes`** / **`invoice_pagos`** — SRI documents with full line items, tax buckets, and payment splits. Credit notes carry `refund_of_invoice_number`, `motivo`, and a `motivo_category` classifier (`refund` / `loyalty` / `other`).
- **`unparsed_facturas`** / **`unparsed_consumos`** — emails the parsers couldn't handle, with a reason, so nothing is silently dropped.
- **`llm_decisions`** — audit log of every LLM classification (model, prompt, raw response, parsed result).

## Key principles

### Idempotent orchestration

`run_monthly_rollover(conn, today)` runs at the start of every session (CLI command, bot startup, web app lifespan) and is idempotent: committing past forecasts and generating new ones has no effect beyond the first run. State is always valid regardless of which interface touched the DB last.

### Live budget allocations

Budget envelopes are transactions with negative amounts, updated in place as linked spending arrives (`new_alloc = alloc + abs(expense)`, capped at 0). Money is "spent" when allocated, not when used — the running balance never double-counts. See [Core Concepts](concepts.md).

### Nothing enters silently

Every automated write (Gmail registration, delegate users) is tagged with `source` and `needs_review=1`, and auto-backups run before every mutating CLI command.

## Testing

```bash
pytest tests/                                    # all tests
pytest tests/test_budgets.py                     # one module
pytest tests/test_budgets.py -k "test_capping"   # matching tests
```

Tests use in-memory SQLite via `create_test_db()` from `cashflow.database`, which initializes tables, mock accounts, categories, and settings in one call:

```python
from cashflow.database import create_test_db

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()
```

Mock data available: accounts `Cash`, `Visa Produbanco` (cut-off 14, pay 25), `Amex Produbanco` (cut-off 2, pay 15); the default category set; `forecast_horizon_months = 6`. Mock patches use full paths: `patch('cashflow.controller.date')`.

# Personal Cash Flow Tool

A CLI tool for managing personal finances. Built around budget envelopes, credit card billing-cycle awareness, and a single timeline that forecasts your real cash position into the future. Interactive mode (`-i`) gives you step-by-step guided entry with numbered menus, shortcuts, and previews — no configuration needed. Optionally, enable LLM-powered natural language input ("Spent 45.50 on groceries today") via [LiteLLM](https://github.com/BerriAI/litellm) with a free Gemini API key or local models through Ollama. A companion [Telegram bot](#telegram-bot) lets you track expenses on-the-go.

## See It In Action

### Interactive mode

```bash
python3 cli.py add -i                          # Add transaction
python3 cli.py accounts add -i                 # Add account
python3 cli.py categories add -i               # Add category
python3 cli.py subscriptions add -i            # Add budget/subscription
python3 cli.py edit 123 -i                     # Edit transaction
python3 cli.py subscriptions edit budget_food -i  # Edit budget/subscription
```

Step-by-step guided entry with selection menus, defaults, and previews. No LLM, no API keys, no configuration — works out of the box. Available on all entity commands.

**Input shortcuts** — designed for speed:

| Prompt type | Accepts | Examples |
|---|---|---|
| Choice (type, status, etc.) | Number, unique prefix, or full name | `1`, `cr` → credit_card, `sp` → split |
| Amount | `$`, commas, locale decimals | `$9.99`, `1,234.50`, `9,99` |
| Date | YYYY-MM-DD, MM/DD, shortcuts | `yesterday`, `today`, `+2` (months) |
| Selection (account, category) | Number or substring | `2`, `visa` |

```
Interactive Transaction Entry
Press Ctrl+C to cancel at any time.

Type [1.SIMPLE / 2.installment / 3.split]: 1
Date [2026-03-07]:
Description: Supermaxi groceries

Account:
  1. Cash (cash)
  2. Visa Pichincha (credit_card, cut-off: 25, pay: 5)
  3. Visa Produbanco (credit_card, cut-off: 14, pay: 25)
[number or name]> 2

Amount: $45.50

Category:
  1. Dining-Snacks - Eating out, takeout, coffee, and social food/drinks
  2. Home Groceries - Food and household items for home
  3. Personal - Discretionary spending, entertainment, hobbies
[number or name]> 2

Budget:
  1. budget_groceries_feb_mar ($120/$400 spent, $280 left)
  2. budget_personal_mar ($0/$100 spent, $100 left)
[number or name, empty to skip]> 1

Status [1.NORMAL / 2.pending / 3.planning]:
Is this income? [y/N]:

Transaction Preview
┌────────────┬──────────────────────────┐
│ Field      │ Value                    │
├────────────┼──────────────────────────┤
│ Date       │ 2026-03-07               │
│ Date Payed │ 2026-04-05               │
│ Desc       │ Supermaxi groceries      │
│ Account    │ Visa Pichincha           │
│ Amount     │ -45.50                   │
│ Category   │ Home Groceries           │
│ Budget     │ budget_groceries_feb_mar │
└────────────┴──────────────────────────┘

Proceed? [Y/n]:
Successfully added 1 transaction(s).
```

### Natural language input (requires LLM)

With an LLM configured (see [LLM Configuration](#llm-configuration)), you can skip the prompts and type transactions in plain English:

```bash
python3 cli.py add "Spent 45.50 on groceries at Supermaxi today on Visa Pichincha"
```

```
Transaction Preview
┌────────────┬──────────────────────────┐
│ Field      │ Value                    │
├────────────┼──────────────────────────┤
│ Date       │ 2026-03-07               │
│ Date Payed │ 2026-04-05               │
│ Desc       │ Supermaxi - groceries    │
│ Account    │ Visa Pichincha           │
│ Amount     │ -45.50                   │
│ Category   │ Home Groceries           │
│ Budget     │ budget_groceries_feb_mar │
└────────────┴──────────────────────────┘

Proceed with this request? [Y/n]
```

The LLM auto-detects dates, accounts, categories, amounts, and transaction types — including installments, splits, pending status, and grace periods:

```bash
python3 cli.py add "Bought laptop for 1200 in 12 installments on Visa Pichincha"
python3 cli.py add "Phone plan 600 starting the 5th of 12 installments on Visa Pichincha"
python3 cli.py add "Bought a TV for 500 on Visa Pichincha with 3 months grace period"
python3 cli.py add "Friend will pay me 100 on March 15, pending"
python3 cli.py add "Split: 30 groceries, 15 snacks at Supermaxi"
```

### Budget envelopes and running balance

```bash
python3 cli.py subscriptions add -i            # Interactive
python3 cli.py subscriptions add "Monthly groceries budget of 400 on Cash"  # Natural language
```

Creates a recurring envelope that reserves $400 each month. The envelope shows up as a line item in your cash flow — money is "set aside" the moment the budget activates. When you spend against it, the envelope shrinks and your running balance stays the same:

```
cli.py view
┌──────────┬────────────────────────┬──────────┬────────┬────────────┐
│ Paid     │ Description            │ Account  │ Amount │ Balance    │
├──────────┼────────────────────────┼──────────┼────────┼────────────┤
│ 03/01    │ Salary                 │ Cash     │ +3000  │ 3000.00    │
│ 03/01    │ budget_groceries ✉     │ Cash     │  -400  │ 2600.00    │  ← $400 reserved
│ ...      │                        │          │        │            │
└──────────┴────────────────────────┴──────────┴────────┴────────────┘
```

Now you spend $80 on groceries. The budget envelope absorbs it — balance unchanged:

```
cli.py add -i   (or: cli.py add "Groceries 80 on Cash, home groceries budget")
cli.py view
┌──────────┬────────────────────────┬──────────┬────────┬────────────┐
│ Paid     │ Description            │ Account  │ Amount │ Balance    │
├──────────┼────────────────────────┼──────────┼────────┼────────────┤
│ 03/01    │ Salary                 │ Cash     │ +3000  │ 3000.00    │
│ 03/01    │ budget_groceries ✉     │ Cash     │  -320  │ 2680.00    │  ← was -400, absorbed $80
│ 03/05    │ Groceries              │ Cash     │   -80  │ 2600.00    │  ← balance still 2600
│ ...      │                        │          │        │            │
└──────────┴────────────────────────┴──────────┴────────┴────────────┘
```

The budget went from -400 to -320 ($80 spent, $320 left). Your running balance didn't change — that money was already earmarked. This means the balance always shows your **real disposable cash**: money not committed to any budget.

All subscriptions and budgets run on a monthly cycle — one transaction per month, anchored to the start date's day-of-month (see [Monthly cycle](#subscriptions-add---add-budget-or-subscription) for details).

### Companion Telegram bot

Track expenses on-the-go with the companion [Telegram bot](#telegram-bot). Send messages like _"Lunch 12.50 on Cash"_ and get a preview with inline buttons to confirm, edit, or cancel. Use `/summary` to check budget status.

```
📊 Budgets: March 2026

🟢 Home Groceries
   $250.45 of $400.00 | $149.55 left

🟡 Transportation
   $85.00 of $100.00 | $15.00 left

🔴 Dining-Snacks
   $120.00 of $80.00 | $40.00 over
```

---

## What Makes This Different?

- **Works out of the box**: Interactive mode (`-i`) covers every operation — no API keys, no configuration, just install and go
- **True Cash Flow Forecasting**: See exactly how much money you'll have on any future date, accounting for all commitments
- **Smart Credit Card Handling**: Automatically calculates payment dates based on billing cycles — no more manual tracking
- **Live Budget Envelopes**: Spending reduces the envelope in real-time so you always see how much is left, while your running balance shows real disposable cash
- **Single Timeline**: Past, present, and future transactions in one unified view — no separate budget sheets
- **Even faster with LLMs**: Add an LLM provider to unlock natural language input ("Spent 45.50 on groceries today") and the companion [Telegram bot](#telegram-bot) for tracking on-the-go

---

## Table of Contents

1. [See It In Action](#see-it-in-action)
2. [Quick Start](#quick-start)
3. [LLM Configuration](#llm-configuration)
4. [Telegram Bot](#telegram-bot)
5. [Core Concepts](#core-concepts)
6. [CLI Command Reference](#cli-command-reference)
7. [Common Workflows](#common-workflows)
8. [Advanced Features](#advanced-features)
9. [Understanding Transaction Statuses](#understanding-transaction-statuses)
10. [Understanding Credit Card Cycles](#understanding-credit-card-cycles)
11. [Troubleshooting & FAQ](#troubleshooting--faq)
12. [Technical Details](#technical-details)
13. [Command Quick Reference](#command-quick-reference)

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip (Python package manager)

### Installation

1. **Clone or download this repository**

   ```bash
   cd cash_flow
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your first account**

   ```bash
   python3 cli.py accounts add -i
   ```

   The database ships with 11 default categories (Housing, Home Groceries, Personal Groceries, Dining-Snacks, Transportation, Health, Personal, Income, Savings, Loans, Others). You can add custom ones with `python3 cli.py categories add -i`.

4. **Add your first transaction**

   ```bash
   python3 cli.py add -i
   ```

5. **View your cash flow**

   ```bash
   python3 cli.py view
   ```

You're ready to go — no API keys needed. For natural language input, see [LLM Configuration](#llm-configuration) to set up Gemini (free tier) or Ollama (local, free).

---

## LLM Configuration

The CLI works fully without LLMs via interactive mode (`-i`). To enable natural language input (`cli.py add "Spent 50 on groceries"`), configure an LLM provider. The application uses [LiteLLM](https://github.com/BerriAI/litellm), a unified interface that supports any provider (Gemini, Ollama, OpenAI, Anthropic, etc.).

### Quick Start (Default - Gemini Only)

1. **Get a Google AI API key** at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

2. **Add to `.env` file**

   ```bash
   echo "GEMINI_API_KEY=your_api_key_here" >> .env
   ```

3. **Test it**

   ```bash
   python3 cli.py add "Spent 50 on groceries today"
   ```

That's it. The system uses Gemini for all parsing by default. No `llm_config.yaml` needed.

**Multiple API keys**: To handle Gemini's free-tier rate limits, you can add numbered keys (`GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, etc.) in `.env`. The system picks a random key per request and rotates on rate limit errors.

---

### Hybrid Setup: Local + Cloud (Cost Optimization)

Route simple tasks to a free local model and complex tasks to Gemini. Based on benchmarking with 25 real test cases:

| Function | Recommended Model | Accuracy | Avg Speed | Why |
|----------|-------------------|----------|-----------|-----|
| Pre-parse (date/account) | Ollama `llama3.2:3b` | 96% | 0.8s | Simple extraction, free |
| Transaction parsing | Gemini `2.5-flash` | — | ~1.2s | Complex JSON, needs accuracy |
| Subscription parsing | Gemini `2.5-flash` | — | ~1.2s | Budget creation needs accuracy |
| Account parsing | Gemini `2.5-flash` | — | ~1.2s | Local models generate code instead of JSON |

#### Setup

1. **Install and start Ollama**

   ```bash
   ollama pull llama3.2:3b
   ollama serve  # Runs on port 11434
   ```

2. **Copy the configuration template**

   ```bash
   cp llm_config.yaml.example llm_config.yaml
   ```

   The example file is pre-configured with the recommended hybrid routing above.

3. **Test**

   ```bash
   python3 cli.py add "test transaction 10 cash"
   ```

   Pre-parse runs on `llama3.2:3b` locally, then full parsing goes to Gemini.

---

### Configuration Reference

All configuration lives in `llm_config.yaml` (optional — defaults to all-Gemini without it).

#### Per-Function Model Routing

```yaml
function_models:
  pre_parse_date_and_account:
    provider: "ollama"
    model: "llama3.2:3b"

  parse_transaction_string:
    provider: "gemini"
    model: "gemini-2.5-flash"

  parse_subscription_string:
    provider: "gemini"
    model: "gemini-2.5-flash"

  parse_account_string:
    provider: "gemini"
    model: "gemini-2.5-flash"
```

#### Providers

```yaml
providers:
  gemini:
    type: "litellm"
    api_key_env: "GEMINI_API_KEY"

  ollama:
    type: "litellm"
    base_url: "http://localhost:11434"
```

#### Fallback Chains

If the primary model fails, try alternatives in order:

```yaml
fallback_chain:
  - provider: "gemini"
    model: "gemini-2.5-flash"
```

#### Global Settings

```yaml
timeout_seconds: 30
max_retries: 2
temperature: 0.0
```

---

### Environment Variable Overrides

Lower priority than `llm_config.yaml`, useful for Docker deployments:

```bash
LLM_DEFAULT_PROVIDER=gemini
LLM_DEFAULT_MODEL=gemini-2.5-flash
LLM_OLLAMA_BASE_URL=http://localhost:11434

# Per-function overrides (format: provider/model)
LLM_PRE_PARSE_MODEL=ollama/llama3.2:3b
LLM_TRANSACTION_PARSE_MODEL=gemini/gemini-2.5-flash
```

---

### Adding More Providers

Any LiteLLM-compatible provider works:

```yaml
providers:
  openai:
    type: "litellm"
    api_key_env: "OPENAI_API_KEY"

  anthropic:
    type: "litellm"
    api_key_env: "ANTHROPIC_API_KEY"
```

See `llm_config.yaml.example` for full documentation with benchmark results and troubleshooting tips.

---

## Telegram Bot

A companion chatbot for tracking expenses on-the-go. Requires an LLM provider (see above) since the bot uses natural language parsing.

### Quick Setup

1. **Get your bot token from [@BotFather](https://t.me/BotFather)**
   - Send `/newbot` to BotFather on Telegram
   - Follow prompts to create your bot
   - Copy the token provided

2. **Add token and allowed users to `.env` file**

   ```bash
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_ALLOWED_USERS=123456789,987654321
   GEMINI_API_KEY=your_gemini_key_here
   ```

   `TELEGRAM_ALLOWED_USERS` is a comma-separated list of Telegram user IDs that are allowed to interact with the bot. **The bot is protected by this allowlist** — unauthorized users receive a rejection message and their attempts are logged. If the variable is omitted or empty, the bot is open to anyone, so always set it in production.

   To find your Telegram user ID, send a message to [@userinfobot](https://t.me/userinfobot) on Telegram.

3. **Start the bot**

   ```bash
   python3 bot.py
   ```

### Docker Deployment

Run the bot as a persistent background service:

```bash
docker compose -f docker-compose.bot.yml up -d --build
```

The Docker setup mounts the project directory into the container, so the bot shares the same `cash_flow.db` as the CLI. If you use Ollama locally, the container routes to the host via `LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434`.

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and reset state |
| `/help` | Usage instructions |
| `/summary` | Budget envelope view for the current month |
| `/summary October` | Budget view for a specific month |
| `/cancel` | Cancel current transaction |

### Usage

Just send messages like:

- `"Spent 50 on groceries today"`
- `"Bought laptop for 1200 in 12 installments on Visa"`
- `"Split: 30 on groceries, 15 on snacks"`

The bot will:

1. Parse your message using the same LLM backend as the CLI
2. Show a formatted preview with inline buttons
3. Let you **Confirm** or **Revise** before saving
4. Allow corrections in natural language if needed

The `/summary` view shows per-month budget envelopes with spent/remaining amounts and navigation buttons to browse months or toggle to a planning/pending view.

---

## Core Concepts

### Everything is a Transaction

In this tool, **everything is a transaction**. This simple idea is the key to powerful forecasting. Instead of having separate systems for your history, subscriptions, and budgets, we represent them all in the same `transactions` table. This gives you a single, unified timeline of your money—past, present, and future.

### The Key to Forecasting: Two Dates

The core principle of the system is to distinguish between:

- **`date_created`**: When a transaction occurred (purchase date)
- **`date_payed`**: When it actually impacts your cash flow (payment date)

This distinction is crucial for credit cards. When you buy something on January 15th, but your credit card bill isn't due until February 5th, your cash flow is affected on February 5th, not January 15th.

### Subscriptions and Recurring Payments

Tell the tool about your Netflix subscription once, and it will automatically create future `'forecast'` transactions for as many months ahead as you want. The same goes for rent, bills, or any recurring payment. This means you can immediately see how much money is already earmarked for future months, removing any surprises.

### Live Budgeting: The Digital Envelope System

Budgets aren't just numbers in a separate sheet; they are live, dynamic transactions that function like a **digital envelope system**. When you set a $400 Food budget for the month, the system creates a single transaction with an amount of `-400`. This transaction is your "envelope"—it represents the total pool of money allocated for that category.

As you spend, you are "taking money" directly from this envelope. Here's how it works in practice:

1. **Initial State:** The "Food Budget" transaction shows `-400`.
2. **You spend $50 on groceries:** The system finds the Food Budget envelope and updates its balance: `-400 + 50 = -350`. The budget transaction now shows you have $350 remaining.
3. **You spend another $370:** This is more than the $350 left in your envelope. The system handles this intelligently:
   - The "Food Budget" transaction is updated by the remaining $350, bringing its balance to `0`. It is now capped at zero to show the allocation is fully spent.
   - Your actual expense of $370 is still recorded in full.

This method provides the best of both worlds: you can see at a glance that your food budget is exhausted, but your overall cash flow remains perfectly accurate because the **real transaction amount is always preserved**.

At the end of the month, you decide what happens to any leftover budget money. You can have it automatically "returned" to your cash flow, giving you an accurate picture of your available funds. Alternatively, you can choose to "keep" the remaining amount allocated. This is useful if the money was already spent on untracked small items or set aside, ensuring your budget for the month is officially closed out without affecting your cash balance.

### Putting It All Together: True Forecasting

The power of this system comes from a simple but profound principle: **everything is a transaction**. Your past spending, your future subscription payments, your installment plans, and your live budget envelopes all exist as rows in the same table. This gives you a single, unified timeline of your money.

The forecast is accurate because it's not based on abstract limits; it's based on the **actual cash impact** of every financial event. The key is that money allocated to a budget is considered 'spent' from your cash flow the moment you allocate it. Spending against that budget later simply categorizes the expense without affecting your overall cash balance again. This prevents double-counting and ensures you always know exactly how much disposable cash you have.

To see this in action, imagine a "Cash Flow Report" that calculates your running balance. Notice how an expense made from a budget does not impact the balance, because that money was already earmarked.

```
--- Your Cash Flow Report (Excerpt for Nov 2025) ---
date_payed  | description              | cash_flow_impact | running_balance
---------------------------------------------------------------------------
            | Balance from Oct 31        |                  | $2000.00
2025-11-01  | Monthly Salary           | +3000.00         | $5000.00
2025-11-01  | Food Budget Allocation   | -400.00          | $4600.00
2025-11-15  | Netflix Subscription     | -15.99           | $4584.01
2025-11-20  | Groceries                | -80.00           | $4584.01 (No change)
            | *Food Budget transaction is updated to -320*  |                  | $4584.01        <-- Envelope updates, cash balance is unaffected.
2025-11-25  | New Laptop (2/6)         | -200.00          | $4384.01
```

Behind the scenes, the `$80` grocery expense is still recorded as a transaction, and the "Food Budget" allocation is automatically updated to show `$320` remaining. As if using the envelope money, then seeing how much you still have in it.

So, your cash balance remains correct and your budget allocation is always up-to-date and easy to track.

This approach offers great flexibility. If your circumstances change, you can edit a budget's amount mid-month, and the system will instantly recalculate its balance, giving you a constantly accurate financial picture. This unified view removes the guesswork and gives you a clear, honest picture of your financial future.

---

## CLI Command Reference

All commands follow the pattern: `python3 cli.py <command> [options]`

For detailed help on any command: `python3 cli.py <command> -h`

### Transaction Management

#### `add` - Add a transaction

The easiest way to record expenses and income. Two modes:

**Natural language** (requires LLM):

```bash
python3 cli.py add "Spent 45.50 on groceries at Walmart today"
python3 cli.py add "Bought TV for 600 in 12 installments on Visa card"
python3 cli.py add "Income 3000 on Cash"
python3 cli.py add "Split purchase: 30 on groceries, 15 on snacks"
```

**Interactive guided entry** (no LLM needed — works offline):

```bash
python3 cli.py add -i
```

Prompts step-by-step for type, date, description, account, amount, category, and budget with numbered selection menus. Supports simple, installment, and split transactions. Choice prompts accept numbers (`1`), unique prefixes (`cr` → credit_card, `sp` → split), or full names. Amounts accept `$` signs and commas (`$9.99`, `1,234.50`, `9,99`).

**What it does**: Shows you a preview table and asks for confirmation before creating the transaction.

**Key features**:

- Auto-detects transaction type (simple, installment, split) via LLM, or choose interactively with `-i`
- Calculates payment dates for credit cards automatically
- Shows preview before committing
- Supports pending and planning statuses

**Example output**:

```
Transaction Preview
┌────────────┬─────────────────┐
│ Field      │ Value           │
├────────────┼─────────────────┤
│ Date       │ 2026-02-02      │
│ Date Payed │ 2026-03-05      │
│ Desc       │ Groceries       │
│ Account    │ VisaCard        │
│ Amount     │ -45.50          │
│ Category   │ groceries       │
└────────────┴─────────────────┘

Proceed with this request? [Y/n]
```

---

#### `add --import` - Import multiple transactions from CSV

Bulk import transactions from a CSV file.

```bash
python3 cli.py add --import transactions.csv
```

**CSV format**: `date,description,account,amount`

```csv
01/15/26,Groceries at Walmart,Cash,-45.50
01/16/26,Gas station,Cash,-35.00
```

**What it does**: Reads each line, shows a preview, and asks for confirmation for each transaction.

---

#### `add --import --installments` - Import installment sequences from CSV

Import pre-existing installment plans (e.g., from a credit card statement showing "3/12" installments).

```bash
python3 cli.py add --import installments.csv --installments
```

**CSV format**: `date,description,account,amount,current_installment,total_installments`

```csv
01/15/26,New Laptop,VisaCard,83.33,3,12
```

**What it does**: Creates the remaining installments (3/12 through 12/12 in this example), automatically calculating future payment dates.

---

#### `edit` - Modify transaction details

Edit a transaction's properties. Use `--all` to edit all installments in a group.

**Flag-based** (change specific fields):

```bash
python3 cli.py edit 123 --status pending
python3 cli.py edit 456 --category groceries --budget budget_food
python3 cli.py edit 789 --amount 50.00
python3 cli.py edit 100 --date 2026-01-15
python3 cli.py edit 200 --status planning --all  # Edit all installments
```

**Interactive guided edit** (no flags needed):

```bash
python3 cli.py edit 123 -i
python3 cli.py edit 456 -i --all  # Interactive edit applied to all installments
```

Shows current values and prompts each field with the current value as default. Press Enter to keep, or type a new value to change. Only changed fields are applied.

**Available options**:

- `--description, -d`: Change description
- `--amount, -a`: Change amount
- `--date, -D`: Change creation date (YYYY-MM-DD)
- `--category, -c`: Assign to category
- `--budget, -b`: Link to budget
- `--status, -s`: Change status (committed/pending/planning/forecast)
- `--all`: Apply changes to entire transaction group
- `--interactive, -i`: Interactive guided mode

---

#### `delete` - Remove transactions

Delete a transaction or an entire group (e.g., all installments).

```bash
python3 cli.py delete 123        # Delete single transaction
python3 cli.py delete 456 --all  # Delete all installments in group
```

**What it does**: Shows transaction details and asks for confirmation before deletion.

---

#### `clear` - Commit pending/planning transactions

Change transaction status from 'pending' or 'planning' to 'committed'.

```bash
python3 cli.py clear 123        # Commit single transaction
python3 cli.py clear 456 --all  # Commit all installments
```

**Use case**: When a pending purchase is confirmed, or when you decide to commit to a planned expense.

---

### Explicit Creation (`create`)

The `create` command (alias `cr`) provides scriptable, flag-based entity creation with no LLM and no confirmation prompts. Good for automation, tests, and seeding.

#### `create transaction` - Create a transaction with explicit parameters

```bash
# Simple expense
python3 cli.py create transaction "Supermaxi groceries" 45.50 Cash -c groceries

# With budget
python3 cli.py create transaction "Supermaxi groceries" 45.50 Cash -c groceries -b budget_groceries_feb_mar

# Income
python3 cli.py create transaction "Salary" 3000 Cash --income

# Installments (12 monthly payments of 100 each)
python3 cli.py create transaction "Laptop" 1200 VisaCard -n 12 -c electronics

# Partial installments (starting from 5th of 12)
python3 cli.py create transaction "Phone plan" 600 VisaCard -n 12 --start-installment 5

# Specific date
python3 cli.py create transaction "Dinner" 25 Cash -d 2026-03-01 -c dining

# Pending / planning
python3 cli.py create transaction "Friend owes me 50" 50 Cash --pending
python3 cli.py create transaction "Maybe a TV" 800 Cash --planning
```

**Parameters**:

| Positional      | Description                                      |
|-----------------|--------------------------------------------------|
| `description`   | Transaction description                          |
| `amount`        | Amount (or total for installments)               |
| `account`       | Account ID                                       |

| Flag                    | Description                                           |
|-------------------------|-------------------------------------------------------|
| `--category, -c`        | Category name                                         |
| `--budget, -b`          | Budget ID                                             |
| `--date, -d`            | Transaction date YYYY-MM-DD (default: today)          |
| `--installments, -n`    | Number of installments (promotes amount to total)     |
| `--start-installment`   | Starting installment number (default: 1)              |
| `--grace-period, -g`    | Grace period in months                                |
| `--income`              | Mark as income                                        |
| `--pending`             | Mark as pending                                       |
| `--planning`            | Mark as planning                                      |

---

#### `create account` - Create an account

```bash
python3 cli.py create account Cash cash
python3 cli.py create account VisaCard credit_card --cut-off-day 25 --payment-day 5
```

**Parameters**: `id` (name), `type` (cash/credit_card), `--cut-off-day, -c`, `--payment-day, -p`.

---

#### `create budget` - Create a budget/subscription

```bash
python3 cli.py create budget "Groceries" 300 Cash groceries
python3 cli.py create budget "Netflix" 15.99 VisaCard entertainment --start 2026-02-01
python3 cli.py create budget "Vacation" 200 Cash savings --start 2026-02-01 --end 2026-12-31
```

**Parameters**: `name`, `amount`, `account`, `category`, `--start, -s`, `--end, -e`, `--underspend, -u` (keep/return).

---

#### `create category` - Create a category

```bash
python3 cli.py create category dining "Eating out, takeout, coffee"
```

**Parameters**: `name` (lowercase, no spaces), `description` (helps LLM auto-categorize).

> **Note**: Also available via `categories add` — both do the same thing.

---

### Account Management

#### `accounts list` - View all accounts

```bash
python3 cli.py accounts list
```

**Example output**:

```
All Accounts
┌────────────┬─────────────┬─────────────┬──────────────┐
│ Account ID │ Type        │ Cut-off Day │ Payment Day  │
├────────────┼─────────────┼─────────────┼──────────────┤
│ Cash       │ cash        │ N/A         │ N/A          │
│ VisaCard   │ credit_card │ 25          │ 5            │
└────────────┴─────────────┴─────────────┴──────────────┘
```

---

#### `accounts add` - Add a new account

**Natural language** (requires LLM):

```bash
python3 cli.py accounts add "Cash account"
python3 cli.py accounts add "Visa card with cut-off on 25 and payment on 5"
python3 cli.py accounts add "MasterCard closing on 15th, due on 3rd"
```

**Interactive guided entry** (no LLM needed):

```bash
python3 cli.py accounts add -i
```

Prompts for account name, type (cash/credit_card), and cut-off/payment days for credit cards. Type prompt accepts `1`/`2`, `ca`/`cr`, or full name. Shows a preview table before creating.

---

#### `accounts adjust-billing` - One-time billing cycle adjustment

Temporarily adjust credit card billing cycle for a specific month (e.g., when bank changes statement date).

```bash
python3 cli.py accounts adjust-billing VisaCard 2026-02 27 --payment-day 7
```

**Parameters**:

- `account_id`: Credit card account
- `month`: Affected month (YYYY-MM)
- `cut_off_day`: Actual cut-off day for this month
- `--payment-day, -p`: Payment day if also changed (optional)

**Use case**: Bank moves your statement date from 25th to 27th for one month only.

---

### Budget & Subscription Management

#### `subscriptions list` - View budgets and subscriptions

```bash
python3 cli.py subscriptions list              # Active only
python3 cli.py subscriptions list --all        # Include expired
python3 cli.py subscriptions list --budgets-only  # Budgets only
```

**Example output**:

```
Subscriptions
┌──────────────────┬────────────┬────────────┬─────────┬─────────┬────────────┬────────────┬────────┐
│ ID               │ Name       │ Type       │ Amount  │ Account │ Start Date │ End Date   │ Status │
├──────────────────┼────────────┼────────────┼─────────┼─────────┼────────────┼────────────┼────────┤
│ budget_groceries │ Groceries  │ Budget     │ $300.00 │ Cash    │ 2026-01-01 │ Ongoing    │ Active │
│ sub_netflix      │ Netflix    │ Subscription│ $15.99 │ Visa    │ 2025-06-01 │ Ongoing    │ Active │
└──────────────────┴────────────┴────────────┴─────────┴─────────┴────────────┴────────────┴────────┘
```

---

#### `subscriptions add` - Add budget or subscription

**Natural language** (requires LLM):

```bash
python3 cli.py subscriptions add "Monthly groceries budget of 300 on Cash"
python3 cli.py subscriptions add "Netflix subscription 15.99 on Visa"
python3 cli.py subscriptions add "Vacation fund 200/month until December"
```

**Interactive guided entry** (no LLM needed):

```bash
python3 cli.py subscriptions add -i
```

Prompts for kind (subscription/budget/income), name, amount, account, category, dates, and underspend behavior. Auto-generates the subscription ID. Shows a preview table before creating and generates forecast transactions. End date defaults to end of start month and supports `+N` shortcut (e.g., `+3` = 3 months after start date, snapped to end of month).

**What it does**: Parses your description or walks you through step by step, shows preview, asks for confirmation, and generates forecast transactions.

**Monthly cycle**: Everything runs on a monthly cycle anchored to `start_date`:

- The **day-of-month** from `start_date` is used for every forecast transaction. A budget starting on March 7th creates allocations on the 7th of each month (Apr 7, May 7, etc.). If the day doesn't exist in a month (e.g., the 31st in February), it falls back to the last day of that month.
- **End date is inclusive**: a subscription with `start=03-01, end=04-05` generates transactions for both March 1st and April 1st, because April 1st falls before the end date. But `start=03-20, end=04-05` only generates March 20th — April 20th would be past the end date.
- **Cash accounts**: `date_payed = date_created` (same day). **Credit cards**: payment date is calculated from the card's billing cycle (cut-off/payment days).
- **Budget spending** is tracked per calendar month regardless of the allocation day — all March expenses count toward the March budget whether the allocation landed on the 1st or the 15th.

---

#### `subscriptions edit` - Modify existing budget/subscription

Update budget parameters.

**Flag-based** (change specific fields):

```bash
python3 cli.py subscriptions edit budget_groceries --amount 350
python3 cli.py subscriptions edit budget_groceries --amount 350 --retroactive
python3 cli.py subscriptions edit sub_netflix --account Cash
python3 cli.py subscriptions edit budget_vacation --end 2026-12-31
python3 cli.py subscriptions edit budget_vacation --end none  # Make ongoing
```

**Interactive guided edit** (no flags needed):

```bash
python3 cli.py subscriptions edit budget_groceries -i
```

Shows current values and prompts each field with defaults. Press Enter to keep, type a new value to change. Only changed fields are applied.

**Parameters**:

- `--name, -n`: New name
- `--amount, -a`: New monthly amount
- `--account, -c`: New account
- `--end, -e`: End date (YYYY-MM-DD) or "none"
- `--underspend, -u`: "keep" or "return"
- `--retroactive, -r`: Apply changes to past months (corrections only)
- `--interactive, -i`: Interactive guided mode

**Important**: Amount changes are not retroactive by default—they only affect future months. Use `--retroactive` to correct past allocation errors.

---

#### `subscriptions delete` - Delete budget/subscription

Remove a budget or subscription.

```bash
python3 cli.py subscriptions delete budget_groceries
python3 cli.py subscriptions delete sub_netflix --force  # Skip confirmation
```

**What it does**: Shows details and linked transaction counts, asks for confirmation (unless `--force`), then deletes.

**Note**: Cannot delete if committed transactions exist. Delete forecast transactions first.

---

### Categories

#### `categories list` - View all categories

```bash
python3 cli.py categories list
```

---

#### `categories add` - Create new category

```bash
python3 cli.py categories add groceries "Food and household items"
python3 cli.py categories add utilities "Electricity, water, gas, internet"
python3 cli.py categories add -i  # Interactive guided mode
```

---

#### `categories edit` - Update category description

```bash
python3 cli.py categories edit groceries "Food, household items, and toiletries"
```

---

#### `categories delete` - Remove category

```bash
python3 cli.py categories delete old_category
```

**Note**: Cannot delete if transactions are using it.

---

### Viewing & Reports

#### `view` - Main cash flow view

Display transactions with running balance and month-over-month comparison.

```bash
python3 cli.py view                      # Default: 3 months from today
python3 cli.py view -m 6                 # Show 6 months
python3 cli.py view --from 2026-01       # Start from specific month
python3 cli.py view -s                   # Summary mode (aggregate credit cards)
python3 cli.py view -s -p                # Summary with planning included
python3 cli.py view --sort date_created  # Sort by purchase date
```

**Display features**:

- Running Balance: Cumulative balance after each transaction
- MoM Change: Month-over-month comparison (last transaction of month, color-coded)
- Starting Balance: Balance before displayed period
- Pending from Past: Old pending transactions shown separately at top
- Month Sections: Visual separators between months

**Color coding**:

- Blue: Budget allocations
- Grey: Pending transactions
- Italic: Forecast transactions
- Magenta Italic: Planning transactions
- Default: Committed transactions

**Summary mode (`-s`)**:

- Aggregates credit card transactions into monthly payment entries
- Shows "VisaCard Payment" instead of individual purchases
- Cash transactions shown normally
- Planning transactions shown individually (unless `-p` used)

**Sorting**:

- `--sort date_payed` (default): When money leaves your account
- `--sort date_created`: When purchases actually happened

**Example output**:

```
Cash Flow - February 2026 to April 2026
Starting Balance: $4,584.01

┌──────────────┬─────────────────────────────┬──────────┬──────────────┬──────────────┐
│ Date Payed   │ Description                 │ Amount   │ Running Bal  │ MoM Change   │
├──────────────┼─────────────────────────────┼──────────┼──────────────┼──────────────┤
│ 2026-02-01   │ Food Budget Allocation      │ -400.00  │ 4,184.01     │              │
│ 2026-02-15   │ Groceries                   │ -80.00   │ 4,184.01     │              │
│ 2026-02-28   │ Salary                      │ +3000.00 │ 7,184.01     │ +2,600.00 ↑  │
└──────────────┴─────────────────────────────┴──────────┴──────────────┴──────────────┘
```

---

#### `export` - Export transactions to CSV

```bash
python3 cli.py export transactions.csv
python3 cli.py export transactions.csv --with-balance
```

**What it does**: Exports all transactions to CSV format for external analysis.

---

### Reconciliation

#### `fix --balance` - Adjust total balance

Fix total cash balance to match actual amount (adds correction transaction).

```bash
python3 cli.py fix --balance 1500.00
python3 cli.py fix --balance 1500.00 --account Cash
```

**Use case**: Your actual bank balance is $1,500 but the system shows $1,450. This creates a +$50 adjustment transaction.

---

#### `fix --payment` - Reconcile credit card statement

Reconcile credit card statement against tracked transactions.

```bash
# Interactive mode (shows transactions, asks for amount)
python3 cli.py fix --payment VisaCard -i

# Auto-detect month, provide amount
python3 cli.py fix --payment VisaCard 450.50

# Explicit month and amount
python3 cli.py fix --payment VisaCard 2026-01 450.50
```

**Smart month detection** (when month omitted):

- Before cut-off day: Reconciles current month
- After cut-off day: Reconciles next month
- Cash accounts: Always current month

**Interactive mode example** (`-i`):

```
Statement Adjustment for VisaCard - January 2026
Payment date: 2026-02-05

Transactions on 2026-02-05
┌────┬────────────┬─────────────────────────┬──────────┐
│ ID │ Date       │ Description             │ Amount   │
├────┼────────────┼─────────────────────────┼──────────┤
│ 45 │ 2026-01-15 │ Groceries              │ -80.00   │
│ 47 │ 2026-01-20 │ Gas station            │ -35.00   │
│ 52 │ 2026-01-25 │ Restaurant             │ -50.00   │
├────┴────────────┼─────────────────────────┼──────────┤
│                 │ CURRENT TOTAL           │ -165.00  │
└─────────────────┴─────────────────────────┴──────────┘

Enter actual statement amount: 175.50

Adjustment: $165.00 → $175.50 (difference: +$10.50)
Proceed? [Y/n]:
```

**What it does**: Creates a "Payment Adjustment" transaction for the difference between tracked total and actual statement.

---

### Backup

#### `backup` - Create a manual backup

```bash
python3 cli.py backup                    # Create an unnamed manual backup
python3 cli.py backup "pre-migration"    # Create a named manual backup
python3 cli.py backup list               # List all backups (with type column)
python3 cli.py backup restore <file>     # Restore from a backup
```

**What it does**: Creates timestamped database snapshots using SQLite's backup API, which is safe even while the database is in use.

**Manual vs auto backups**: Manual backups (created via `cli.py backup`) are never auto-deleted by the retention policy. You can optionally give them a name for easy identification. Auto backups are created before every mutating CLI command and are subject to retention.

| Type | Filename pattern | Example |
|------|-----------------|---------|
| Auto | `cash_flow_YYYYMMDD_HHMMSS_ffffff.db` | `cash_flow_20260307_143625_123456.db` |
| Manual | `cash_flow_manual_YYYYMMDD_HHMMSS_ffffff.db` | `cash_flow_manual_20260307_143625_123456.db` |
| Manual (named) | `cash_flow_manual_YYYYMMDD_HHMMSS_ffffff_SLUG.db` | `cash_flow_manual_20260307_143625_123456_pre_migration.db` |

**Backup log**: Every backup (auto and manual) is recorded in `backups/backup.log` with the triggering operation:

```
2026-03-07 14:36:25 | cash_flow_20260307_143625_123456.db | add pichincha, mar 7, supermaxi
2026-03-07 14:40:00 | cash_flow_manual_20260307_144000_654321_pre_migration.db | manual backup: pre-migration
```

**Retention policy**: Auto backups are automatically pruned to save disk space. Manual backups are never auto-deleted.

| Age | Kept |
|-----|------|
| Today | First backup of the day + last N (default 5) |
| 1 day to `BACKUP_MAX_DAYS` (default 30) | Last backup per day |
| Older than `BACKUP_MAX_DAYS` | Deleted |

**Configuration** via environment variables (or `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKUP_ENABLED` | `true` | Enable/disable auto-backup |
| `BACKUP_DIR` | `backups` | Directory to store backups |
| `BACKUP_KEEP_TODAY` | `5` | Number of recent backups to keep for today (plus the first) |
| `BACKUP_RECENT_DAYS` | `7` | Days threshold for "keep last per day" policy |
| `BACKUP_MAX_DAYS` | `30` | Delete backups older than this many days |
| `BACKUP_LOG_RETENTION_DAYS` | `30` | Days to keep backup log entries |

**Restore example**:

```bash
python3 cli.py backup list                              # Find the backup you want
python3 cli.py backup restore cash_flow_20260307_150623_093810.db  # Restore it
```

Restore always creates a pre-restore safety backup (marked as manual) first, so you can undo a restore if needed.

---

## Common Workflows

### Setting Up Your First Month

**Goal**: Get the system configured with accounts, categories, and initial balance.

1. **Create your accounts**

   ```bash
   python3 cli.py accounts add "Cash account"
   python3 cli.py accounts add "Visa card with cut-off on 25 and payment on 5"
   ```

2. **Categories are pre-loaded** — 11 defaults are created automatically (Housing, Home Groceries, Dining-Snacks, Transportation, etc.). Add custom ones if needed:

   ```bash
   python3 cli.py categories add utilities "Electricity, water, gas"
   ```

3. **Record your current balance**

   ```bash
   python3 cli.py fix --balance 2500.00 --account Cash
   ```

4. **Set up monthly budgets**

   ```bash
   python3 cli.py subscriptions add "Groceries budget 400 on Cash"
   python3 cli.py subscriptions add "Entertainment budget 150 on Cash"
   python3 cli.py subscriptions add "Utilities budget 200 on Cash"
   ```

5. **Add recurring subscriptions**

   ```bash
   python3 cli.py subscriptions add "Netflix 15.99 on Visa"
   python3 cli.py subscriptions add "Gym membership 50 on Visa"
   ```

6. **View your forecast**

   ```bash
   python3 cli.py view -m 3
   ```

You should now see your budgets allocated for the next few months and your subscriptions forecasted!

---

### Adding a Monthly Budget

**Goal**: Set up a new budget that allocates money each month and tracks spending.

1. **Create the budget**

   ```bash
   python3 cli.py subscriptions add "Monthly groceries budget of 400 on Cash"
   ```

2. **Verify it was created**

   ```bash
   python3 cli.py subscriptions list
   ```

3. **Record expenses against it**

   ```bash
   python3 cli.py add "Spent 50 on groceries from groceries budget"
   ```

4. **Check remaining budget**

   ```bash
   python3 cli.py view | grep "Groceries Budget"
   ```

The budget allocation transaction will show the remaining balance (e.g., -350 if you spent $50 from a $400 budget).

**Budget behaviors**:

- **"keep" (default)**: Unused money stays allocated (covers untracked purchases)
- **"return"**: Unused money returns to cash flow at month end

To change behavior:

```bash
python3 cli.py subscriptions edit budget_groceries --underspend return
```

---

### Tracking a Large Purchase with Installments

**Goal**: Record a purchase being paid over multiple months.

1. **Add the installment purchase**

   ```bash
   python3 cli.py add "Bought new laptop for 1200 in 12 installments on Visa"
   ```

2. **View the installment plan**

   ```bash
   python3 cli.py view -m 12
   ```

   You'll see 12 transactions (e.g., "New Laptop (1/12)", "New Laptop (2/12)", etc.) spread across future months, each on your credit card's payment date.

3. **Edit all installments at once** (e.g., mark as pending)

   ```bash
   python3 cli.py edit <transaction_id> --status pending --all
   ```

4. **Delete the entire installment plan**

   ```bash
   python3 cli.py delete <transaction_id> --all
   ```

**Note**: When you edit or delete with `--all`, it affects all installments in the group.

---

### Reconciling Your Credit Card Statement

**Goal**: Ensure tracked transactions match your actual credit card bill.

**Scenario**: You receive your Visa bill for January, due February 5th, showing $485.50.

1. **Run interactive reconciliation**

   ```bash
   python3 cli.py fix --payment VisaCard -i
   ```

2. **Review the transaction list**

   The tool shows all transactions on the payment date and the current total.

3. **Enter your statement amount**

   ```
   Enter actual statement amount: 485.50
   ```

4. **Review the adjustment**

   ```
   Adjustment: $475.00 → $485.50 (difference: +$10.50)
   Proceed? [Y/n]:
   ```

5. **Confirm**

   Press Y. The tool creates a "Payment Adjustment - VisaCard (+10.50)" transaction to reconcile the difference.

**Common causes of differences**:

- Forgotten transaction
- Wrong amount entered
- Credit card fee or interest
- Returned item

**Tip**: Use `python3 cli.py view --sort date_created` to see purchases by date and identify missing transactions.

---

### Planning Future Expenses

**Goal**: Model potential future expenses without committing to them yet.

**Use case**: You're considering a vacation in June but haven't decided yet.

1. **Add as a planning transaction**

   ```bash
   python3 cli.py add "Planning vacation package for 2000 on Visa in June"
   ```

   (When the LLM asks, set status to "planning")

2. **View the impact on your forecast**

   ```bash
   python3 cli.py view -m 6
   ```

   Planning transactions show in magenta italic and affect your projected balance.

3. **When you decide to commit**

   ```bash
   python3 cli.py clear <transaction_id>
   ```

   This changes status from "planning" to "committed".

4. **Or delete if you cancel the plan**

   ```bash
   python3 cli.py delete <transaction_id>
   ```

**Planning vs Pending**:

- **Planning**: Future potential expense, affects forecast
- **Pending**: Expense already happened, awaiting confirmation (doesn't affect running balance until cleared)

---

### Month-End Review

**Goal**: Review spending, adjust budgets, and clean up pending transactions.

1. **Check budget allocations**

   ```bash
   python3 cli.py subscriptions list --budgets-only
   python3 cli.py view -m 1 | grep "Budget"
   ```

   Look for budgets showing $0 (depleted) or large remaining balances.

2. **Review pending transactions**

   ```bash
   python3 cli.py view | grep "pending"
   ```

3. **Commit confirmed transactions**

   ```bash
   python3 cli.py clear <transaction_id>
   ```

4. **Delete cancelled transactions**

   ```bash
   python3 cli.py delete <transaction_id>
   ```

5. **Adjust next month's budgets if needed**

   ```bash
   # Increase groceries budget
   python3 cli.py subscriptions edit budget_groceries --amount 450
   ```

6. **Check month-over-month change**

   ```bash
   python3 cli.py view -m 2
   ```

   Look at the "MoM Change" column on the last transaction of each month—green means improvement, red means decline.

7. **Export for analysis** (optional)

   ```bash
   python3 cli.py export monthly_report.csv --with-balance
   ```

---

## Advanced Features

### Split Transactions

Record a single purchase split across multiple categories/budgets.

```bash
python3 cli.py add "Spent 100: 60 on groceries, 40 on household items"
```

The LLM will detect this as a split transaction and create separate entries for each portion.

---

### Grace Periods

Model "buy now, pay later" scenarios where the cash flow impact is delayed.

**Note**: This feature requires manual transaction creation. Use `date_created` for purchase date and `date_payed` for the future payment date.

---

### Retroactive Budget Corrections

Fix budget allocation errors in past months.

**Scenario**: You allocated $400/month for groceries but meant to allocate $450.

```bash
python3 cli.py subscriptions edit budget_groceries --amount 450 --retroactive
```

**What it does**:

- Updates all past committed months to $450
- Recalculates budget balances
- Future forecasts use $450

**Important**: This is for corrections, not price changes. Don't use retroactive for "I want to increase my budget going forward."

---

### Transaction Groups

Installments and split transactions are automatically linked via `origin_id`.

**Benefits**:

- Edit all installments with `--all` flag
- Delete entire group with `--all` flag
- Track related transactions

**How to check group membership**:

```bash
python3 cli.py view | grep "<description>"
```

Look for numbered entries like "Laptop (3/12)".

---

### Billing Cycle Adjustments

Handle one-time changes to credit card billing cycles.

**Scenario**: Your bank moves your Visa statement date from the 25th to the 27th for February only.

```bash
python3 cli.py accounts adjust-billing VisaCard 2026-02 27 --payment-day 7
```

**What it does**: Creates a one-time override for that month. Future months use the original billing cycle.

---

### Summary Mode vs Detailed View

**Detailed view** (default):

- Shows every transaction individually
- Best for: tracking specific expenses, finding transactions

**Summary mode** (`-s`):

- Aggregates credit card transactions into monthly "Payment" entries
- Cash transactions shown normally
- Best for: clean forecast view, seeing overall cash flow

```bash
python3 cli.py view          # Detailed
python3 cli.py view -s       # Summary
python3 cli.py view -s -p    # Summary with planning aggregated too
```

---

## Understanding Transaction Statuses

Every transaction has a `status` field that determines how it affects your cash flow forecast.

### `committed`

**What it is**: Confirmed, finalized transaction.

**When to use**:

- Default status for most transactions
- Purchases that have already happened
- Income received

**Impact on balance**: Fully affects running balance

**Example**: "Groceries $50 on Visa, purchased yesterday"

---

### `forecast`

**What it is**: Auto-generated future transaction from a subscription or budget.

**When to use**:

- Automatically created by the system
- Represents predictable future expenses

**Impact on balance**: Affects running balance (shows expected future state)

**Example**: "Netflix subscription $15.99" scheduled for next month

**Note**: Forecast transactions become `committed` when the month arrives (via monthly rollover).

---

### `pending`

**What it is**: Transaction happened but not yet confirmed.

**When to use**:

- Expense made but not yet reflected in bank account
- Waiting for transaction to clear
- Uncertain if charge will go through

**Impact on balance**: Does NOT affect running balance until cleared

**Example**: "Restaurant charge $60, card was swiped but might not process"

**How to commit**: `python3 cli.py clear <id>`

---

### `planning`

**What it is**: Potential future expense, not yet committed.

**When to use**:

- Considering a purchase
- Modeling "what if" scenarios
- Future expense you might make

**Impact on balance**: Affects running balance in forecast (shows potential impact)

**Example**: "Vacation package $2,000 in June—still deciding"

**How to commit**: `python3 cli.py clear <id>`

**How to cancel**: `python3 cli.py delete <id>`

---

### Status Comparison Table

| Status      | Affects Balance? | Auto-Generated? | Use Case                          |
|-------------|------------------|-----------------|-----------------------------------|
| committed   | Yes              | No              | Confirmed transactions            |
| forecast    | Yes              | Yes             | Predicted recurring expenses      |
| pending     | No               | No              | Unconfirmed transactions          |
| planning    | Yes              | No              | Potential future expenses         |

---

## Understanding Credit Card Cycles

Credit cards have two critical dates that determine when a purchase impacts your cash flow.

### The Two Key Dates

1. **Cut-off Day** (Statement Closing Date)
   - Last day of the billing period
   - Purchases on or before this date appear on current statement
   - Purchases after this date appear on next statement

2. **Payment Day** (Due Date)
   - When the bill must be paid
   - When money actually leaves your account
   - This is your `date_payed`

---

### How the System Calculates Payment Dates

**Rule**: A purchase's payment date depends on whether it falls before or after the cut-off day.

#### Same-Month Cycle

Purchase date is AFTER cut-off → Payment next month

**Example**: Cut-off: 25th, Payment: 5th

- Purchase: Jan 28 → Payment: Feb 5 (same month interval)

#### Next-Month Cycle

Purchase date is ON or BEFORE cut-off → Payment in following month

**Example**: Cut-off: 25th, Payment: 5th

- Purchase: Jan 15 → Payment: Feb 5 (next month)
- Purchase: Jan 25 → Payment: Feb 5 (next month)

---

### Visual Examples

**Account**: Visa (cut-off: 25th, payment: 5th)

```
January Timeline:
1  5  10  15  20  25  28  31
|  |              |  [cutoff]  |

Purchase on Jan 15:
  - Before cutoff (25th)
  - Goes on Jan statement
  - Payment: Feb 5

Purchase on Jan 28:
  - After cutoff (25th)
  - Goes on Feb statement
  - Payment: Mar 5
```

---

### Setting Up Credit Card Accounts

When adding a credit card, you need both dates:

```bash
python3 cli.py create account VisaCard credit_card \
  --cut-off-day 25 \
  --payment-day 5
```

Or use natural language:

```bash
python3 cli.py accounts add "Visa card with cut-off on 25 and payment on 5"
```

---

### Checking Payment Dates

After adding a transaction, verify the payment date:

```bash
python3 cli.py view --sort date_payed
```

Look for your transaction in the appropriate month based on the billing cycle.

---

### One-Time Billing Adjustments

If your bank changes the billing cycle for a single month:

```bash
python3 cli.py accounts adjust-billing VisaCard 2026-02 27 --payment-day 7
```

This creates a one-time override for February only.

---

## Troubleshooting & FAQ

### Database Location and Backup

**Q: Where is my database stored?**

A: `cash_flow.db` in the same directory as `cli.py`. Backups are stored in `backups/`.

**Q: How do I back up my data?**

Backups happen automatically before every mutating command. You can also create one manually:

```bash
python3 cli.py backup
```

**Q: How do I restore from backup?**

```bash
python3 cli.py backup list                    # Find the backup
python3 cli.py backup restore <filename>      # Restore it (creates safety backup first)
```

**Q: How do I configure backup retention?**

Set environment variables in `.env`. See [Backup](#backup) for the full configuration table.

---

### Resetting the System

**Q: How do I start fresh?**

1. Delete the database:

   ```bash
   rm cash_flow.db
   ```

2. Run any command to recreate it:

   ```bash
   python3 cli.py accounts list
   ```

---

### Balance Discrepancies

**Q: My balance doesn't match my bank account. What do I do?**

**Solution 1**: Use balance fix

```bash
python3 cli.py fix --balance <actual_amount> --account Cash
```

**Solution 2**: Find missing transactions

```bash
python3 cli.py view --sort date_created
python3 cli.py export transactions.csv
```

Compare exported CSV with bank statement to identify missing entries.

---

**Q: My credit card statement doesn't match tracked total. How do I reconcile?**

Use interactive statement fix:

```bash
python3 cli.py fix --payment VisaCard -i
```

This shows all transactions and lets you enter the actual statement amount. See [Reconciling Your Credit Card Statement](#reconciling-your-credit-card-statement).

---

### Budget Issues

**Q: I changed my budget amount but past months didn't update. Why?**

Budget changes are NOT retroactive by default. Use `--retroactive` for corrections:

```bash
python3 cli.py subscriptions edit budget_groceries --amount 450 --retroactive
```

---

**Q: My budget shows $0 but I haven't spent that much. What happened?**

Check if you overspent. Budgets cap at $0 when depleted.

```bash
python3 cli.py view | grep "Budget"
```

If allocation shows -0.00, you've used all the allocated funds.

---

**Q: How do I stop a budget without deleting it?**

Set an end date:

```bash
python3 cli.py subscriptions edit budget_groceries --end 2026-12-31
```

---

### Transaction Management

**Q: How do I find a transaction ID?**

```bash
python3 cli.py view
```

The first column is the ID. Or search:

```bash
python3 cli.py view | grep "Groceries"
```

---

**Q: I deleted a transaction by accident. Can I recover it?**

Only if you have a database backup:

```bash
cp cash_flow.db.backup cash_flow.db
```

Otherwise, re-add the transaction manually.

---

**Q: How do I edit all installments at once?**

Use the `--all` flag:

```bash
python3 cli.py edit <any_installment_id> --status pending --all
```

---

### LLM Parsing Issues

**Q: The LLM is misinterpreting my natural language input. What can I do?**

Be more explicit:

**Instead of**: "Bought stuff for 50"

**Try**: "Spent 50.00 on groceries on Cash today"

Include:

- Amount with decimal
- Category
- Account name
- Date (or "today"/"yesterday")

---

**Q: Do I need an API key for the LLM?**

Yes. Set up a `.env` file with your Gemini API key:

```
GEMINI_API_KEY=your_api_key_here
```

---

### Common Errors

**Error: "Account not found"**

Check available accounts:

```bash
python3 cli.py accounts list
```

Add the missing account:

```bash
python3 cli.py accounts add "Cash account"
```

---

**Error: "Category does not exist"**

Add the category:

```bash
python3 cli.py categories add groceries "Food and household"
```

---

**Error: "Subscription has committed transactions"**

You can't delete a budget/subscription with committed transactions. Delete forecast transactions first, or wait until they expire.

---

## Technical Details

### Technology Stack

- **Language**: Python 3.10+
- **Database**: SQLite
- **Testing**: Python `unittest` framework
- **CLI**: `argparse` + `rich` (tables, colors)
- **Telegram Bot**: `python-telegram-bot` 21.0
- **LLM**: [LiteLLM](https://github.com/BerriAI/litellm) — unified interface for Gemini, Ollama, OpenAI, Anthropic, etc.
- **Deployment**: Docker (optional, for the Telegram bot)

---

### Project Structure

The codebase is organized into three packages matching the layered architecture:

```
cash_flow/
├── cli.py                      # CLI entry point
├── bot.py                      # Telegram bot entry point
├── cashflow/                   # Core business logic
│   ├── controller.py           #   Orchestrator (transaction processing, rollover)
│   ├── transactions.py         #   Transaction factory functions
│   ├── repository.py           #   Data access layer (all SQL queries)
│   ├── database.py             #   Schema definition and initialization
│   └── config.py               #   Environment variable loading
├── llm/                        # LLM integration
│   ├── backend.py              #   Provider abstraction (LiteLLM, key rotation, fallbacks)
│   └── parser.py               #   NL→JSON parsing prompts and response handling
├── ui/                         # Presentation layer
│   ├── cli_display.py          #   Rich terminal tables and CSV export
│   └── telegram_format.py      #   Telegram Markdown formatting and navigation
├── tests/                      # Unit tests (80 tests, in-memory SQLite)
├── specs/                      # Feature specifications
├── llm_config.yaml.example     # LLM routing configuration template
├── Dockerfile.bot              # Docker image for the Telegram bot
├── docker-compose.bot.yml      # Docker Compose for bot deployment
└── requirements.txt
```

---

### Database Schema

**`accounts`** - Payment accounts

```sql
CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    account_type TEXT NOT NULL,
    cut_off_day INTEGER,
    payment_day INTEGER
);
```

**`categories`** - Expense categories

```sql
CREATE TABLE categories (
    name TEXT PRIMARY KEY,
    description TEXT
);
```

**`subscriptions`** - Recurring budgets and subscriptions

```sql
CREATE TABLE subscriptions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    monthly_amount REAL NOT NULL,
    payment_account_id TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    is_budget BOOLEAN DEFAULT 0,
    underspend_behavior TEXT DEFAULT 'keep'
);
```

**`transactions`** - All financial events

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_created DATE NOT NULL,
    date_payed DATE NOT NULL,
    description TEXT NOT NULL,
    account TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT,
    budget TEXT,
    status TEXT DEFAULT 'committed',
    origin_id TEXT,
    FOREIGN KEY (account) REFERENCES accounts(account_id)
);
```

**`settings`** - User settings

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

**`llm_examples`** - Raw user inputs paired with LLM parse results

```sql
CREATE TABLE llm_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_input TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    transaction_ids TEXT,
    source TEXT NOT NULL DEFAULT 'cli',
    timestamp DATE DEFAULT CURRENT_DATE
);
```

Captures the natural language input that produced each transaction, along with the full parsed JSON and the IDs of the resulting transactions. Only saved when a transaction is confirmed (not for batch imports or cancelled entries). Used for future fuzzy matching, few-shot example retrieval, and local model training.

---

### Key Architectural Principles

#### Idempotency and State Management

The system uses an "orchestrator pattern" where `run_monthly_rollover(conn, date.today())` is called at the start of every session to ensure valid state.

This function is **idempotent**—running it multiple times has no effect beyond the first run:

- `commit_past_and_current_forecasts()`: Only affects `'forecast'` status transactions
- `generate_forecasts()`: Checks if forecasts already exist before creating new ones

**Golden Rule**: Always call `run_monthly_rollover()` at session start.

---

#### The Live Budget Allocation System

Budgets are transactions with negative amounts that update in real-time as you spend:

1. **Allocation**: Create transaction with `-400` (the envelope)
2. **Spending**: Update allocation: `-400 + 50 = -350` (money taken from envelope)
3. **Overspending**: Cap at `0` if you spend more than remaining

This prevents double-counting—money is "spent" when allocated, not when used.

---

### Development and Testing

The project uses **Test-Driven Development (TDD)**:

1. Write test first (define expected behavior)
2. Run test (confirm it fails)
3. Write code to make test pass
4. Refactor if needed

**Running tests**:

```bash
python3 -m unittest discover -s tests      # Run all tests
python3 -m unittest tests.test_budgets     # Run a specific test module
```

Tests use in-memory databases (`:memory:`) for speed and isolation. Use `create_test_db()` from `cashflow.database` for test setup — it initializes all tables, mock data, categories, and settings in one call:

```python
from cashflow.database import create_test_db

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()
```

**Available mock data in `create_test_db()`**:

| Type | Values |
|------|--------|
| **Accounts** | `Cash` (cash), `Visa Produbanco` (credit_card, cut-off=14, payment=25), `Amex Produbanco` (credit_card, cut-off=2, payment=15) |
| **Categories** | Housing, Home Groceries, Personal Groceries, Dining-Snacks, Transportation, Health, Personal, Income, Savings, Loans, Others |
| **Settings** | `forecast_horizon_months` = 6 |

When writing tests, use only the categories listed above — the app validates categories against the database. For budgets, use the category that best fits your test scenario (e.g. `"Others"` for generic tests, `"Home Groceries"` for food-related tests).

---

### Future Vision

- Email/SMS integration - Recording transactions automatically from purchase notifications.
- Financial advice ("You're on track to overspend on entertainment by $50 this month")
- Receipt/statement OCR via multimodal models

---

## Command Quick Reference

### Aliases

Most commands have short aliases for faster typing:

| Command         | Aliases      |
|-----------------|--------------|
| create          | cr           |
| accounts        | acc, a       |
| categories      | cat, c       |
| subscriptions   | sub, s       |
| view            | v            |
| export          | exp, x       |
| edit            | e            |
| delete          | del, d       |
| clear           | cl           |
| fix             | f            |
| backup          | bk           |

**Example**:

```bash
python3 cli.py a list      # Same as: accounts list
python3 cli.py s list      # Same as: subscriptions list
python3 cli.py v -m 6      # Same as: view --months 6
```

---

### Quick Command Cheat Sheet

```bash
# === SETUP (categories are pre-loaded; add custom ones if needed) ===
python3 cli.py accounts add "Cash account"        # LLM parses description
python3 cli.py accounts add -i                    # or: interactive guided mode
python3 cli.py categories add utilities "Electricity, water, gas"
python3 cli.py categories add -i                  # or: interactive guided mode
python3 cli.py subscriptions add "Groceries budget 400 on Cash"
python3 cli.py subscriptions add -i               # or: interactive guided mode

# === DAILY USE ===
python3 cli.py add "Spent 50 on groceries today"
python3 cli.py add -i                             # Interactive (no LLM)
python3 cli.py view
python3 cli.py view -s                            # Summary mode

# === MANAGING TRANSACTIONS ===
python3 cli.py edit 123 --status pending
python3 cli.py edit 123 -i                        # Interactive guided edit
python3 cli.py delete 456
python3 cli.py clear 789                          # Commit pending transaction

# === RECONCILIATION ===
python3 cli.py fix --payment VisaCard -i          # Interactive statement fix
python3 cli.py fix --balance 1500                 # Fix total balance

# === BUDGETS ===
python3 cli.py subscriptions list
python3 cli.py subscriptions edit budget_groceries --amount 450
python3 cli.py subscriptions edit budget_groceries -i  # Interactive guided edit
python3 cli.py subscriptions delete old_budget

# === VIEWING ===
python3 cli.py view -m 6                          # 6 months
python3 cli.py view --from 2026-01                # Start from January
python3 cli.py view --sort date_created           # Sort by purchase date
python3 cli.py export report.csv --with-balance

# === BACKUP ===
python3 cli.py backup                             # Manual backup (unnamed)
python3 cli.py backup "pre-migration"             # Manual backup (named)
python3 cli.py backup list                        # List backups (with type)
python3 cli.py backup restore <file>              # Restore from backup
```

---

## License

This project is open source and available under the MIT License.

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit a pull request

---

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Happy budgeting!** 🚀

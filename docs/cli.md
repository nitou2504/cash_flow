# CLI Reference

Entry point: `python3 cli.py COMMAND`. For detailed help on any command: `python3 cli.py <command> -h`.

Every command runs the monthly rollover on startup, so state is always current.

## Contents

1. [Adding transactions](#adding-transactions)
2. [Command reference](#command-reference)
3. [Common workflows](#common-workflows)
4. [Advanced features](#advanced-features)
5. [Troubleshooting & FAQ](#troubleshooting--faq)
6. [Quick reference](#quick-reference)

---

## Adding transactions

### Interactive mode (no LLM, works offline)

```bash
python3 cli.py add -i                          # Add transaction
python3 cli.py accounts add -i                 # Add account
python3 cli.py categories add -i               # Add category
python3 cli.py subscriptions add -i            # Add budget/subscription
python3 cli.py edit 123 -i                     # Edit transaction
python3 cli.py subscriptions edit budget_food -i  # Edit budget/subscription
```

Step-by-step guided entry with selection menus, defaults, and previews. No API keys, no configuration.

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
[number or name]> 2

Amount [prefix + for income]: $45.50

Category:
  1. Dining-Snacks - Eating out, takeout, coffee
  2. Home Groceries - Food and household items for home
[number or name]> 2

Budget:
  1. budget_groceries_feb_mar ($120/$400 spent, $280 left)
[number or name, empty to skip]> 1

Status [1.NORMAL / 2.pending / 3.planning]:

Transaction Preview
┌────────────┬──────────────────────────┐
│ Date       │ 2026-03-07               │
│ Date Payed │ 2026-04-05               │
│ Desc       │ Supermaxi groceries      │
│ Account    │ Visa Pichincha           │
│ Amount     │ -45.50                   │
│ Category   │ Home Groceries           │
│ Budget     │ budget_groceries_feb_mar │
└────────────┴──────────────────────────┘

Proceed? [Y/n]:
```

### Natural language (requires [LLM configuration](llm.md))

```bash
python3 cli.py add "Spent 45.50 on groceries at Supermaxi today on Visa Pichincha"
python3 cli.py add "Bought laptop for 1200 in 12 installments on Visa Pichincha"
python3 cli.py add "Phone plan 600 starting the 5th of 12 installments on Visa Pichincha"
python3 cli.py add "Bought a TV for 500 on Visa Pichincha with 3 months grace period"
python3 cli.py add "Friend will pay me 100 on March 15, pending"
python3 cli.py add "Split: 30 groceries, 15 snacks at Supermaxi"
```

The LLM auto-detects dates, accounts, categories, amounts, and transaction types — including installments, splits, pending status, and grace periods. A preview is shown before anything is saved (`-y` skips it).

### Explicit creation (no LLM, no prompts — for scripts and automation)

```bash
# Simple expense
python3 cli.py create transaction "Supermaxi groceries" 45.50 Cash -c groceries

# With budget
python3 cli.py create transaction "Supermaxi groceries" 45.50 Cash -c groceries -b budget_groceries_feb_mar

# Income
python3 cli.py create transaction "Salary" 3000 Cash --income

# Installments (12 monthly payments)
python3 cli.py create transaction "Laptop" 1200 VisaCard -n 12 -c electronics

# Partial installments (starting from 5th of 12)
python3 cli.py create transaction "Phone plan" 600 VisaCard -n 12 --start-installment 5

# Pending / planning
python3 cli.py create transaction "Friend owes me 50" 50 Cash --pending
python3 cli.py create transaction "Maybe a TV" 800 Cash --planning
```

| Flag | Description |
|------|-------------|
| `--category, -c` | Category name |
| `--budget, -b` | Budget ID |
| `--date, -d` | Transaction date YYYY-MM-DD (default: today) |
| `--installments, -n` | Number of installments (promotes amount to total) |
| `--start-installment` | Starting installment number (default: 1) |
| `--grace-period, -g` | Grace period in months |
| `--income` / `--pending` / `--planning` | Status flags |
| `--source` | Transaction source tag (e.g. `mom`) |
| `--needs-review` | Mark for review (`0` or `1`) |

Also available: `create account`, `create budget`, `create category`:

```bash
python3 cli.py create account VisaCard credit_card --cut-off-day 25 --payment-day 5
python3 cli.py create budget "Groceries" 300 Cash groceries
python3 cli.py create budget "Vacation" 200 Cash savings --start 2026-02-01 --end 2026-12-31
python3 cli.py create category dining "Eating out, takeout, coffee"
```

### CSV import

```bash
python3 cli.py add --import transactions.csv               # date,description,account,amount
python3 cli.py add --import installments.csv --installments  # + current_installment,total_installments
```

The installments variant creates the remaining installments from a statement line like "3/12", automatically calculating future payment dates.

---

## Command reference

### `view` — cash flow timeline

```bash
python3 cli.py view                      # Default: 3 months from today
python3 cli.py view -m 6                 # Show 6 months
python3 cli.py view --from 2026-01       # Start from specific month
python3 cli.py view -s                   # Summary mode (aggregate credit cards)
python3 cli.py view -s -p                # Summary with planning included
python3 cli.py view --sort date_created  # Sort by purchase date
```

Shows running balance, month-over-month change, starting balance, old pending transactions, and month separators. Color coding: blue = budget allocations, grey = pending, italic = forecast, magenta italic = planning.

**Summary mode (`-s`)** aggregates credit card transactions into monthly payment entries ("VisaCard Payment") — a clean forecast view. Cash transactions show normally.

### `edit` — modify transactions

```bash
# Flag-based
python3 cli.py edit 123 --status pending
python3 cli.py edit 456 --category groceries --budget budget_food
python3 cli.py edit 200 --status planning --all      # All installments in group

# Natural language (LLM)
python3 cli.py edit 42 "change amount to 45.50"
python3 cli.py edit 42 "move to home groceries budget"
python3 cli.py edit 42 "change date to march 5" -y   # Skip confirmation

# Interactive
python3 cli.py edit 123 -i
```

Flags: `--description/-d`, `--amount/-a`, `--date/-D`, `--category/-c`, `--budget/-b`, `--status/-s`, `--source`, `--needs-review`, `--all` (whole group), `-i`, `-y`.

**Amount sign handling**: a bare number keeps the original sign — an expense stays an expense. Prefix `+` to force income, `-` to force expense.

### `delete`, `clear`

```bash
python3 cli.py delete 123        # Delete (asks confirmation)
python3 cli.py delete 456 --all  # Delete whole installment group
python3 cli.py clear 123         # Commit pending/planning → committed
python3 cli.py clear 456 --all
```

### `review` — approve flagged transactions

Transactions created by [Telegram extra users](telegram-bot.md#extra-users-delegates) or the [Gmail pipeline](gmail-sync.md) are flagged `needs_review`.

```bash
python3 cli.py review ls                     # all unreviewed
python3 cli.py review ls --source gmail      # filter by source
python3 cli.py review 605                    # show details + mark reviewed
python3 cli.py review 605 -i                 # interactive edit + mark reviewed
python3 cli.py review 605 --budget budget_personal_jan_feb  # fix + mark reviewed
```

### `accounts`

```bash
python3 cli.py accounts list
python3 cli.py accounts add -i
python3 cli.py accounts add "Visa card with cut-off on 25 and payment on 5"   # LLM
python3 cli.py accounts adjust-billing VisaCard 2026-02 27 --payment-day 7   # one-off cycle change
```

### `subscriptions` — budgets & recurring payments

```bash
python3 cli.py subscriptions list              # Active only
python3 cli.py subscriptions list --all        # Include expired
python3 cli.py subscriptions list --budgets-only

python3 cli.py subscriptions add -i
python3 cli.py subscriptions add "Monthly groceries budget of 400 on Cash"    # LLM
python3 cli.py subscriptions add "Netflix subscription 15.99 on Visa"         # LLM

python3 cli.py subscriptions edit budget_groceries --amount 350
python3 cli.py subscriptions edit budget_groceries --amount 350 --retroactive # fix past months too
python3 cli.py subscriptions edit budget_vacation --end 2026-12-31
python3 cli.py subscriptions edit budget_vacation --end none                  # make ongoing
python3 cli.py subscriptions edit budget_groceries -i

python3 cli.py subscriptions delete budget_groceries
```

Edit flags: `--name/-n`, `--amount/-a`, `--account/-c`, `--end/-e`, `--underspend/-u` (keep/return), `--retroactive/-r`, `-i`.

Amount changes are **not retroactive by default** — they only affect future months. `--retroactive` is for correcting past allocation errors. Deleting is blocked while committed transactions exist.

### `categories`

```bash
python3 cli.py categories list
python3 cli.py categories add groceries "Food and household items"
python3 cli.py categories edit groceries "Food, household items, and toiletries"
python3 cli.py categories delete old_category    # blocked if transactions use it
```

The description matters: it's fed to the LLM for auto-classification.

### `liabilities` — what you owe per credit card

```bash
python3 cli.py liabilities        # Default 6-month horizon
python3 cli.py liab -m 3          # 3-month horizon
python3 cli.py owe -d             # Detail mode (per-transaction breakdown)
```

Renders four tables: per-cycle liabilities per card, subscriptions over the horizon, budget envelopes over the horizon, and a summary split into *owed on next bill*, *owed later cycles*, and horizon totals.

**Owed semantics**: a transaction is "owed" when `date_created <= today` and `date_payed > today` — money already spent but not yet pulled from your account, including future installment cuotas of past purchases.

### `fix` — reconciliation

```bash
# Fix total cash balance to match reality (creates adjustment transaction)
python3 cli.py fix --balance 1500.00
python3 cli.py fix --balance 1500.00 --account Cash

# Reconcile a CC statement
python3 cli.py fix --payment VisaCard -i           # interactive: shows txns, asks amount
python3 cli.py fix --payment VisaCard 450.50       # auto-detect month
python3 cli.py fix --payment VisaCard 2026-01 450.50
```

Smart month detection: before the cut-off day reconciles the current month; after it, the next month.

### `export`

```bash
python3 cli.py export transactions.csv
python3 cli.py export transactions.csv --with-balance
```

### `backup`

```bash
python3 cli.py backup                    # Manual backup (never auto-deleted)
python3 cli.py backup "pre-migration"    # Named manual backup
python3 cli.py backup list
python3 cli.py backup restore <file>     # Creates a pre-restore safety backup first
```

Auto backups are created before every mutating CLI command (SQLite backup API, safe while in use) and logged to `backups/backup.log`.

Retention (auto backups only):

| Age | Kept |
|-----|------|
| Today | First backup of the day + last N (default 5) |
| 1 day to `BACKUP_MAX_DAYS` (default 30) | Last backup per day |
| Older | Deleted |

Configuration via `.env`: `BACKUP_ENABLED`, `BACKUP_DIR`, `BACKUP_KEEP_TODAY`, `BACKUP_RECENT_DAYS`, `BACKUP_MAX_DAYS`, `BACKUP_LOG_RETENTION_DAYS`.

### `bot` — Telegram bot container management

```bash
python3 cli.py bot restart    # Rebuild and restart the container
python3 cli.py bot logs       # Last 50 lines
python3 cli.py bot logs -f    # Follow
python3 cli.py bot stop
```

---

## Common workflows

### Setting up your first month

```bash
python3 cli.py accounts add -i                                    # Cash + cards
python3 cli.py fix --balance 2500.00 --account Cash               # starting balance
python3 cli.py subscriptions add "Groceries budget 400 on Cash"   # envelopes
python3 cli.py subscriptions add "Netflix 15.99 on Visa"          # subscriptions
python3 cli.py view -m 3                                          # see the forecast
```

Categories are pre-loaded; add custom ones with `categories add`.

### Tracking a large purchase with installments

```bash
python3 cli.py add "Bought new laptop for 1200 in 12 installments on Visa"
python3 cli.py view -m 12                       # see "Laptop (1/12)" … spread out
python3 cli.py edit <id> --status pending --all # edit the whole group
python3 cli.py delete <id> --all                # or delete the whole plan
```

### Reconciling a credit card statement

```bash
python3 cli.py fix --payment VisaCard -i
# → shows tracked transactions for the cycle and the current total
# → enter the actual statement amount
# → creates a "Payment Adjustment" transaction for the difference
```

Common causes of differences: forgotten transaction, wrong amount, card fees/interest, returns. Use `view --sort date_created` to compare purchases against the statement.

### Planning future expenses

```bash
python3 cli.py add "Planning vacation package for 2000 on Visa in June"  # status: planning
python3 cli.py view -m 6      # planning shows magenta italic, affects projection
python3 cli.py clear <id>     # commit when decided
python3 cli.py delete <id>    # or drop the plan
```

### Month-end review

```bash
python3 cli.py subscriptions list --budgets-only   # depleted or underused envelopes?
python3 cli.py view | grep pending                  # anything to clear or delete?
python3 cli.py subscriptions edit budget_groceries --amount 450   # adjust next month
python3 cli.py view -m 2                            # check MoM change column
python3 cli.py export monthly_report.csv --with-balance
```

---

## Advanced features

- **Split transactions** — `add "Spent 100: 60 on groceries, 40 on household items"` creates separate linked entries per portion.
- **Grace periods** — "buy now, pay later": the effective date shifts forward N months before the billing formula applies.
- **Retroactive budget corrections** — `subscriptions edit <id> --amount 450 --retroactive` updates past committed months and recalculates balances. For corrections only, not for "increase going forward".
- **Transaction groups** — installments and splits share an `origin_id`; `--all` edits/deletes the whole group.
- **Billing cycle adjustments** — `accounts adjust-billing` creates a one-month override; future months use the normal cycle.

---

## Troubleshooting & FAQ

**Where is my data?** `cash_flow.db` next to `cli.py`; backups in `backups/`.

**Start fresh?** `rm cash_flow.db`, then run any command to recreate it.

**Balance doesn't match my bank.** `fix --balance <actual>` — or export CSV and compare against the statement to find missing entries.

**Budget shows $0 but I haven't spent that much.** Envelopes cap at 0 when depleted — you overspent.

**Stop a budget without deleting it.** `subscriptions edit <id> --end 2026-12-31`.

**Find a transaction ID.** First column of `view`; grep the description.

**Deleted a transaction by accident.** `backup list` → `backup restore <file>` (auto backups run before every mutation).

**LLM misinterprets input.** Be explicit: amount with decimals, category, account name, and a date. See [LLM configuration](llm.md).

**"Account not found" / "Category does not exist"** — check `accounts list` / `categories list` and add the missing one.

**"Subscription has committed transactions"** — budgets/subscriptions can't be deleted while committed transactions reference them.

---

## Quick reference

### Aliases

| Command | Aliases | | Command | Aliases |
|---|---|---|---|---|
| `add` | | | `view` | `v` |
| `create` | `cr` | | `edit` | `e` |
| `accounts` | `acc`, `a` | | `delete` | `del`, `d` |
| `categories` | `cat`, `c` | | `clear` | `cl` |
| `subscriptions` | `sub`, `s` | | `fix` | `f` |
| `liabilities` | `liab`, `owe` | | `backup` | `bk` |
| `review` | `rv` | | `export` | `exp`, `x` |

### Cheat sheet

```bash
# === DAILY USE ===
python3 cli.py add "Spent 50 on groceries today"
python3 cli.py add -i                             # Interactive (no LLM)
python3 cli.py view
python3 cli.py view -s                            # Summary mode

# === MANAGING TRANSACTIONS ===
python3 cli.py edit 123 --status pending
python3 cli.py delete 456
python3 cli.py clear 789                          # Commit pending/planning

# === RECONCILIATION ===
python3 cli.py fix --payment VisaCard -i
python3 cli.py fix --balance 1500

# === BUDGETS ===
python3 cli.py subscriptions list
python3 cli.py subscriptions edit budget_groceries --amount 450

# === REVIEW (Gmail / delegates) ===
python3 cli.py review ls
python3 cli.py review 605 -i

# === BACKUP ===
python3 cli.py backup "pre-migration"
python3 cli.py backup restore <file>
```

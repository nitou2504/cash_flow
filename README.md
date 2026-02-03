# Personal Cash Flow Tool

A powerful, terminal-based cash flow management system designed for clarity, traceability, and accurate forecasting. Track expenses, manage budgets, handle credit card payments, and see your financial future—all from the command line.

## What Makes This Different?

- **True Cash Flow Forecasting**: See exactly how much money you'll have on any future date, accounting for all commitments
- **Smart Credit Card Handling**: Automatically calculates payment dates based on billing cycles—no more manual tracking
- **Live Budget System**: Digital envelopes that update in real-time as you spend, with accurate remaining balances
- **Natural Language Input**: Add transactions by typing "Spent 45.50 on groceries today" instead of filling forms
- **Single Timeline View**: Past, present, and future transactions in one unified view—no separate budget sheets
- **Telegram Bot Integration**: Track expenses on-the-go via Telegram chat with natural language and confirmation workflow

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Telegram Bot](#telegram-bot)
3. [Core Concepts](#core-concepts)
4. [CLI Command Reference](#cli-command-reference)
5. [Common Workflows](#common-workflows)
6. [Advanced Features](#advanced-features)
7. [Understanding Transaction Statuses](#understanding-transaction-statuses)
8. [Understanding Credit Card Cycles](#understanding-credit-card-cycles)
9. [Troubleshooting & FAQ](#troubleshooting--faq)
10. [Technical Details](#technical-details)
11. [Command Quick Reference](#command-quick-reference)

---

## Quick Start

### Prerequisites

- Python 3.7+
- pip (Python package manager)
- SQLite (usually included with Python)

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
   python3 cli.py accounts add-manual Cash cash
   ```

4. **Add a category**
   ```bash
   python3 cli.py categories add groceries "Food and household items"
   ```

5. **Record your first income**
   ```bash
   python3 cli.py add "Income 3000 on Cash"
   ```

6. **Add your first expense**
   ```bash
   python3 cli.py add "Spent 45.50 on groceries today"
   ```

7. **View your cash flow**
   ```bash
   python3 cli.py view
   ```

You should see a table showing your transactions with running balance. You're ready to go!

---

## Telegram Bot

Track expenses on-the-go using the Telegram chatbot! Add transactions via natural language messages with an intuitive confirmation and correction workflow.

### Quick Setup

1. **Install Telegram bot dependencies**
   ```bash
   pip install python-telegram-bot==21.0
   ```

2. **Get your bot token from [@BotFather](https://t.me/BotFather)**
   - Send `/newbot` to BotFather on Telegram
   - Follow prompts to create your bot
   - Copy the token provided

3. **Add token to `.env` file**
   ```bash
   TELEGRAM_BOT_TOKEN=your_token_here
   ```

4. **Start the bot**
   ```bash
   python3 telegram_bot.py
   ```

5. **Chat with your bot**
   - Find your bot on Telegram
   - Send `/start` to begin
   - Start tracking expenses naturally!

### Usage

Just send messages like:
- `"Spent 50 on groceries today"`
- `"Bought laptop for 1200 in 12 installments on Visa"`
- `"Split: 30 on groceries, 15 on snacks"`

The bot will:
1. Parse your message using the same LLM as the CLI
2. Show a formatted preview with inline buttons
3. Let you ✅ Confirm or ✍️ Revise before saving
4. Allow corrections in natural language if needed

For detailed setup instructions and troubleshooting, see [TELEGRAM_BOT_SETUP.md](TELEGRAM_BOT_SETUP.md).

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

#### `add` - Add a transaction using natural language

The easiest way to record expenses and income.

```bash
python3 cli.py add "Spent 45.50 on groceries at Walmart today"
python3 cli.py add "Bought TV for 600 in 12 installments on Visa card"
python3 cli.py add "Income 3000 on Cash"
python3 cli.py add "Split purchase: 30 on groceries, 15 on snacks"
```

**What it does**: Parses your natural language description using an LLM, shows you a preview table, and asks for confirmation before creating the transaction.

**Key features**:
- Auto-detects transaction type (simple, installment, split)
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

#### `add-batch` - Import multiple transactions from CSV

Bulk import transactions from a CSV file.

```bash
python3 cli.py add-batch transactions.csv
```

**CSV format**: `date,description,account,amount`
```csv
01/15/26,Groceries at Walmart,Cash,-45.50
01/16/26,Gas station,Cash,-35.00
```

**What it does**: Reads each line, shows a preview, and asks for confirmation for each transaction.

---

#### `add-installments` - Import installment sequences from CSV

Import pre-existing installment plans (e.g., from a credit card statement showing "3/12" installments).

```bash
python3 cli.py add-installments installments.csv
```

**CSV format**: `date,description,account,amount,current_installment,total_installments`
```csv
01/15/26,New Laptop,VisaCard,83.33,3,12
```

**What it does**: Creates the remaining installments (3/12 through 12/12 in this example), automatically calculating future payment dates.

---

#### `edit` - Modify transaction details

Edit a transaction's properties. Use `--all` to edit all installments in a group.

```bash
python3 cli.py edit 123 --status pending
python3 cli.py edit 456 --category groceries --budget budget_food
python3 cli.py edit 789 --amount 50.00
python3 cli.py edit 100 --date 2026-01-15
python3 cli.py edit 200 --status planning --all  # Edit all installments
```

**Available options**:
- `--description, -d`: Change description
- `--amount, -a`: Change amount
- `--date, -D`: Change creation date (YYYY-MM-DD)
- `--category, -c`: Assign to category
- `--budget, -b`: Link to budget
- `--status, -s`: Change status (committed/pending/planning/forecast)
- `--all`: Apply changes to entire transaction group

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

#### `accounts add-manual` - Create account with parameters

Add an account with explicit parameters.

```bash
# Cash account
python3 cli.py accounts add-manual Cash cash

# Credit card (requires cut-off and payment days)
python3 cli.py accounts add-manual VisaCard credit_card --cut-off-day 25 --payment-day 5
```

**Parameters**:
- `id`: Account name (e.g., "Cash", "VisaCard")
- `type`: "cash" or "credit_card"
- `--cut-off-day, -c`: Statement closing day (1-31, credit cards only)
- `--payment-day, -p`: Payment due day (1-31, credit cards only)

---

#### `accounts add-natural` - Natural language account creation (recommended)

Add accounts using natural language—easier than manual mode.

```bash
python3 cli.py accounts add "Cash account"
python3 cli.py accounts add "Visa card with cut-off on 25 and payment on 5"
python3 cli.py accounts add "MasterCard closing on 15th, due on 3rd"
```

**What it does**: Parses your description, shows the generated account details, and asks for confirmation.

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

#### `subscriptions add-manual` - Create budget with parameters

Manually configure a budget or subscription.

```bash
python3 cli.py subscriptions add-manual "Groceries" 300 Cash groceries
python3 cli.py subscriptions add-manual "Netflix" 15.99 VisaCard entertainment \
  --start 2026-02-01
python3 cli.py subscriptions add-manual "Vacation Fund" 200 Cash savings \
  --start 2026-02-01 --end 2026-12-31
```

**Parameters**:
- `name`: Budget/subscription name
- `amount`: Monthly amount
- `account`: Account to charge
- `category`: Category name
- `--start, -s`: Start date (default: today)
- `--end, -e`: End date (omit for ongoing)
- `--underspend, -u`: "keep" (rollover) or "return" unused funds

---

#### `subscriptions add` - Natural language creation (recommended)

Add budgets and subscriptions using natural language.

```bash
python3 cli.py subscriptions add "Monthly groceries budget of 300 on Cash"
python3 cli.py subscriptions add "Netflix subscription 15.99 on Visa"
python3 cli.py subscriptions add "Vacation fund 200/month until December"
```

**What it does**: Parses your description, shows JSON preview, asks for confirmation, and generates forecast transactions.

---

#### `subscriptions edit` - Modify existing budget/subscription

Update budget parameters.

```bash
python3 cli.py subscriptions edit budget_groceries --amount 350
python3 cli.py subscriptions edit budget_groceries --amount 350 --retroactive
python3 cli.py subscriptions edit sub_netflix --account Cash
python3 cli.py subscriptions edit budget_vacation --end 2026-12-31
python3 cli.py subscriptions edit budget_vacation --end none  # Make ongoing
```

**Parameters**:
- `--name, -n`: New name
- `--amount, -a`: New monthly amount
- `--account, -c`: New account
- `--end, -e`: End date (YYYY-MM-DD) or "none"
- `--underspend, -u`: "keep" or "rollover"
- `--retroactive, -r`: Apply changes to past months (corrections only)

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

## Common Workflows

### Setting Up Your First Month

**Goal**: Get the system configured with accounts, categories, and initial balance.

1. **Create your accounts**
   ```bash
   python3 cli.py accounts add "Cash account"
   python3 cli.py accounts add "Visa card with cut-off on 25 and payment on 5"
   ```

2. **Add common categories**
   ```bash
   python3 cli.py categories add groceries "Food and household items"
   python3 cli.py categories add utilities "Electricity, water, gas"
   python3 cli.py categories add entertainment "Movies, dining out, hobbies"
   python3 cli.py categories add transport "Gas, public transit, car expenses"
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
- **"keep" (default)**: Unused money stays allocated (rolled over)
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
python3 cli.py accounts add-manual VisaCard credit_card \
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

A: `cash_flow.db` in the same directory as `cli.py`.

**Q: How do I back up my data?**

```bash
cp cash_flow.db cash_flow.db.backup
```

Or use git:

```bash
git add cash_flow.db
git commit -m "Backup database"
```

**Q: How do I restore from backup?**

```bash
cp cash_flow.db.backup cash_flow.db
```

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

Yes. Set up a `.env` file with your Google AI API key:

```
GOOGLE_API_KEY=your_api_key_here
```

---

### Performance

**Q: The CLI is slow. How can I speed it up?**

- Reduce forecast horizon:
  ```bash
  python3 cli.py view -m 3  # Instead of -m 12
  ```

- Use summary mode:
  ```bash
  python3 cli.py view -s
  ```

- Archive old transactions (manual process: export, delete old data, keep database small)

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

- **Language**: Python 3.7+
- **Database**: SQLite
- **Testing**: Python `unittest` framework
- **CLI**: `argparse`
- **Display**: `rich` library (tables, colors)
- **LLM**: Google Generative AI API

---

### Project Structure

```
cash_flow/
├── cli.py                    # Main CLI interface and command handlers
├── main.py                   # Controller: orchestrates business logic
├── transactions.py           # Core transaction creation logic
├── repository.py             # Data persistence layer (database operations)
├── database.py               # Schema creation and initialization
├── interface.py              # Display logic (view, export)
├── llm_parser.py             # Natural language parsing
├── requirements.txt          # Python dependencies
├── cash_flow.db              # SQLite database (created on first run)
├── tests/                    # Unit tests
│   ├── test_transactions.py
│   ├── test_budgets.py
│   └── ...
└── specs/                    # Feature specifications
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
python3 -m tests.test_transactions
python3 -m tests.test_budgets
```

Tests use in-memory databases (`:memory:`) for speed and isolation.

---

### Future Vision: Enhanced LLM Integration

The backend is designed to be driven by structured JSON objects. The ultimate goal is deeper LLM integration for:

- Smarter natural language parsing
- Automatic categorization
- Anomaly detection ("This grocery purchase is 3x your usual—is this correct?")
- Financial advice ("You're on track to overspend on entertainment by $50 this month")

---

## Command Quick Reference

### Aliases

Most commands have short aliases for faster typing:

| Command         | Aliases      |
|-----------------|--------------|
| accounts        | acc, a       |
| categories      | cat, c       |
| subscriptions   | sub, s       |
| view            | v            |
| export          | exp, x       |
| edit            | e            |
| delete          | del, d       |
| clear           | cl           |
| fix             | f            |
| add-batch       | ab           |
| add-installments| ai           |

**Example**:
```bash
python3 cli.py a list      # Same as: accounts list
python3 cli.py s list      # Same as: subscriptions list
python3 cli.py v -m 6      # Same as: view --months 6
```

---

### Quick Command Cheat Sheet

```bash
# === SETUP ===
python3 cli.py accounts add "Cash account"
python3 cli.py categories add groceries "Food and household"
python3 cli.py subscriptions add "Groceries budget 400 on Cash"

# === DAILY USE ===
python3 cli.py add "Spent 50 on groceries today"
python3 cli.py view
python3 cli.py view -s                    # Summary mode

# === MANAGING TRANSACTIONS ===
python3 cli.py edit 123 --status pending
python3 cli.py delete 456
python3 cli.py clear 789                  # Commit pending transaction

# === RECONCILIATION ===
python3 cli.py fix --payment VisaCard -i  # Interactive statement fix
python3 cli.py fix --balance 1500         # Fix total balance

# === BUDGETS ===
python3 cli.py subscriptions list
python3 cli.py subscriptions edit budget_groceries --amount 450
python3 cli.py subscriptions delete old_budget

# === VIEWING ===
python3 cli.py view -m 6                  # 6 months
python3 cli.py view --from 2026-01        # Start from January
python3 cli.py view --sort date_created   # Sort by purchase date
python3 cli.py export report.csv --with-balance
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

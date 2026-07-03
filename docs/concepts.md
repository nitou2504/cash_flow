# Core Concepts

## Everything is a Transaction

Instead of separate systems for history, subscriptions, and budgets, everything is represented in the same `transactions` table — a single, unified timeline of your money: past, present, and future.

## The Key to Forecasting: Two Dates

- **`date_created`** — when a transaction occurred (purchase date)
- **`date_payed`** — when it actually impacts your cash flow (payment date)

This distinction is crucial for credit cards. When you buy something on January 15th but your credit card bill isn't due until February 5th, your cash flow is affected on February 5th, not January 15th.

## Subscriptions and Recurring Payments

Tell the tool about your Netflix subscription once, and it automatically creates future `forecast` transactions for as many months ahead as you want. You immediately see how much money is already earmarked for future months.

Everything runs on a monthly cycle anchored to `start_date`:

- The **day-of-month** from `start_date` is used for every forecast transaction. A budget starting on March 7th creates allocations on the 7th of each month. If the day doesn't exist in a month (the 31st in February), it falls back to the last day of that month.
- **End date is inclusive**: `start=03-01, end=04-05` generates transactions for both March 1st and April 1st. But `start=03-20, end=04-05` only generates March 20th.
- **Cash accounts**: `date_payed = date_created`. **Credit cards**: payment date is calculated from the card's billing cycle.
- **Budget spending** is tracked per calendar month regardless of the allocation day.

## Live Budgeting: The Digital Envelope System

Budgets are live transactions, not numbers in a separate sheet. A $400 Food budget creates a transaction of `-400` — the envelope.

1. **Initial state:** the "Food Budget" transaction shows `-400`.
2. **You spend $50 on groceries:** the envelope absorbs it: `-400 + 50 = -350`. $350 remaining.
3. **You spend another $370:** more than the $350 left. The envelope is capped at `0` (fully spent), but your actual $370 expense is still recorded in full.

You can see at a glance that the budget is exhausted, while your overall cash flow remains accurate because the **real transaction amount is always preserved**.

The running balance never double-counts: money is "spent" from your cash flow the moment it's allocated to an envelope. Spending against the budget later just categorizes the expense.

```
cli.py view
┌──────────┬────────────────────────┬──────────┬────────┬────────────┐
│ Paid     │ Description            │ Account  │ Amount │ Balance    │
├──────────┼────────────────────────┼──────────┼────────┼────────────┤
│ 03/01    │ Salary                 │ Cash     │ +3000  │ 3000.00    │
│ 03/01    │ budget_groceries ✉     │ Cash     │  -320  │ 2680.00    │  ← was -400, absorbed $80
│ 03/05    │ Groceries              │ Cash     │   -80  │ 2600.00    │  ← balance unchanged
└──────────┴────────────────────────┴──────────┴────────┴────────────┘
```

### Underspend behavior

At month end, you decide what happens to leftover budget money:

- **keep** (default): leftover stays reserved (covers untracked purchases; allocation stays negative)
- **return**: a positive "Budget Release" transaction returns the leftover to your cash flow

## Transaction Statuses

| Status      | Affects balance? | Auto-generated? | Use case                          |
|-------------|------------------|-----------------|-----------------------------------|
| `committed` | Yes              | No              | Confirmed transactions            |
| `forecast`  | Yes              | Yes             | Predicted recurring expenses — becomes `committed` on monthly rollover |
| `pending`   | No               | No              | Happened but unconfirmed — commit with `clear` |
| `planning`  | Yes              | No              | What-if / potential future expense — commit with `clear` or delete |

**Planning vs pending**: planning is a future *potential* expense that affects the forecast; pending is an expense that already happened but awaits confirmation and does **not** affect the running balance until cleared.

## Credit Card Cycles

Credit cards have two key dates:

1. **Cut-off day** (statement closing): purchases on or before this day appear on the current statement; after it, on the next one.
2. **Payment day** (due date): when money actually leaves your account — this becomes `date_payed`.

```
Account: Visa (cut-off: 25th, payment: 5th)

Purchase on Jan 15:  before cutoff → Jan statement → payment Feb 5
Purchase on Jan 28:  after cutoff  → Feb statement → payment Mar 5
```

Grace periods shift the effective date forward N months before applying the billing formula.

One-off cycle changes (bank moves your statement date for a single month):

```bash
python3 cli.py accounts adjust-billing VisaCard 2026-02 27 --payment-day 7
```

## Monthly Rollover

`run_monthly_rollover()` runs at the start of every session (CLI, bot, web) and keeps state valid. It is **idempotent**:

- commits past/current `forecast` transactions
- generates new forecasts up to the horizon
- runs month-end budget reconciliation (underspend keep/return)

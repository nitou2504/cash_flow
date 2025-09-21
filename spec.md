# 📑 Specification: Simplified Personal Cash Flow Tool

## 1. Overview

This document outlines the design for a personal cash flow management tool focused on simplicity, traceability, and ease of use. The core principle is to represent every financial event in a single, flat `transactions` table, making the entire system transparent and easily exportable to human-readable formats like CSV.

The system is built on three simple data models:
*   **`transactions`**: The central ledger for all financial events (expenses, income, budgets, etc.).
*   **`accounts`**: A small table to define the properties of payment methods (e.g., credit card cut-off dates).
*   **`budgets`**: A simple lookup table defining the monthly financial plan.

---

## 2. Data Model

### 2.1 `transactions` Table

This is the single source of truth for all financial data. Each row represents one atomic financial event.

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | No | Primary Key for the transaction. |
| `date_created` | DATE | No | The date the transaction occurred. |
| `date_payed` | DATE | No | The date the transaction affects cash flow. |
| `description` | TEXT | No | A human-readable description. |
| `account` | TEXT | Yes | The account used. `NULL` for `forecast` transactions. |
| `amount` | REAL | No | The value. Negative for debits, positive for credits. |
| `category` | TEXT | Yes | Detailed classification. `NULL` for `forecast` transactions. |
| `budget_category` | TEXT | Yes | The budget this transaction belongs to. `NULL` if not budgeted. |
| `status` | TEXT | No | The state of the transaction (see below). |
| `origin_id` | TEXT | Yes | Groups related transactions. Format: `YYYYMMDD-<Letter>`. |

#### Status Enum:
*   `committed`: A real, confirmed financial event. Its impact is determined by its `date_payed`.
*   `pending`: A transaction awaiting confirmation (e.g., a loan to be repaid).
*   `forecast`: A virtual transaction representing the live state of a budget.


#### Category Enum

* `food`
* `dining`
* `transport`
* `housing`
* `health`
* `education`
* `entertainment`
* `shopping`
* `personal`
* `family`
* `savings`
* `income`
* `fees`
* `other`

---

### 2.2 `accounts` Table

Stores the properties of each payment account, enabling automated logic.

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `account_id` | TEXT | No | Primary Key, the human-readable account name. |
| `account_type` | TEXT | No | `credit_card`, `debit_card`, `cash`, `bank_account`. |
| `cut_off_day` | INTEGER | Yes | For credit cards, the day the statement closes (1-31). |
| `payment_day` | INTEGER | Yes | For credit cards, the day the payment is due (1-31). |

---

### 2.3 `budgets` Table

Defines the monthly financial plan. This is the source of truth for original budget amounts.

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `budget_category` | TEXT | No | Primary Key, the name of the budget. |
| `amount` | REAL | No | The total monthly allocated amount. |

---

## 3. Key Workflows & Examples

### Example A: Simple Cash Expense

**Input:** *"Taxi 4.50 cash"*

**Result:** A single `committed` transaction is created.

| date_created | date_payed | description | account | amount | category | budget_category | status | origin_id |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-10-16 | 2025-10-16 | Taxi | Cash | -4.50 | taxi | transport | committed | `NULL` |

---

### Example B: Credit Card Transaction

**Context:** The `accounts` table has an entry for `Visa Produbanco` with `cut_off_day: 14` and `payment_day: 25`.

**Input:** *"Dinner at Luigi's 45.00 with Visa Produbanco"* on **October 16th**.

**Logic:**
1. The system sees the transaction is on the 16th, which is *after* the cut-off day of the 14th.
2. It correctly calculates that this payment will be due on the *next* month's statement.
3. It sets `date_payed` to November 25th.

**Result:**

| date_created | date_payed | description | account | amount | category | budget_category | status | origin_id |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-10-16 | 2025-11-25 | Dinner at Luigi's | Visa Produbanco | -45.00 | restaurant | food | committed | `NULL` |

---

### Example C: Credit Card Installments

**Input:** *"New TV 900.00 with Visa Produbanco, 3 installments"*

**Logic:**
1. The system generates a unique `origin_id` (e.g., `20251016-T1V9`).
2. It creates three separate `committed` transactions, each for `-300.00`.
3. It appends `(1/3)`, `(2/3)`, `(3/3)` to the descriptions.
4. It calculates the correct future `date_payed` for each installment.

**Result:**

| date_created | date_payed | description | account | amount | category | budget_category | status | origin_id |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-10-16 | 2025-11-25 | New TV (1/3) | Visa Produbanco | -300.00 | electronics | shopping | committed | 20251016-T1V9 |
| 2025-10-16 | 2025-12-25 | New TV (2/3) | Visa Produbanco | -300.00 | electronics | shopping | committed | 20251016-T1V9 |
| 2025-10-16 | 2026-01-25 | New TV (3/3) | Visa Produbanco | -300.00 | electronics | shopping | committed | 20251016-T1V9 |

---

### Example D: Split Transaction

**Input:** *"Supermaxi 120. 100 for family food, 20 for personal snacks."*

**Logic:**
1. The system generates a unique `origin_id` (e.g., `20251016-S5M2`).
2. It creates two separate `committed` transactions linked by the `origin_id`.

**Result:**

| date_created | date_payed | description | account | amount | category | budget_category | status | origin_id |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-10-17 | 2025-11-25 | Supermaxi | Visa Produbanco | -100.00 | groceries | food | committed | 20251016-S5M2 |
| 2025-10-17 | 2025-11-25 | Supermaxi | Visa Produbanco | -20.00 | snacks | personal | committed | 20251016-S5M2 |

---

### Example E: The Budgeting Cycle

This example shows how the live `forecast` transaction is managed.

**1. Initial State:** The `budgets` table defines the plan.
*   `budgets` table:
    *   `budget_category: 'food'`, `amount: 300`
    *   `budget_category: 'transport'`, `amount: 100`

**2. Start of Month (Oct 1st):** The system creates `forecast` transactions.
*   `transactions` table:
    *   `date_payed: '2025-10-31', amount: -300, budget_category: 'food', status: 'forecast'`
    *   `date_payed: '2025-10-31', amount: -100, budget_category: 'transport', status: 'forecast'`

**3. Logging an Expense (Oct 17th):** A user buys groceries.
*   A new `committed` transaction is added:
    *   `date_created: '2025-10-17', amount: -50, budget_category: 'food', status: 'committed'`

**4. Live Budget Update:** The system immediately finds and updates the `forecast` transaction for the 'food' budget.
*   **Logic:** `UPDATE transactions SET amount = amount + 50 WHERE budget_category = 'food' AND status = 'forecast' ...`
*   The `food` forecast transaction's amount is now **-250**.

**5. Final State:** The `transactions` table now reflects the live remaining budget.
*   `transactions` table:
    *   `... amount: -250, budget_category: 'food', status: 'forecast'`
    *   `... amount: -100, budget_category: 'transport', status: 'forecast'`
    *   `... amount: -50, budget_category: 'food', status: 'committed'`

---

## 4. CSV Export Example

Exporting the `transactions` table provides a clear, useful report.

```csv
id,date_created,date_payed,description,account,amount,category,budget_category,status,origin_id
101,2025-10-16,2025-10-16,Taxi,Cash,-4.50,taxi,transport,committed,
102,2025-10-16,2025-11-25,Dinner at Luigi's,Visa Produbanco,-45.00,restaurant,food,committed,
103,2025-10-17,2025-11-25,Supermaxi,Visa Produbanco,-100.00,groceries,food,committed,20251016-S5M2
104,2025-10-17,2025-11-25,Supermaxi,Visa Produbanco,-20.00,snacks,personal,committed,20251016-S5M2
105,2025-10-31,2025-10-31,Food Budget,, -235.00,,food,forecast,
```
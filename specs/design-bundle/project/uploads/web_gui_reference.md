# Cash Flow — Web GUI Reference Document

Feature inventory and user stories for building a web-based frontend.

---

## 1. Feature Map

### 1.1 Transaction Management

| Feature | Description | Current Interface |
|---------|-------------|-------------------|
| Add (natural language) | LLM parses free-text into structured transaction | CLI `add`, Telegram message |
| Add (structured) | Explicit fields: desc, amount, account, category, budget, date | CLI `create tx` |
| Add (interactive) | Step-by-step guided entry with prompts | CLI `add -i` |
| Add (CSV import) | Bulk import from CSV file | CLI `add --import` |
| Edit | Modify any field; natural language or explicit flags | CLI `edit`, Telegram `/review` |
| Delete | Remove single transaction or entire group (installments) | CLI `delete` |
| Clear | Commit a pending/planning transaction | CLI `clear` |
| Review | Browse needs_review transactions, approve/edit/skip | CLI `review`, Telegram `/review` |

**Transaction types:**
- **Simple** — single expense or income
- **Installment** — N payments over N months, optional grace period, optional start-from
- **Split** — single purchase allocated across multiple categories/budgets

**Statuses:** committed, pending, planning, forecast

### 1.2 Views & Reports

| Feature | Description |
|---------|-------------|
| Timeline view | Transactions sorted by payment date with running balance |
| Created view | Transactions sorted by purchase date with monthly spending totals |
| Summary view | CC payments aggregated into single row per payment date |
| Planning toggle | Include/exclude planning transactions |
| Month navigation | View specific month range (`--from`, `--months`) |
| Liabilities | CC debt forecast: by card, by cycle, real vs subscriptions vs budgets |
| Liabilities detail | Expand each billing cycle to see individual transactions |
| Export CSV | Download transactions with optional running balance column |

### 1.3 Account Management

| Feature | Description |
|---------|-------------|
| List accounts | Show all accounts with type, cut-off, payment day |
| Add account | Name, type (cash/credit_card), billing cycle config |
| Adjust billing | One-off billing cycle override for specific month |

### 1.4 Category Management

| Feature | Description |
|---------|-------------|
| List categories | All categories with descriptions |
| Add category | Name + description |
| Edit category | Change description |
| Delete category | Remove (if no transactions reference it) |

### 1.5 Budget Envelope System

| Feature | Description |
|---------|-------------|
| List budgets | Active/expired budgets with amounts and accounts |
| List subscriptions | Non-budget recurring charges |
| Add budget/subscription | Amount, account, category, start/end, underspend behavior |
| Edit budget | Change amount, account, end date, underspend; retroactive option |
| Delete budget | Remove if no committed transactions linked |
| Budget absorption | Expenses linked to budget reduce allocation (visible in timeline) |
| Underspend release | Month-end: "return" behavior creates positive release transaction |
| Budget horizon | Forecast view showing future allocations |

### 1.6 Reconciliation

| Feature | Description |
|---------|-------------|
| Balance fix | Enter actual bank balance → system creates adjustment transaction |
| Statement fix | Enter CC statement amount → system adjusts to match |
| Interactive fix | Step-by-step: see transactions on payment date, enter statement, confirm |

### 1.7 Gmail Sync (Automated Pipeline)

| Feature | Description |
|---------|-------------|
| Ingest consumos | Pull CC notification emails → parse → store in consumos table |
| Ingest invoices | Pull SRI invoice emails → parse XML → store in invoices table |
| Register consumos | Auto-classify unregistered consumos → create transactions |
| Invoice matching | Link consumos to invoices by amount/date |
| Scheduled sync | Runs automatically at midnight + midday |
| Manual sync | CLI with date filters, dry-run, show-unparsed |
| LLM classification | Ollama-based merchant categorization with rules fallback |
| Decision audit | All LLM decisions logged in llm_decisions table |

### 1.8 Telegram Bot

| Feature | Description |
|---------|-------------|
| Add transaction | Natural language message → preview → confirm/revise/cancel |
| Summary | Budget envelopes or planning view, month navigation |
| Review | Approve/edit/skip needs_review transactions |
| Multi-user | Owner (full access) + extra users (auto-confirm, tagged source) |
| Language | EN/ES toggle per user |
| Notifications | Cross-user notifications on new transactions |

### 1.9 Backup & Restore

| Feature | Description |
|---------|-------------|
| Auto backup | Before mutations, with retention policy |
| Manual backup | Named snapshots |
| List backups | Sorted by timestamp |
| Restore | Restore from backup (creates pre-restore snapshot) |
| Retention | Today: first+last N; past days: last per day; manual never deleted |

---

## 2. User Stories & Flows

### 2.1 Adding a Transaction

#### US-2.1.1: Quick add via natural language
> As a user, I want to type a free-text description of my expense so the system auto-parses it into a structured transaction.

**Flow:**
1. User types description (e.g., "Supermaxi groceries 15.50, visa pichincha, apr 22")
2. System shows parsed preview: description, amount, account, date, category, budget
3. User confirms, revises, or cancels
4. On confirm → transaction created, budget updated if linked

**Acceptance:**
- LLM extracts: description, amount, account, date, category, budget
- Date defaults to today if omitted
- Category auto-detected from description
- Budget resolved by category + payment month
- Preview shows all parsed fields before commit

#### US-2.1.2: Structured add via form
> As a user, I want to fill a form with explicit fields when I need precision.

**Flow:**
1. User opens "Add Transaction" form
2. Fills: description, amount, account (dropdown), category (dropdown), budget (dropdown filtered by account+month), date, status
3. Optional: mark as income, pending, planning
4. Submit → transaction created

#### US-2.1.3: Add installment purchase
> As a user, I want to split a purchase into N monthly installments.

**Flow:**
1. User enters transaction details + number of installments
2. Optional: grace period (months before first payment), start-from installment number
3. Preview shows all N transactions with calculated payment dates
4. Confirm → N transactions created with shared origin_id

**Acceptance:**
- Each installment: `"[desc] (X/N)"` naming
- Payment dates follow CC billing cycle formula
- Grace period shifts first payment forward
- Start-from skips earlier installments (for adding remaining payments)

#### US-2.1.4: Add split transaction
> As a user, I want to split one purchase across multiple categories/budgets.

**Flow:**
1. User enters base transaction (description, total amount, account, date)
2. Adds splits: each with category, budget, partial amount
3. System validates splits sum to total
4. Confirm → multiple transactions with shared origin_id

#### US-2.1.5: CSV import
> As a user, I want to bulk-import transactions from a CSV file.

**Flow:**
1. User uploads CSV file
2. System shows preview of parsed rows
3. User confirms → all transactions created
4. Option: `--installments` mode for installment CSV format

---

### 2.2 Viewing Transactions

#### US-2.2.1: Timeline view (payment date)
> As a user, I want to see my transactions ordered by when money actually moves, with a running balance.

**Display:**
- Rows: ID, purchase date, payment date, description, account, amount, category, budget, status
- Running balance column (cumulative)
- Month-over-month balance change at last transaction of each month
- Color coding: blue (budget allocations), gray (pending), italic (forecast), magenta italic (planning)
- Pending transactions from past months shown grayed at top

#### US-2.2.2: Created view (purchase date)
> As a user, I want to see transactions by purchase date to track spending as it happens.

**Display:**
- Same columns minus running balance
- Monthly spending total at bottom of each month

#### US-2.2.3: Summary view
> As a user, I want CC payments aggregated so I see one row per payment date instead of individual charges.

**Display:**
- CC transactions grouped into "Account Payment" row per payment date
- Individual transactions hidden in aggregate
- Planning and pending shown separately

#### US-2.2.4: Month filtering
> As a user, I want to navigate to specific months.

**Controls:**
- "From" month picker (YYYY-MM)
- "Months to show" count (default: 3)
- Previous/next month navigation

#### US-2.2.5: Planning toggle
> As a user, I want to include/exclude planning transactions from the view.

---

### 2.3 Editing & Deleting

#### US-2.3.1: Edit transaction fields
> As a user, I want to edit any field of an existing transaction.

**Editable fields:** description, amount, date, category, budget, status, source, needs_review

**Flow:**
1. User selects transaction
2. Modifies fields via form or natural language instruction
3. Preview shows before/after diff
4. Confirm → transaction updated

**Special cases:**
- Date change on CC transaction → payment date recalculated
- Date change may trigger type conversion (different billing cycle)
- Budget change → old budget restored, new budget absorbs

#### US-2.3.2: Edit transaction group
> As a user, I want to edit all installments in a group at once.

**Flow:**
- Select any transaction in group → "Edit all" option
- Changes applied to all transactions sharing origin_id

#### US-2.3.3: Delete transaction
> As a user, I want to delete a transaction, with budget restoration.

**Flow:**
1. User selects transaction → delete
2. If linked to budget → budget allocation restored
3. Confirm → deleted

#### US-2.3.4: Delete transaction group
> As a user, I want to delete all installments at once.

#### US-2.3.5: Clear (commit) transaction
> As a user, I want to move a pending/planning transaction to committed status.

---

### 2.4 Budget Management

#### US-2.4.1: View budget dashboard
> As a user, I want to see all active budgets with allocated vs spent vs remaining for the current month.

**Display per budget:**
- Name, monthly amount, account, category
- Allocated (forecast amount)
- Spent (sum of committed expenses this month)
- Remaining (allocated - spent, capped at 0)
- Underspend behavior (keep/return)

#### US-2.4.2: Create budget
> As a user, I want to create a new budget envelope.

**Flow:**
1. Fill: name, monthly amount, account, category, start date, underspend behavior
2. System generates forecast allocations for horizon (3 months ahead)
3. Confirm → budget + forecasts created

#### US-2.4.3: Edit budget
> As a user, I want to change a budget's amount, account, or end date.

**Flow:**
1. Select budget → edit
2. Modify fields
3. Option: retroactive (update past allocations) or forward-only
4. If setting end date → budget auto-renamed with date suffix
5. System regenerates future forecasts

#### US-2.4.4: View budget absorption
> As a user, I want to see how expenses absorb into budget allocations in the timeline.

**Visual:** Budget allocation row shows remaining amount after absorption. Linked expenses show budget reference.

---

### 2.5 Account Management

#### US-2.5.1: View accounts
> As a user, I want to see all accounts with their billing cycle configuration.

**Display:** Name, type, cut-off day, payment day, cycle description

#### US-2.5.2: Add account
> As a user, I want to add a new account (cash or credit card).

**Flow:**
1. Enter name, type
2. If credit card: cut-off day, payment day
3. Confirm → account created

#### US-2.5.3: Adjust billing cycle
> As a user, I want to override the billing cycle for a specific month (bank shifted dates).

**Flow:**
1. Select account + month
2. Enter temporary cut-off and payment day
3. System recalculates payment dates for affected transactions

---

### 2.6 Category Management

#### US-2.6.1: CRUD categories
> As a user, I want to create, view, edit, and delete expense categories.

---

### 2.7 Subscription Management

#### US-2.7.1: View subscriptions
> As a user, I want to see all recurring charges with status (active/expired).

**Filters:** All, budgets only, subscriptions only

#### US-2.7.2: Add subscription
> As a user, I want to add a recurring charge (e.g., Spotify, internet).

**Fields:** Name, amount, account, category, start date, end date (optional)

#### US-2.7.3: Edit subscription
> As a user, I want to modify a subscription's amount or end it.

---

### 2.8 Liabilities View

#### US-2.8.1: CC debt forecast
> As a user, I want to see what I owe on each credit card, broken down by billing cycle.

**Display:**
- Per card: current cycle owed, future cycles
- Breakdown: real expenses vs subscription forecasts vs budget allocations
- Grand total across all cards
- Summary mode (aggregate future) vs detail mode (each cycle)

---

### 2.9 Review Flow

#### US-2.9.1: Review auto-imported transactions
> As a user, I want to review transactions created by Gmail sync and approve, edit, or flag them.

**Flow:**
1. Open review queue (list of needs_review transactions)
2. For each: see details (source, linked consumo, invoice match, LLM decision)
3. Actions: approve (clear review flag), edit fields + approve, skip
4. Batch approve option

---

### 2.10 Reconciliation

#### US-2.10.1: Balance reconciliation
> As a user, I want to reconcile my app balance with my actual bank balance.

**Flow:**
1. Enter actual balance (optionally filter by account)
2. System calculates difference
3. Creates adjustment transaction to match

#### US-2.10.2: CC statement reconciliation
> As a user, I want to match my CC payment to the bank statement amount.

**Flow:**
1. Select account + month
2. System shows all transactions on that payment date
3. Enter statement amount
4. System creates adjustment if mismatch
5. Confirm → adjustment committed

---

### 2.11 Gmail Sync Management

#### US-2.11.1: View sync status
> As a user, I want to see when the last sync ran and what was processed.

#### US-2.11.2: Manual sync trigger
> As a user, I want to manually trigger a Gmail sync with date filters.

**Options:** Since last sync, after specific date, dry run, show unparsed emails

#### US-2.11.3: View consumos
> As a user, I want to see all parsed consumos with their registration status and invoice matches.

#### US-2.11.4: View invoices
> As a user, I want to see all parsed invoices with line items and tax details.

#### US-2.11.5: View LLM decisions
> As a user, I want to see the LLM classification audit log for auto-registered transactions.

---

### 2.12 Backup Management

#### US-2.12.1: Create manual backup
> As a user, I want to create a named backup snapshot.

#### US-2.12.2: List backups
> As a user, I want to see all backups sorted by date with type (auto/manual).

#### US-2.12.3: Restore from backup
> As a user, I want to restore the database from a previous backup.

**Safety:** System creates a pre-restore snapshot before restoring.

---

### 2.13 Multi-User Support

#### US-2.13.1: Extra user transaction entry
> As an extra user (e.g., family member), I want to add expenses that get tagged with my name and auto-flagged for review.

**Behavior:**
- Transactions auto-confirmed (no preview step)
- Tagged with `source=<name>`
- Flagged `needs_review=1`
- Owner notified via Telegram

#### US-2.13.2: Owner review of extra user transactions
> As the owner, I want to review and approve transactions submitted by family members.

---

## 3. Data Model Summary (for API design)

### Core Entities

```
Transaction {
  id: int (auto)
  description: string
  amount: float (negative=expense, positive=income)
  date_created: date
  date_payed: date
  account: FK → Account
  category: string (FK → Category)
  budget: string (FK → Subscription.id, nullable)
  status: enum(committed, pending, planning, forecast)
  origin_id: string (groups installments/splits, nullable)
  source: string (nullable, e.g. "mom", "gmail")
  needs_review: bool
  notes: string (nullable)
}

Account {
  id: string (name)
  type: enum(cash, credit_card)
  cut_off_day: int (nullable)
  payment_day: int (nullable)
}

Category {
  name: string (PK)
  description: string
}

Subscription {
  id: string (PK, e.g. "budget_home_mortgage")
  name: string
  amount: float
  account: FK → Account
  category: string
  start_date: date
  end_date: date (nullable)
  is_budget: bool
  monthly_amount: float (nullable, for budgets)
  underspend_behavior: enum(keep, return)
}

Consumo {
  msg_id: string (PK, Gmail message ID)
  bank: string
  account: string
  merchant: string
  amount: float
  purchased_at: datetime
  card_last: string
  registered_txn_id: int (FK → Transaction, nullable)
  link_source: string
  linked_at: datetime
  matched_invoice_number: string
  matched_at: datetime
}

Invoice {
  id: int (auto)
  msg_id: string (Gmail message ID)
  invoice_number: string
  vendor: string
  issue_date: date
  total: float
  doc_type: enum(factura, nota_credito)
  items: JSON
  taxes: JSON
  forma_pago: string
}

LLMDecision {
  id: int (auto)
  consumo_msg_id: string
  prompt: text
  response: text
  category: string
  created_at: datetime
}

BillingOverride {
  account_id: string
  reference_month: string (YYYY-MM)
  cut_off_day: int
  payment_day: int
}
```

### Key Relationships
- Transaction → Account (many-to-one)
- Transaction → Category (many-to-one)
- Transaction → Subscription via budget field (many-to-one, optional)
- Transaction group via origin_id (one-to-many)
- Consumo → Transaction via registered_txn_id (one-to-one)
- Consumo → Invoice via matched_invoice_number (one-to-one)

---

## 4. Web GUI Page Map (Suggested)

| Page | Features | Priority |
|------|----------|----------|
| **Dashboard** | Running balance, current month spending, budget status bars, recent transactions | P0 |
| **Transactions** | Timeline/created toggle, filters, search, add/edit/delete, month nav | P0 |
| **Add Transaction** | Natural language input + form, installment/split modes, preview | P0 |
| **Budgets** | Budget cards with progress bars, allocation vs spent, manage | P0 |
| **Accounts** | Account list, add, billing cycle config | P1 |
| **Categories** | CRUD list | P1 |
| **Subscriptions** | Active/expired list, add/edit | P1 |
| **Liabilities** | CC debt by card/cycle, summary/detail toggle | P1 |
| **Review Queue** | Pending reviews, approve/edit/skip, batch actions | P1 |
| **Reconciliation** | Balance fix, statement fix, guided wizard | P2 |
| **Gmail Sync** | Sync status, manual trigger, consumos/invoices browser | P2 |
| **Backups** | List, create, restore | P2 |
| **Settings** | Accounts, categories, sync config, user management | P2 |

---

## 5. Key Business Rules (for implementation reference)

1. **CC billing formula:** purchase ≤ cut-off → pay next month; purchase > cut-off → pay month+2
2. **Budget absorption:** allocation += abs(expense), capped at 0
3. **Monthly rollover:** auto-runs on app startup — generates forecasts, reconciles budgets, commits current month forecasts
4. **Forecast horizon:** 3 months ahead by default
5. **Underspend return:** creates positive "Budget Release" transaction at month end
6. **Group operations:** installments/splits share origin_id; edit/delete can target whole group
7. **Review flag:** Gmail-synced and extra-user transactions get needs_review=1
8. **Amount convention:** negative = expense, positive = income
9. **Pending excluded:** pending transactions not counted in running balance
10. **Planning included:** planning transactions counted in running balance (what-if scenarios)

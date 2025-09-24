
* keep **transactions** as the single ledger (no extra audit columns)
* treat **budgets** as a kind of **subscription** (one-month-per-row forecasts)
* use predictable ids / links so bulk ops are trivial
* let subscription record include the **payment method** + a simple **underspend policy** setting


# 1 — ID & naming conventions

* `subscription.id`: short stable id, e.g. `sub_<uuid>`, `spotify`, `budget_food`
* `budget_category` -> `budget` rename for simplicity and will correspond to `subscription.id` if the subscription is a budget
* `origin_id` (groups all months of a subscription) = `<subscription.id>`
  Example: `sub_3f2a1b`

# 2 — Schemas (minimal / exact)

## `transactions` (single ledger)

Important columns only:

* `id` INTEGER PRIMARY KEY
* `date` DATE         -- usually first-of-month for forecasts; actual date for committed transactions
* `description` TEXT
* `amount` REAL      
* `category` TEXT     -- high-level true category (Food, Internet, Salary)
* `budget` TEXT NULL   -- e.g. `budget_food` (links a transaction to that subscription)
* `status` TEXT       -- `forecast` or `committed`
* `origin_id` TEXT NULL         -- `sub_food` groups rows, or installments origin id 
* `account_id` TEXT NULL        -- payment method / account used


## `subscriptions` (tiny helper)

* `id` TEXT PRIMARY KEY        -- e.g. `food` or `sub_<uuid>`
* `name` TEXT                  -- e.g. `Food` (for description)
* `category` TEXT              -- `Food`, `Internet` (maps to transactions.category)
* `monthly_amount` REAL
* `payment_account_id` TEXT    -- link to account id to use
* `start_date` DATE            -- first month to generate and also date for next transactions (e.g each month's 15th)
* `end_date` DATE NULL         -- NULL = indefinite
* `is_budget` BOOL -- explicitely show if a subscription is a budget for the budget related logic
* `underspend_behavior` TEXT   -- `'keep'` or `'return'` (default: `'keep'`) for budget specific transactions

  * `'keep'` = keep the budget transaction as-is (record remains).
  * `'return'` = at month close generate a positive `Budget Release` committed transaction that returns unused funds.

# 3 — Runtime contracts / invariants

* Forecast budget transaction for month M:

  * `date = YYYY-MM-01`
  * `amount = -monthly_amount`
  * `category = subscriptions.category` (e.g. `Food`)
  * `budget = <subscription.id>` (e.g. `budget_food`)
  * `status = 'forecast'`
  * `origin_id = generate unique id as with the installment ones, so it is easy to track all the transactions`
  * `account_id = subscriptions.payment_account_id`
* Actual spend transactionsand `status='committed'`. If they belong to that budget month, they should have `budget` set to the same `budget = <subscription.id>` 

# 4 — During-the-month behavior 

* You create the forecast budget transaction at month end . That row represents the **allocated money**.
* As you record actual expenses, they are normal `committed` transactions with `budget = <subscription.id>`.
* To compute remaining for the month:

  ```
  remaining = ABS(budget_row.amount) - SUM(ABS(committed_expense.amount) WHERE month)
  ```

  (Adapt signs to negative-outflow convention.)

# 5 — Month-end rules: overspend and underspend (explicit)

## Overspend (your rule)

* If `spent > planned`:

  1. The original forecast/commit budget transaction should get = 0 (never show negative) as it can count as a credit (or maybe inverted).
  2. Create a new committed transaction to record the excess:

     * `description = "<subscription.id> Overbudget <YYYY-MM>"`
     * `amount = -abs(planned - spent)` (negative outflow)
     * `category = subscriptions.category`
     * `budget = <subscription.id>`
     * `status = 'committed'`
     * `origin_id = (same origin)` 
     * `account_id = same as budget account id`

## Underspend (configurable via `subscriptions.underspend_behavior`)

* `underspend_behavior = 'keep'` (default):

  * Do **nothing**. Budget forecast row remains in history as the planned allocation. The remaining amount shows as available if you choose to show it, but you intentionally left it allocated.
* `underspend_behavior = 'return'`:

  * Create a committed **Budget Release** transaction:

    * `description = "<name> Budget Release <YYYY-MM>"`
    * `amount = +(planned - spent)` (positive inflow)
    * `category = 'Budget Release'` 
    * `budget = <subscription.id>`
    * `status = 'committed'`
    * `origin_id = same id`
    * `account_id = subscriptions.payment_account_id` (money returns to that account)

> Note: leaving the budget row intact is simpler and fully auditable; `return` provides immediate net-worth accuracy. The `underspend_behavior` setting on the subscription controls that per-budet.

# 6 — Horizon & automatic generation (indefinite subscriptions)

* Have a small scheduler job that montlhy will generate the forecast transactions up to the horizon (6 months or 3 months from the current mont)

# 7 — Promotion to committed

* On month start:

  * Promote that month’s forecast to committed:



# 8 — Changing amount or payment method (simple operations)

* **Change monthly\_amount effective from month M:**

  1. Update `subscriptions.monthly_amount`.
  2. Delete future forecasts generated by that subscription:

     ```sql
     DELETE FROM transactions
     WHERE origin_id = 'sub_<id>' AND status = 'forecast' AND date >= 'M-01';
     ```
  3. Regenerate forecasts from M onward with new amount.
* **Change payment account:**

  * Update `subscriptions.payment_account_id`.
  * Update future forecasts:

    ```sql
    UPDATE transactions
    SET account_id = :new_account
    WHERE origin_id = 'sub_<id>' AND status = 'forecast' AND date >= :today_first_of_month;
    ```


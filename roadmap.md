
### **Phase 1 — Core Budget & Transaction Logic (foundation before AI)**

**1. Installment and Committed Transactions (+)**

> Purchases in installments create *committed* future transactions that affect budgets in those months.

* Ensure correct budget allocation updates across all affected months.
* Budgets for future months must exist (or be auto-created) so installment allocations can be applied.
* When generating forecasted budgets, detect existing committed transactions and adjust allocations accordingly.
* Analyze the better approach: either creating future budgets to all the months we have commited transactions to a budget, or respect the forecast window setting.

**2. Editing and Retroactive Transaction Adjustments (+)**

> The system must handle edits to past or installment-linked transactions.

* If a past transaction is added (e.g., a tax discovered later or forgotten purchase), the corresponding past month’s budget allocation should update if necessary.
* If the transaction was initially logged as full payment but was actually deferred, automatically create installment entries for future months and adjust all related budgets.
* If the opposite happens (was logged as deferred but paid in full), remove installments and update budgets accordingly.
* Transactions belonging to installments should be easily identifiable and modifiable. Consider if adding another column or using the n/n from the transaction description.

**3. Credit Card Cut Date Flexibility (+)**

> Credit card cut dates are not always fixed and may shift by a day or two.

* Implement a mechanism to recalculate pay dates and update affected budget allocations.
* If a transaction moves from one card cycle to another:

  * Update the previous month’s budget.
    * Consider the edge case of `return transactions` (When the month ends and some money is left from the budget, it can be returned to the cash flow with such transaction)
  * Adjust the current or next month’s budget accordingly.
  * Handle the update of multiple transaction records if the edit is on a purchase done in installments.


**4. Importing Existing Transactions (–)**

> Add a mechanism to import transactions or statements from Excel or CSV.

* Handle users who already have ongoing budgets or installment plans (e.g., “3rd of 6 payments”).
* Simplest flow: import recent statements + current balance, let the system recreate installments and recent transactions.
* Optionally, detect recurring payments and suggest creating “subscriptions” automatically.

**5. Handling Taxes or Post-Charge Adjustments (–)**

> Some transactions (e.g., Uber, Steam) have final charges that appear later due to taxes.

* Allow users to manually define “pending/fixed” adjustments, or
* Automatically reconcile them when the monthly statement is available.

---

### **Phase 2 — Reconciliation & AI/LLM Integration (automation layer)**

**6. LLM-Powered Natural Language Entry (–)**

> Integrate an LLM once the financial logic is stable.

* Primary goal: register transactions via natural language input (“Bought coffee for $3 with card X”).
* Decide how to retrieve transaction IDs when the user need to edit something— e.g., "Modify the coffee purchase, it was $3.99" and the system should use some strategy to get its ID, like fuzzy matching description or letting the LLM see all transactions of the month if not many.

**7. LLM-Assisted Reconciliation (–)**

> Use the LLM to reconcile user records with official card statements.

* Identify discrepancies or missing items automatically, like missing transactions in the application records or moving transactions to the next cycle if they not appeared on the current statement.
* Suggest new transactions or corrections for user review.

---

### **Phase 3 — Planning & Advanced Features (future expansion)**

**8. Debt & Credit Planning (–)**

> Implement a debt management planner.

* Track card interest rates, deferment options, and friend loans.
* Simulate repayment scenarios and total interest over time.
* Possibly integrate with budgets to prioritize debt payoff in cash flow.

---

## 🧩 Dependencies (in order of implementation)

1. **Core transaction & budget logic** (installments, edits, retroactive changes).
2. **Card cycle & budget recalculation system.**
3. **Import mechanism** (depends on stable transaction logic).
4. **Reconciliation system (manual or LLM-assisted).**
5. **LLM natural language interface** (depends on all above).
6. **Debt planner** (optional module using existing budget and transaction data).

---

## 🧠 Summary Table

| Priority | Feature                               | Depends On              | Notes                      |
| -------- | ------------------------------------- | ----------------------- | -------------------------- |
| ++       | Installments & committed transactions | Base transaction schema | Core of multi-month logic  |
| ++       | Edit & retroactive handling           | Installments            | Ensures data integrity     |
| +        | Card cut date adjustment              | Budget allocation logic | Prevents misalignment      |
| -        | Import transactions                   | Core logic              | Enables migration          |
| -        | Tax / post-charge handling            | Reconciliation logic    | Useful for accuracy        |
| -        | LLM natural language                  | Core logic              | For user convenience       |
| -        | LLM reconciliation                    | Reconciliation logic    | Reduces manual review      |
| -        | Debt planner                          | Budgets, transactions   | Financial planning feature |


# Personal Cash Flow Tool

## 1. Overview

This is a simple, yet powerful, personal cash flow management tool designed for clarity and traceability. The core principle of the system is to represent every financial event—past, present, and future—in a single, flat `transactions` table.

Its key feature is the ability to distinguish between the date a transaction occurred (`date_created`) and the date it actually impacts your cash flow (`date_payed`), providing a true financial picture, especially when dealing with credit card payments.

## 2. Core Features

*   **Multiple Transaction Types:** Handles simple expenses, installment purchases, and split transactions.
*   **Intelligent Credit Card Logic:** Automatically calculates the correct payment date for credit card transactions based on user-defined cut-off and payment days.
*   **Subscription Management:** Automatically forecasts recurring payments like subscriptions and bills.
*   **Dynamic Budget Tracking:** Treats monthly budgets as a running balance, updated in real-time with every expense. Budgets are capped at zero to accurately reflect when allocated funds are depleted without distorting the overall cash flow.
*   **Robust Editing and Corrections:** Easily change a transaction's date or a budget's amount. The system intelligently recalculates all affected budgets and payment dates—even across future, committed months—ensuring your financial plan is always accurate and up-to-date.
*   **Flexible Payment Timing:** Model "buy now, pay later" scenarios with grace periods that delay the cash flow impact of a purchase.
*   **Powerful Forecasting:** By representing all future commitments (installments, subscriptions, budgets) as transactions, it provides a clear and accurate view of your future cash flow.
*   **Test-Driven:** Developed using a Test-Driven Development (TDD) approach to ensure reliability and correctness.

## 3. A Clear View of Your Financial Future

In this tool, **everything is a transaction**. This simple idea is the key to our powerful forecasting. Instead of having separate systems for your history, your subscriptions, and your budgets, we represent them all in the same `transactions` table. This gives you a single, unified timeline of your money—past, present, and future.

### Subscriptions and Recurring Payments

Tell the tool about your Netflix subscription once, and it will automatically create future `'forecast'` transactions for as many months ahead as you want. The same goes for rent, bills, or any recurring payment. This means you can immediately see how much money is already earmarked for future months, removing any surprises.

### Live Budgeting: The Digital Envelope System

Budgets aren't just numbers in a separate sheet; they are live, dynamic transactions that function like a **digital envelope system**. When you set a $400 Food budget for the month, the system creates a single transaction with an amount of `-400`. This transaction is your "envelope"—it represents the total pool of money allocated for that category.

As you spend, you are "taking money" directly from this envelope. Here’s how it works in practice:

1.  **Initial State:** The "Food Budget" transaction shows `-400`.
2.  **You spend $50 on groceries:** The system finds the Food Budget envelope and updates its balance: `-400 + 50 = -350`. The budget transaction now shows you have $350 remaining.
3.  **You spend another $370:** This is more than the $350 left in your envelope. The system handles this intelligently:
    *   The "Food Budget" transaction is updated by the remaining $350, bringing its balance to `0`. It is now capped at zero to show the allocation is fully spent.
    *   Your actual expense of $370 is still recorded in full.

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

## 4. Future Vision: LLM-Powered Input

The backend logic is designed to be driven by a structured JSON object. The ultimate goal is to connect this system to a Large Language Model (LLM) that can parse natural language, allowing for extremely easy recording of expenses.

## 5. Technical Details

*   **Language:** Python 3
*   **Database:** SQLite
*   **Testing:** Uses the built-in `unittest` framework.

### Project Structure

*   `main.py`: The main controller that processes incoming transaction requests. Also contains an example script to demonstrate usage.
*   `transactions.py`: Contains all the core business logic for creating different types of transactions.
*   `repository.py`: The data persistence layer, responsible for all interactions with the database.
*   `database.py`: Handles the initial setup, schema creation, and populates the database with initial data.
*   `spec.md`: The detailed specification document for the project.
*   `plan.md`: The implementation plan based on the specification.
*   `tests/`: A directory containing all the unit tests for the project.

## 6. How to Run

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Initialize and Run:**
    To run the pre-configured examples and create the `cash_flow.db` file, simply execute:
    ```bash
    python3 main.py
    ```
    This will create the database, add sample transactions, set up subscriptions, run budget scenarios, and print the final contents of the `transactions` table to the console.

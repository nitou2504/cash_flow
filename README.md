# Personal Cash Flow Tool

## 1. Overview

This is a simple, yet powerful, personal cash flow management tool designed for clarity and traceability. The core principle of the system is to represent every financial event—past, present, and future—in a single, flat `transactions` table.

Its key feature is the ability to distinguish between the date a transaction occurred (`date_created`) and the date it actually impacts your cash flow (`date_payed`), providing a true financial picture, especially when dealing with credit card payments.

## 2. Core Features

*   **Multiple Transaction Types:** Handles simple expenses, installment purchases, and split transactions.
*   **Intelligent Credit Card Logic:** Automatically calculates the correct payment date for credit card transactions based on user-defined cut-off and payment days.
*   **Subscription Management:** Automatically forecasts recurring payments like subscriptions and bills.
*   **Dynamic Budget Tracking:** Treats monthly budgets as a running balance, updated in real-time with every expense.
*   **Powerful Forecasting:** By representing all future commitments (installments, subscriptions, budgets) as transactions, it provides a clear and accurate view of your future cash flow.
*   **Test-Driven:** Developed using a Test-Driven Development (TDD) approach to ensure reliability and correctness.

## 3. A Clear View of Your Financial Future

In this tool, **everything is a transaction**. This simple idea is the key to our powerful forecasting. Instead of having separate systems for your history, your subscriptions, and your budgets, we represent them all in the same `transactions` table. This gives you a single, unified timeline of your money—past, present, and future.

### Subscriptions and Recurring Payments

Tell the tool about your Netflix subscription once, and it will automatically create future `'forecast'` transactions for as many months ahead as you want. The same goes for rent, bills, or any recurring payment. This means you can immediately see how much money is already earmarked for future months, removing any surprises.

### Live Budgeting

Budgets aren't just numbers in a separate sheet; they are live transactions. When you set a $400 Food budget for the month, we create a `-400` transaction that acts as your monthly allocation.

As you spend money on groceries, this budget transaction is updated in real-time. Spend $50, and the budget transaction's amount automatically changes to `-350`. This shows you exactly how much you have left at a glance, directly in your transaction history. At the end of the month, you decide what happens to any leftover budget money. You can have it automatically "returned" to your cash flow, giving you an accurate picture of your available funds. Alternatively, you can choose to "keep" the remaining amount allocated. This is useful if the money was already spent on untracked small items or set aside, ensuring your budget for the month is officially closed out without affecting your cash balance.

### Putting It All Together: True Forecasting

Because your future installment payments, your Netflix subscription, and your remaining Food budget are all just rows in the same table, forecasting becomes simple and intuitive. You can easily see your entire financial picture to answer questions like:

*   *"Given all my subscriptions and installment payments, what will my credit card bill be in December?"*
*   *"How much disposable income will I actually have next month after all my commitments are met?"*

A quick look at your future transactions gives you the answer:

```
--- Your Financial Timeline (Excerpt) ---
date_payed  | description              | amount  | status
-----------------------------------------------------------
2025-10-25  | Dinner at Luigi's        | -45.00  | committed  <-- A past, real expense
2025-11-15  | Netflix Subscription     | -15.99  | forecast   <-- A future, automatic payment
2025-11-25  | New Laptop (2/6)         | -200.00 | committed  <-- A future, real commitment
2025-11-30  | Food Budget              | -150.00 | committed  <-- Your remaining live budget for the month
```

This unified view makes financial planning intuitive and removes the guesswork.

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

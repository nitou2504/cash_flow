# Technical Considerations & Design Principles

This document outlines the core architectural principles, data structures, and development methodologies used in the Personal Cash Flow Tool.

## 1. Core Architectural Principle: Idempotency and State Management

A key design principle of this application is the separation of state management from business logic functions. The system's state, particularly the status of monthly transactions (`'forecast'` vs. `'committed'`), is critical for the correct execution of operations like budget updates.

### The Orchestrator Pattern

The application relies on an "orchestrator" (the main application flow, currently represented by the `if __name__ == '__main__':` block) to ensure the system is in a valid state *before* executing any specific business logic.

The primary tool for this is the `run_monthly_rollover()` function. This function is designed to be **idempotent**, meaning it can be run multiple times without changing the result beyond its initial application.

-   **`commit_past_and_current_forecasts()`**: This sub-function only affects transactions with a `'forecast'` status. Running it a second time on a committed month will find no matching rows and do nothing.
-   **`generate_forecasts()`**: This sub-function first checks for the latest existing forecast. If the forecast horizon is already full, it does nothing.

**Golden Rule:** The main application flow should **always call `run_monthly_rollover(conn, date.today())` at the beginning of any session.** This acts as a safe, low-cost "state synchronization" step, guaranteeing that the current month's data is correctly committed before any other operations are performed. This responsibility is intentionally kept at the orchestrator level and not embedded within business logic functions (like `process_budget_update`) to maintain the **Single Responsibility Principle**.

## 2. The Live Budget Allocation System

The budget system is designed to provide a real-time, accurate view of both remaining allocations and overall cash flow. It functions like a "digital envelope" system.

1.  **Allocation as a Transaction:** When a budget is created (e.g., $400 for Food), a single transaction with a negative amount (`-400`) is created. This is the "envelope" and represents money that is now considered spent from a cash-flow forecasting perspective.
2.  **Real-Time Updates:** When an expense is logged against this budget (e.g., $50 for groceries), the system finds the budget allocation transaction and updates its amount: `-400 + 50 = -350`. The allocation now shows exactly how much is left in the envelope.
3.  **Overspending and Capping:** If an expense exceeds the remaining budget, the allocation is capped at `0`. For example, if you have $50 left and spend $70, the allocation becomes `0`. The full $70 expense is still recorded, ensuring the overall cash flow remains accurate.
4.  **Forecasting Accuracy:** Because the budget money is "spent" upfront when the allocation is made, subsequent expenses against that budget do not impact the overall running balance of your cash. This prevents double-counting and provides a trustworthy forecast of your actual disposable income at any point in the future.

## 3. Database Schema

The application uses a simple SQLite database with four core tables.

-   **`accounts`**: Stores bank accounts, credit cards, or cash.
    -   `account_id` (TEXT, PK): The unique name/ID of the account (e.g., "Cash").
    -   `account_type` (TEXT): The type of account (e.g., "cash", "credit_card").
    -   `cut_off_day` (INTEGER): For credit cards, the billing cycle cut-off day.
    -   `payment_day` (INTEGER): For credit cards, the bill payment day.

-   **`subscriptions`**: Stores the definitions for any recurring financial event, including budgets.
    -   `id` (TEXT, PK): The unique ID for the subscription (e.g., "sub_netflix", "budget_food").
    -   `name` (TEXT): The human-readable name (e.g., "Netflix Subscription").
    -   `category` (TEXT): The financial category (e.g., "entertainment").
    -   `monthly_amount` (REAL): The recurring monthly cost.
    -   `payment_account_id` (TEXT, FK): The account used for payment.
    -   `start_date` (DATE): The date the subscription begins.
    -   `end_date` (DATE): The optional date the subscription ends.
    -   `is_budget` (BOOLEAN): A flag (0 or 1) to indicate if this is a budget allocation.
    -   `underspend_behavior` (TEXT): The policy for leftover budget funds ('keep' or 'return').

-   **`transactions`**: A flat table representing every single financial event, past, present, and future.
    -   `id` (INTEGER, PK): The unique ID for the transaction row.
    -   `date_created` (DATE): The date the transaction was made or initiated.
    -   `date_payed` (DATE): The date the transaction impacts cash flow (crucial for credit cards).
    -   `description` (TEXT): A description of the transaction.
    -   `account` (TEXT, FK): The account linked to the transaction.
    -   `amount` (REAL): The transaction amount (negative for expenses, positive for income).
    -   `category` (TEXT): The financial category.
    -   `budget` (TEXT): The ID of the budget this transaction is linked to, if any.
    -   `status` (TEXT): The state of the transaction ('committed' or 'forecast').
    -   `origin_id` (TEXT): An ID linking related transactions (e.g., installments, or the parent subscription).

-   **`settings`**: Key-value table that stores user-defined settings.
    -   `key` (TEXT, PK): The unique name/ID of the setting (e.g., "forecast_horizon_months").
    -   `value` (TEXT): Setting value.

## 4. Development and Testing Strategy

The project is developed using a strict **Test-Driven Development (TDD)** methodology.

-   **Test-First Approach:** For every new feature or bug fix, a test is written first to define the expected behavior. The test is run to confirm it fails, and then the application code is written or modified until the test passes.
-   **Test Location:** All tests are located in the `tests/` directory at the project root.
-   **In-Memory Database:** To ensure tests are fast, isolated, and repeatable, each test case creates a fresh SQLite database `:in:memory:`. This guarantees that tests do not interfere with each other or leave artifacts on the file system.
-   **Running Tests:** Tests are designed to be run as modules from the **project's root directory**. This allows the test files to correctly import the application modules. The standard command to run a test suite is:
    ```bash
    python3 -m tests.test_filename
    ```

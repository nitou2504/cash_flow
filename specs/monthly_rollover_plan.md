# Monthly Rollover Implementation Plan

This document outlines the plan to create a robust, on-demand process for finalizing a given month's transactions and forecasting for future months. This "rollover" mechanism will handle the transition of forecasted transactions to committed ones and ensure the forecast window is always maintained.

## 1. Database Schema Changes (`database.py`)

A new table will be added to store user-defined settings, making the application more flexible.

*   **Create New `settings` Table:**
    A key-value table will be created to hold application-wide settings, such as the forecast horizon.
    ```sql
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    ```

*   **Insert Initial Settings:**
    The `insert_mock_data` function will be updated to populate the `settings` table with default values.
    *   A default `forecast_horizon_months` will be set to `6`.

## 2. Data Persistence Layer (`repository.py`)

The repository will be updated with new functions to manage settings and to handle the monthly "committing" of forecasted transactions.

*   **`get_setting(conn: Connection, key: str) -> str`**:
    *   **Purpose:** Retrieves a specific setting value from the `settings` table by its key.
    *   **Logic:** Executes a `SELECT` query on the `settings` table.

*   **`commit_past_and_current_forecasts(conn: Connection, month_date: date)`**:
    *   **Purpose:** Changes the status of all `'forecast'` transactions to `'committed'` for a given month. This action "locks in" the financial events for that period.
    *   **Logic:**
        1.  Calculates the first and last day of the month based on `month_date`.
        2.  Executes an `UPDATE` query on the `transactions` table, setting `status = 'committed'` for all rows where `status = 'forecast'` and `date_created` falls within that month.

## 3. Main Controller Logic (`main.py`)

A new master function will be created to orchestrate the entire monthly rollover process.

*   **`run_monthly_rollover(conn: Connection, process_date: date)`**:
    *   **Purpose:** Acts as the main, on-demand entry point for all monthly processing. It is idempotent and can be run safely at any time for a given month.
    *   **Logic:**
        1.  **Commit Forecasts:** Calls `repository.commit_past_and_current_forecasts()` for the `process_date` to convert all of the current month's forecasts into committed transactions. This is the crucial step that "activates" the current month's budgets.
        2.  **Retrieve Horizon:** Fetches the `forecast_horizon_months` value from the database using `repository.get_setting()`.
        3.  **Generate New Forecasts:** Calls the existing `generate_forecasts()` function, passing the retrieved horizon. This ensures the forecast window is always "topped up" for the required number of months into the future.

## 4. Demonstration (`main.py`)

The main execution block will be updated to include a call to the new `run_monthly_rollover` function to demonstrate its usage and verify its correctness.

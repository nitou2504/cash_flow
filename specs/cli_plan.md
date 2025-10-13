# Plan: Command-Line Interface (CLI)

This document outlines the plan to create a Command-Line Interface (CLI) for the Personal Cash Flow Tool. The CLI will provide a user-friendly way to add, view, and export transactions.

## 1. Core Objectives

1.  **LLM-Powered Transaction Entry:** Allow users to add transactions using natural language (e.g., `"lunch at cafe 15.75 cash food budget"`).
2.  **Formatted Terminal View:** Provide a clear, readable table of all transactions directly in the terminal, including a running cash flow balance.
3.  **CSV Export:** Allow users to export their complete transaction history to a CSV file, with an option to include the running balance.
4.  **Clean Architecture:** Maintain a strict separation between the user interface (CLI) and the core application logic.

## 2. Project Structure & Setup

To achieve a clean architecture, we will introduce three new files and update our dependencies.

1.  **`cli.py`:** The main entry point for the CLI. It will handle command-line argument parsing (`add`, `view`, `export`) and orchestrate calls to the other modules.
2.  **`llm_parser.py`:** This module will be solely responsible for interacting with the Google Gemini API. It will contain the system prompt, the API call logic, and the JSON parsing.
3.  **`interface.py`:** This new file will act as a bridge between the CLI and the core application logic. It will contain the functions for preparing data for display (e.g., calculating the running balance, formatting tables).
4.  **`requirements.txt`:** The following libraries will be added:
    *   `google-generativeai`: For interacting with the Gemini LLM.
    *   `rich`: For creating beautifully formatted tables in the terminal.

## 3. Key Feature Implementation Plan

### Step 1: Running Balance Calculation (The Core Logic)

This is the most critical new piece of logic. It must correctly determine which transactions impact the cash flow.

-   **New Function:** A new function, `get_transactions_with_running_balance()`, will be created in `repository.py`.
-   **Sorting:** It will fetch all transactions sorted ascending by `date_payed`.
-   **Calculation Logic:** It will iterate through the transactions and calculate the `running_balance` by keeping a cumulative sum of the `amount` column. The system's "live budget" feature ensures this simple calculation is always accurate. When an expense is logged against a budget, the budget's own allocation transaction is updated in real-time, meaning the `amount` column for all transactions remains the single source of truth for cash flow impact.
-   **Output:** The function will return the list of transaction dictionaries, each enhanced with a `running_balance` key.

### Step 2: The `view` Command

-   **Function:** A new function, `view_transactions(conn)`, will be created in `interface.py`.
-   **Action:** It will call `repository.get_transactions_with_running_balance()` to get the data.
-   **Formatting:** It will use the `rich` library to render the data in a clean, padded table format for easy reading in the terminal.

### Step 3: The `export` Command

-   **Function:** A new function, `export_transactions_to_csv(conn, file_path, include_balance)`, will be created in `interface.py`.
-   **Action:** It will also call `repository.get_transactions_with_running_balance()`.
-   **CSV Generation:** It will use Python's built-in `csv` module to write the data to the specified `file_path`.
-   **Optional Column:** The `include_balance` boolean parameter will control whether the `running_balance` column is included in the final CSV file.

### Step 4: The `add` Command (LLM Integration)

-   **System Prompt:** A detailed system prompt will be crafted in `llm_parser.py`. It will instruct the Gemini model on its role, the required JSON schema, and provide clear examples for `simple`, `installment`, and `split` transactions to ensure reliable output.
-   **LLM Function:** A function, `parse_transaction_string(user_input)`, will handle the API call. It will securely read the `GOOGLE_API_KEY` from an environment variable.
-   **User Flow in `cli.py`:**
    1.  The user runs `python cli.py add "..."`.
    2.  The CLI calls `llm_parser.parse_transaction_string()`.
    3.  The generated JSON is printed to the console.
    4.  **Safety Check:** The user is prompted for confirmation (`[Y/n]`).
    5.  If confirmed, the JSON is passed to the existing `main.process_transaction_request()` function to be logged in the database.

## 4. CLI Usage Specification

The final CLI will have the following structure:

```bash
# Add a transaction using natural language
python cli.py add "1200 for a new laptop in 6 installments on my visa, starting from the 3rd of 6 total payments"

# View all transactions in a formatted table
python cli.py view

# Export all transactions to a CSV file
python cli.py export transactions.csv

# Export all transactions including the running balance column
python cli.py export transactions_with_balance.csv --with-balance
```

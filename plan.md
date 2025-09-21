# Cash Flow Application Implementation Plan

This document outlines the function and module plan for the initial implementation of the personal cash flow tool. It is designed to be modular, scalable, and directly address the requirements laid out in `spec.md`.

## 1. LLM Input and Main Controller (`main.py`)

The system will be driven by a central controller that receives a structured JSON object, presumably from a natural language processing (LLP) model that parses user input. This controller will be responsible for directing the workflow based on the type of transaction requested.

### Assumed LLM JSON Output Formats

**Simple Transaction:**
```json
{
    "type": "simple",
    "description": "Taxi",
    "amount": 4.50,
    "account": "Cash",
    "category": "taxi",
    "budget_category": "transport"
}
```

**Installment Transaction:**
```json
{
    "type": "installment",
    "description": "New TV",
    "total_amount": 900.00,
    "installments": 3,
    "account": "Visa Produbanco",
    "category": "electronics",
    "budget_category": "shopping"
}
```

**Split Transaction:**
```json
{
    "type": "split",
    "description": "Supermaxi",
    "account": "Visa Produbanco",
    "splits": [
        { "amount": 100, "category": "groceries", "budget_category": "food" },
        { "amount": 20, "category": "snacks", "budget_category": "personal" }
    ]
}
```

### Controller Function (`main.py`)

-   **`process_transaction_request(conn: Connection, request: dict)`**
    -   **Purpose:** Acts as the main router for incoming transaction requests. It inspects the JSON and calls the appropriate business logic functions.
    -   **Logic:**
        1.  Reads the `type` field from the `request` dictionary.
        2.  Fetches the required account details from the database using `repository.get_account_by_name()`.
        3.  Uses a `match` or `if/elif/else` block to delegate to the correct function in the `transactions` module based on the `type`.
        4.  Receives a list of one or more transaction dictionaries from the logic module.
        5.  Passes this list to `repository.add_transactions()` to persist the data.

---

## 2. Core Transaction Logic (`transactions.py`)

This module contains all the business logic for creating transaction data structures. It is completely decoupled from the database and does not perform any database operations itself.

-   **`_generate_origin_id() -> str`**
    -   **Purpose:** Creates a unique ID for linking related transactions (installments or splits).
    -   **Details:** Returns a string in the format `YYYYMMDD-<random_string>`.

-   **`_calculate_credit_card_payment_date(transaction_date: date, cut_off_day: int, payment_day: int) -> date`**
    -   **Purpose:** Implements the core logic for determining the correct payment date for a credit card transaction based on its cut-off and payment days.

-   **`_create_base_transaction(description: str, amount: float, category: str | None, budget_category: str | None, transaction_date: date) -> dict`**
    -   **Purpose:** A private factory function to construct the common fields for any transaction dictionary.
    -   **Details:** Populates fields like `description`, `amount` (ensuring it's negative), `category`, `budget_category`, `date_created`, and sets `status` to `'committed'`.

-   **`create_single_transaction(description: str, amount: float, category: str | None, budget_category: str | None, account: dict, transaction_date: date) -> dict`**
    -   **Purpose:** A single, intelligent function to create one complete transaction dictionary, handling the logic for both cash and credit card payments.
    -   **Logic:**
        1.  Calls `_create_base_transaction` to build the foundation.
        2.  Sets the `account` name.
        3.  Checks the `account['account_type']`. If it's a `'credit_card'`, it calls `_calculate_credit_card_payment_date` to set the `date_payed`. Otherwise, `date_payed` is the same as `transaction_date`.

-   **`create_installment_transactions(description: str, total_amount: float, installments: int, category: str | None, budget_category: str | None, account: dict, transaction_date: date) -> list[dict]`**
    -   **Purpose:** Generates a list of transaction dictionaries for a purchase made in installments.
    -   **Logic:**
        1.  Generates a single `origin_id` for the entire set.
        2.  Calculates the amount for each installment.
        3.  Loops `installments` times, calculating the future date for each purchase.
        4.  For each installment, it calls `create_single_transaction` to generate the transaction dictionary with the correct future `date_payed`.
        5.  Appends `(n/installments)` to the description and adds the `origin_id`.

-   **`create_split_transactions(description: str, splits: list[dict], account: dict, transaction_date: date) -> list[dict]`**
    -   **Purpose:** Generates a list of transaction dictionaries for a split purchase.
    -   **Logic:**
        1.  Generates a single `origin_id`.
        2.  Loops through each item in the `splits` list.
        3.  For each split item, it calls `create_single_transaction`, passing the main description and account but the specific amount and categories from the split item.
        4.  Adds the `origin_id` to each created transaction.

---

## 3. Data Persistence (`repository.py`)

This module is the dedicated database abstraction layer. Its sole responsibility is to execute SQL queries to fetch and save data.

-   **`get_account_by_name(conn: Connection, name: str) -> dict`**
    -   **Purpose:** Retrieves a single account's details from the database by its name.

-   **`add_transactions(conn: Connection, transactions: list[dict])`**
    -   **Purpose:** Inserts a list of one or more transaction dictionaries into the database.
    -   **Details:** Uses `cursor.executemany()` for efficient bulk insertion.

-   **`get_all_transactions(conn: Connection) -> list[dict]`**
    -   **Purpose:** Retrieves all transactions from the database for display or export.

---

## 4. Database Setup and Initialization (`database.py`)

This module handles the initial setup and schema creation for the SQLite database. It is intended to be run once or whenever the database needs to be reset to a clean state.

-   **`create_connection(db_path: str) -> Connection`**
    -   **Purpose:** Establishes and returns a connection to the SQLite database file.

-   **`create_tables(conn: Connection)`**
    -   **Purpose:** Creates the `accounts` and `transactions` tables if they do not already exist, based on the schema in `spec.md`.

-   **`insert_initial_data(conn: Connection)`**
    -   **Purpose:** Populates the `accounts` table with default data (e.g., a "Cash" account and a sample credit card) to make the application immediately usable.

-   **`initialize_database(db_path: str)`**
    -   **Purpose:** A master function that orchestrates the entire database setup process.
    -   **Details:** It calls `create_connection`, `create_tables`, and `insert_initial_data` in sequence. This is the primary function to be called by any setup script.
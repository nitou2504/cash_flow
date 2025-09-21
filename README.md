# Personal Cash Flow Tool

## 1. Overview

This is a simple, yet powerful, personal cash flow management tool designed for clarity and traceability. The core principle of the system is to represent every financial event in a single, flat `transactions` table.

Its key feature is the ability to distinguish between the date a transaction occurred (`date_created`) and the date it actually impacts your cash flow (`date_payed`), providing a true financial picture, especially when dealing with credit card payments.

## 2. Core Features

*   **Multiple Transaction Types:** Handles simple expenses, installment purchases, and split transactions.
*   **Intelligent Credit Card Logic:** Automatically calculates the correct payment date for credit card transactions based on user-defined cut-off and payment days.
*   **Test-Driven:** Developed using a Test-Driven Development (TDD) approach to ensure reliability and correctness.
*   **Modular Architecture:** The code is separated into distinct modules for database management, business logic, and data persistence, making it easy to maintain and extend.

## 3. Future Vision: LLM-Powered Input

The backend logic is designed to be driven by a structured JSON object. The ultimate goal is to connect this system to a Large Language Model (LLM) that can parse natural language.

This will allow for extremely easy recording of expenses, where a user can simply input:

> "Supermarket 125.50 on Visa, 100 for groceries and 25.50 for snacks"

The LLM will then generate the required JSON to be processed by the `main.py` controller, making this a seamless and intuitive tool for personal finance management.

## 4. Technical Details

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

## 5. How to Run

1.  **Install Dependencies:**
    Before running the application, it's good practice to install any dependencies.
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: This project currently has no external dependencies, but this step is included for future maintainability.)*

2.  **Initialize the Database:**
    The main script is configured to initialize the database automatically.

3.  **Run the Example Script:**
    To run the pre-configured examples and create the `cash_flow.db` file, simply execute:
    ```bash
    python3 main.py
    ```
    This will create the database, add a few sample transactions, and print the final contents of the `transactions` table to the console.
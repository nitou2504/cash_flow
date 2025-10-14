
import argparse
import sqlite3
import json
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from dotenv import load_dotenv

from database import create_connection, initialize_database
import repository
import interface
import llm_parser
import main as controller

def handle_accounts_list(conn: sqlite3.Connection):
    """Displays a list of all accounts."""
    accounts = repository.get_all_accounts(conn)
    table = Table(title="All Accounts")
    table.add_column("Account ID")
    table.add_column("Type")
    table.add_column("Cut-off Day")
    table.add_column("Payment Day")

    for acc in accounts:
        table.add_row(
            acc['account_id'],
            acc['account_type'],
            str(acc.get('cut_off_day', 'N/A')),
            str(acc.get('payment_day', 'N/A'))
        )
    
    console = Console()
    console.print(table)

def handle_accounts_add(conn: sqlite3.Connection, args: argparse.Namespace):
    """Adds a new account."""
    repository.add_account(
        conn,
        args.id,
        args.type,
        args.cut_off_day,
        args.payment_day
    )
    print(f"Successfully added account: {args.id}")

def handle_add(conn: sqlite3.Connection, args: argparse.Namespace):
    """Parses a natural language string to add a transaction."""
    accounts = repository.get_all_accounts(conn)
    if not accounts:
        print("Error: No accounts found. Please add an account first using 'accounts add'.")
        return

    print("Parsing your request with the LLM...")
    transaction_json = llm_parser.parse_transaction_string(args.description, accounts)

    if transaction_json:
        console = Console()
        syntax = Syntax(json.dumps(transaction_json, indent=4), "json", theme="default", line_numbers=True)
        console.print("\nGenerated Transaction:")
        console.print(syntax)

        confirm = input("\nProceed to add this transaction? [Y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            controller.process_transaction_request(conn, transaction_json)
        else:
            print("Operation cancelled.")

def main():
    load_dotenv()
    # --- Database Setup ---
    db_path = "cash_flow.db"
    initialize_database(db_path)
    conn = create_connection(db_path)

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Personal Cash Flow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a transaction using natural language")
    add_parser.add_argument("description", help="The natural language description of the transaction")

    # Accounts command
    acc_parser = subparsers.add_parser("accounts", help="Manage accounts")
    acc_subparsers = acc_parser.add_subparsers(dest="subcommand", required=True)
    
    acc_list_parser = acc_subparsers.add_parser("list", help="List all accounts")
    
    acc_add_parser = acc_subparsers.add_parser("add", help="Add a new account")
    acc_add_parser.add_argument("id", help="The unique ID/name of the account")
    acc_add_parser.add_argument("type", choices=["cash", "credit_card"], help="The type of account")
    acc_add_parser.add_argument("--cut-off-day", type=int, help="Cut-off day (for credit cards)")
    acc_add_parser.add_argument("--payment-day", type=int, help="Payment day (for credit cards)")

    # View command
    view_parser = subparsers.add_parser("view", help="View all transactions")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export transactions to CSV")
    export_parser.add_argument("file_path", help="Path to the CSV file")
    export_parser.add_argument("--with-balance", action="store_true", help="Include running balance")

    args = parser.parse_args()

    # --- Command Handling ---
    if args.command == "add":
        handle_add(conn, args)
    elif args.command == "accounts":
        if args.subcommand == "list":
            handle_accounts_list(conn)
        elif args.subcommand == "add":
            handle_accounts_add(conn, args)
    elif args.command == "view":
        interface.view_transactions(conn)
    elif args.command == "export":
        interface.export_transactions_to_csv(conn, args.file_path, args.with_balance)

    conn.close()

if __name__ == "__main__":
    main()

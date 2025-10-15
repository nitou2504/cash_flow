
import argparse
import sqlite3
import json
import csv
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from datetime import date, datetime

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

def handle_accounts_add_manual(conn: sqlite3.Connection, args: argparse.Namespace):
    """Adds a new account using manual arguments."""
    repository.add_account(
        conn,
        args.id,
        args.type,
        args.cut_off_day,
        args.payment_day
    )
    print(f"Successfully added account: {args.id}")

def handle_accounts_add_natural(conn: sqlite3.Connection, args: argparse.Namespace):
    """Parses a natural language string to add a new account."""
    print("Parsing your request with the LLM...")
    account_json = llm_parser.parse_account_string(args.description)

    if account_json:
        console = Console()
        syntax = Syntax(json.dumps(account_json, indent=4), "json", theme="default", line_numbers=True)
        console.print("\nGenerated Account Details:")
        console.print(syntax)

        confirm = input("\nProceed to add this account? [Y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            repository.add_account(
                conn,
                account_json["account_id"],
                account_json["account_type"],
                account_json.get("cut_off_day"),
                account_json.get("payment_day")
            )
            print(f"Successfully added account: {account_json['account_id']}")
        else:
            print("Operation cancelled.")

def handle_add(conn: sqlite3.Connection, args: argparse.Namespace):
    """Parses a natural language string to add a transaction, subscription, or budget."""
    accounts = repository.get_all_accounts(conn)
    if not accounts:
        print("Error: No accounts found. Please add an account first using 'accounts add'.")
        return

    print("Parsing your request with the LLM...")
    request_json = llm_parser.parse_transaction_string(args.description, accounts)

    if request_json:
        console = Console()
        syntax = Syntax(json.dumps(request_json, indent=4), "json", theme="default", line_numbers=True)
        console.print("\nGenerated Request:")
        console.print(syntax)

        confirm = input("\nProceed with this request? [Y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            request_type = request_json.get("request_type")
            if request_type == "transaction":
                transaction_date = None
                if "date_created" in request_json:
                    transaction_date = date.fromisoformat(request_json["date_created"])
                controller.process_transaction_request(conn, request_json, transaction_date=transaction_date)
            elif request_type == "subscription":
                controller.process_subscription_request(conn, request_json["details"])
                # Rerun rollover to immediately commit forecasts for the new sub
                controller.run_monthly_rollover(conn, date.today())
            else:
                print(f"Error: Unknown request type '{request_type}'.")
        else:
            print("Operation cancelled.")

def handle_add_batch(conn: sqlite3.Connection, args: argparse.Namespace):
    """Adds multiple transactions from a CSV file."""
    try:
        with open(args.file_path, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip header
            lines = list(reader)
    except FileNotFoundError:
        print(f"Error: File not found at {args.file_path}")
        return
    except StopIteration:
        print(f"Error: CSV file at {args.file_path} is empty or has no header.")
        return

    accounts = repository.get_all_accounts(conn)
    if not accounts:
        print("Error: No accounts found. Please add an account first using 'accounts add'.")
        return
    
    account_ids = {acc['account_id'] for acc in accounts}

    console = Console()
    print(f"Found {len(lines)} transactions to process from {args.file_path}...")

    for i, row in enumerate(lines):
        if not row:
            continue
        
        try:
            # Expected format: creation_date,description,account_id,amount
            date_str, description, account_id, amount_str = row
        except ValueError:
            console.print(f"\n[yellow]Skipping line {i+2}: Incorrect number of columns. Expected 4, got {len(row)}.[/yellow]")
            continue

        # --- Data Validation ---
        try:
            transaction_date = datetime.strptime(date_str, '%m/%d/%y').date()
            amount = float(amount_str)
        except ValueError as e:
            console.print(f"\n[red]Error parsing line {i+2}: {row} - Invalid date or amount format. {e}[/red]")
            continue
        
        if account_id not in account_ids:
            console.print(f"\n[red]Error on line {i+2}: Account '{account_id}' not found in the database. Skipping.[/red]")
            console.print(f"Available accounts are: {', '.join(account_ids)}")
            continue

        # --- User Confirmation ---
        console.print("\n--- New Transaction ---")
        console.print(f"  Date: {transaction_date.strftime('%Y-%m-%d')}")
        console.print(f"  Desc: {description.strip()}")
        console.print(f"  Acct: {account_id}")
        console.print(f"  Amnt: {amount:.2f}")
        
        confirm = input("Proceed to add this transaction? [Y/n/a] (Yes/No/Abort) ")
        if confirm.lower() == 'y' or confirm == '':
            # Flatten the request structure to match what the controller expects
            request_data = {
                "type": "simple",
                "description": description.strip(),
                "amount": amount,
                "account": account_id,
            }
            controller.process_transaction_request(conn, request_data, transaction_date=transaction_date)
            console.print("[green]Transaction added successfully.[/green]")
        elif confirm.lower() == 'a':
            print("Operation aborted by user.")
            break
        else:
            print("Transaction skipped.")
    
    print("\nBatch processing finished.")

def handle_delete(conn: sqlite3.Connection, args: argparse.Namespace):
    """Deletes a transaction by its ID."""
    transaction_id = args.transaction_id
    
    # Fetch the transaction to show details before deleting
    transaction = repository.get_transaction_by_id(conn, transaction_id)
    
    if not transaction:
        print(f"Error: Transaction with ID {transaction_id} not found.")
        return

    console = Console()
    console.print("\n--- Transaction to Delete ---")
    table = Table(show_header=False, box=None)
    table.add_row("ID:", str(transaction['id']))
    table.add_row("Date:", str(transaction['date_payed']))
    table.add_row("Description:", transaction['description'])
    table.add_row("Account:", transaction['account'])
    table.add_row("Amount:", f"{transaction['amount']:.2f}")
    console.print(table)

    confirm = input(f"\nAre you sure you want to permanently delete this transaction? [y/N] ")
    if confirm.lower() == 'y':
        controller.process_transaction_deletion(conn, transaction_id)
        print(f"Successfully deleted transaction {transaction_id}.")
    else:
        print("Operation cancelled.")

def main():
    load_dotenv()
    # --- Database Setup ---
    db_path = "cash_flow.db"
    initialize_database(db_path)
    conn = create_connection(db_path)

    # Per technical spec, always run rollover on startup to sync state.
    controller.run_monthly_rollover(conn, date.today())

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Personal Cash Flow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a transaction using natural language")
    add_parser.add_argument("description", help="The natural language description of the transaction")

    # Add batch command
    add_batch_parser = subparsers.add_parser("add-batch", help="Add multiple transactions from a CSV file")
    add_batch_parser.add_argument("file_path", help="Path to the CSV file")

    # Accounts command
    acc_parser = subparsers.add_parser("accounts", help="Manage accounts")
    acc_subparsers = acc_parser.add_subparsers(dest="subcommand", required=True)
    
    acc_list_parser = acc_subparsers.add_parser("list", help="List all accounts")
    
    acc_add_manual_parser = acc_subparsers.add_parser("add-manual", help="Add a new account manually")
    acc_add_manual_parser.add_argument("id", help="The unique ID/name of the account")
    acc_add_manual_parser.add_argument("type", choices=["cash", "credit_card"], help="The type of account")
    acc_add_manual_parser.add_argument("--cut-off-day", type=int, help="Cut-off day (for credit cards)")
    acc_add_manual_parser.add_argument("--payment-day", type=int, help="Payment day (for credit cards)")

    acc_add_natural_parser = acc_subparsers.add_parser("add-natural", help="Add a new account using natural language")
    acc_add_natural_parser.add_argument("description", help="The natural language description of the account")

    # View command
    view_parser = subparsers.add_parser("view", help="View all transactions")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export transactions to CSV")
    export_parser.add_argument("file_path", help="Path to the CSV file")
    export_parser.add_argument("--with-balance", action="store_true", help="Include running balance")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a transaction by its ID")
    delete_parser.add_argument("transaction_id", type=int, help="The ID of the transaction to delete")

    args = parser.parse_args()

    # --- Command Handling ---
    if args.command == "add":
        handle_add(conn, args)
    elif args.command == "add-batch":
        handle_add_batch(conn, args)
    elif args.command == "accounts":
        if args.subcommand == "list":
            handle_accounts_list(conn)
        elif args.subcommand == "add-manual":
            handle_accounts_add_manual(conn, args)
        elif args.subcommand == "add-natural":
            handle_accounts_add_natural(conn, args)
    elif args.command == "view":
        interface.view_transactions(conn)
    elif args.command == "export":
        interface.export_transactions_to_csv(conn, args.file_path, args.with_balance)
    elif args.command == "delete":
        handle_delete(conn, args)

    conn.close()

if __name__ == "__main__":
    main()

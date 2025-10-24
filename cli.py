
import argparse
import sqlite3
import json
import csv
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

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

def handle_edit(conn: sqlite3.Connection, args: argparse.Namespace):
    """Handles the editing of a transaction."""
    updates = {}
    if args.description is not None:
        updates["description"] = args.description
    if args.amount is not None:
        updates["amount"] = args.amount
    if args.category is not None:
        updates["category"] = args.category
    if args.budget is not None:
        updates["budget"] = args.budget
    if args.status is not None:
        updates["status"] = args.status

    if not updates and not args.date:
        print("No changes specified. Use --description, --amount, etc. to edit.")
        return

    try:
        new_date = date.fromisoformat(args.date) if args.date else None
        controller.process_transaction_edit(conn, args.transaction_id, updates, new_date)
        print(f"Successfully updated transaction {args.transaction_id}.")
    except (ValueError, sqlite3.Error) as e:
        print(f"Error updating transaction: {e}")


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

def handle_clear(conn: sqlite3.Connection, args: argparse.Namespace):
    """Clears a pending transaction by its ID."""
    transaction_id = args.transaction_id
    try:
        controller.process_transaction_clearance(conn, transaction_id)
    except ValueError as e:
        print(f"Error: {e}")

def handle_add_installments(conn: sqlite3.Connection, args: argparse.Namespace):
    """
    Adds multiple transactions from a CSV file, designed to handle
    pre-existing single installments using the provided creation date.
    """
    try:
        with open(args.file_path, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
            lines = list(reader)
    except FileNotFoundError:
        print(f"Error: File not found at {args.file_path}")
        return
    except StopIteration:
        print(f"Error: CSV file at {args.file_path} is empty.")
        return

    console = Console()
    print(f"Found {len(lines)} transactions to process from {args.file_path}...")
    
    processed_count = 0
    for i, row in enumerate(lines):
        try:
            created_str, desc, acct, amt_str, curr_inst_str, total_inst_str = row
        except ValueError:
            console.print(f"\n[yellow]Skipping line {i+2}: Incorrect number of columns. Expected 6, got {len(row)}.[/yellow]")
            continue

        try:
            transaction_date = datetime.strptime(created_str, '%m/%d/%y').date()
            amount = float(amt_str)
        except ValueError as e:
            console.print(f"\n[red]Error parsing line {i+2}: {row} - Invalid date or amount. {e}[/red]")
            continue

        is_installment = curr_inst_str and total_inst_str
        
        console.print("\n--- New Transaction ---")
        console.print(f"  Creation Date: {transaction_date.strftime('%Y-%m-%d')}")
        console.print(f"  Description:   {desc}")
        console.print(f"  Account:       {acct}")
        console.print(f"  Amount:        {amount:.2f}")
        if is_installment:
            console.print(f"  Installment:   Starting from {curr_inst_str} of {total_inst_str}")
        
        confirm = input("Proceed to add this transaction? [Y/n/a] (Yes/No/Abort) ")

        if confirm.lower() == 'y' or confirm == '':
            request_data = {
                "account": acct,
                "description": desc,
            }
            if is_installment:
                current_installment = int(curr_inst_str)
                total_installments = int(total_inst_str)
                
                # Calculate the original total purchase amount.
                original_total_amount = amount * total_installments
                
                # Calculate the number of remaining installments to create.
                installments_to_create = total_installments - current_installment + 1
                
                request_data.update({
                    "type": "installment",
                    "total_amount": original_total_amount,
                    "installments": installments_to_create,
                    "start_from_installment": current_installment,
                    "total_installments": total_installments
                })
            else:
                request_data.update({
                    "type": "simple",
                    "amount": amount,
                })
            
            try:
                controller.process_transaction_request(conn, request_data, transaction_date=transaction_date)
                console.print("[green]Transaction added successfully.[/green]")
                processed_count += 1
            except ValueError as e:
                console.print(f"[red]Error processing transaction: {e}[/red]")

        elif confirm.lower() == 'a':
            print("Operation aborted by user.")
            break
        else:
            print("Transaction skipped.")
            
    print("\nBatch processing finished.")
    
    if processed_count > 0:
        controller.run_monthly_rollover(conn, date.today())

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

    # Add installments command
    add_installments_parser = subparsers.add_parser("add-installments", help="Add multiple pre-existing installments from a CSV file")
    add_installments_parser.add_argument("file_path", help="Path to the CSV file")

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
    view_parser = subparsers.add_parser("view", help="View transactions for the upcoming months")
    view_parser.add_argument("--months", type=int, default=3, help="Number of months to display (default: 3)")
    view_parser.add_argument("--summary", action="store_true", help="Summarize credit card payments into single monthly entries")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export transactions to CSV")
    export_parser.add_argument("file_path", help="Path to the CSV file")
    export_parser.add_argument("--with-balance", action="store_true", help="Include running balance")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a transaction by its ID")
    delete_parser.add_argument("transaction_id", type=int, help="The ID of the transaction to delete")

    # Edit command
    edit_parser = subparsers.add_parser("edit", help="Edit an existing transaction")
    edit_parser.add_argument("transaction_id", type=int, help="The ID of the transaction to edit")
    edit_parser.add_argument("--description", type=str, help="New description for the transaction")
    edit_parser.add_argument("--amount", type=float, help="New amount for the transaction")
    edit_parser.add_argument("--date", type=str, help="New creation date (YYYY-MM-DD) for the transaction")
    edit_parser.add_argument("--category", type=str, help="New category for the transaction")
    edit_parser.add_argument("--budget", type=str, help="New budget for the transaction")
    edit_parser.add_argument("--status", type=str, choices=["committed", "pending", "planning", "forecast"], help="New status for the transaction")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear a pending transaction by its ID")
    clear_parser.add_argument("transaction_id", type=int, help="The ID of the transaction to clear")

    args = parser.parse_args()

    # --- Command Handling ---
    if args.command == "add":
        handle_add(conn, args)
    elif args.command == "add-batch":
        handle_add_batch(conn, args)
    elif args.command == "add-installments":
        handle_add_installments(conn, args)
    elif args.command == "accounts":
        if args.subcommand == "list":
            handle_accounts_list(conn)
        elif args.subcommand == "add-manual":
            handle_accounts_add_manual(conn, args)
        elif args.subcommand == "add-natural":
            handle_accounts_add_natural(conn, args)
    elif args.command == "view":
        interface.view_transactions(conn, args.months, args.summary)
    elif args.command == "export":
        interface.export_transactions_to_csv(conn, args.file_path, args.with_balance)
    elif args.command == "delete":
        handle_delete(conn, args)
    elif args.command == "edit":
        handle_edit(conn, args)
    elif args.command == "clear":
        handle_clear(conn, args)

    conn.close()

if __name__ == "__main__":
    main()

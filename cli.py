
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

def handle_categories_list(conn: sqlite3.Connection):
    """Displays a list of all valid categories."""
    categories = repository.get_all_categories(conn)
    table = Table(title="Valid Categories")
    table.add_column("Category Name", style="bold")
    table.add_column("Description")

    for cat in categories:
        table.add_row(cat['name'], cat['description'])

    console = Console()
    console.print(table)

def handle_categories_add(conn: sqlite3.Connection, args: argparse.Namespace):
    """Adds a new category manually."""
    try:
        repository.add_category(conn, args.name, args.description)
        print(f"Successfully added category: {args.name}")
    except ValueError as e:
        print(f"Error: {e}")

def handle_categories_edit(conn: sqlite3.Connection, args: argparse.Namespace):
    """Edits the description of an existing category."""
    try:
        repository.update_category(conn, args.name, args.description)
        print(f"Successfully updated category: {args.name}")
    except ValueError as e:
        print(f"Error: {e}")

def handle_categories_delete(conn: sqlite3.Connection, args: argparse.Namespace):
    """Deletes a category."""
    try:
        # Validate category exists before asking for confirmation
        if not repository.category_exists(conn, args.name):
            print(f"Error: Category '{args.name}' does not exist.")
            return

        confirm = input(f"Are you sure you want to delete category '{args.name}'? [y/N] ")
        if confirm.lower() == 'y':
            repository.delete_category(conn, args.name)
            print(f"Successfully deleted category: {args.name}")
        else:
            print("Operation cancelled.")
    except ValueError as e:
        print(f"Error: {e}")

def handle_subscriptions_list(conn: sqlite3.Connection, args: argparse.Namespace):
    """Displays a list of all subscriptions with their status."""
    subscriptions = repository.get_all_subscriptions_with_status(conn)

    # Show active only by default (unless --all is specified)
    if not args.all:
        subscriptions = [s for s in subscriptions if s['status'] == 'Active']

    # Filter by budgets-only if requested
    if args.budgets_only:
        subscriptions = [s for s in subscriptions if s['is_budget']]

    table = Table(title="Subscriptions")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Amount", justify="right")
    table.add_column("Account")
    table.add_column("Start Date")
    table.add_column("End Date")
    table.add_column("Status")

    for sub in subscriptions:
        # Format end_date display
        end_date_str = str(sub['end_date']) if sub['end_date'] else "Ongoing"

        # Determine type
        sub_type = "Budget" if sub['is_budget'] else "Subscription"

        # Color code status
        status = sub['status']
        if status == 'Active':
            status_style = "[green]Active[/green]"
        else:  # Expired
            status_style = "[red]Expired[/red]"

        table.add_row(
            sub['id'],
            sub['name'],
            sub_type,
            f"${sub['monthly_amount']:.2f}",
            sub['payment_account_id'],
            str(sub['start_date']),
            end_date_str,
            status_style
        )

    console = Console()
    console.print(table)

def handle_subscriptions_add_manual(conn: sqlite3.Connection, args: argparse.Namespace):
    """Adds a new budget manually with optional end date for limited-time budgets."""
    from datetime import datetime

    # Parse dates if provided
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date() if args.start else date.today().replace(day=1)
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date() if args.end else None

    # Generate a readable ID from the name
    budget_id = f"budget_{args.name.lower().replace(' ', '_')}"

    budget_data = {
        "id": budget_id,
        "name": args.name,
        "category": args.category,
        "monthly_amount": args.amount,
        "payment_account_id": args.account,
        "start_date": start_date,
        "end_date": end_date,
        "is_budget": True,
        "underspend_behavior": args.underspend if hasattr(args, 'underspend') and args.underspend else "keep"
    }

    try:
        repository.add_subscription(conn, budget_data)
        budget_type = "limited-time" if end_date else "ongoing"
        print(f"Successfully added {budget_type} budget: {args.name}")

        # Generate forecasts for the new budget
        controller.generate_forecasts(conn, horizon_months=6, from_date=start_date)
        print(f"Generated forecast allocations for '{args.name}'.")
    except Exception as e:
        print(f"Error adding budget: {e}")


def handle_subscriptions_add_llm(conn: sqlite3.Connection, args: argparse.Namespace):
    """Parses a natural language string to add a subscription or budget using LLM."""
    accounts = repository.get_all_accounts(conn)
    if not accounts:
        print("Error: No accounts found. Please add an account first using 'accounts add'.")
        return

    print("Parsing your request with the LLM...")
    subscription_json = llm_parser.parse_subscription_string(conn, args.description, accounts)

    if subscription_json:
        console = Console()
        syntax = Syntax(json.dumps(subscription_json, indent=4), "json", theme="default", line_numbers=True)
        console.print("\nGenerated Subscription/Budget:")
        console.print(syntax)

        confirm = input("\nProceed with this request? [Y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            try:
                controller.process_subscription_request(conn, subscription_json)
                # Rerun rollover to immediately commit forecasts for the new subscription
                controller.run_monthly_rollover(conn, date.today())
            except Exception as e:
                print(f"Error creating subscription/budget: {e}")
        else:
            print("Operation cancelled.")


def handle_subscriptions_edit(conn: sqlite3.Connection, args: argparse.Namespace):
    """Edits an existing subscription's properties."""
    from datetime import datetime

    # Build updates dictionary from provided arguments
    updates = {}

    if args.name is not None:
        updates['name'] = args.name

    if args.amount is not None:
        updates['monthly_amount'] = args.amount

    if args.account is not None:
        updates['payment_account_id'] = args.account

    if args.end is not None:
        if args.end.lower() == 'none':
            # Allow removing end_date to make it ongoing
            updates['end_date'] = None
        else:
            updates['end_date'] = datetime.strptime(args.end, '%Y-%m-%d').date()

    if args.underspend is not None:
        updates['underspend_behavior'] = args.underspend

    if not updates:
        print("Error: No changes specified. Use --name, --amount, --account, --end, or --underspend")
        return

    try:
        # Pass retroactive flag for amount updates
        retroactive = args.retroactive if hasattr(args, 'retroactive') else False
        controller.process_budget_update(conn, args.subscription_id, updates, retroactive=retroactive)
    except Exception as e:
        print(f"Error editing subscription: {e}")


def handle_subscriptions_delete(conn: sqlite3.Connection, args: argparse.Namespace):
    """Deletes a subscription after user confirmation."""
    # Fetch subscription details for confirmation
    subscription = repository.get_subscription_by_id(conn, args.subscription_id)
    if not subscription:
        print(f"Error: Subscription '{args.subscription_id}' not found")
        return

    # Show subscription details
    sub_type = "Budget" if subscription['is_budget'] else "Subscription"
    print(f"\n{sub_type} to delete:")
    print(f"  ID: {subscription['id']}")
    print(f"  Name: {subscription['name']}")
    print(f"  Amount: ${subscription['monthly_amount']:.2f}/month")
    print(f"  Start: {subscription['start_date']}")
    print(f"  End: {subscription.get('end_date', 'Ongoing')}")

    # Get transaction counts
    tx_counts = repository.get_transaction_count_by_budget(conn, args.subscription_id)
    if tx_counts:
        print(f"\nLinked transactions:")
        for status, count in tx_counts.items():
            print(f"  {status}: {count}")

    # Confirmation prompt
    if not args.force:
        response = input(f"\nAre you sure you want to delete this {sub_type.lower()}? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Deletion cancelled.")
            return

    try:
        controller.process_budget_deletion(conn, args.subscription_id)
    except Exception as e:
        print(f"Error: {e}")


def handle_add(conn: sqlite3.Connection, args: argparse.Namespace):
    """Parses a natural language string to add a transaction using LLM."""
    accounts = repository.get_all_accounts(conn)
    if not accounts:
        print("Error: No accounts found. Please add an account first using 'accounts add'.")
        return

    budgets = repository.get_all_budgets(conn)

    print("Parsing your request with the LLM...")
    request_json = llm_parser.parse_transaction_string(conn, args.description, accounts, budgets)

    if request_json:
        console = Console()
        syntax = Syntax(json.dumps(request_json, indent=4), "json", theme="default", line_numbers=True)
        console.print("\nGenerated Transaction:")
        console.print(syntax)

        confirm = input("\nProceed with this request? [Y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            # --- Budget Name to ID Conversion ---
            budget_name_to_id_map = {b['name']: b['id'] for b in budgets}

            # For simple and installment transactions
            if 'budget' in request_json and request_json['budget'] in budget_name_to_id_map:
                budget_name = request_json['budget']
                request_json['budget'] = budget_name_to_id_map[budget_name]

            # For split transactions
            if request_json.get('type') == 'split' and 'splits' in request_json:
                for split in request_json['splits']:
                    if 'budget' in split and split['budget'] in budget_name_to_id_map:
                        budget_name = split['budget']
                        split['budget'] = budget_name_to_id_map[budget_name]
            # --- End Conversion ---

            transaction_date = None
            if "date_created" in request_json:
                transaction_date = date.fromisoformat(request_json["date_created"])
            controller.process_transaction_request(conn, request_json, transaction_date=transaction_date)
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
    """Deletes a transaction or a group of transactions by ID."""
    transaction_id = args.transaction_id
    delete_group = args.all

    console = Console()
    
    try:
        if delete_group:
            # We need to import controller to use _get_transaction_group_info
            group_info = controller._get_transaction_group_info(conn, transaction_id)
            siblings = group_info.get("siblings", [])
            if not siblings:
                print(f"Error: No transactions found for group associated with ID {transaction_id}.")
                return

            console.print("\n--- Transaction Group to Delete ---")
            table = Table(box=None)
            table.add_column("ID")
            table.add_column("Date")
            table.add_column("Description")
            table.add_column("Account")
            table.add_column("Amount")
            for t in siblings:
                table.add_row(str(t['id']), str(t['date_payed']), t['description'], t['account'], f"{t['amount']:.2f}")
            console.print(table)
            
            confirm_msg = f"\nAre you sure you want to permanently delete these {len(siblings)} transactions? [y/N] "

        else:
            transaction = repository.get_transaction_by_id(conn, transaction_id)
            if not transaction:
                print(f"Error: Transaction with ID {transaction_id} not found.")
                return

            console.print("\n--- Transaction to Delete ---")
            table = Table(show_header=False, box=None)
            table.add_row("ID:", str(transaction['id']))
            table.add_row("Date:", str(transaction['date_payed']))
            table.add_row("Description:", transaction['description'])
            table.add_row("Account:", transaction['account'])
            table.add_row("Amount:", f"{transaction['amount']:.2f}")
            console.print(table)
            
            confirm_msg = f"\nAre you sure you want to permanently delete this transaction? [y/N] "

        confirm = input(confirm_msg)
        if confirm.lower() == 'y':
            controller.process_transaction_deletion(conn, transaction_id, delete_group)
            print(f"Successfully deleted transaction(s).")
        else:
            print("Operation cancelled.")

    except ValueError as e:
        print(f"Error: {e}")

def handle_clear(conn: sqlite3.Connection, args: argparse.Namespace):
    """Clears a pending or planning transaction by its ID, committing it."""
    transaction_id = args.transaction_id
    try:
        controller.process_transaction_clearance(conn, transaction_id)
    except ValueError as e:
        print(f"Error: {e}")

def handle_fix(conn: sqlite3.Connection, args: argparse.Namespace):
    """Creates a balance adjustment transaction to match actual balance."""
    try:
        account = args.account if hasattr(args, 'account') and args.account else "Cash"
        controller.process_balance_adjustment(conn, args.actual_balance, account)
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
    add_batch_parser = subparsers.add_parser("add-batch", aliases=["ab"], help="Add multiple transactions from a CSV file")
    add_batch_parser.add_argument("file_path", help="Path to the CSV file")

    # Add installments command
    add_installments_parser = subparsers.add_parser("add-installments", aliases=["ai"], help="Add multiple pre-existing installments from a CSV file")
    add_installments_parser.add_argument("file_path", help="Path to the CSV file")

    # Accounts command
    acc_parser = subparsers.add_parser("accounts", aliases=["acc", "a"], help="Manage accounts")
    acc_subparsers = acc_parser.add_subparsers(dest="subcommand", required=True)
    
    acc_list_parser = acc_subparsers.add_parser("list", aliases=["ls", "l"], help="List all accounts")

    acc_add_manual_parser = acc_subparsers.add_parser("add-manual", aliases=["am"], help="Add a new account manually")
    acc_add_manual_parser.add_argument("id", help="The unique ID/name of the account")
    acc_add_manual_parser.add_argument("type", choices=["cash", "credit_card"], help="The type of account")
    acc_add_manual_parser.add_argument("--cut-off-day", "-c", type=int, help="Cut-off day (for credit cards)")
    acc_add_manual_parser.add_argument("--payment-day", "-p", type=int, help="Payment day (for credit cards)")

    acc_add_natural_parser = acc_subparsers.add_parser("add-natural", aliases=["an"], help="Add a new account using natural language")
    acc_add_natural_parser.add_argument("description", help="The natural language description of the account")

    # Categories command
    cat_parser = subparsers.add_parser("categories", aliases=["cat", "c"], help="Manage categories")
    cat_subparsers = cat_parser.add_subparsers(dest="subcommand", required=True)

    cat_list_parser = cat_subparsers.add_parser("list", aliases=["ls", "l"], help="List all valid categories")

    cat_add_parser = cat_subparsers.add_parser("add", aliases=["a"], help="Add a new category manually")
    cat_add_parser.add_argument("name", help="The name of the category")
    cat_add_parser.add_argument("description", help="A description of what this category covers")

    cat_edit_parser = cat_subparsers.add_parser("edit", aliases=["e"], help="Edit an existing category's description")
    cat_edit_parser.add_argument("name", help="The name of the category to edit")
    cat_edit_parser.add_argument("description", help="The new description for this category")

    cat_delete_parser = cat_subparsers.add_parser("delete", aliases=["del", "d"], help="Delete a category")
    cat_delete_parser.add_argument("name", help="The name of the category to delete")

    # Subscriptions command
    subscriptions_parser = subparsers.add_parser("subscriptions", aliases=["sub", "s"], help="Manage subscriptions and budgets")
    subscriptions_subparsers = subscriptions_parser.add_subparsers(dest="subcommand", required=True)

    subscriptions_list_parser = subscriptions_subparsers.add_parser("list", aliases=["ls", "l"], help="List all subscriptions (active by default)")
    subscriptions_list_parser.add_argument("--all", "-a", action="store_true", help="Show all subscriptions including expired")
    subscriptions_list_parser.add_argument("--budgets-only", "-b", action="store_true", help="Show only budgets")

    subscriptions_add_parser = subscriptions_subparsers.add_parser("add-manual", aliases=["am"], help="Add a new budget manually")
    subscriptions_add_parser.add_argument("name", help="The name of the budget")
    subscriptions_add_parser.add_argument("amount", type=float, help="The monthly budget amount")
    subscriptions_add_parser.add_argument("account", help="The account to use for this budget")
    subscriptions_add_parser.add_argument("category", help="The category for this budget")
    subscriptions_add_parser.add_argument("--start", "-s", type=str, help="Start date (YYYY-MM-DD). Defaults to first of current month")
    subscriptions_add_parser.add_argument("--end", "-e", type=str, help="End date (YYYY-MM-DD) for limited-time budgets. Omit for ongoing budgets")
    subscriptions_add_parser.add_argument("--underspend", "-u", choices=["keep", "return"], help="What to do with underspent funds (default: keep)")

    subscriptions_add_llm_parser = subscriptions_subparsers.add_parser("add", aliases=["a"], help="Add subscription/budget using natural language")
    subscriptions_add_llm_parser.add_argument("description", help="Natural language description of the subscription/budget")

    subscriptions_edit_parser = subscriptions_subparsers.add_parser("edit", aliases=["e"], help="Edit an existing subscription")
    subscriptions_edit_parser.add_argument("subscription_id", help="Subscription ID to edit")
    subscriptions_edit_parser.add_argument("--name", "-n", help="New name for the subscription")
    subscriptions_edit_parser.add_argument("--amount", "-a", type=float, help="New monthly amount")
    subscriptions_edit_parser.add_argument("--account", "-c", help="New payment account")
    subscriptions_edit_parser.add_argument("--end", "-e", help='New end date (YYYY-MM-DD) or "none" to remove')
    subscriptions_edit_parser.add_argument("--underspend", "-u", choices=["keep", "rollover"], help="Underspend behavior")
    subscriptions_edit_parser.add_argument("--retroactive", "-r", action="store_true", help="Update all past allocations (use for corrections, not price changes)")

    subscriptions_delete_parser = subscriptions_subparsers.add_parser("delete", aliases=["del", "d"], help="Delete a subscription (only if no committed transactions exist)")
    subscriptions_delete_parser.add_argument("subscription_id", help="Subscription ID to delete")
    subscriptions_delete_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompt")

    # View command
    view_parser = subparsers.add_parser("view", aliases=["v"], help="View transactions for the upcoming months")
    view_parser.add_argument("--months", "-m", type=int, default=3, help="Number of months to display (default: 3)")
    view_parser.add_argument("--from", "-f", dest="start_from", type=str, help="The starting month to display (e.g., '2025-10')")
    view_parser.add_argument("--summary", "-s", action="store_true", help="Summarize credit card payments into single monthly entries")
    view_parser.add_argument("--include-planning", "-p", action="store_true", help="Include 'planning' transactions in the summary totals")

    # Export command
    export_parser = subparsers.add_parser("export", aliases=["exp", "x"], help="Export transactions to CSV")
    export_parser.add_argument("file_path", help="Path to the CSV file")
    export_parser.add_argument("--with-balance", "-b", action="store_true", help="Include running balance")

    # Delete command
    delete_parser = subparsers.add_parser("delete", aliases=["del", "d"], help="Delete a transaction by its ID")
    delete_parser.add_argument("transaction_id", type=int, help="The ID of the transaction to delete")
    delete_parser.add_argument("--all", "-a", action="store_true", help="Delete the entire transaction group (e.g., all installments)")

    # Edit command
    edit_parser = subparsers.add_parser("edit", aliases=["e"], help="Edit an existing transaction")
    edit_parser.add_argument("transaction_id", type=int, help="The ID of the transaction to edit")
    edit_parser.add_argument("--description", "-d", type=str, help="New description for the transaction")
    edit_parser.add_argument("--amount", "-a", type=float, help="New amount for the transaction")
    edit_parser.add_argument("--date", "-D", type=str, help="New creation date (YYYY-MM-DD) for the transaction")
    edit_parser.add_argument("--category", "-c", type=str, help="New category for the transaction")
    edit_parser.add_argument("--budget", "-b", type=str, help="New budget for the transaction")
    edit_parser.add_argument("--status", "-s", type=str, choices=["committed", "pending", "planning", "forecast"], help="New status for the transaction")

    # Clear command
    clear_parser = subparsers.add_parser("clear", aliases=["cl"], help="Commits a pending or planning transaction by its ID")
    clear_parser.add_argument("transaction_id", type=int, help="The ID of the transaction to clear")

    # Fix command
    fix_parser = subparsers.add_parser("fix", aliases=["f"], help="Adjust balance to match actual total balance")
    fix_parser.add_argument("actual_balance", type=float, help="Your actual current total balance (all accounts combined)")
    fix_parser.add_argument("--account", "-a", default="Cash",
                           help="Account where the discrepancy occurred (e.g., use 'Visa Produbanco' for card fees/interest, 'Cash' for lost cash or forgotten purchases). Default: Cash")

    args = parser.parse_args()

    # --- Command Handling ---
    if args.command == "add":
        handle_add(conn, args)
    elif args.command in ["add-batch", "ab"]:
        handle_add_batch(conn, args)
    elif args.command in ["add-installments", "ai"]:
        handle_add_installments(conn, args)
    elif args.command in ["accounts", "acc", "a"]:
        if args.subcommand in ["list", "ls", "l"]:
            handle_accounts_list(conn)
        elif args.subcommand in ["add-manual", "am"]:
            handle_accounts_add_manual(conn, args)
        elif args.subcommand in ["add-natural", "an"]:
            handle_accounts_add_natural(conn, args)
    elif args.command in ["categories", "cat", "c"]:
        if args.subcommand in ["list", "ls", "l"]:
            handle_categories_list(conn)
        elif args.subcommand in ["add", "a"]:
            handle_categories_add(conn, args)
        elif args.subcommand in ["edit", "e"]:
            handle_categories_edit(conn, args)
        elif args.subcommand in ["delete", "del", "d"]:
            handle_categories_delete(conn, args)
    elif args.command in ["subscriptions", "sub", "s"]:
        if args.subcommand in ["list", "ls", "l"]:
            handle_subscriptions_list(conn, args)
        elif args.subcommand in ["add-manual", "am"]:
            handle_subscriptions_add_manual(conn, args)
        elif args.subcommand in ["add", "a"]:
            handle_subscriptions_add_llm(conn, args)
        elif args.subcommand in ["edit", "e"]:
            handle_subscriptions_edit(conn, args)
        elif args.subcommand in ["delete", "del", "d"]:
            handle_subscriptions_delete(conn, args)
    elif args.command in ["view", "v"]:
        interface.view_transactions(conn, args.months, args.summary, args.include_planning, args.start_from)
    elif args.command in ["export", "exp", "x"]:
        interface.export_transactions_to_csv(conn, args.file_path, args.with_balance)
    elif args.command in ["delete", "del", "d"]:
        handle_delete(conn, args)
    elif args.command in ["edit", "e"]:
        handle_edit(conn, args)
    elif args.command in ["clear", "cl"]:
        handle_clear(conn, args)
    elif args.command in ["fix", "f"]:
        handle_fix(conn, args)

    conn.close()

if __name__ == "__main__":
    main()

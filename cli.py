
# Suppress Google AI SDK warnings before importing anything
import os
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

import argparse
import sqlite3
import json
import csv
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from dotenv import load_dotenv

from cashflow.database import create_connection, initialize_database
from cashflow import repository
from cashflow import backup as db_backup
from cashflow.config import (
    BACKUP_ENABLED, BACKUP_DIR, BACKUP_KEEP_TODAY, BACKUP_RECENT_DAYS, BACKUP_MAX_DAYS,
    BACKUP_LOG_RETENTION_DAYS,
)
from ui import cli_display as interface
from llm import parser as llm_parser
from cashflow import controller

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

def handle_accounts_adjust_billing(conn: sqlite3.Connection, args: argparse.Namespace):
    """Adjusts credit card billing cycle for a specific month."""
    try:
        # Parse the month string to a date object (use first day of month)
        month_date = datetime.strptime(args.month, "%Y-%m").date()

        # Call the controller function
        controller.process_billing_cycle_adjustment(
            conn,
            args.account_id,
            month_date,
            args.cut_off_day,
            args.payment_day
        )
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

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
    table.add_column("Underspend")
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

        underspend = sub.get('underspend_behavior', '') if sub['is_budget'] else ''

        table.add_row(
            sub['id'],
            sub['name'],
            sub_type,
            underspend,
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


def handle_add_interactive(conn: sqlite3.Connection, args=None):
    """Interactive guided transaction entry (no LLM needed)."""
    from ui.interactive import interactive_add_transaction
    request = interactive_add_transaction(conn)
    if request:
        if args:
            desc = request.get('description', '')
            amt = request.get('amount', request.get('total_amount', ''))
            acc = request.get('account', '')
            args._backup_context = f"-i {desc} ${amt} {acc}"
        transaction_date = request.pop("_transaction_date", None)
        controller.process_transaction_request(conn, request, transaction_date=transaction_date)
    elif args:
        args._backup_skip = True


def handle_accounts_add_interactive(conn: sqlite3.Connection):
    """Interactive guided account creation."""
    from ui.interactive import interactive_add_account
    result = interactive_add_account(conn)
    if result:
        name, acc_type, cut_off_day, payment_day = result
        try:
            repository.add_account(conn, name, acc_type, cut_off_day, payment_day)
            print(f"Successfully added account: {name}")
        except Exception as e:
            print(f"Error adding account: {e}")


def handle_categories_add_interactive(conn: sqlite3.Connection):
    """Interactive guided category creation."""
    from ui.interactive import interactive_add_category
    result = interactive_add_category(conn)
    if result:
        name, description = result
        try:
            repository.add_category(conn, name, description)
            print(f"Successfully added category: {name}")
        except ValueError as e:
            print(f"Error: {e}")


def handle_subscriptions_add_interactive(conn: sqlite3.Connection):
    """Interactive guided subscription/budget creation."""
    from ui.interactive import interactive_add_subscription
    sub_data = interactive_add_subscription(conn)
    if sub_data:
        try:
            repository.add_subscription(conn, sub_data)
            kind = "budget" if sub_data.get('is_budget') else "subscription"
            print(f"Successfully added {kind}: {sub_data['name']}")
            controller.generate_forecasts(conn, horizon_months=6, from_date=sub_data['start_date'])
            print(f"Generated forecast allocations for '{sub_data['name']}'.")
            controller.run_monthly_rollover(conn, date.today())
        except Exception as e:
            print(f"Error adding subscription: {e}")


def handle_edit_interactive(conn: sqlite3.Connection, args: argparse.Namespace):
    """Interactive guided transaction edit."""
    from ui.interactive import interactive_edit_transaction

    def _set_edit_context(updates, new_date):
        parts = [f"#{args.transaction_id}"]
        parts.extend(f"{k}: {v}" for k, v in updates.items())
        if new_date:
            parts.append(f"date: {new_date}")
        args._backup_context = f"-i {', '.join(parts)}"

    if getattr(args, 'all', False):
        group_info = controller._get_transaction_group_info(conn, args.transaction_id)
        siblings = group_info.get("siblings", [])
        if len(siblings) <= 1:
            # Single transaction, just edit it
            result = interactive_edit_transaction(conn, args.transaction_id)
            if result:
                updates, new_date = result
                _set_edit_context(updates, new_date)
                controller.process_transaction_edit(conn, args.transaction_id, updates, new_date)
                print(f"Successfully updated transaction {args.transaction_id}.")
            else:
                args._backup_skip = True
        else:
            # Edit first, then apply to all
            result = interactive_edit_transaction(conn, args.transaction_id)
            if result:
                updates, new_date = result
                _set_edit_context(updates, new_date)
                for sibling in siblings:
                    controller.process_transaction_edit(conn, sibling['id'], updates, new_date)
                print(f"Successfully updated {len(siblings)} transactions in group.")
            else:
                args._backup_skip = True
    else:
        result = interactive_edit_transaction(conn, args.transaction_id)
        if result:
            updates, new_date = result
            _set_edit_context(updates, new_date)
            try:
                controller.process_transaction_edit(conn, args.transaction_id, updates, new_date)
                print(f"Successfully updated transaction {args.transaction_id}.")
            except (ValueError, sqlite3.Error) as e:
                print(f"Error updating transaction: {e}")
        else:
            args._backup_skip = True


def handle_subscriptions_edit_interactive(conn: sqlite3.Connection, args: argparse.Namespace):
    """Interactive guided subscription edit."""
    from ui.interactive import interactive_edit_subscription
    updates = interactive_edit_subscription(conn, args.subscription_id)
    if updates:
        try:
            retroactive = getattr(args, 'retroactive', False)
            controller.process_budget_update(conn, args.subscription_id, updates, retroactive=retroactive)
        except Exception as e:
            print(f"Error editing subscription: {e}")


def handle_create_transaction(conn: sqlite3.Connection, args: argparse.Namespace):
    """Creates a transaction from explicit flags (no LLM, no confirmation)."""
    transaction_date = date.fromisoformat(args.date) if args.date else date.today()

    if args.pending and args.planning:
        print("Error: --pending and --planning are mutually exclusive.")
        return

    if args.installments:
        if args.installments < 2:
            print("Error: --installments must be at least 2.")
            return
        request = {
            "type": "installment",
            "description": args.description,
            "total_amount": args.amount,
            "installments": args.installments - args.start_installment + 1,
            "total_installments": args.installments,
            "start_from_installment": args.start_installment,
            "account": args.account,
            "category": args.category,
            "budget": args.budget,
            "grace_period_months": args.grace_period,
            "is_income": args.income,
            "is_pending": args.pending,
            "is_planning": args.planning,
            "source": getattr(args, 'source', None),
            "needs_review": bool(getattr(args, 'needs_review', 0)),
        }
    else:
        if args.start_installment != 1:
            print("Error: --start-installment requires --installments.")
            return
        request = {
            "type": "simple",
            "description": args.description,
            "amount": args.amount,
            "account": args.account,
            "category": args.category,
            "budget": args.budget,
            "grace_period_months": args.grace_period,
            "is_income": args.income,
            "is_pending": args.pending,
            "is_planning": args.planning,
            "source": getattr(args, 'source', None),
            "needs_review": bool(getattr(args, 'needs_review', 0)),
        }

    args._backup_context = f"transaction {args.description} ${args.amount} {args.account}"
    controller.process_transaction_request(conn, request, transaction_date=transaction_date)


def handle_add(conn: sqlite3.Connection, args: argparse.Namespace):
    """Parses a natural language string to add a transaction using LLM."""
    if args.import_file:
        if args.installments:
            args.file_path = args.import_file
            return handle_add_installments(conn, args)
        args.file_path = args.import_file
        return handle_add_batch(conn, args)
    if args.installments and not args.import_file:
        print("Error: --installments requires --import FILE.")
        return
    if args.interactive:
        return handle_add_interactive(conn, args)
    if not args.description:
        print("Error: provide a description, use -i for interactive mode, or --import for CSV import.")
        return

    from cashflow import transactions as tx_module

    accounts = repository.get_all_accounts(conn)
    if not accounts:
        print("Error: No accounts found. Please add an account first using 'accounts add'.")
        return

    budgets = repository.get_all_budgets(conn)

    print("Parsing your request with the LLM...")

    # Calculate payment month for budget filtering
    payment_month = tx_module.calculate_payment_month(args.description, accounts)

    # Full parse with payment context
    request_json = llm_parser.parse_transaction_string(conn, args.description, accounts, budgets, payment_month)

    if request_json:
        from ui.interactive import display_transaction_preview

        transaction_date = date.fromisoformat(request_json.get("date_created", date.today().isoformat()))
        account_name = request_json.get('account', 'Unknown')
        account = next((a for a in accounts if a['account_id'] == account_name), None)

        display_transaction_preview(request_json, account, transaction_date)

        if getattr(args, 'yes', False):
            confirm = 'y'
        else:
            confirm = input("\nProceed with this request? [Y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            # LLM now returns budget IDs directly, no conversion needed
            transaction_date = None
            if "date_created" in request_json:
                transaction_date = date.fromisoformat(request_json["date_created"])
            controller.process_transaction_request(conn, request_json, transaction_date=transaction_date, user_input=args.description, source="cli")
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
    if getattr(args, 'source', None) is not None:
        updates["source"] = args.source
    needs_review_val = getattr(args, 'needs_review', None)
    if needs_review_val is not None:
        updates["needs_review"] = needs_review_val

    if not updates and not args.date:
        args._backup_skip = True
        print("No changes specified. Use --description, --amount, etc. to edit.")
        return

    parts = [f"#{args.transaction_id}"]
    parts.extend(f"--{k} {v}" for k, v in updates.items())
    if args.date:
        parts.append(f"--date {args.date}")
    args._backup_context = " ".join(parts)

    try:
        new_date = date.fromisoformat(args.date) if args.date else None

        # Handle group edits (all installments)
        if args.all:
            group_info = controller._get_transaction_group_info(conn, args.transaction_id)
            siblings = group_info.get("siblings", [])

            if len(siblings) <= 1:
                print(f"Transaction {args.transaction_id} is not part of a group. Editing single transaction.")
                controller.process_transaction_edit(conn, args.transaction_id, updates, new_date)
                print(f"Successfully updated transaction {args.transaction_id}.")
            else:
                # Show what will be updated
                console = Console()
                table = Table(title=f"Updating {len(siblings)} transactions in group")
                table.add_column("ID")
                table.add_column("Date")
                table.add_column("Description")
                table.add_column("Amount")

                for t in siblings:
                    table.add_row(
                        str(t['id']),
                        str(t['date_payed']),
                        t['description'],
                        f"{t['amount']:.2f}"
                    )
                console.print(table)

                confirm = input(f"\nApply changes to all {len(siblings)} transactions? [y/N] ")
                if confirm.lower() != 'y':
                    args._backup_skip = True
                    print("Operation cancelled.")
                    return

                # Apply updates to all siblings
                for sibling in siblings:
                    controller.process_transaction_edit(conn, sibling['id'], updates, new_date)

                print(f"Successfully updated {len(siblings)} transactions in group.")
        else:
            controller.process_transaction_edit(conn, args.transaction_id, updates, new_date)
            print(f"Successfully updated transaction {args.transaction_id}.")
    except (ValueError, sqlite3.Error) as e:
        print(f"Error updating transaction: {e}")


def handle_review(conn: sqlite3.Connection, args: argparse.Namespace):
    """Router for the review command."""
    action = args.action

    if action == "ls" or action is None:
        handle_review_list(conn, args)
        return

    # Try to parse action as a transaction ID
    try:
        transaction_id = int(action)
    except ValueError:
        print(f"Unknown review action: '{action}'. Use 'ls' or a transaction ID.")
        return

    # Route sub-actions
    if args.sub_action == "clear":
        repository.mark_reviewed(conn, transaction_id)
        print(f"Transaction {transaction_id} marked as reviewed.")
        args._backup_context = f"#{transaction_id} clear"
        return

    if getattr(args, 'interactive', False):
        # Reuse interactive edit then mark reviewed
        edit_args = argparse.Namespace(
            transaction_id=transaction_id,
            all=False,
            interactive=True,
            _backup_context=None,
            _backup_skip=False,
        )
        handle_edit_interactive(conn, edit_args)
        if not getattr(edit_args, '_backup_skip', False):
            repository.mark_reviewed(conn, transaction_id)
            print(f"Transaction {transaction_id} marked as reviewed.")
        args._backup_context = f"#{transaction_id} -i"
        args._backup_skip = getattr(edit_args, '_backup_skip', False)
        return

    # Check for edit flags
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

    new_date = date.fromisoformat(args.date) if args.date else None

    if updates or new_date:
        try:
            controller.process_transaction_edit(conn, transaction_id, updates, new_date)
            repository.mark_reviewed(conn, transaction_id)
            print(f"Transaction {transaction_id} updated and marked as reviewed.")
        except (ValueError, sqlite3.Error) as e:
            print(f"Error updating transaction: {e}")
            return
    else:
        # No flags: show transaction details and mark reviewed
        tx = repository.get_transaction_by_id(conn, transaction_id)
        if not tx:
            print(f"Transaction {transaction_id} not found.")
            return
        console = Console()
        table = Table(title=f"Transaction #{transaction_id}", box=None)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        for key in ["id", "date_payed", "description", "account", "amount", "category", "budget", "status", "source"]:
            table.add_row(key, str(tx.get(key, "")))
        console.print(table)
        repository.mark_reviewed(conn, transaction_id)
        print(f"Transaction {transaction_id} marked as reviewed.")

    args._backup_context = f"#{transaction_id}"


def handle_review_list(conn: sqlite3.Connection, args: argparse.Namespace):
    """Display unreviewed transactions."""
    source_filter = getattr(args, 'source', None)
    transactions = repository.get_transactions_needing_review(conn, source=source_filter)

    if not transactions:
        print("No transactions need review.")
        args._backup_skip = True
        return

    console = Console()
    title = "Transactions Needing Review"
    if source_filter:
        title += f" (source: {source_filter})"
    table = Table(title=title)
    table.add_column("ID", style="bold")
    table.add_column("Date")
    table.add_column("Description")
    table.add_column("Amount", justify="right")
    table.add_column("Account")
    table.add_column("Budget")
    table.add_column("Source")

    for tx in transactions:
        table.add_row(
            str(tx["id"]),
            str(tx["date_payed"]),
            tx["description"],
            f"{tx['amount']:.2f}",
            tx.get("account", ""),
            tx.get("budget", "") or "",
            tx.get("source", "") or "",
        )

    console.print(table)
    args._backup_skip = True


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
                args._backup_skip = True
                print(f"Error: No transactions found for group associated with ID {transaction_id}.")
                return

            group_desc = f"#{transaction_id} +{len(siblings)} {siblings[0]['description']}"
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
            tx_desc = group_desc

        else:
            transaction = repository.get_transaction_by_id(conn, transaction_id)
            if not transaction:
                args._backup_skip = True
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
            tx_desc = f"#{transaction_id} {transaction['description']}"

        confirm = input(confirm_msg)
        if confirm.lower() == 'y':
            args._backup_context = tx_desc
            controller.process_transaction_deletion(conn, transaction_id, delete_group)
            print(f"Successfully deleted transaction(s).")
        else:
            args._backup_skip = True
            print("Operation cancelled.")

    except ValueError as e:
        print(f"Error: {e}")

def handle_clear(conn: sqlite3.Connection, args: argparse.Namespace):
    """Clears a pending or planning transaction by its ID, committing it."""
    transaction_id = args.transaction_id

    try:
        # Handle group clears (all installments)
        if args.all:
            group_info = controller._get_transaction_group_info(conn, transaction_id)
            siblings = group_info.get("siblings", [])

            if len(siblings) <= 1:
                tx = repository.get_transaction_by_id(conn, transaction_id)
                if tx:
                    args._backup_context = f"#{transaction_id} {tx['description']} (was {tx['status']})"
                print(f"Transaction {transaction_id} is not part of a group. Clearing single transaction.")
                controller.process_transaction_clearance(conn, transaction_id)
                print(f"Successfully cleared transaction {transaction_id}.")
            else:
                group_desc = f"#{transaction_id} +{len(siblings)} {siblings[0]['description']} (was {siblings[0]['status']})"
                # Show what will be cleared
                console = Console()
                table = Table(title=f"Clearing {len(siblings)} transactions in group")
                table.add_column("ID")
                table.add_column("Date")
                table.add_column("Description")
                table.add_column("Status")
                table.add_column("Amount")

                for t in siblings:
                    table.add_row(
                        str(t['id']),
                        str(t['date_payed']),
                        t['description'],
                        t['status'],
                        f"{t['amount']:.2f}"
                    )
                console.print(table)

                confirm = input(f"\nClear (commit) all {len(siblings)} transactions? [y/N] ")
                if confirm.lower() != 'y':
                    args._backup_skip = True
                    print("Operation cancelled.")
                    return

                args._backup_context = group_desc
                # Clear all siblings
                for sibling in siblings:
                    controller.process_transaction_clearance(conn, sibling['id'])

                print(f"Successfully cleared {len(siblings)} transactions in group.")
        else:
            tx = repository.get_transaction_by_id(conn, transaction_id)
            if tx:
                args._backup_context = f"#{transaction_id} {tx['description']} (was {tx['status']})"
            controller.process_transaction_clearance(conn, transaction_id)
            print(f"Successfully cleared transaction {transaction_id}.")
    except ValueError as e:
        print(f"Error: {e}")

def get_smart_payment_month(conn: sqlite3.Connection, account_id: str) -> date:
    """
    Determines the appropriate month for payment fix based on current date and cut-off day.

    For credit cards:
    - If today >= cut-off day: Return next month (you're working on next bill)
    - If today < cut-off day: Return current month (still on current bill)

    For cash accounts:
    - Always return current month
    """
    account = repository.get_account_by_name(conn, account_id)
    if not account:
        # Default to current month if account not found (error will be caught later)
        return date.today().replace(day=1)

    today = date.today()

    if account['account_type'] == 'credit_card':
        cut_off_day = account['cut_off_day']

        if today.day >= cut_off_day:
            # Past cut-off, working on next month's bill
            next_month = today + relativedelta(months=1)
            return next_month.replace(day=1)
        else:
            # Before cut-off, still on current month's bill
            return today.replace(day=1)
    else:
        # Cash account, use current month
        return today.replace(day=1)


def handle_fix(conn: sqlite3.Connection, args: argparse.Namespace):
    """Routes to balance fix or payment fix based on flags."""

    if args.balance:
        # Balance fix mode
        try:
            controller.process_balance_adjustment(conn, args.balance, args.account)
        except ValueError as e:
            print(f"Error: {e}")

    elif args.payment:
        # Payment fix mode
        # Smart detection: if month looks like a number, it's actually the amount
        actual_month = None
        actual_amount = args.amount

        if args.month:
            # Try to parse as month first
            try:
                actual_month = datetime.strptime(args.month, "%Y-%m").date()
            except ValueError:
                # Not a valid month format, might be the amount instead
                try:
                    actual_amount = float(args.month)
                    # Smart month selection based on cut-off day
                    actual_month = get_smart_payment_month(conn, args.payment)
                except ValueError:
                    print("Error: Invalid month format. Use YYYY-MM (e.g., 2025-11)")
                    return
        else:
            # No month provided, use smart selection
            actual_month = get_smart_payment_month(conn, args.payment)

        if args.interactive:
            # Interactive mode
            handle_statement_fix_interactive(conn, args.payment, actual_month)
        else:
            # Non-interactive mode
            if not actual_amount:
                print("Error: Statement amount required (or use -i for interactive)")
                return
            handle_statement_fix_noninteractive(conn, args.payment, actual_month, actual_amount)


def handle_statement_fix_noninteractive(
    conn: sqlite3.Connection,
    account_id: str,
    month: date,
    statement_amount: float
):
    """Non-interactive payment fix - no preview, no confirmation, just do it."""

    try:
        result = controller.process_statement_adjustment(
            conn, account_id, month, statement_amount
        )

        if result:
            # Success message
            diff = result['difference']
            adjustment_amount = -diff
            adj_sign = "+" if adjustment_amount >= 0 else "-"
            diff_sign = "+" if diff >= 0 else "-"
            print(f"✓ Payment adjusted for {account_id} ({result['payment_date']})")
            print(f"  Previous: ${result['current_total']:.2f}  →  "
                  f"Statement: ${statement_amount:.2f}  →  "
                  f"Difference: {diff_sign}${abs(diff):.2f}")
            print(f"  Transaction created: Payment Adjustment - {account_id} ({adj_sign}${abs(adjustment_amount):.2f})")
        else:
            print(f"✓ No adjustment needed - statement matches current total")

    except ValueError as e:
        print(f"Error: {e}")


def handle_statement_fix_interactive(
    conn: sqlite3.Connection,
    account_id: str,
    month: date
):
    """Interactive payment fix - shows table, asks for amount, confirms."""
    from ui.interactive import interactive_statement_fix

    statement_amount = interactive_statement_fix(conn, account_id, month)
    if statement_amount is None:
        return

    try:
        result = controller.process_statement_adjustment(
            conn, account_id, month, statement_amount
        )

        if result:
            diff = result['difference']
            adjustment_amount = -diff
            adj_sign = "+" if adjustment_amount >= 0 else "-"
            print(f"\n✓ Payment adjusted for {account_id} ({result['payment_date']})")
            print(f"  Transaction created: Payment Adjustment - {account_id} ({adj_sign}${abs(adjustment_amount):.2f})")
        else:
            print(f"✓ No adjustment needed - statement matches current total")

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

def handle_backup(db_path: str, args: argparse.Namespace):
    """Handle backup subcommands: create, list, restore."""
    console = Console()
    backup_args = args.backup_args

    if not backup_args:
        # unnamed manual backup
        path = db_backup.create_backup(db_path, BACKUP_DIR, manual=True)
        db_backup.write_backup_log(BACKUP_DIR, path.name, "manual backup")
        console.print(f"[green]Backup created: {path.name}[/green]")

    elif backup_args[0] in ("list", "ls", "l"):
        backups = db_backup.list_backups(BACKUP_DIR)
        if not backups:
            print("No backups found.")
            return
        table = Table(title=f"Backups in {BACKUP_DIR}/")
        table.add_column("Filename")
        table.add_column("Type")
        table.add_column("Date")
        table.add_column("Time")
        table.add_column("Size")
        for b in backups:
            size_kb = b["size"] / 1024
            table.add_row(
                b["path"].name,
                "[bold cyan]manual[/bold cyan]" if b["manual"] else "auto",
                b["date"].isoformat(),
                b["datetime"].strftime("%H:%M:%S"),
                f"{size_kb:.0f} KB",
            )
        console.print(table)

    elif backup_args[0] in ("restore", "r"):
        if len(backup_args) < 2:
            print("Error: restore requires a filename")
            return
        backup_file = backup_args[1]
        # Allow just filename (resolve to backup dir)
        backup_path = Path(backup_file)
        if not backup_path.exists():
            backup_path = Path(BACKUP_DIR) / backup_file
        if not backup_path.exists():
            console.print(f"[red]Backup not found: {backup_file}[/red]")
            return

        confirm = input(f"Restore from {backup_path.name}? This will overwrite the current database. [y/N] ")
        if confirm.lower() != "y":
            print("Restore cancelled.")
            return

        pre_restore = db_backup.restore_backup(str(backup_path), db_path, BACKUP_DIR)
        db_backup.write_backup_log(BACKUP_DIR, pre_restore.name, "pre-restore")
        console.print(f"[green]Database restored from {backup_path.name}[/green]")
        console.print(f"[dim]Pre-restore backup saved: {pre_restore.name}[/dim]")

    else:
        # first arg(s) = backup name
        name = " ".join(backup_args)
        path = db_backup.create_backup(db_path, BACKUP_DIR, manual=True, name=name)
        db_backup.write_backup_log(BACKUP_DIR, path.name, f"manual backup: {name}")
        console.print(f"[green]Backup created: {path.name}[/green]")


def describe_operation(args: argparse.Namespace) -> str:
    """Build a one-line description of the CLI operation for backup logging."""
    cmd = getattr(args, "command", "")

    # Rich context set by handlers (preferred)
    ctx = getattr(args, "_backup_context", None)
    if ctx:
        return f"{cmd} {ctx}"[:80]

    # Fallback to args-based description
    parts = [cmd]

    if cmd == "add":
        desc = getattr(args, "description", None)
        imp = getattr(args, "import_file", None)
        interactive = getattr(args, "interactive", False)
        if interactive:
            parts.append("-i")
        elif imp:
            parts.append(f"--import {imp}")
        elif desc:
            parts.append(desc)
    elif cmd in ("create", "cr"):
        entity = getattr(args, "create_entity", "")
        parts.append(entity)
        desc = getattr(args, "description", None)
        if desc:
            parts.append(desc)
    elif cmd in ("delete", "del", "d"):
        tid = getattr(args, "transaction_id", "")
        parts.append(f"#{tid}")
    elif cmd in ("edit", "e"):
        tid = getattr(args, "transaction_id", "")
        parts.append(f"#{tid}")
    elif cmd in ("clear", "cl"):
        tid = getattr(args, "transaction_id", "")
        parts.append(f"#{tid}")
    elif cmd in ("review", "rv"):
        action = getattr(args, "action", "ls")
        parts.append(str(action))
    elif cmd in ("fix", "f"):
        balance = getattr(args, "balance", None)
        payment = getattr(args, "payment", None)
        account = getattr(args, "account", None)
        if balance is not None:
            parts.append(f"--balance {balance}")
        if payment:
            parts.append(f"--payment {payment}")
        if account:
            parts.append(f"--account {account}")
    elif cmd in ("accounts", "acc", "a", "categories", "cat", "c", "subscriptions", "sub", "s"):
        sub = getattr(args, "subcommand", "")
        if sub:
            parts.append(sub)
        name = getattr(args, "subscription_id", None) or getattr(args, "name", None)
        if name:
            parts.append(str(name))

    result = " ".join(str(p) for p in parts if p)
    return result[:80]


def main():
    load_dotenv()
    # --- Database Setup ---
    db_path = "cash_flow.db"
    initialize_database(db_path)
    conn = create_connection(db_path)

    # Per technical spec, always run rollover on startup to sync state.
    controller.run_monthly_rollover(conn, date.today())

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="""
Personal Cash Flow Management System
=====================================
Track expenses, manage budgets, handle credit card payments, and forecast cash flow.
Supports multiple accounts (cash and credit cards), installment tracking, and natural language input.
        """,
        epilog="""
COMMON WORKFLOWS:
  First-time setup:
    1. cli.py accounts add "Cash account"
    2. cli.py accounts add "Credit card with cut-off on 25th and payment on 5th"
    3. cli.py categories add groceries "Food and household items"

  Daily usage:
    cli.py add "Spent 45.50 on groceries at Supermarket today"
    cli.py add -i                  # Interactive guided entry (no LLM needed)
    cli.py view                    # See upcoming transactions
    cli.py view -s                 # Summary view (aggregated credit card payments)

  Managing budgets:
    cli.py subscriptions add "Monthly groceries budget of 300 on Cash"
    cli.py subscriptions list

  Reconciliation:
    cli.py fix --payment MyCard -i              # Interactive statement reconciliation
    cli.py fix --balance 1500.00 --account Cash # Fix total balance

  Transaction management:
    cli.py edit 123 --status pending            # Change one transaction
    cli.py edit 123 --status pending --all      # Change all installments
    cli.py delete 456 --all                     # Delete entire installment group
    cli.py clear 789                            # Commit a pending transaction
    cli.py clear 789 --all                      # Commit all in group

  Review extra user transactions:
    cli.py review ls                            # List unreviewed
    cli.py review ls --source mom               # Filter by source
    cli.py review 605                           # Show + mark reviewed
    cli.py review 605 clear                     # Mark reviewed silently
    cli.py review 605 -i                        # Interactive edit + review

  Pending & planning:
    cli.py add "Friend owes me 50, pending"
    cli.py add "What if I buy a TV for 800"        # Planning transaction
    cli.py clear 789                               # Commit when confirmed

ALIASES:
  Most commands have short aliases (shown in brackets below):
  - create [cr]          - accounts [acc, a]         - view [v]
  - subscriptions [sub, s] - categories [cat, c]     - edit [e]
  - export [exp, x]      - delete [del, d]           - fix [f]
  - clear [cl]           - backup [bk]           - review [rv]

For detailed help on any command: cli.py COMMAND -h
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="Available Commands",
        metavar="COMMAND"
    )

    # ==================== TRANSACTION COMMANDS ====================

    # Add command
    add_parser = subparsers.add_parser(
        "add",
        help="Add a transaction (natural language, interactive, or CSV import)",
        description="""
Add a transaction using natural language or interactive guided entry.

Natural language (requires LLM):
  cli.py add "Spent 45.50 on groceries at Supermaxi today"
  cli.py add "Bought TV for 600 in 12 installments on Visa card"
  cli.py add "Phone plan 600 starting the 5th of 12 on Visa Pichincha"
  cli.py add "Bought laptop with 3 months grace period on Visa"
  cli.py add "Friend owes me 100, pending"
  cli.py add "What if I buy headphones for 80"
  cli.py add "Split: 30 groceries, 15 snacks at Supermaxi"

Interactive (no LLM needed):
  cli.py add -i
  Amount defaults to expense; prefix with + for income (e.g. +1000 for salary).

CSV import:
  cli.py add --import transactions.csv
  cli.py add --import installments.csv --installments
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_parser.add_argument("description", nargs="?", help="Natural language description (or use -i)")
    add_parser.add_argument("--interactive", "-i", action="store_true",
                            help="Interactive guided entry (no LLM needed). Accepts numbers, prefixes, $amounts, +N month shortcuts")
    add_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt (auto-accept)")
    add_parser.add_argument("--import", dest="import_file", metavar="FILE",
                            help="Import transactions from a CSV file")
    add_parser.add_argument("--installments", action="store_true",
                            help="Treat CSV as installment format (use with --import)")

    # ==================== EXPLICIT CREATION (SCRIPTABLE) ====================

    create_parser = subparsers.add_parser(
        "create",
        aliases=["cr"],
        help="Create entities with explicit parameters (no LLM)",
        description="""
Create transactions, accounts, budgets, or categories with explicit parameters.
No LLM, no confirmation prompts. Good for automation, tests, and seeding.

Subcommands:
  transaction [tx, t]   Create a transaction
  account [acc, a]      Create an account
  budget [bud, b]       Create a budget/subscription
  category [cat, c]     Create a category

Examples:
  cli.py create transaction "Supermaxi groceries" 45.50 Cash -c groceries
  cli.py create account Cash cash
  cli.py create budget "Groceries" 300 Cash groceries
  cli.py create category dining "Eating out, takeout, coffee"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create_subparsers = create_parser.add_subparsers(
        dest="create_entity", required=True, title="Entity Types", metavar="ENTITY",
    )

    # create transaction
    create_tx_parser = create_subparsers.add_parser(
        "transaction",
        aliases=["tx", "t"],
        help="Create a transaction with explicit parameters",
        description="""
Create a transaction directly from flags (no LLM, no confirmation).

Examples:
  cli.py create transaction "Supermaxi groceries" 45.50 Cash -c groceries
  cli.py create transaction "Laptop" 1200 VisaCard -n 12 -c electronics
  cli.py create transaction "Phone plan" 600 VisaCard -n 12 --start-installment 5
  cli.py create transaction "Salary" 3000 Cash --income
  cli.py create transaction "Maybe a TV" 800 Cash --planning
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create_tx_parser.add_argument("description", help="Transaction description")
    create_tx_parser.add_argument("amount", type=float, help="Amount (or total for installments)")
    create_tx_parser.add_argument("account", help="Account ID")
    create_tx_parser.add_argument("--category", "-c", help="Category name")
    create_tx_parser.add_argument("--budget", "-b", help="Budget ID")
    create_tx_parser.add_argument("--date", "-d", help="Transaction date (YYYY-MM-DD, default: today)")
    create_tx_parser.add_argument("--installments", "-n", type=int, help="Number of installments (promotes amount to total)")
    create_tx_parser.add_argument("--start-installment", type=int, default=1, help="Starting installment number (default: 1, use with --installments)")
    create_tx_parser.add_argument("--grace-period", "-g", type=int, default=0, help="Grace period in months")
    create_tx_parser.add_argument("--income", action="store_true", default=False, help="Mark as income (positive amount)")
    create_tx_parser.add_argument("--pending", action="store_true", default=False, help="Mark as pending")
    create_tx_parser.add_argument("--planning", action="store_true", default=False, help="Mark as planning")
    create_tx_parser.add_argument("--source", type=str, help="Transaction source (e.g. mom)")
    create_tx_parser.add_argument("--needs-review", type=int, choices=[0, 1], default=0, help="Mark for review")

    # create account
    create_acc_parser = create_subparsers.add_parser(
        "account",
        aliases=["acc", "a"],
        help="Create an account with explicit parameters",
        description="""
Create a new account with explicit parameters.

Examples:
  cli.py create account Cash cash
  cli.py create account VisaCard credit_card --cut-off-day 25 --payment-day 5
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create_acc_parser.add_argument("id", help="Unique account ID/name (e.g., 'Cash', 'VisaCard')")
    create_acc_parser.add_argument("type", choices=["cash", "credit_card"], help="Account type")
    create_acc_parser.add_argument("--cut-off-day", "-c", type=int, help="Statement cut-off day (1-31, credit cards only)")
    create_acc_parser.add_argument("--payment-day", "-p", type=int, help="Payment due day (1-31, credit cards only)")

    # create budget
    create_bud_parser = create_subparsers.add_parser(
        "budget",
        aliases=["bud", "b"],
        help="Create a budget/subscription with explicit parameters",
        description="""
Create a budget or subscription with explicit parameters.

Examples:
  cli.py create budget "Groceries" 300 Cash groceries
  cli.py create budget "Netflix" 15.99 VisaCard entertainment --start 2026-02-01
  cli.py create budget "Vacation" 200 Cash savings --start 2026-02-01 --end 2026-12-31
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create_bud_parser.add_argument("name", help="Budget name (e.g., 'Groceries', 'Netflix')")
    create_bud_parser.add_argument("amount", type=float, help="Monthly amount in dollars")
    create_bud_parser.add_argument("account", help="Account ID to charge")
    create_bud_parser.add_argument("category", help="Category name")
    create_bud_parser.add_argument("--start", "-s", type=str, help="Start date YYYY-MM-DD (default: today)")
    create_bud_parser.add_argument("--end", "-e", type=str, help="End date YYYY-MM-DD (omit for ongoing)")
    create_bud_parser.add_argument("--underspend", "-u", choices=["keep", "return"], help="Unused budget behavior: 'keep' or 'return'")

    # create category
    create_cat_parser = create_subparsers.add_parser(
        "category",
        aliases=["cat", "c"],
        help="Create a new category",
        description="""
Create a new category with a description for LLM auto-categorization.

Examples:
  cli.py create category dining "Eating out, takeout, coffee"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    create_cat_parser.add_argument("name", help="Category name (lowercase, no spaces)")
    create_cat_parser.add_argument("description", help="What this category covers")

    # ==================== ACCOUNT MANAGEMENT ====================

    # Accounts command
    acc_parser = subparsers.add_parser(
        "accounts",
        aliases=["acc", "a"],
        help="Manage payment accounts (cash and credit cards)",
        description="Manage payment accounts including cash accounts and credit cards with billing cycles"
    )
    acc_subparsers = acc_parser.add_subparsers(
        dest="subcommand",
        required=True,
        title="Account Operations"
    )

    acc_list_parser = acc_subparsers.add_parser(
        "list",
        aliases=["ls", "l"],
        help="List all accounts with their details"
    )

    acc_add_natural_parser = acc_subparsers.add_parser(
        "add",
        aliases=["a", "an"],
        help="Add account (natural language or interactive)",
        description="""
Add a new account using natural language or interactive guided mode.
Examples:
  cli.py accounts add "Cash account"
  cli.py accounts add "Visa card with cut-off on 25 and payment on 5"
  cli.py accounts add -i    # Interactive guided mode (no LLM needed)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    acc_add_natural_parser.add_argument("description", nargs="?", help="Natural language account description")
    acc_add_natural_parser.add_argument("--interactive", "-i", action="store_true", help="Interactive guided mode (no LLM needed)")

    acc_adjust_billing_parser = acc_subparsers.add_parser(
        "adjust-billing",
        aliases=["ab"],
        help="Adjust billing cycle for a specific month (one-time change)",
        description="Temporarily adjust credit card billing cycle for a month (e.g., when bank changes statement date)"
    )
    acc_adjust_billing_parser.add_argument("account_id", help="Credit card account ID")
    acc_adjust_billing_parser.add_argument("month", help="Affected month (YYYY-MM format)")
    acc_adjust_billing_parser.add_argument("cut_off_day", type=int, help="Actual cut-off day for this month (1-31)")
    acc_adjust_billing_parser.add_argument("--payment-day", "-p", type=int, help="Temporary payment day if also changed (1-31)")

    # ==================== CATEGORY MANAGEMENT ====================

    # Categories command
    cat_parser = subparsers.add_parser(
        "categories",
        aliases=["cat", "c"],
        help="Manage expense categories",
        description="Manage transaction categories (groceries, utilities, entertainment, etc.)"
    )
    cat_subparsers = cat_parser.add_subparsers(
        dest="subcommand",
        required=True,
        title="Category Operations"
    )

    cat_list_parser = cat_subparsers.add_parser(
        "list",
        aliases=["ls", "l"],
        help="List all available categories"
    )

    cat_add_parser = cat_subparsers.add_parser(
        "add",
        aliases=["a"],
        help="Create a new category",
        description="""
Create a new category. The description helps the LLM auto-categorize transactions.
Examples:
  cli.py categories add dining "Eating out, takeout, coffee"
  cli.py categories add -i    # Interactive guided mode
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    cat_add_parser.add_argument("name", nargs="?", help="Category name (lowercase, no spaces)")
    cat_add_parser.add_argument("description", nargs="?", help="What this category covers")
    cat_add_parser.add_argument("--interactive", "-i", action="store_true", help="Interactive guided mode")

    cat_edit_parser = cat_subparsers.add_parser(
        "edit",
        aliases=["e"],
        help="Update category description",
        description="""
Update the description for an existing category.
Example:
  cli.py categories edit dining "Restaurants, fast food, coffee shops"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    cat_edit_parser.add_argument("name", help="Category name to edit")
    cat_edit_parser.add_argument("description", help="New description")

    cat_delete_parser = cat_subparsers.add_parser(
        "delete",
        aliases=["del", "d"],
        help="Remove a category",
        description="""
Delete a category (will fail if transactions are using it).
Example:
  cli.py categories delete dining
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    cat_delete_parser.add_argument("name", help="Category name to delete")

    # ==================== BUDGET & SUBSCRIPTION MANAGEMENT ====================

    # Subscriptions command
    subscriptions_parser = subparsers.add_parser(
        "subscriptions",
        aliases=["sub", "s"],
        help="Manage recurring budgets and subscriptions",
        description="""
Manage monthly budgets and recurring subscriptions.
Budgets automatically allocate funds each month and track spending against limits.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subscriptions_subparsers = subscriptions_parser.add_subparsers(
        dest="subcommand",
        required=True,
        title="Budget Operations"
    )

    subscriptions_list_parser = subscriptions_subparsers.add_parser(
        "list",
        aliases=["ls", "l"],
        help="List budgets and subscriptions",
        description="Show active budgets/subscriptions by default (use --all to include expired)"
    )
    subscriptions_list_parser.add_argument("--all", "-a", action="store_true", help="Include expired budgets/subscriptions")
    subscriptions_list_parser.add_argument("--budgets-only", "-b", action="store_true", help="Show only budgets (exclude subscriptions)")

    subscriptions_add_llm_parser = subscriptions_subparsers.add_parser(
        "add",
        aliases=["a"],
        help="Add budget/subscription (natural language or interactive)",
        description="""
Add a budget or subscription using natural language or interactive guided mode.
Examples:
  cli.py subscriptions add "Monthly groceries budget of 300 on Cash"
  cli.py subscriptions add "Netflix subscription 15.99 on Visa"
  cli.py subscriptions add "Vacation fund 200/month until December"
  cli.py subscriptions add -i    # Interactive guided mode (no LLM needed)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subscriptions_add_llm_parser.add_argument("description", nargs="?", help="Natural language budget/subscription description")
    subscriptions_add_llm_parser.add_argument("--interactive", "-i", action="store_true", help="Interactive guided mode (no LLM needed). End date accepts +N months shortcut")

    subscriptions_edit_parser = subscriptions_subparsers.add_parser(
        "edit",
        aliases=["e"],
        help="Modify an existing budget/subscription",
        description="Update budget parameters (amount, dates, behavior, etc.). Use -i for interactive guided mode."
    )
    subscriptions_edit_parser.add_argument("subscription_id", help="Budget/subscription ID to edit")
    subscriptions_edit_parser.add_argument("--name", "-n", help="New name")
    subscriptions_edit_parser.add_argument("--amount", "-a", type=float, help="New monthly amount")
    subscriptions_edit_parser.add_argument("--account", "-c", help="New account ID")
    subscriptions_edit_parser.add_argument("--end", "-e", help='End date (YYYY-MM-DD) or "none" to make ongoing')
    subscriptions_edit_parser.add_argument("--underspend", "-u", choices=["keep", "return"], help="Unused budget behavior: 'keep' leaves leftover in place for untracked purchases, 'return' releases it back to free balance")
    subscriptions_edit_parser.add_argument("--retroactive", "-r", action="store_true", help="Apply changes to past months (corrections only, not price changes)")
    subscriptions_edit_parser.add_argument("--interactive", "-i", action="store_true", help="Interactive guided mode")

    subscriptions_delete_parser = subscriptions_subparsers.add_parser(
        "delete",
        aliases=["del", "d"],
        help="Delete a budget/subscription",
        description="Remove a budget or subscription (must have no committed transactions)"
    )
    subscriptions_delete_parser.add_argument("subscription_id", help="Budget/subscription ID")
    subscriptions_delete_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompt")

    # ==================== VIEWING & REPORTING ====================

    # View command
    view_parser = subparsers.add_parser(
        "view",
        aliases=["v"],
        help="View transactions and cash flow forecast",
        description="""
Display transactions with running balance and month-over-month comparison.

DISPLAY FEATURES:
  - Running Balance: Cumulative balance after each transaction
  - MoM Change: Month-over-month comparison of lowest balance points
                (shown on last transaction of each month, color-coded green/red)
  - Starting Balance: Balance before the displayed period begins
  - Pending from Past: Old pending transactions shown separately at top
  - Month Sections: Visual separators between months

COLOR CODING:
  - Blue: Budget allocation transactions
  - Grey: Pending transactions (not yet committed)
  - Italic: Forecast transactions (auto-generated predictions)
  - Magenta Italic: Planning transactions (potential future expenses)
  - Default: Committed transactions

SUMMARY MODE (-s):
  - Aggregates credit card transactions into monthly payment entries
  - Shows "VisaCard Payment" instead of individual purchases
  - Cash transactions and non-credit accounts shown normally
  - Planning transactions shown individually unless -p is used

CREATED-DATE MODE (-c):
  Sort by purchase date instead of payment date.
  Hides Running Balance, MoM Change, and Starting Balance; shows Month Total instead.
  Month borders and --from/-m filter by creation month instead of payment month.
  Combine with -s to group credit card spending per creation month.

Examples:
  cli.py view                         # Default: 3 months from today
  cli.py view -m 6                    # Show 6 months
  cli.py view --from 2025-10          # Start from October 2025
  cli.py view -s                      # Summary mode (cleaner view)
  cli.py view -s -p                   # Summary with planning included
  cli.py view -c                      # Sort by purchase date with month totals
  cli.py view -c -s                   # CC grouped by creation month
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    view_parser.add_argument("--months", "-m", type=int, default=3, help="Number of months to display (default: 3)")
    view_parser.add_argument("--from", "-f", dest="start_from", type=str, help="Starting month in YYYY-MM format (default: current month)")
    view_parser.add_argument("--summary", "-s", action="store_true", help="Summary mode: aggregate credit card transactions into monthly payment entries")
    view_parser.add_argument("--include-planning", "-p", action="store_true", help="In summary mode, include planning transactions in aggregated totals (default: show separately)")
    view_parser.add_argument("--created", "-c", action="store_true", help="Sort by creation date (when you bought it, not when it's paid)")

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        aliases=["exp", "x"],
        help="Export transactions to CSV file",
        description="""
Export all transactions to CSV for external analysis.
Examples:
  cli.py export output.csv
  cli.py export output.csv -b    # Include running balance column
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    export_parser.add_argument("file_path", help="Output CSV file path")
    export_parser.add_argument("--with-balance", "-b", action="store_true", help="Include running balance column")

    # ==================== TRANSACTION EDITING ====================

    # Delete command
    delete_parser = subparsers.add_parser(
        "delete",
        aliases=["del", "d"],
        help="Delete a transaction or group",
        description="""
Delete a single transaction or an entire transaction group (installments).
Use --all to delete all related transactions (e.g., all installments in a payment plan).

Examples:
  cli.py delete 123              # Delete single transaction
  cli.py delete 123 --all        # Delete entire installment group
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    delete_parser.add_argument("transaction_id", type=int, help="Transaction ID to delete")
    delete_parser.add_argument("--all", "-a", action="store_true", help="Delete entire transaction group (all installments/splits)")

    # Edit command
    edit_parser = subparsers.add_parser(
        "edit",
        aliases=["e"],
        help="Modify transaction details",
        description="""
Edit transaction properties like status, amount, category, etc.
Use --all to apply changes to all transactions in a group (e.g., mark all installments as pending).
Use -i for interactive guided mode (shows current values, prompts each field).

INTERACTIVE AMOUNT EDITING (-i):
  Bare number (e.g. 99): keeps the original sign (expense stays expense).
  Prefix with + (e.g. +99): force positive (income/refund).
  Prefix with - (e.g. -99): force negative (expense).

Transaction statuses:
  - committed: Confirmed transaction (default)
  - pending: Awaiting confirmation (doesn't affect running balance)
  - planning: Future potential transaction (affects forecast)
  - forecast: Auto-generated future transaction

Examples:
  cli.py edit 123 --status pending
  cli.py edit 456 --status planning --all    # Change all installments
  cli.py edit 789 --category groceries --budget budget_food
  cli.py edit 123 -i                         # Interactive guided mode
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    edit_parser.add_argument("transaction_id", type=int, help="Transaction ID to edit")
    edit_parser.add_argument("--description", "-d", type=str, help="New description")
    edit_parser.add_argument("--amount", "-a", type=float, help="New amount")
    edit_parser.add_argument("--date", "-D", type=str, help="New creation date (YYYY-MM-DD)")
    edit_parser.add_argument("--category", "-c", type=str, help="New category")
    edit_parser.add_argument("--budget", "-b", type=str, help="New budget ID")
    edit_parser.add_argument("--status", "-s", type=str, choices=["committed", "pending", "planning", "forecast"], help="New status")
    edit_parser.add_argument("--source", type=str, help="Set transaction source (e.g. mom)")
    edit_parser.add_argument("--needs-review", type=int, choices=[0, 1], help="Set needs_review flag")
    edit_parser.add_argument("--all", action="store_true", help="Apply changes to all transactions in group (installments/splits)")
    edit_parser.add_argument("--interactive", "-i", action="store_true", help="Interactive guided mode")

    # Clear command
    clear_parser = subparsers.add_parser(
        "clear",
        aliases=["cl"],
        help="Commit a pending/planning transaction",
        description="""
Change transaction status from 'pending' or 'planning' to 'committed'.
Use --all to clear all transactions in a group (e.g., all installments).

Examples:
  cli.py clear 123               # Commit a single pending transaction
  cli.py clear 123 --all         # Commit all transactions in the group
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    clear_parser.add_argument("transaction_id", type=int, help="Transaction ID to commit")
    clear_parser.add_argument("--all", action="store_true", help="Clear all transactions in the group (e.g., all installments)")

    # ==================== REVIEW ====================

    review_parser = subparsers.add_parser(
        "review",
        aliases=["rv"],
        help="Review transactions from extra users",
        description="""
Review transactions created by extra users (e.g. family members).

Commands:
  cli.py review ls                            # list all unreviewed
  cli.py review ls --source mom               # filter by source
  cli.py review 605                           # show transaction, mark reviewed
  cli.py review 605 --budget "personal food"  # edit fields + mark reviewed
  cli.py review 605 -i                        # interactive edit + mark reviewed
  cli.py review 605 clear                     # mark reviewed without showing
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    review_parser.add_argument("action", nargs="?", default="ls", help="'ls' to list, or transaction ID")
    review_parser.add_argument("sub_action", nargs="?", default=None, help="'clear' to mark reviewed without editing")
    review_parser.add_argument("--description", "-d", type=str, help="New description")
    review_parser.add_argument("--amount", "-a", type=float, help="New amount")
    review_parser.add_argument("--date", "-D", type=str, help="New date (YYYY-MM-DD)")
    review_parser.add_argument("--category", "-c", type=str, help="New category")
    review_parser.add_argument("--budget", "-b", type=str, help="New budget ID")
    review_parser.add_argument("--status", "-s", type=str, choices=["committed", "pending", "planning", "forecast"], help="New status")
    review_parser.add_argument("--source", type=str, help="Filter by source (for ls)")
    review_parser.add_argument("--interactive", "-i", action="store_true", help="Interactive edit mode")

    # ==================== RECONCILIATION ====================

    # Fix command
    fix_parser = subparsers.add_parser(
        "fix",
        aliases=["f"],
        help="Reconcile balances and statements",
        description="""
Reconcile account balances or credit card statements.

Balance Fix:
  Adjust total cash balance to match actual amount (adds correction transaction).
  Example: cli.py fix --balance 1500.00

Statement Fix:
  Reconcile credit card statement against tracked transactions.
  Interactive mode (-i) shows all transactions and asks for statement amount.
  Non-interactive mode creates adjustment transaction automatically.

  Smart Month Detection:
    - If month omitted, auto-detects based on cut-off day
    - Before cut-off: reconciles current month
    - After cut-off: reconciles next month
    - Cash accounts: always use current month

  Examples:
    cli.py fix --payment VisaCard -i              # Interactive (auto-detects month)
    cli.py fix --payment VisaCard 450.50         # Amount only (auto-detects month)
    cli.py fix --payment VisaCard 2026-01 450.50 # Explicit month and amount
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    fix_group = fix_parser.add_mutually_exclusive_group(required=True)

    # Balance fix flag
    fix_group.add_argument("--balance", "-b", type=float, metavar="AMOUNT",
                          help="Fix total balance to this amount (creates adjustment transaction)")

    # Payment fix flag
    fix_group.add_argument("--payment", "-p", metavar="ACCOUNT",
                          help="Reconcile credit card statement for this account")

    # Arguments for payment fix
    fix_parser.add_argument("month", nargs="?", help="Month for statement (YYYY-MM). Auto-detected if omitted.")
    fix_parser.add_argument("amount", nargs="?", type=float, help="Statement amount (required unless using -i)")

    # Options
    fix_parser.add_argument("--account", "-a", default="Cash",
                           help="Account for balance fix (default: Cash)")
    fix_parser.add_argument("--interactive", "-i", action="store_true",
                           help="Interactive mode: show transactions and prompt for statement amount")

    # ==================== BACKUP ====================

    backup_parser = subparsers.add_parser(
        "backup",
        aliases=["bk"],
        help="Manage database backups",
        description="""
Manage database backups. Creates timestamped copies using SQLite's backup API.

Usage:
  backup                     Create an unnamed manual backup
  backup "pre-migration"     Create a named manual backup
  backup list                List all backups (with type column)
  backup restore <file>      Restore from a backup file

Manual backups are never auto-deleted by the retention policy.

Configuration via environment variables (or .env):
  BACKUP_ENABLED            Enable auto-backup (default: true)
  BACKUP_DIR                Backup directory (default: backups)
  BACKUP_KEEP_TODAY         Keep last N backups for today (default: 5)
  BACKUP_RECENT_DAYS        Days to keep one-per-day (default: 7)
  BACKUP_MAX_DAYS           Delete backups older than this (default: 30)
  BACKUP_LOG_RETENTION_DAYS Days to keep backup log entries (default: 30)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    backup_parser.add_argument("backup_args", nargs="*", default=[], metavar="ACTION",
        help='list (ls/l) | restore (r) FILE | "name" for named backup')

    args = parser.parse_args()

    # --- Auto-backup before mutating commands ---
    read_only_commands = {"view", "v", "export", "exp", "x", "backup", "bk"}
    read_only_subcommands = {"list", "ls", "l"}
    is_read_only = args.command in read_only_commands
    if args.command in ["accounts", "acc", "a", "categories", "cat", "c", "subscriptions", "sub", "s"]:
        if hasattr(args, "subcommand") and args.subcommand in read_only_subcommands:
            is_read_only = True
    if args.command in ["review", "rv"]:
        action = getattr(args, "action", "ls")
        if action == "ls" or action is None:
            is_read_only = True

    backup_path = None
    if BACKUP_ENABLED and not is_read_only:
        backup_path = db_backup.create_backup(db_path, BACKUP_DIR)
        db_backup.apply_retention(BACKUP_DIR, BACKUP_KEEP_TODAY, BACKUP_RECENT_DAYS, BACKUP_MAX_DAYS)
        db_backup.apply_log_retention(BACKUP_DIR, BACKUP_LOG_RETENTION_DAYS)

    # --- Command Handling ---
    if args.command in ["backup", "bk"]:
        handle_backup(db_path, args)
    elif args.command == "add":
        handle_add(conn, args)
    elif args.command in ["create", "cr"]:
        if args.create_entity in ["transaction", "tx", "t"]:
            handle_create_transaction(conn, args)
        elif args.create_entity in ["account", "acc", "a"]:
            handle_accounts_add_manual(conn, args)
        elif args.create_entity in ["budget", "bud", "b"]:
            handle_subscriptions_add_manual(conn, args)
        elif args.create_entity in ["category", "cat", "c"]:
            handle_categories_add(conn, args)
    elif args.command in ["accounts", "acc", "a"]:
        if args.subcommand in ["list", "ls", "l"]:
            handle_accounts_list(conn)
        elif args.subcommand in ["add", "a", "an"]:
            if getattr(args, 'interactive', False):
                handle_accounts_add_interactive(conn)
            else:
                if not args.description:
                    print("Error: description required (or use -i for interactive mode)")
                    conn.close()
                    return
                handle_accounts_add_natural(conn, args)
        elif args.subcommand in ["adjust-billing", "ab"]:
            handle_accounts_adjust_billing(conn, args)
    elif args.command in ["categories", "cat", "c"]:
        if args.subcommand in ["list", "ls", "l"]:
            handle_categories_list(conn)
        elif args.subcommand in ["add", "a"]:
            if getattr(args, 'interactive', False):
                handle_categories_add_interactive(conn)
            else:
                if not args.name or not args.description:
                    print("Error: name and description required (or use -i for interactive mode)")
                    conn.close()
                    return
                handle_categories_add(conn, args)
        elif args.subcommand in ["edit", "e"]:
            handle_categories_edit(conn, args)
        elif args.subcommand in ["delete", "del", "d"]:
            handle_categories_delete(conn, args)
    elif args.command in ["subscriptions", "sub", "s"]:
        if args.subcommand in ["list", "ls", "l"]:
            handle_subscriptions_list(conn, args)
        elif args.subcommand in ["add", "a"]:
            if getattr(args, 'interactive', False):
                handle_subscriptions_add_interactive(conn)
            else:
                if not args.description:
                    print("Error: description required (or use -i for interactive mode)")
                    conn.close()
                    return
                handle_subscriptions_add_llm(conn, args)
        elif args.subcommand in ["edit", "e"]:
            if getattr(args, 'interactive', False):
                handle_subscriptions_edit_interactive(conn, args)
            else:
                handle_subscriptions_edit(conn, args)
        elif args.subcommand in ["delete", "del", "d"]:
            handle_subscriptions_delete(conn, args)
    elif args.command in ["view", "v"]:
        interface.view_transactions(conn, args.months, args.summary, args.include_planning, args.start_from, "date_created" if args.created else "date_payed")
    elif args.command in ["export", "exp", "x"]:
        interface.export_transactions_to_csv(conn, args.file_path, args.with_balance)
    elif args.command in ["delete", "del", "d"]:
        handle_delete(conn, args)
    elif args.command in ["edit", "e"]:
        if getattr(args, 'interactive', False):
            handle_edit_interactive(conn, args)
        else:
            handle_edit(conn, args)
    elif args.command in ["clear", "cl"]:
        handle_clear(conn, args)
    elif args.command in ["review", "rv"]:
        handle_review(conn, args)
    elif args.command in ["fix", "f"]:
        handle_fix(conn, args)

    # Write backup log after handler (so _backup_context is available)
    if backup_path and not getattr(args, '_backup_skip', False):
        operation = describe_operation(args)
        db_backup.write_backup_log(BACKUP_DIR, backup_path.name, operation)

    conn.close()

if __name__ == "__main__":
    main()

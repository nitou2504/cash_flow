
# Suppress Google AI SDK warnings before importing anything
import os
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

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
    import transactions as tx_module

    accounts = repository.get_all_accounts(conn)
    if not accounts:
        print("Error: No accounts found. Please add an account first using 'accounts add'.")
        return

    budgets = repository.get_all_budgets(conn)

    print("Parsing your request with the LLM...")

    # Phase 1: Pre-parse to get date and account for payment calculation
    pre_parsed = llm_parser.pre_parse_date_and_account(args.description, accounts)

    # Calculate payment date for budget context
    payment_month = None
    if pre_parsed:
        try:
            trans_date = date.fromisoformat(pre_parsed.get('date', date.today().isoformat()))
            account_name = pre_parsed.get('account')
            account = next((a for a in accounts if a['account_id'] == account_name), None)
            if account:
                payment_date = tx_module.simulate_payment_date(account, trans_date)
                payment_month = payment_date.replace(day=1)
        except (ValueError, KeyError):
            pass  # Fall back to no payment context

    # Phase 2: Full parse with payment context
    request_json = llm_parser.parse_transaction_string(conn, args.description, accounts, budgets, payment_month)

    if request_json:
        console = Console()

        # Display as a transaction preview table instead of JSON
        transaction_date = date.fromisoformat(request_json.get("date_created", date.today().isoformat()))
        account_name = request_json.get('account', 'Unknown')
        account = next((a for a in accounts if a['account_id'] == account_name), None)

        # Calculate actual payment date for display
        if account:
            payment_date = tx_module.simulate_payment_date(account, transaction_date)
        else:
            payment_date = transaction_date

        # Create preview table
        table = Table(title="Transaction Preview", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="dim")
        table.add_column("Value")

        # Display based on transaction type
        tx_type = request_json.get('type', 'simple')

        if tx_type == 'simple':
            amount = request_json.get('amount', 0)
            table.add_row("Date Created", str(transaction_date))
            table.add_row("Date Payed", str(payment_date))
            table.add_row("Description", request_json.get('description', ''))
            table.add_row("Account", account_name)
            table.add_row("Amount", f"-{abs(amount):.2f}" if not request_json.get('is_income') else f"+{abs(amount):.2f}")
            table.add_row("Category", request_json.get('category', '') or '')
            table.add_row("Budget", request_json.get('budget', '') or '')
            if request_json.get('is_pending'):
                table.add_row("Status", "pending")
            elif request_json.get('is_planning'):
                table.add_row("Status", "planning")

        elif tx_type == 'installment':
            total = request_json.get('total_amount', 0)
            installments = request_json.get('installments', 1)
            per_installment = total / installments if installments else total
            table.add_row("Type", "Installment")
            table.add_row("Date Created", str(transaction_date))
            table.add_row("First Payment", str(payment_date))
            table.add_row("Description", request_json.get('description', ''))
            table.add_row("Account", account_name)
            table.add_row("Total Amount", f"-{abs(total):.2f}")
            table.add_row("Installments", f"{installments}x of {per_installment:.2f}")
            table.add_row("Category", request_json.get('category', '') or '')
            table.add_row("Budget", request_json.get('budget', '') or '')

        elif tx_type == 'split':
            table.add_row("Type", "Split Transaction")
            table.add_row("Date Created", str(transaction_date))
            table.add_row("Date Payed", str(payment_date))
            table.add_row("Description", request_json.get('description', ''))
            table.add_row("Account", account_name)
            for i, split in enumerate(request_json.get('splits', []), 1):
                table.add_row(f"Split {i}", f"-{abs(split.get('amount', 0)):.2f} | {split.get('category', '')} | {split.get('budget', '') or ''}")

        console.print(table)

        confirm = input("\nProceed with this request? [Y/n] ")
        if confirm.lower() == 'y' or confirm == '':
            # LLM now returns budget IDs directly, no conversion needed
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
        # Handle group clears (all installments)
        if args.all:
            group_info = controller._get_transaction_group_info(conn, transaction_id)
            siblings = group_info.get("siblings", [])

            if len(siblings) <= 1:
                print(f"Transaction {transaction_id} is not part of a group. Clearing single transaction.")
                controller.process_transaction_clearance(conn, transaction_id)
                print(f"Successfully cleared transaction {transaction_id}.")
            else:
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
                    print("Operation cancelled.")
                    return

                # Clear all siblings
                for sibling in siblings:
                    controller.process_transaction_clearance(conn, sibling['id'])

                print(f"Successfully cleared {len(siblings)} transactions in group.")
        else:
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

    try:
        # Get account and determine payment date
        account = repository.get_account_by_name(conn, account_id)
        if not account:
            print(f"Error: Account '{account_id}' not found")
            return

        if account['account_type'] == 'credit_card':
            payment_date = date(month.year, month.month, account['payment_day'])
        else:
            # Cash account: use last day of month
            next_month = month + relativedelta(months=1)
            payment_date = next_month.replace(day=1) - relativedelta(days=1)

        # Get transactions on payment date
        all_trans = repository.get_all_transactions(conn)
        payment_trans = [
            t for t in all_trans
            if t['account'] == account_id
            and t['date_payed'] == payment_date
            and t['status'] in ['committed', 'forecast']
        ]

        current_total = sum(t['amount'] for t in payment_trans)

        # Display header
        print(f"\nStatement Adjustment for {account_id} - {month.strftime('%B %Y')}")
        print(f"Payment date: {payment_date}\n")

        # Show table with transactions
        if payment_trans:
            table = Table(title=f"Transactions on {payment_date}")
            table.add_column("ID", style="cyan", width=6)
            table.add_column("Date", style="dim", width=12)
            table.add_column("Description")
            table.add_column("Amount", justify="right", width=10)

            for t in payment_trans:
                table.add_row(
                    str(t['id']),
                    str(t['date_created']),
                    t['description'],
                    f"{t['amount']:.2f}"
                )

            table.add_row("", "", "CURRENT TOTAL", f"{current_total:.2f}", style="bold")

            console = Console()
            console.print(table)
        else:
            print(f"⚠ No transactions found on {payment_date}")
            print(f"Current total: $0.00")

        print()

        # Ask for statement amount
        try:
            statement_amount = float(input("Enter actual statement amount: "))
        except (ValueError, EOFError):
            print("Operation cancelled")
            return

        # Calculate difference
        difference = statement_amount - current_total

        if abs(difference) < 0.01:
            print("\n✓ No adjustment needed - statement matches current total!")
            return

        # Show adjustment summary
        adjustment_amount = -difference
        adj_sign = "+" if adjustment_amount >= 0 else "-"
        diff_sign = "+" if difference >= 0 else "-"
        print(f"\nAdjustment: ${current_total:.2f} → ${statement_amount:.2f} (difference: {diff_sign}${abs(difference):.2f})")

        # Confirm
        confirm = input("Proceed? [Y/n]: ")
        if confirm.lower() not in ['y', '']:
            print("Operation cancelled")
            return

        # Process
        result = controller.process_statement_adjustment(
            conn, account_id, month, statement_amount
        )

        if result:
            print(f"\n✓ Payment adjusted for {account_id} ({payment_date})")
            print(f"  Transaction created: Payment Adjustment - {account_id} ({adj_sign}${abs(adjustment_amount):.2f})")

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
    parser = argparse.ArgumentParser(
        prog="cash_flow",
        description="""
Personal Cash Flow Management System
=====================================
Track expenses, manage budgets, handle credit card payments, and forecast cash flow.
Supports multiple accounts (cash and credit cards), installment tracking, and natural language input.
        """,
        epilog="""
COMMON WORKFLOWS:
  First-time setup:
    1. cash_flow accounts add "Cash account"
    2. cash_flow accounts add "Credit card with cut-off on 25th and payment on 5th"
    3. cash_flow categories add groceries "Food and household items"

  Daily usage:
    cash_flow add "Spent 45.50 on groceries at Supermarket today"
    cash_flow view                    # See upcoming transactions
    cash_flow view -s                 # Summary view (aggregated credit card payments)

  Managing budgets:
    cash_flow subscriptions add "Monthly groceries budget of 300 on Cash"
    cash_flow subscriptions list

  Reconciliation:
    cash_flow fix --payment MyCard -i              # Interactive statement reconciliation
    cash_flow fix --balance 1500.00 --account Cash # Fix total balance

  Transaction management:
    cash_flow edit 123 --status pending            # Change one transaction
    cash_flow edit 123 --status pending --all      # Change all installments
    cash_flow delete 456 --all                     # Delete entire installment group

ALIASES:
  Most commands have short aliases (shown in brackets below):
  - accounts [acc, a]    - subscriptions [sub, s]    - view [v]
  - categories [cat, c]  - export [exp, x]           - edit [e]
  - delete [del, d]      - clear [cl]                - fix [f]

For detailed help on any command: cash_flow COMMAND -h
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
        help="Add a transaction using natural language",
        description="""
Add a transaction using natural language description.
Examples:
  cash_flow add "Spent 45.50 on groceries at Walmart today"
  cash_flow add "Bought TV for 600 in 12 installments on Visa card"
  cash_flow add "Split purchase: 30 on groceries, 15 on snacks"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_parser.add_argument("description", help="Natural language transaction description")

    # Add batch command
    add_batch_parser = subparsers.add_parser(
        "add-batch",
        aliases=["ab"],
        help="Import multiple transactions from CSV",
        description="Import transactions from a CSV file (format: date,description,account,amount)"
    )
    add_batch_parser.add_argument("file_path", help="Path to the CSV file")

    # Add installments command
    add_installments_parser = subparsers.add_parser(
        "add-installments",
        aliases=["ai"],
        help="Import installment transactions from CSV",
        description="Import pre-existing installments from CSV (format: date,description,account,amount,current_installment,total_installments)"
    )
    add_installments_parser.add_argument("file_path", help="Path to the CSV file")

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

    acc_add_manual_parser = acc_subparsers.add_parser(
        "add-manual",
        aliases=["am"],
        help="Add account manually with specific parameters",
        description="Add a new account with explicit parameters (use 'add-natural' for easier setup)"
    )
    acc_add_manual_parser.add_argument("id", help="Unique account ID/name (e.g., 'Cash', 'VisaCard')")
    acc_add_manual_parser.add_argument("type", choices=["cash", "credit_card"], help="Account type")
    acc_add_manual_parser.add_argument("--cut-off-day", "-c", type=int, help="Statement cut-off day (1-31, required for credit cards)")
    acc_add_manual_parser.add_argument("--payment-day", "-p", type=int, help="Payment due day (1-31, required for credit cards)")

    acc_add_natural_parser = acc_subparsers.add_parser(
        "add-natural",
        aliases=["an"],
        help="Add account using natural language (recommended)",
        description="""
Add a new account using natural language.
Examples:
  cash_flow accounts add "Cash account"
  cash_flow accounts add "Visa card with cut-off on 25 and payment on 5"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    acc_add_natural_parser.add_argument("description", help="Natural language account description")

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
        description="Add a new expense category (e.g., 'groceries', 'utilities', 'entertainment')"
    )
    cat_add_parser.add_argument("name", help="Category name (lowercase, no spaces)")
    cat_add_parser.add_argument("description", help="What this category covers")

    cat_edit_parser = cat_subparsers.add_parser(
        "edit",
        aliases=["e"],
        help="Update category description"
    )
    cat_edit_parser.add_argument("name", help="Category name to edit")
    cat_edit_parser.add_argument("description", help="New description")

    cat_delete_parser = cat_subparsers.add_parser(
        "delete",
        aliases=["del", "d"],
        help="Remove a category",
        description="Delete a category (will fail if transactions are using it)"
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

    subscriptions_add_parser = subscriptions_subparsers.add_parser(
        "add-manual",
        aliases=["am"],
        help="Add budget/subscription with specific parameters",
        description="Manually configure a budget or subscription with all parameters"
    )
    subscriptions_add_parser.add_argument("name", help="Budget name (e.g., 'Groceries', 'Netflix')")
    subscriptions_add_parser.add_argument("amount", type=float, help="Monthly amount in dollars")
    subscriptions_add_parser.add_argument("account", help="Account ID to charge")
    subscriptions_add_parser.add_argument("category", help="Category name")
    subscriptions_add_parser.add_argument("--start", "-s", type=str, help="Start date YYYY-MM-DD (default: today)")
    subscriptions_add_parser.add_argument("--end", "-e", type=str, help="End date YYYY-MM-DD (omit for ongoing)")
    subscriptions_add_parser.add_argument("--underspend", "-u", choices=["keep", "return"], help="Unused budget behavior: 'keep' (rollover) or 'return' (default: keep)")

    subscriptions_add_llm_parser = subscriptions_subparsers.add_parser(
        "add",
        aliases=["a"],
        help="Add budget/subscription using natural language (recommended)",
        description="""
Add a budget or subscription using natural language.
Examples:
  cash_flow subscriptions add "Monthly groceries budget of 300 on Cash"
  cash_flow subscriptions add "Netflix subscription 15.99 on Visa"
  cash_flow subscriptions add "Vacation fund 200/month until December"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subscriptions_add_llm_parser.add_argument("description", help="Natural language budget/subscription description")

    subscriptions_edit_parser = subscriptions_subparsers.add_parser(
        "edit",
        aliases=["e"],
        help="Modify an existing budget/subscription",
        description="Update budget parameters (amount, dates, behavior, etc.)"
    )
    subscriptions_edit_parser.add_argument("subscription_id", help="Budget/subscription ID to edit")
    subscriptions_edit_parser.add_argument("--name", "-n", help="New name")
    subscriptions_edit_parser.add_argument("--amount", "-a", type=float, help="New monthly amount")
    subscriptions_edit_parser.add_argument("--account", "-c", help="New account ID")
    subscriptions_edit_parser.add_argument("--end", "-e", help='End date (YYYY-MM-DD) or "none" to make ongoing')
    subscriptions_edit_parser.add_argument("--underspend", "-u", choices=["keep", "rollover"], help="Unused budget handling")
    subscriptions_edit_parser.add_argument("--retroactive", "-r", action="store_true", help="Apply changes to past months (corrections only, not price changes)")

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

SORTING:
  --sort date_payed: Show transactions by payment date (default)
                     Good for: seeing when money actually leaves your account
  --sort date_created: Show transactions by purchase/creation date
                       Good for: tracking when expenses actually happened

Examples:
  cash_flow view                         # Default: 3 months from today
  cash_flow view -m 6                    # Show 6 months
  cash_flow view --from 2025-10          # Start from October 2025
  cash_flow view -s                      # Summary mode (cleaner view)
  cash_flow view -s -p                   # Summary with planning included
  cash_flow view --sort date_created     # Sort by purchase date
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    view_parser.add_argument("--months", "-m", type=int, default=3, help="Number of months to display (default: 3)")
    view_parser.add_argument("--from", "-f", dest="start_from", type=str, help="Starting month in YYYY-MM format (default: current month)")
    view_parser.add_argument("--summary", "-s", action="store_true", help="Summary mode: aggregate credit card transactions into monthly payment entries")
    view_parser.add_argument("--include-planning", "-p", action="store_true", help="In summary mode, include planning transactions in aggregated totals (default: show separately)")
    view_parser.add_argument("--sort", choices=["date_payed", "date_created"], default="date_payed", help="Sort transactions by payment date (default) or creation date")

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        aliases=["exp", "x"],
        help="Export transactions to CSV file",
        description="Export all transactions to CSV format for external analysis"
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

Transaction statuses:
  - committed: Confirmed transaction (default)
  - pending: Awaiting confirmation (doesn't affect running balance)
  - planning: Future potential transaction (affects forecast)
  - forecast: Auto-generated future transaction

Examples:
  cash_flow edit 123 --status pending
  cash_flow edit 456 --status planning --all    # Change all installments
  cash_flow edit 789 --category groceries --budget budget_food
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
    edit_parser.add_argument("--all", action="store_true", help="Apply changes to all transactions in group (installments/splits)")

    # Clear command
    clear_parser = subparsers.add_parser(
        "clear",
        aliases=["cl"],
        help="Commit a pending/planning transaction",
        description="""
Change transaction status from 'pending' or 'planning' to 'committed'.
Use --all to clear all transactions in a group (e.g., all installments).
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    clear_parser.add_argument("transaction_id", type=int, help="Transaction ID to commit")
    clear_parser.add_argument("--all", action="store_true", help="Clear all transactions in the group (e.g., all installments)")

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
  Example: cash_flow fix --balance 1500.00

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
    cash_flow fix --payment VisaCard -i              # Interactive (auto-detects month)
    cash_flow fix --payment VisaCard 450.50         # Amount only (auto-detects month)
    cash_flow fix --payment VisaCard 2026-01 450.50 # Explicit month and amount
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
        elif args.subcommand in ["adjust-billing", "ab"]:
            handle_accounts_adjust_billing(conn, args)
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
        interface.view_transactions(conn, args.months, args.summary, args.include_planning, args.start_from, args.sort)
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

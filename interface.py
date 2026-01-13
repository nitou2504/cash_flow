import sqlite3
import csv
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from rich.console import Console
from rich.table import Table

import repository

def view_transactions(conn: sqlite3.Connection, months: int, summary: bool = False, include_planning: bool = False, start_from: str = None):
    """
    Retrieves and displays transactions, with an optional summary mode for credit cards.
    """
    all_transactions = repository.get_transactions_with_running_balance(conn)

    # Calculate monthly minimum balances from original transactions (before summarization)
    # This ensures consistency across all view modes
    monthly_minimums = {}
    for t in all_transactions:
        month_key = t['date_payed'].strftime('%Y-%m')
        if month_key not in monthly_minimums:
            monthly_minimums[month_key] = t['running_balance']
        else:
            monthly_minimums[month_key] = min(monthly_minimums[month_key], t['running_balance'])

    display_transactions = []
    if not summary:
        display_transactions = all_transactions
    else:
        # --- Summarization Logic ---
        accounts = repository.get_all_accounts(conn)
        credit_card_accounts = {acc['account_id'] for acc in accounts if acc['account_type'] == 'credit_card'}

        # Build a map of (account, date) -> running_balance from all_transactions
        # This will be used to get the correct running balance for summary transactions
        date_balance_map = {}
        for t in all_transactions:
            key = (t['account'], t['date_payed'])
            # Store the running balance of the last transaction for this account/date
            date_balance_map[key] = t['running_balance']

        summarized_payments = {}  # Key: (account, date_payed), Value: {'amount': float, 'statuses': set}
        other_transactions = []
        planning_transactions = []

        for t in all_transactions:
            if t['account'] in credit_card_accounts:
                # If not including planning in summary, separate them to be displayed individually
                if not include_planning and t['status'] == 'planning':
                    planning_transactions.append(t)
                    continue

                key = (t['account'], t['date_payed'])
                if key not in summarized_payments:
                    summarized_payments[key] = {'amount': 0.0, 'statuses': set(), 'running_balance': 0.0}

                summarized_payments[key]['amount'] += t['amount']
                summarized_payments[key]['statuses'].add(t['status'])
                # Store the running balance from the last transaction with this date
                summarized_payments[key]['running_balance'] = t['running_balance']
            else:
                other_transactions.append(t)

        summary_transactions = []
        for (account, date_payed), data in summarized_payments.items():
            statuses = data['statuses']
            status = 'forecast'
            if 'committed' in statuses: status = 'committed'
            elif 'pending' in statuses: status = 'pending'
            elif 'planning' in statuses: status = 'planning'

            summary_trans = {
                'id': '--', 'date_payed': date_payed, 'date_created': date_payed,
                'description': f"{account} Payment", 'account': account,
                'amount': data['amount'], 'category': 'Credit Card', 'budget': '',
                'status': status, 'origin_id': None,
                'running_balance': data['running_balance']  # Use the actual running balance
            }
            summary_transactions.append(summary_trans)

        # Combine and sort all transactions
        combined = sorted(other_transactions + summary_transactions + planning_transactions, key=lambda x: (x['date_payed'], x.get('id', 0) if x.get('id') != '--' else 999999))

        # Don't recalculate running balance - use the ones from original transactions
        for t in combined:
            display_transactions.append(t)
        # --- End Summarization ---

    # --- Date Filtering ---
    today = date.today()
    start_date = today.replace(day=1)

    if start_from:
        try:
            # Parse YYYY-MM and ensure it's the first of the month
            start_date = datetime.strptime(start_from, '%Y-%m').date().replace(day=1)
        except ValueError:
            # Using Console for rich printing
            console = Console()
            console.print(f"[red]Error: Invalid date format for --from. Please use YYYY-MM. Defaulting to current month.[/red]")
            # Keep default start_date which is already set

    end_date = (start_date + relativedelta(months=months)) - relativedelta(days=1)

    pending_from_past = [
        t for t in display_transactions
        if t['status'] == 'pending' and t['date_payed'] < start_date
    ]
    
    transactions_in_period = [
        t for t in display_transactions
        if start_date <= t['date_payed'] <= end_date
    ]
    
    try:
        last_transaction_before_period = next(
            t for t in reversed(display_transactions) if t['date_payed'] < start_date
        )
        starting_balance = last_transaction_before_period['running_balance']
    except StopIteration:
        starting_balance = 0.0

    table = Table(
        title=f"Cash Flow: {today.strftime('%B %Y')} - {end_date.strftime('%B %Y')}",
        show_header=True, header_style="bold magenta"
    )
    table.add_column("ID", style="dim")
    table.add_column("Date Payed")
    table.add_column("Date Created", style="dim")
    table.add_column("Description")
    table.add_column("Account")
    table.add_column("Amount", justify="right")
    table.add_column("Category")
    table.add_column("Budget")
    table.add_column("Status")
    table.add_column("Running Balance", justify="right")
    table.add_column("MoM Change", justify="right")

    if pending_from_past:
        table.add_row(
            "", "", "", "[bold yellow]Pending from Previous Months[/bold yellow]",
            "", "", "", "", "", "", ""
        )
        for t in pending_from_past:
            table.add_row(
                str(t['id']), str(t['date_payed']), str(t['date_created']),
                t['description'], t['account'], f"{t['amount']:.2f}",
                t['category'], t.get('budget', '') or '', t['status'],
                f"{t['running_balance']:.2f}", "", style="grey50"
            )
        table.add_section()

    table.add_row(
        "", "", "", "Starting Balance", "", "", "", "", "",
        f"[bold green]{starting_balance:.2f}[/]", ""
    )
    table.add_section()

    budgets = repository.get_all_budgets(conn)
    budget_ids = {b['id'] for b in budgets}

    # Get sorted list of months in period for MoM calculation
    sorted_months = sorted(monthly_minimums.keys())

    last_month = None
    for i, t in enumerate(transactions_in_period):
        current_month = t['date_payed'].strftime('%Y-%m')

        # Check if this is the last transaction of the month or last transaction overall
        is_last_in_month = (i == len(transactions_in_period) - 1) or \
                          (transactions_in_period[i + 1]['date_payed'].strftime('%Y-%m') != current_month)

        if last_month and current_month != last_month:
            table.add_section()

        is_budget_allocation = t.get('origin_id') in budget_ids and t.get('budget') == t.get('origin_id')
        status = t['status']
        row_style = "" # Default style for committed transactions

        if is_budget_allocation:
            row_style = "blue"
        elif status == 'pending':
            row_style = "grey50"
        elif status == 'forecast':
            row_style = "italic"
        elif status == 'planning':
            row_style = "italic magenta"

        # Calculate MoM change for last transaction in month
        mom_change_str = ""
        if is_last_in_month:
            current_min = monthly_minimums.get(current_month, t['running_balance'])
            month_idx = sorted_months.index(current_month) if current_month in sorted_months else -1

            if month_idx > 0:
                prev_month = sorted_months[month_idx - 1]
                prev_min = monthly_minimums.get(prev_month, 0.0)
                mom_change = current_min - prev_min

                if mom_change > 0:
                    mom_change_str = f"[green]+{mom_change:.2f}[/green]"
                elif mom_change < 0:
                    mom_change_str = f"[red]{mom_change:.2f}[/red]"
                else:
                    mom_change_str = "0.00"

        table.add_row(
            str(t['id']), str(t['date_payed']), str(t['date_created']),
            t['description'], t['account'], f"{t['amount']:.2f}",
            t['category'], t.get('budget', '') or '', t['status'],
            f"{t['running_balance']:.2f}", mom_change_str, style=row_style
        )
        last_month = current_month

    console = Console()
    console.print(table)

def export_transactions_to_csv(conn: sqlite3.Connection, file_path: str, include_balance: bool = False):
    """
    Exports all transactions to a CSV file.
    """
    transactions = repository.get_transactions_with_running_balance(conn)
    
    # Define the full set of headers
    headers = [
        "id", "date_created", "date_payed", "description", "account",
        "amount", "category", "budget", "status", "origin_id"
    ]
    if include_balance:
        headers.append("running_balance")

    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        for t in transactions:
            # Create a dictionary for the current row to handle missing keys gracefully
            row_dict = dict(t)
            row_data = [row_dict.get(h) for h in headers]
            writer.writerow(row_data)
    
    print(f"Successfully exported {len(transactions)} transactions to {file_path}")

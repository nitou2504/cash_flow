import sqlite3
import csv
from datetime import date
from dateutil.relativedelta import relativedelta
from rich.console import Console
from rich.table import Table

import repository

def view_transactions(conn: sqlite3.Connection, months: int, summary: bool = False):
    """
    Retrieves and displays transactions, with an optional summary mode for credit cards.
    """
    all_transactions = repository.get_transactions_with_running_balance(conn)
    
    display_transactions = []
    if not summary:
        display_transactions = all_transactions
    else:
        # --- Summarization Logic ---
        accounts = repository.get_all_accounts(conn)
        credit_card_accounts = {acc['account_id'] for acc in accounts if acc['account_type'] == 'credit_card'}

        summarized_payments = {}  # Key: (account, date_payed), Value: {'amount': float, 'statuses': set}
        other_transactions = []

        for t in all_transactions:
            if t['account'] in credit_card_accounts:
                key = (t['account'], t['date_payed'])
                if key not in summarized_payments:
                    summarized_payments[key] = {'amount': 0.0, 'statuses': set()}
                
                summarized_payments[key]['amount'] += t['amount']
                summarized_payments[key]['statuses'].add(t['status'])
            else:
                other_transactions.append(t)
        
        summary_transactions = []
        for (account, date_payed), data in summarized_payments.items():
            statuses = data['statuses']
            status = 'forecast'
            if 'committed' in statuses: status = 'committed'
            elif 'pending' in statuses: status = 'pending'

            summary_trans = {
                'id': '--', 'date_payed': date_payed, 'date_created': date_payed,
                'description': f"{account} Payment", 'account': account,
                'amount': data['amount'], 'category': 'Credit Card', 'budget': '',
                'status': status, 'origin_id': None
            }
            summary_transactions.append(summary_trans)
            
        combined = sorted(other_transactions + summary_transactions, key=lambda x: x['date_payed'])
        
        running_balance = 0.0
        for t in combined:
            if t["status"] != "pending":
                running_balance += t["amount"]
            t["running_balance"] = running_balance
            display_transactions.append(t)
        # --- End Summarization ---

    # --- Date Filtering ---
    today = date.today()
    start_date = today.replace(day=1)
    end_date = (start_date + relativedelta(months=months)) - relativedelta(days=1)
    
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
    table.add_column("Date Payed", style="cyan")
    table.add_column("Date Created", style="dim")
    table.add_column("Description", style="bold")
    table.add_column("Account")
    table.add_column("Amount", justify="right")
    table.add_column("Category")
    table.add_column("Budget")
    table.add_column("Status")
    table.add_column("Running Balance", justify="right")

    table.add_row(
        "", "", "", "Starting Balance", "", "", "", "", "",
        f"[bold green]{starting_balance:.2f}[/]"
    )
    table.add_section()

    last_month = None
    for t in transactions_in_period:
        current_month = t['date_payed'].strftime('%Y-%m')
        if last_month and current_month != last_month:
            table.add_section()
        
        status = t['status']
        row_style, amount_style, balance_style = "", "yellow", "green"

        if status == 'pending':
            row_style, amount_style, balance_style = "dim", "grey50", "grey50"
        elif status == 'forecast':
            row_style, amount_style, balance_style = "italic", "cyan", "bright_blue"

        table.add_row(
            str(t['id']), str(t['date_payed']), str(t['date_created']),
            t['description'], t['account'], f"[{amount_style}]{t['amount']:.2f}[/]",
            t['category'], t.get('budget', '') or '', t['status'],
            f"[{balance_style}]{t['running_balance']:.2f}[/]", style=row_style
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

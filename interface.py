import sqlite3
import csv
from datetime import date
from dateutil.relativedelta import relativedelta
from rich.console import Console
from rich.table import Table

import repository

def view_transactions(conn: sqlite3.Connection, months: int):
    """
    Retrieves and displays transactions for a given number of upcoming months.
    """
    all_transactions = repository.get_transactions_with_running_balance(conn)

    # --- Date Filtering ---
    today = date.today()
    # We want to show from the beginning of the current month
    start_date = today.replace(day=1)
    # And for the number of months specified
    end_date = (start_date + relativedelta(months=months)) - relativedelta(days=1)
    
    # Filter transactions to show only the relevant period
    transactions = [
        t for t in all_transactions
        if start_date <= t['date_payed'] <= end_date
    ]
    
    # Find the running balance just before the start date to provide context
    try:
        last_transaction_before_period = next(
            t for t in reversed(all_transactions) if t['date_payed'] < start_date
        )
        starting_balance = last_transaction_before_period['running_balance']
    except StopIteration:
        starting_balance = 0.0

    table = Table(
        title=f"Cash Flow: {today.strftime('%B %Y')} - {end_date.strftime('%B %Y')}",
        show_header=True,
        header_style="bold magenta"
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

    # Add a row for the starting balance
    table.add_row(
        "", "", "", "Starting Balance", "", "", "", "", "",
        f"[bold green]{starting_balance:.2f}[/]"
    )
    table.add_section()

    last_month = None
    for t in transactions:
        current_month = t['date_payed'].strftime('%Y-%m')
        if last_month and current_month != last_month:
            table.add_section()
        
        status = t['status']
        
        row_style = ""
        amount_style = "yellow"
        balance_style = "green"

        if status == 'pending':
            row_style = "dim"
            amount_style = "grey50"
            balance_style = "grey50"
        elif status == 'forecast':
            row_style = "italic"
            amount_style = "cyan"
            balance_style = "bright_blue"

        table.add_row(
            str(t['id']),
            str(t['date_payed']),
            str(t['date_created']),
            t['description'],
            t['account'],
            f"[{amount_style}]{t['amount']:.2f}[/]",
            t['category'],
            t.get('budget', '') or '',
            t['status'],
            f"[{balance_style}]{t['running_balance']:.2f}[/]",
            style=row_style
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

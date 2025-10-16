import sqlite3
import csv
from rich.console import Console
from rich.table import Table

import repository

def view_transactions(conn: sqlite3.Connection):
    """
    Retrieves and displays all transactions in a formatted table,
    with separators between months.
    """
    transactions = repository.get_transactions_with_running_balance(conn)
    
    table = Table(title="Cash Flow Transactions", show_header=True, header_style="bold magenta")
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

    last_month = None
    for t in transactions:
        current_month = t['date_payed'].strftime('%Y-%m')
        if last_month and current_month != last_month:
            table.add_section()
        
        is_pending = t['status'] == 'pending'
        row_style = "dim" if is_pending else ""
        amount_style = "grey50" if is_pending else "yellow"
        balance_style = "grey50" if is_pending else "green"

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

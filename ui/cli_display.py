import sqlite3
import csv
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from rich.console import Console
from rich.table import Table

from cashflow import repository

def view_transactions(conn: sqlite3.Connection, months: int, summary: bool = False, include_planning: bool = False, start_from: str = None, sort_by: str = "date_payed"):
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
        # Sort transactions based on user preference
        if sort_by == "date_created":
            display_transactions = sorted(all_transactions, key=lambda x: (x['date_created'], x['id']))
        else:  # default to date_payed
            display_transactions = sorted(all_transactions, key=lambda x: (x['date_payed'], x['id']))
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

        summarized_payments = {}
        other_transactions = []
        planning_transactions = []
        pending_transactions = []

        for t in all_transactions:
            if t['account'] in credit_card_accounts:
                # Planning and pending show individually — they shouldn't inflate
                # the aggregate payment amount (pending is excluded from running
                # balance; showing it in the aggregate misleads reconciliation).
                if not include_planning and t['status'] == 'planning':
                    planning_transactions.append(t)
                    continue
                if t['status'] == 'pending':
                    pending_transactions.append(t)
                    continue

                if sort_by == "date_created":
                    key = (t['account'], t['date_created'].strftime('%Y-%m'))
                else:
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
        if sort_by == "date_created":
            for (account, creation_month), data in summarized_payments.items():
                statuses = data['statuses']
                status = 'forecast'
                if 'committed' in statuses: status = 'committed'
                elif 'pending' in statuses: status = 'pending'
                elif 'planning' in statuses: status = 'planning'

                month_date = datetime.strptime(creation_month, '%Y-%m').date().replace(day=1)
                month_label = month_date.strftime('%b')
                summary_trans = {
                    'id': '--', 'date_created': month_date, 'date_payed': '',
                    'description': f"{account} ({month_label})", 'account': account,
                    'amount': data['amount'], 'category': 'Credit Card', 'budget': '',
                    'status': status, 'origin_id': None, 'running_balance': 0.0,
                }
                summary_transactions.append(summary_trans)
        else:
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
                    'running_balance': data['running_balance']
                }
                summary_transactions.append(summary_trans)

        # Combine and sort all transactions
        if sort_by == "date_created":
            combined = sorted(other_transactions + summary_transactions + planning_transactions + pending_transactions, key=lambda x: (x['date_created'], x.get('id', 0) if x.get('id') != '--' else 0))
        else:  # default to date_payed
            combined = sorted(other_transactions + summary_transactions + planning_transactions + pending_transactions, key=lambda x: (x['date_payed'], x.get('id', 0) if x.get('id') != '--' else 999999))

        # Don't recalculate running balance - use the ones from original transactions
        for t in combined:
            display_transactions.append(t)
        # --- End Summarization ---

    # --- Date Filtering ---
    today = date.today()
    start_date = today.replace(day=1)
    date_field = 'date_created' if sort_by == 'date_created' else 'date_payed'

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
        if t['status'] == 'pending' and t[date_field] < start_date
    ]

    transactions_in_period = [
        t for t in display_transactions
        if start_date <= t[date_field] <= end_date
    ]

    # Pre-compute monthly spending totals for created-date mode (negative amounts, exclude pending)
    monthly_spending = {}
    if sort_by == "date_created":
        for t in transactions_in_period:
            if t['amount'] < 0 and t['status'] != 'pending':
                month_key = t['date_created'].strftime('%Y-%m')
                monthly_spending[month_key] = monthly_spending.get(month_key, 0.0) + t['amount']

    starting_balance = 0.0
    if sort_by != "date_created":
        try:
            last_transaction_before_period = next(
                t for t in reversed(display_transactions) if t['date_payed'] < start_date
            )
            starting_balance = last_transaction_before_period['running_balance']
        except StopIteration:
            pass

    table = Table(
        title=f"Cash Flow: {today.strftime('%B %Y')} - {end_date.strftime('%B %Y')}",
        show_header=True, header_style="bold magenta"
    )

    if sort_by == "date_created":
        table.add_column("ID", style="dim")
        table.add_column("Date Created")
        table.add_column("Date Payed", style="dim")
        table.add_column("Description")
        table.add_column("Account")
        table.add_column("Amount", justify="right")
        table.add_column("Category")
        table.add_column("Budget")
        table.add_column("Status")
        table.add_column("Month Spent", justify="right")
    else:
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
        if sort_by == "date_created":
            table.add_row(
                "", "", "", "[bold yellow]Pending from Previous Months[/bold yellow]",
                "", "", "", "", "", ""
            )
            for t in pending_from_past:
                table.add_row(
                    str(t['id']), str(t['date_created']), str(t['date_payed']),
                    t['description'], t['account'], f"{t['amount']:.2f}",
                    t['category'], t.get('budget', '') or '', t['status'], "",
                    style="grey50"
                )
        else:
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

    if sort_by != "date_created":
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
        current_month = t[date_field].strftime('%Y-%m')

        # Check if this is the last transaction of the month or last transaction overall
        is_last_in_month = (i == len(transactions_in_period) - 1) or \
                          (transactions_in_period[i + 1][date_field].strftime('%Y-%m') != current_month)

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

        if sort_by == "date_created":
            month_total_str = ""
            if is_last_in_month:
                total = monthly_spending.get(current_month, 0.0)
                if total < 0:
                    month_total_str = f"[red]{total:.2f}[/red]"
                else:
                    month_total_str = "0.00"

            table.add_row(
                str(t['id']), str(t['date_created']), str(t['date_payed']),
                t['description'], t['account'], f"{t['amount']:.2f}",
                t['category'], t.get('budget', '') or '', t['status'],
                month_total_str, style=row_style
            )
        else:
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


def _classify_origin(origin_id: str | None) -> str:
    if not origin_id:
        return "real"
    if origin_id.startswith("sub_"):
        return "sub"
    if origin_id.startswith("budget_"):
        return "budget"
    return "real"


def show_liabilities(conn: sqlite3.Connection, months: int = 6, detail: bool = False, summary: bool = False):
    """
    Per-card breakdown of what is owed and forecast.
    Single table with columns: card, pay date, real, subs, budgets, total, owed-now.
    """
    console = Console()
    today = date.today()
    today_iso = today.isoformat()
    horizon_end = today + relativedelta(months=months)

    accounts = repository.get_all_accounts(conn)
    cc_accounts = [a for a in accounts if a.get("account_type") == "credit_card"]
    cur = conn.cursor()

    grand_owed_current = 0.0
    grand_owed_later = 0.0
    grand_horizon = 0.0
    sub_horizon_total = 0.0
    budget_horizon_total = 0.0

    # ---------- CC by cycle ----------
    cc_table = Table(
        title=f"Liabilities — as of {today}, horizon {months}mo",
        show_header=True, header_style="bold magenta",
    )
    cc_table.add_column("Card")
    cc_table.add_column("Pay date")
    cc_table.add_column("Real",    justify="right")
    cc_table.add_column("Subs",    justify="right")
    cc_table.add_column("Budgets", justify="right")
    cc_table.add_column("Total",   justify="right")
    cc_table.add_column("Owed",    justify="right")

    for acc in cc_accounts:
        name = acc["account_id"]
        cur.execute(
            """
            SELECT date_payed, date_created, amount, origin_id
            FROM transactions
            WHERE account = ?
              AND date_payed >= ? AND date_payed <= ?
              AND status IN ('committed', 'forecast')
              AND amount < 0
            ORDER BY date_payed
            """,
            (name, today_iso, horizon_end.isoformat()),
        )
        cycles: dict = {}
        for date_payed, date_created, amount, origin_id in cur.fetchall():
            cycles.setdefault(date_payed, []).append(
                {"date_created": date_created, "amount": amount, "origin_id": origin_id}
            )
        if not cycles:
            continue

        sorted_cycles = sorted(cycles.keys())

        def cycle_metrics(txs):
            real = sum(t["amount"] for t in txs if _classify_origin(t["origin_id"]) == "real")
            subs = sum(t["amount"] for t in txs if _classify_origin(t["origin_id"]) == "sub")
            buds = sum(t["amount"] for t in txs if _classify_origin(t["origin_id"]) == "budget")
            owed = sum(t["amount"] for t in txs if str(t["date_created"]) <= today_iso)
            return real, subs, buds, real + subs + buds, owed

        if summary:
            # Current statement row (cycle 1)
            first_cd = sorted_cycles[0]
            real, subs, buds, tot, owed = cycle_metrics(cycles[first_cd])
            cc_table.add_row(
                name, f"{first_cd} (current)",
                f"${abs(real):.2f}", f"${abs(subs):.2f}", f"${abs(buds):.2f}",
                f"${abs(tot):.2f}",
                f"${abs(owed):.2f}" if owed else "—",
            )
            grand_owed_current += owed
            grand_horizon += tot
            # Future aggregated row (cycles 2+)
            future_txs = [t for cd in sorted_cycles[1:] for t in cycles[cd]]
            if future_txs:
                real, subs, buds, tot, owed = cycle_metrics(future_txs)
                cc_table.add_row(
                    name, f"future {len(sorted_cycles)-1} cycles",
                    f"${abs(real):.2f}", f"${abs(subs):.2f}", f"${abs(buds):.2f}",
                    f"${abs(tot):.2f}",
                    f"${abs(owed):.2f}" if owed else "—",
                )
                grand_owed_later += owed
                grand_horizon += tot
        else:
            for idx, cd in enumerate(sorted_cycles):
                real, subs, buds, tot, owed = cycle_metrics(cycles[cd])
                cc_table.add_row(
                    name, str(cd),
                    f"${abs(real):.2f}", f"${abs(subs):.2f}", f"${abs(buds):.2f}",
                    f"${abs(tot):.2f}",
                    f"${abs(owed):.2f}" if owed else "—",
                )
                if idx == 0:
                    grand_owed_current += owed
                else:
                    grand_owed_later += owed
                grand_horizon += tot

    console.print(cc_table)

    # ---------- Subs ----------
    cur.execute(
        """
        SELECT origin_id, account, COUNT(*), SUM(amount)
        FROM transactions
        WHERE origin_id LIKE 'sub_%'
          AND date_payed >= ? AND date_payed <= ?
          AND amount < 0
          AND status IN ('committed', 'forecast')
        GROUP BY origin_id, account
        ORDER BY SUM(amount)
        """,
        (today_iso, horizon_end.isoformat()),
    )
    sub_rows = cur.fetchall()
    sub_horizon_total = sum(r[3] for r in sub_rows)

    if not summary:
        sub_table = Table(title="Subscriptions (horizon)", show_header=True, header_style="bold magenta")
        sub_table.add_column("Subscription")
        sub_table.add_column("Account")
        sub_table.add_column("Months", justify="right")
        sub_table.add_column("Total",  justify="right")
        for origin_id, account, n, total in sub_rows:
            sub_table.add_row(origin_id, account, str(n), f"${abs(total):.2f}")
        console.print(sub_table)

    # ---------- Budgets ----------
    cur.execute(
        """
        SELECT origin_id, account, COUNT(*), SUM(amount)
        FROM transactions
        WHERE origin_id LIKE 'budget_%'
          AND date_payed >= ? AND date_payed <= ?
          AND amount < 0
          AND status IN ('committed', 'forecast')
        GROUP BY origin_id, account
        ORDER BY SUM(amount)
        """,
        (today_iso, horizon_end.isoformat()),
    )
    bud_rows = cur.fetchall()
    budget_horizon_total = sum(r[3] for r in bud_rows)

    if not summary:
        bud_table = Table(title="Budget envelopes (horizon)", show_header=True, header_style="bold magenta")
        bud_table.add_column("Budget")
        bud_table.add_column("Account")
        bud_table.add_column("Months", justify="right")
        bud_table.add_column("Total",  justify="right")
        for origin_id, account, n, total in bud_rows:
            bud_table.add_row(origin_id, account, str(n), f"${abs(total):.2f}")
        console.print(bud_table)

    # ---------- Summary ----------
    summary = Table(title="Summary", show_header=True, header_style="bold magenta")
    summary.add_column("Metric")
    summary.add_column("Amount", justify="right")
    summary.add_row("Owed — next CC bill (current statements)",    f"${abs(grand_owed_current):.2f}")
    summary.add_row("Owed — later cycles (post-cutoff)",            f"${abs(grand_owed_later):.2f}")
    summary.add_row(f"CC horizon total ({months}mo)",               f"${abs(grand_horizon):.2f}")
    summary.add_row("Subs horizon",                                 f"${abs(sub_horizon_total):.2f}")
    summary.add_row("Budgets horizon (speculative)",                f"${abs(budget_horizon_total):.2f}")
    console.print(summary)

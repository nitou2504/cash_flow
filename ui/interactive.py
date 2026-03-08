"""Interactive prompt helpers and transaction entry flow (no LLM needed)."""

import sqlite3
from datetime import date, timedelta
from rich.console import Console
from rich.table import Table

from cashflow import repository
from cashflow.transactions import simulate_payment_date


console = Console()


def prompt_select(title, items, display_fn, allow_skip=False):
    """Numbered list selection. User types number or substring to select."""
    if not items:
        console.print(f"[yellow]No {title.lower()} available.[/yellow]")
        return None

    console.print(f"\n[bold]{title}:[/bold]")
    for i, item in enumerate(items, 1):
        console.print(f"  {i}. {display_fn(item)}")

    hint = "number or name" + (", empty to skip" if allow_skip else "")
    while True:
        try:
            raw = input(f"[{hint}]> ").strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if not raw:
            if allow_skip:
                return None
            console.print("[red]Selection required.[/red]")
            continue

        # Try numeric
        try:
            idx = int(raw)
            if 1 <= idx <= len(items):
                return items[idx - 1]
            console.print(f"[red]Enter 1-{len(items)}.[/red]")
            continue
        except ValueError:
            pass

        # Substring match
        matches = [item for item in items if raw.lower() in display_fn(item).lower()]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]Ambiguous: {', '.join(display_fn(m) for m in matches)}[/yellow]")
        else:
            console.print("[red]No match found.[/red]")


def prompt_text(label, default=None, required=True):
    """Free text input."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            raw = input(f"{label}{suffix}: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw:
            if default:
                return default
            if not required:
                return None
            console.print("[red]This field is required.[/red]")
            continue
        return raw


def prompt_amount(label="Amount", default=None):
    """Validated positive float."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            raw = input(f"{label}{suffix}: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw and default is not None:
            return default
        try:
            val = float(raw)
            if val <= 0:
                console.print("[red]Must be positive.[/red]")
                continue
            return val
        except ValueError:
            console.print("[red]Enter a valid number.[/red]")


def prompt_date(label="Date", default=None):
    """Date input. Accepts YYYY-MM-DD, MM/DD, 'yesterday', empty=default."""
    if default is None:
        default = date.today()
    while True:
        try:
            raw = input(f"{label} [{default.isoformat()}]: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw:
            return default

        # Named shortcuts
        lower = raw.lower()
        if lower == "yesterday":
            return date.today() - timedelta(days=1)
        if lower == "today":
            return date.today()

        # Try YYYY-MM-DD
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass

        # Try MM/DD (assume current year)
        try:
            parts = raw.split("/")
            if len(parts) == 2:
                m, d = int(parts[0]), int(parts[1])
                return date(date.today().year, m, d)
        except (ValueError, IndexError):
            pass

        console.print("[red]Enter YYYY-MM-DD, MM/DD, 'yesterday', or press Enter for default.[/red]")


def prompt_int(label, default=None, min_val=None, max_val=None):
    """Validated integer."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            raw = input(f"{label}{suffix}: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw and default is not None:
            return default
        try:
            val = int(raw)
            if min_val is not None and val < min_val:
                console.print(f"[red]Minimum is {min_val}.[/red]")
                continue
            if max_val is not None and val > max_val:
                console.print(f"[red]Maximum is {max_val}.[/red]")
                continue
            return val
        except ValueError:
            console.print("[red]Enter a valid integer.[/red]")


def prompt_yes_no(label, default=True):
    """Y/n confirmation."""
    hint = "Y/n" if default else "y/N"
    try:
        raw = input(f"{label} [{hint}]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return None
    if not raw:
        return default
    return raw in ("y", "yes")


def prompt_choice(label, choices, default=None):
    """Inline choice from a short list."""
    display = "/".join(
        c.upper() if c == default else c for c in choices
    )
    while True:
        try:
            raw = input(f"{label} [{display}]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw and default:
            return default
        if raw in choices:
            return raw
        console.print(f"[red]Choose one of: {', '.join(choices)}[/red]")


def _format_account(acc):
    """Display string for an account."""
    info = acc['account_id']
    if acc['account_type'] == 'credit_card':
        info += f" (credit_card, cut-off: {acc.get('cut_off_day', '?')}, pay: {acc.get('payment_day', '?')})"
    else:
        info += f" ({acc['account_type']})"
    return info


def _format_category(cat):
    """Display string for a category."""
    desc = cat.get('description', '')
    if desc:
        return f"{cat['name']} - {desc}"
    return cat['name']


def _format_budget(budget):
    """Display string for a budget."""
    amt = budget.get('monthly_amount', 0)
    spent = budget.get('_spent', 0)
    remaining = amt - spent
    return f"{budget['id']} (${spent:.0f}/${amt:.0f} spent, ${remaining:.0f} left)"


def display_transaction_preview(request, account, transaction_date):
    """Display a rich table preview of a transaction request.

    Used by both interactive flow and LLM-based handle_add.
    """
    payment_date = simulate_payment_date(account, transaction_date) if account else transaction_date

    table = Table(title="Transaction Preview", show_header=True, header_style="bold cyan")
    table.add_column("Field", style="dim")
    table.add_column("Value")

    tx_type = request.get('type', 'simple')

    if tx_type == 'simple':
        amount = request.get('amount', 0)
        table.add_row("Date Created", str(transaction_date))
        table.add_row("Date Payed", str(payment_date))
        table.add_row("Description", request.get('description', ''))
        table.add_row("Account", request.get('account', ''))
        table.add_row("Amount", f"-{abs(amount):.2f}" if not request.get('is_income') else f"+{abs(amount):.2f}")
        table.add_row("Category", request.get('category', '') or '')
        table.add_row("Budget", request.get('budget', '') or '')
        if request.get('is_pending'):
            table.add_row("Status", "pending")
        elif request.get('is_planning'):
            table.add_row("Status", "planning")

    elif tx_type == 'installment':
        total = request.get('total_amount', 0)
        installments = request.get('installments', 1)
        per_installment = total / installments if installments else total
        table.add_row("Type", "Installment")
        table.add_row("Date Created", str(transaction_date))
        table.add_row("First Payment", str(payment_date))
        table.add_row("Description", request.get('description', ''))
        table.add_row("Account", request.get('account', ''))
        table.add_row("Total Amount", f"-{abs(total):.2f}")
        table.add_row("Installments", f"{installments}x of {per_installment:.2f}")
        table.add_row("Category", request.get('category', '') or '')
        table.add_row("Budget", request.get('budget', '') or '')
        grace = request.get('grace_period_months', 0)
        if grace:
            table.add_row("Grace Period", f"{grace} months")
        start_from = request.get('start_from_installment', 1)
        if start_from > 1:
            total_installments = request.get('total_installments', installments + start_from - 1)
            table.add_row("Starting From", f"Installment {start_from} of {total_installments}")

    elif tx_type == 'split':
        table.add_row("Type", "Split Transaction")
        table.add_row("Date Created", str(transaction_date))
        table.add_row("Date Payed", str(payment_date))
        table.add_row("Description", request.get('description', ''))
        table.add_row("Account", request.get('account', ''))
        for i, split in enumerate(request.get('splits', []), 1):
            table.add_row(
                f"Split {i}",
                f"-{abs(split.get('amount', 0)):.2f} | {split.get('category', '')} | {split.get('budget', '') or ''}"
            )

    console.print(table)


def interactive_add_transaction(conn):
    """Interactive step-by-step transaction entry. Returns request dict or None."""
    try:
        return _interactive_flow(conn)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None


def _interactive_flow(conn):
    """Core interactive flow. Raises KeyboardInterrupt/EOFError on cancel."""
    accounts = repository.get_all_accounts(conn)
    if not accounts:
        console.print("[red]No accounts found. Add one first with 'accounts add'.[/red]")
        return None

    categories = repository.get_all_categories(conn)

    console.print("[bold]Interactive Transaction Entry[/bold]")
    console.print("Press Ctrl+C to cancel at any time.\n")

    # 1. Transaction type
    tx_type = prompt_choice("Type", ["simple", "installment", "split"], default="simple")
    if tx_type is None:
        return None

    # 2. Date
    transaction_date = prompt_date("Date", default=date.today())
    if transaction_date is None:
        return None

    # 3. Description
    description = prompt_text("Description")
    if description is None:
        return None

    # 4. Account
    account = prompt_select("Account", accounts, _format_account)
    if account is None:
        return None
    account_name = account['account_id']

    # Calculate payment date for budget filtering
    payment_date = simulate_payment_date(account, transaction_date)
    payment_month = date(payment_date.year, payment_date.month, 1)

    # Get active budgets for the payment month, with spent amounts
    budgets_with_status = repository.get_all_budgets_with_status(conn, payment_month)
    active_budgets = []
    for b in budgets_with_status:
        if b['status'] == 'Active':
            b['_spent'] = repository.get_total_spent_for_budget_in_month(
                conn, b['id'], payment_month)
            active_budgets.append(b)

    if tx_type == "simple":
        return _flow_simple(account_name, account, transaction_date, description,
                            categories, active_budgets)
    elif tx_type == "installment":
        return _flow_installment(account_name, account, transaction_date, description,
                                 categories, active_budgets)
    elif tx_type == "split":
        return _flow_split(account_name, account, transaction_date, description,
                           categories, active_budgets)


def _prompt_category_and_budget(categories, active_budgets):
    """Shared prompts for category and budget selection."""
    # Category
    category = prompt_select("Category", categories, _format_category, allow_skip=True)
    category_name = category['name'] if category else None

    # Budget
    budget_id = None
    if active_budgets:
        budget = prompt_select("Budget", active_budgets, _format_budget, allow_skip=True)
        budget_id = budget['id'] if budget else None

    return category_name, budget_id


def _prompt_flags():
    """Prompt for status and income flag."""
    status = prompt_choice("Status", ["normal", "pending", "planning"], default="normal")
    if status is None:
        return None, None, None
    is_income = prompt_yes_no("Is this income?", default=False)
    if is_income is None:
        return None, None, None
    return is_income, status == "pending", status == "planning"


def _flow_simple(account_name, account, transaction_date, description,
                 categories, active_budgets):
    """Simple transaction flow."""
    # 5. Amount
    amount = prompt_amount()
    if amount is None:
        return None

    # 6-7. Category & Budget
    category_name, budget_id = _prompt_category_and_budget(categories, active_budgets)

    # 8. Flags
    is_income, is_pending, is_planning = _prompt_flags()
    if is_income is None:
        return None

    request = {
        "type": "simple",
        "description": description,
        "account": account_name,
        "amount": amount,
        "category": category_name,
        "budget": budget_id,
        "is_income": is_income,
        "is_pending": is_pending,
        "is_planning": is_planning,
        "_transaction_date": transaction_date,
    }

    # Preview
    display_transaction_preview(request, account, transaction_date)
    confirm = prompt_yes_no("\nProceed?", default=True)
    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        return None
    return request


def _flow_installment(account_name, account, transaction_date, description,
                      categories, active_budgets):
    """Installment transaction flow."""
    # Total amount
    total_amount = prompt_amount("Total amount")
    if total_amount is None:
        return None

    # Number of installments
    installments = prompt_int("Number of installments", min_val=2)
    if installments is None:
        return None

    # Grace period
    grace = prompt_int("Grace period (months)", default=0, min_val=0)
    if grace is None:
        return None

    # Start from installment (for partial imports)
    start_from = prompt_int("Start from installment", default=1, min_val=1, max_val=installments)
    if start_from is None:
        return None

    # Category & Budget
    category_name, budget_id = _prompt_category_and_budget(categories, active_budgets)

    # Flags
    is_income, is_pending, is_planning = _prompt_flags()
    if is_income is None:
        return None

    request = {
        "type": "installment",
        "description": description,
        "account": account_name,
        "total_amount": total_amount,
        "installments": installments,
        "grace_period_months": grace,
        "category": category_name,
        "budget": budget_id,
        "is_income": is_income,
        "is_pending": is_pending,
        "is_planning": is_planning,
        "_transaction_date": transaction_date,
    }

    if start_from > 1:
        request["start_from_installment"] = start_from
        request["total_installments"] = installments
        # Actual installments to generate
        request["installments"] = installments - start_from + 1

    # Preview
    display_transaction_preview(request, account, transaction_date)
    confirm = prompt_yes_no("\nProceed?", default=True)
    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        return None
    return request


def _flow_split(account_name, account, transaction_date, description,
                categories, active_budgets):
    """Split transaction flow."""
    splits = []
    console.print("\n[bold]Enter splits[/bold] (at least 2). Type 'done' when finished.")

    while True:
        console.print(f"\n[dim]--- Split {len(splits) + 1} ---[/dim]")
        amount = prompt_amount(f"Split {len(splits) + 1} amount")
        if amount is None:
            return None

        category_name, budget_id = _prompt_category_and_budget(categories, active_budgets)

        splits.append({
            "amount": amount,
            "category": category_name,
            "budget": budget_id,
        })

        if len(splits) >= 2:
            more = prompt_yes_no("Add another split?", default=False)
            if more is None:
                return None
            if not more:
                break

    # Flags
    is_income, is_pending, is_planning = _prompt_flags()
    if is_income is None:
        return None

    request = {
        "type": "split",
        "description": description,
        "account": account_name,
        "splits": splits,
        "is_income": is_income,
        "is_pending": is_pending,
        "is_planning": is_planning,
        "_transaction_date": transaction_date,
    }

    # Preview
    display_transaction_preview(request, account, transaction_date)
    confirm = prompt_yes_no("\nProceed?", default=True)
    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        return None
    return request

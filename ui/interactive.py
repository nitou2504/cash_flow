"""Interactive prompt helpers and transaction entry flow (no LLM needed)."""

import re
import sqlite3
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
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
            cleaned = raw.replace("$", "")
            # "9,99" → locale decimal; "1,234" / "1,234.50" → thousands separator
            if re.fullmatch(r'\d+,\d{2}', cleaned):
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
            val = float(cleaned)
            if val <= 0:
                console.print("[red]Must be positive.[/red]")
                continue
            return val
        except ValueError:
            console.print("[red]Enter a valid number.[/red]")

def prompt_signed_amount(label="Amount", default=None):
    """Edit amount preserving sign. Bare number keeps original sign, +/- overrides."""
    sign_hint = "+income" if default is not None and default > 0 else "-expense"
    suffix = f" [{default}, prefix +/- to change sign]" if default is not None else ""
    while True:
        try:
            raw = input(f"{label}{suffix}: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw and default is not None:
            return default
        try:
            has_explicit_sign = raw.lstrip("$").startswith("+") or raw.lstrip("$").startswith("-")
            cleaned = raw.replace("$", "")
            if re.fullmatch(r'[+-]?\d+,\d{2}', cleaned):
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
            val = float(cleaned)
            if val == 0:
                console.print("[red]Amount cannot be zero.[/red]")
                continue
            if not has_explicit_sign and default is not None:
                # Bare number: keep original sign
                val = abs(val) * (1 if default > 0 else -1)
            return val
        except ValueError:
            console.print("[red]Enter a valid number. Use +/- prefix to change sign.[/red]")


def _end_of_month(d):
    """Return the last day of the month containing date d."""
    return d.replace(day=1) + relativedelta(months=1) - timedelta(days=1)


def prompt_date(label="Date", default=None, reference_date=None):
    """Date input. Accepts YYYY-MM-DD, MM/DD, 'yesterday', '+N' (months from reference)."""
    if default is None:
        default = date.today()
    hint = default.isoformat()
    if reference_date is not None:
        hint += ", +N months"
    while True:
        try:
            raw = input(f"{label} [{hint}]: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw:
            return default

        # +N months from reference date (end of that month)
        if reference_date is not None and raw.startswith('+'):
            try:
                n = int(raw[1:])
                target = reference_date + relativedelta(months=n)
                return _end_of_month(target)
            except ValueError:
                pass

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
    """Inline choice from a short list. Accepts number, prefix, or full name."""
    display = " / ".join(
        f"{i}.{c.upper()}" if c == default else f"{i}.{c}"
        for i, c in enumerate(choices, 1)
    )
    while True:
        try:
            raw = input(f"{label} [{display}]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None
        if not raw and default:
            return default
        # Exact match
        if raw in choices:
            return raw
        # Numeric selection
        try:
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
        except ValueError:
            pass
        # Unique prefix match
        matches = [c for c in choices if c.startswith(raw)]
        if len(matches) == 1:
            return matches[0]
        # Error feedback
        if len(matches) > 1:
            console.print(f"[yellow]Ambiguous: {', '.join(matches)}[/yellow]")
        else:
            console.print(f"[red]Choose one of: {', '.join(choices)} (or 1-{len(choices)})[/red]")


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

def interactive_add_account(conn):
    """Interactive step-by-step account creation. Returns (account_id, account_type, cut_off_day, payment_day) or None."""
    try:
        console.print("[bold]Interactive Account Creation[/bold]")
        console.print("Press Ctrl+C to cancel at any time.\n")

        name = prompt_text("Account name")
        if name is None:
            return None

        acc_type = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        if acc_type is None:
            return None

        cut_off_day = None
        payment_day = None
        if acc_type == "credit_card":
            cut_off_day = prompt_int("Cut-off day", min_val=1, max_val=31)
            if cut_off_day is None:
                return None
            payment_day = prompt_int("Payment day", min_val=1, max_val=31)
            if payment_day is None:
                return None

        # Preview
        table = Table(title="Account Preview", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="dim")
        table.add_column("Value")
        table.add_row("Name", name)
        table.add_row("Type", acc_type)
        if acc_type == "credit_card":
            table.add_row("Cut-off Day", str(cut_off_day))
            table.add_row("Payment Day", str(payment_day))
        console.print(table)

        confirm = prompt_yes_no("\nProceed?", default=True)
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return None

        return (name, acc_type, cut_off_day, payment_day)

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None


def interactive_add_category(conn):
    """Interactive step-by-step category creation. Returns (name, description) or None."""
    try:
        console.print("[bold]Interactive Category Creation[/bold]")
        console.print("Press Ctrl+C to cancel at any time.\n")

        name = prompt_text("Category name")
        if name is None:
            return None

        description = prompt_text("Description (helps LLM auto-categorize)")
        if description is None:
            return None

        confirm = prompt_yes_no(f"\nCreate category '{name}' ({description})?", default=True)
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return None

        return (name, description)

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None


def interactive_add_subscription(conn):
    """Interactive step-by-step subscription/budget creation. Returns subscription data dict or None."""
    try:
        accounts = repository.get_all_accounts(conn)
        if not accounts:
            console.print("[red]No accounts found. Add one first with 'accounts add'.[/red]")
            return None

        categories = repository.get_all_categories(conn)
        if not categories:
            console.print("[red]No categories found. Add one first with 'categories add'.[/red]")
            return None

        console.print("[bold]Interactive Subscription/Budget Creation[/bold]")
        console.print("Press Ctrl+C to cancel at any time.\n")

        # 1. Kind
        kind = prompt_choice("Kind", ["subscription", "budget", "income"], default="subscription")
        if kind is None:
            return None

        # 2. Name
        name = prompt_text("Name")
        if name is None:
            return None

        # 3. Monthly amount
        amount = prompt_amount("Monthly amount")
        if amount is None:
            return None

        # 4. Account
        account = prompt_select("Account", accounts, _format_account)
        if account is None:
            return None

        # 5. Category
        category = prompt_select("Category", categories, _format_category)
        if category is None:
            return None

        # 6. Start date
        start_date = prompt_date("Start date", default=date.today().replace(day=1))
        if start_date is None:
            return None

        # 7. End date
        end_date = None
        has_end = prompt_yes_no("Set an end date?", default=False)
        if has_end is None:
            return None
        if has_end:
            eom = _end_of_month(start_date)
            end_date = prompt_date("End date", default=eom, reference_date=start_date)
            if end_date is None:
                return None

        # 8. Underspend behavior (budgets only)
        underspend = "keep"
        if kind == "budget":
            underspend = prompt_choice("Underspend behavior", ["keep", "return"], default="keep")
            if underspend is None:
                return None

        # Auto-generate ID
        is_budget = kind in ("budget", "income")
        prefix = "sub_" if kind == "subscription" else "budget_"
        sub_id = prefix + name.lower().replace(" ", "_")

        # Build data dict
        sub_data = {
            "id": sub_id,
            "name": name,
            "category": category['name'],
            "monthly_amount": amount,
            "payment_account_id": account['account_id'],
            "start_date": start_date,
            "end_date": end_date,
            "is_budget": is_budget,
            "underspend_behavior": underspend,
            "is_income": kind == "income",
        }

        # Preview
        table = Table(title="Subscription/Budget Preview", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="dim")
        table.add_column("Value")
        table.add_row("ID", sub_id)
        table.add_row("Kind", kind)
        table.add_row("Name", name)
        table.add_row("Amount", f"${amount:.2f}/month")
        table.add_row("Account", account['account_id'])
        table.add_row("Category", category['name'])
        table.add_row("Start", str(start_date))
        table.add_row("End", str(end_date) if end_date else "Ongoing")
        if kind == "budget":
            table.add_row("Underspend", underspend)
        console.print(table)

        confirm = prompt_yes_no("\nProceed?", default=True)
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return None

        return sub_data

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None

def interactive_edit_transaction(conn, transaction_id):
    """Interactive step-by-step transaction edit. Returns (updates_dict, new_date_or_None) or None."""
    try:
        tx = repository.get_transaction_by_id(conn, transaction_id)
        if not tx:
            console.print(f"[red]Transaction {transaction_id} not found.[/red]")
            return None

        console.print(f"[bold]Editing Transaction {transaction_id}[/bold]")
        console.print("Press Enter to keep current value. Ctrl+C to cancel.\n")

        # Show current values
        table = Table(title="Current Values", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="dim")
        table.add_column("Value")
        table.add_row("Description", tx['description'])
        table.add_row("Amount", f"{tx['amount']:.2f}")
        table.add_row("Date Created", str(tx['date_created']))
        table.add_row("Account", tx['account'])
        table.add_row("Category", tx.get('category') or '')
        table.add_row("Budget", tx.get('budget') or '')
        table.add_row("Status", tx['status'])
        console.print(table)
        console.print()

        # Prompt each field
        description = prompt_text("Description", default=tx['description'])
        if description is None:
            return None

        current_amount = tx['amount']
        amount = prompt_signed_amount("Amount", default=current_amount)
        if amount is None:
            return None

        current_date = date.fromisoformat(str(tx['date_created']))
        new_date = prompt_date("Date created", default=current_date)
        if new_date is None:
            return None

        categories = repository.get_all_categories(conn)
        current_cat = tx.get('category') or ''
        console.print(f"\n[dim]Current category: {current_cat or '(none)'}[/dim]")
        category = prompt_select("Category", categories, _format_category, allow_skip=True)
        category_name = category['name'] if category else current_cat or None

        # Get budgets for the payment month
        payment_date_str = str(tx['date_payed'])
        payment_date = date.fromisoformat(payment_date_str)
        payment_month = date(payment_date.year, payment_date.month, 1)
        budgets = repository.get_all_budgets_with_status(conn, payment_month)
        active_budgets = []
        for b in budgets:
            if b['status'] == 'Active':
                b['_spent'] = repository.get_total_spent_for_budget_in_month(
                    conn, b['id'], payment_month)
                active_budgets.append(b)

        current_budget = tx.get('budget') or ''
        console.print(f"[dim]Current budget: {current_budget or '(none)'}[/dim]")
        budget = prompt_select("Budget", active_budgets, _format_budget, allow_skip=True) if active_budgets else None
        budget_id = budget['id'] if budget else current_budget or None

        status = prompt_choice("Status", ["committed", "pending", "planning"], default=tx['status'])
        if status is None:
            return None

        # Build updates with only changed fields
        updates = {}
        if description != tx['description']:
            updates['description'] = description
        if amount != current_amount:
            updates['amount'] = amount
        if category_name != (tx.get('category') or None):
            updates['category'] = category_name
        if budget_id != (tx.get('budget') or None):
            updates['budget'] = budget_id
        if status != tx['status']:
            updates['status'] = status

        date_changed = new_date != current_date

        if not updates and not date_changed:
            console.print("[yellow]No changes.[/yellow]")
            return None

        # Show changes
        changes_table = Table(title="Changes", show_header=True, header_style="bold cyan")
        changes_table.add_column("Field", style="dim")
        changes_table.add_column("Old")
        changes_table.add_column("New")
        for field, new_val in updates.items():
            old_val = tx.get(field, '')
            changes_table.add_row(field, str(old_val), str(new_val))
        if date_changed:
            changes_table.add_row("date_created", str(current_date), str(new_date))
        console.print(changes_table)

        confirm = prompt_yes_no("\nApply changes?", default=True)
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return None

        return (updates, new_date if date_changed else None)

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None


def interactive_edit_subscription(conn, subscription_id):
    """Interactive step-by-step subscription edit. Returns updates dict or None."""
    try:
        sub = repository.get_subscription_by_id(conn, subscription_id)
        if not sub:
            console.print(f"[red]Subscription '{subscription_id}' not found.[/red]")
            return None

        console.print(f"[bold]Editing Subscription: {subscription_id}[/bold]")
        console.print("Press Enter to keep current value. Ctrl+C to cancel.\n")

        # Show current values
        table = Table(title="Current Values", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="dim")
        table.add_column("Value")
        table.add_row("Name", sub['name'])
        table.add_row("Amount", f"${sub['monthly_amount']:.2f}")
        table.add_row("Account", sub['payment_account_id'])
        table.add_row("Category", sub.get('category', ''))
        table.add_row("Start", str(sub['start_date']))
        table.add_row("End", str(sub.get('end_date')) if sub.get('end_date') else "Ongoing")
        if sub.get('is_budget'):
            table.add_row("Underspend", sub.get('underspend_behavior', 'keep'))
        console.print(table)
        console.print()

        # Prompt each editable field
        name = prompt_text("Name", default=sub['name'])
        if name is None:
            return None

        amount = prompt_amount("Monthly amount", default=sub['monthly_amount'])
        if amount is None:
            return None

        accounts = repository.get_all_accounts(conn)
        console.print(f"\n[dim]Current account: {sub['payment_account_id']}[/dim]")
        account = prompt_select("Account", accounts, _format_account, allow_skip=True)
        account_id = account['account_id'] if account else sub['payment_account_id']

        # End date
        change_end = prompt_yes_no("Change end date?", default=False)
        if change_end is None:
            return None
        end_date = sub.get('end_date')
        end_date_changed = False
        if change_end:
            clear_end = prompt_yes_no("Remove end date (make ongoing)?", default=False)
            if clear_end is None:
                return None
            if clear_end:
                end_date = None
                end_date_changed = True
            else:
                sub_start = date.fromisoformat(str(sub['start_date']))
                current_end = date.fromisoformat(str(sub['end_date'])) if sub.get('end_date') else _end_of_month(sub_start)
                end_date = prompt_date("End date", default=current_end, reference_date=sub_start)
                if end_date is None:
                    return None
                end_date_changed = True

        # Underspend (budgets only)
        underspend = sub.get('underspend_behavior', 'keep')
        underspend_changed = False
        if sub.get('is_budget'):
            new_underspend = prompt_choice("Underspend behavior", ["keep", "return"], default=underspend)
            if new_underspend is None:
                return None
            if new_underspend != underspend:
                underspend = new_underspend
                underspend_changed = True

        # Build updates with only changed fields
        updates = {}
        if name != sub['name']:
            updates['name'] = name
        if amount != sub['monthly_amount']:
            updates['monthly_amount'] = amount
        if account_id != sub['payment_account_id']:
            updates['payment_account_id'] = account_id
        if end_date_changed:
            if end_date is None:
                updates['end_date'] = None
            else:
                updates['end_date'] = end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date))
        if underspend_changed:
            updates['underspend_behavior'] = underspend

        if not updates:
            console.print("[yellow]No changes.[/yellow]")
            return None

        # Show changes
        changes_table = Table(title="Changes", show_header=True, header_style="bold cyan")
        changes_table.add_column("Field", style="dim")
        changes_table.add_column("Old")
        changes_table.add_column("New")
        for field, new_val in updates.items():
            old_val = sub.get(field, '')
            changes_table.add_row(field, str(old_val) if old_val else "(none)", str(new_val) if new_val else "(none)")
        console.print(changes_table)

        confirm = prompt_yes_no("\nApply changes?", default=True)
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return None

        return updates

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None

def interactive_statement_fix(conn, account_id, month):
    """Interactive statement fix flow. Returns statement_amount (float) or None."""
    try:
        account = repository.get_account_by_name(conn, account_id)
        if not account:
            console.print(f"[red]Account '{account_id}' not found.[/red]")
            return None

        if account['account_type'] == 'credit_card':
            payment_date = date(month.year, month.month, account['payment_day'])
        else:
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
        console.print(f"\n[bold]Statement Adjustment for {account_id} - {month.strftime('%B %Y')}[/bold]")
        console.print(f"Payment date: {payment_date}\n")

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
            console.print(table)
        else:
            console.print(f"[yellow]No transactions found on {payment_date}[/yellow]")
            console.print(f"Current total: $0.00")

        console.print()

        # Ask for statement amount
        statement_amount = prompt_amount("Actual statement amount")
        if statement_amount is None:
            return None

        # Statement amounts for expenses are negative
        statement_amount = -abs(statement_amount)

        # Calculate difference
        difference = statement_amount - current_total

        if abs(difference) < 0.01:
            console.print("\n[green]No adjustment needed - statement matches current total![/green]")
            return None

        # Show adjustment summary
        adjustment_amount = -difference
        adj_sign = "+" if adjustment_amount >= 0 else "-"
        diff_sign = "+" if difference >= 0 else "-"
        console.print(f"\nAdjustment: ${current_total:.2f} -> ${statement_amount:.2f} (difference: {diff_sign}${abs(difference):.2f})")

        confirm = prompt_yes_no("Proceed?", default=True)
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return None

        return statement_amount

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None

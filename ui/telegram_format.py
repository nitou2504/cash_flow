from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ui.strings import t, month_name

def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters for Telegram.

    Telegram MarkdownV1 special characters: _ * ` [
    """
    if not text:
        return text
    text = str(text)
    text = text.replace('_', r'\_')
    text = text.replace('*', r'\*')
    text = text.replace('`', r'\`')
    text = text.replace('[', r'\[')
    return text


def display_name(text: str) -> str:
    """Convert raw identifiers to display-friendly names for Telegram.

    Replaces underscores with spaces, applies title case, and escapes
    any remaining Markdown special characters.
    """
    if not text:
        return text
    text = str(text).replace('_', ' ').strip().title()
    # Escape remaining Markdown chars (*, `, [) — underscores are already gone
    text = text.replace('*', r'\*')
    text = text.replace('`', r'\`')
    text = text.replace('[', r'\[')
    return text

def format_transaction_preview(
    transaction_json: Dict[str, Any],
    payment_date: date,
    lang: str = "en",
) -> str:
    """Format transaction as Telegram message with emoji and formatting."""

    tx_type = transaction_json.get('type', 'simple')

    if tx_type == 'simple':
        amount = transaction_json.get('amount', 0)
        amount_str = f"+${abs(amount):.2f}" if transaction_json.get('is_income') else f"-${abs(amount):.2f}"

        status_emoji = "⏳" if transaction_json.get('is_pending') else "💰"

        message = f"{status_emoji} *{t('tx_preview', lang)}*\n\n"
        message += f"📅 *{t('date_created', lang)}:* {transaction_json.get('date_created', 'today')}\n"
        message += f"💳 *{t('payment_date', lang)}:* {payment_date.strftime('%Y-%m-%d')}\n"
        message += f"📝 *{t('description', lang)}:* {escape_markdown(transaction_json.get('description', 'N/A'))}\n"
        message += f"💵 *{t('amount', lang)}:* `{amount_str}`\n"
        message += f"🏦 *{t('account', lang)}:* {escape_markdown(transaction_json.get('account', 'N/A'))}\n"

        if transaction_json.get('category'):
            message += f"🏷️ *{t('category', lang)}:* {escape_markdown(transaction_json['category'])}\n"

        if transaction_json.get('budget'):
            message += f"📊 *{t('budget_label', lang)}:* {display_name(transaction_json['budget'])}\n"

        if transaction_json.get('is_pending'):
            message += f"\n⚠️ *Status:* {t('status_pending', lang)}\n"

        return message

    elif tx_type == 'installment':
        total = transaction_json.get('total_amount', 0)
        installments = transaction_json.get('installments', 1)
        per_installment = total / installments

        message = f"🔄 *{t('tx_installment_preview', lang)}*\n\n"
        message += f"📝 *{t('description', lang)}:* {escape_markdown(transaction_json.get('description', 'N/A'))}\n"
        message += f"💰 *{t('total_amount', lang)}:* `${abs(total):.2f}`\n"
        message += f"📊 *{t('installments', lang)}:* {installments} × ${per_installment:.2f}\n"
        message += f"📅 *{t('first_payment', lang)}:* {payment_date.strftime('%Y-%m-%d')}\n"
        message += f"🏦 *{t('account', lang)}:* {escape_markdown(transaction_json.get('account', 'N/A'))}\n"

        if transaction_json.get('category'):
            message += f"🏷️ *{t('category', lang)}:* {escape_markdown(transaction_json['category'])}\n"

        return message

    elif tx_type == 'split':
        message = f"✂️ *{t('tx_split_preview', lang)}*\n\n"
        message += f"📝 *{t('description', lang)}:* {escape_markdown(transaction_json.get('description', 'N/A'))}\n"
        message += f"📅 *{t('date_label', lang)}:* {transaction_json.get('date_created', 'today')}\n"
        message += f"🏦 *{t('account', lang)}:* {escape_markdown(transaction_json.get('account', 'N/A'))}\n\n"

        for i, split in enumerate(transaction_json.get('splits', []), 1):
            message += f"  *{i}.* ${abs(split.get('amount', 0)):.2f} - {escape_markdown(split.get('category', 'N/A'))}\n"

        return message

    return f"❌ {t('unknown_tx_type', lang)}"

def format_error_message(error_msg: str, lang: str = "en") -> str:
    """Format error messages for user display."""
    return f"❌ *{t('error_header', lang)}*\n\n{error_msg}\n\n{t('error_footer', lang)}"

def format_success_message(description: str, balance: float = None, lang: str = "en") -> str:
    """Format success confirmation."""
    message = f"✅ *{t('tx_saved', lang)}*\n\n📝 {escape_markdown(description)}"

    if balance is not None:
        message += f"\n\n💰 {t('current_balance', lang)}: ${balance:,.2f}"

    return message


def format_budget_envelopes(
    budget_data: List[Dict[str, Any]],
    target_month: date,
    lang: str = "en",
) -> str:
    """
    Format budget envelope view for a single month.

    Args:
        budget_data: List of dicts with name, allocated, spent, remaining, status
        target_month: First day of the month being displayed
        lang: Language code

    Returns:
        Formatted markdown string for Telegram
    """
    m_name = month_name(target_month.month, lang)
    month_str = f"{m_name} {target_month.year}"
    message = f"📊 *{t('budgets_title', lang)}: {month_str}*\n\n"

    if not budget_data:
        message += f"_{t('no_budgets', lang)}_\n"
        return message

    for b in sorted(budget_data, key=lambda x: x['name']):
        allocated = b['allocated']
        spent = b['spent']
        remaining = b['remaining']

        # Status emoji
        if remaining <= 0:
            emoji = "🔴"
        elif allocated > 0 and spent / allocated > 0.8:
            emoji = "🟡"
        else:
            emoji = "🟢"

        name = display_name(b['name'])
        status_tag = f" _({t('forecast_tag', lang)})_" if b['status'] == 'forecast' else ""

        message += f"{emoji} *{name}*{status_tag}\n"
        if remaining < 0:
            message += f"   ${spent:,.2f} of ${allocated:,.2f} | *${abs(remaining):,.2f} {t('over', lang)}*\n\n"
        else:
            message += f"   ${spent:,.2f} of ${allocated:,.2f} | *${remaining:,.2f} {t('left', lang)}*\n\n"

    return message


def _format_transaction_line(t_row: Dict[str, Any]) -> str:
    """Format a single transaction as a compact line."""
    dp = t_row['date_payed']
    date_str = dp.strftime('%b %d') if isinstance(dp, date) else str(dp)
    desc = escape_markdown(t_row.get('description', 'Unknown'))
    if len(desc) > 25:
        desc = desc[:22] + "..."
    amount = t_row['amount']
    amount_str = f"-${abs(amount):,.2f}" if amount < 0 else f"+${abs(amount):,.2f}"
    return f"{date_str} | {desc} | {amount_str}\n"


def format_planning_pending(
    pending: List[Dict[str, Any]],
    planning: List[Dict[str, Any]],
    month_str: str,
    lang: str = "en",
) -> str:
    """
    Format planning and pending transactions view.

    Args:
        pending: All pending transactions (any date)
        planning: Planning transactions for the target month
        month_str: Month description like "March 2026"
        lang: Language code

    Returns:
        Formatted markdown string for Telegram
    """
    message = ""

    # Pending: all dates, full detail
    message += f"⏳ *{t('pending_header', lang)}* ({len(pending)})\n"
    if pending:
        for tx in sorted(pending, key=lambda x: x['date_payed']):
            dp = tx['date_payed']
            date_str = dp.strftime('%b %d, %Y') if isinstance(dp, date) else str(dp)
            desc = escape_markdown(tx.get('description', 'Unknown'))
            amount = tx['amount']
            amount_str = f"-${abs(amount):,.2f}" if amount < 0 else f"+${abs(amount):,.2f}"
            acct = escape_markdown(tx.get('account', ''))
            message += f"• {desc} — `{amount_str}`\n   {date_str} | {acct}\n\n"
    else:
        message += f"_{t('none_label', lang)}_\n"

    message += "\n"

    # Planning: month-specific
    message += f"📋 *{t('planning_header', lang)}: {month_str}* ({len(planning)})\n"
    if planning:
        for tx in sorted(planning, key=lambda x: x['date_payed']):
            message += _format_transaction_line(tx)
    else:
        message += f"_{t('none_label', lang)}_\n"

    return message


def format_summary_navigation_buttons(
    current_month_date: date,
    show_planning: bool = False,
    lang: str = "en",
) -> InlineKeyboardMarkup:
    """
    Create navigation buttons for summary view.

    Args:
        current_month_date: Date object representing current displayed month (first day)
        show_planning: Whether currently showing planning/pending view
        lang: Language code

    Returns:
        InlineKeyboardMarkup with navigation and toggle buttons
    """
    # Calculate previous and next months
    prev_month = current_month_date - relativedelta(months=1)
    next_month = current_month_date + relativedelta(months=1)

    # Format callback data as YYYY-MM with view type
    month_fmt = current_month_date.strftime('%Y-%m')
    prev_callback = f"summary:{prev_month.strftime('%Y-%m')}:{'plan' if show_planning else 'budget'}"
    next_callback = f"summary:{next_month.strftime('%Y-%m')}:{'plan' if show_planning else 'budget'}"

    # Toggle button
    if show_planning:
        toggle_label = f"📊 {t('btn_budget_view', lang)}"
        toggle_callback = f"summary:{month_fmt}:budget"
    else:
        toggle_label = f"🔮 {t('btn_planning', lang)}"
        toggle_callback = f"summary:{month_fmt}:plan"

    keyboard = [
        [
            InlineKeyboardButton(f"⬅️ {t('btn_prev', lang)}", callback_data=prev_callback),
            InlineKeyboardButton(toggle_label, callback_data=toggle_callback),
            InlineKeyboardButton(f"{t('btn_next', lang)} ➡️", callback_data=next_callback),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def format_auto_confirm_message(
    request_json: Dict[str, Any],
    payment_date: date,
    budget_remaining: Optional[float] = None,
    budget_name: Optional[str] = None,
    budget_allocated: Optional[float] = None,
    lang: str = "en",
) -> str:
    """
    Compact reply for auto-confirmed (extra user) transactions.

    Shows date created -> payment date, description, amount,
    and optional budget remaining line with health emoji.
    """
    date_created = request_json.get('date_created', date.today().isoformat())
    dc = date.fromisoformat(date_created) if isinstance(date_created, str) else date_created
    dc_str = dc.strftime('%b %d')
    pd_str = payment_date.strftime('%b %d')

    amount = request_json.get('amount', 0)
    amount_str = f"+${abs(amount):.2f}" if request_json.get('is_income') else f"-${abs(amount):.2f}"

    desc = escape_markdown(request_json.get('description', 'N/A'))

    msg = f"✅ {t('saved', lang)}\n"
    msg += f"📅 {dc_str} → {pd_str}\n"
    msg += f"📝 {desc}\n"
    msg += f"💵 {amount_str}\n"

    if budget_remaining is not None and budget_name is not None:
        bname = display_name(budget_name)
        allocated = budget_allocated or 0
        spent = allocated - budget_remaining
        if budget_remaining <= 0:
            emoji = "🔴"
        elif allocated > 0 and spent / allocated > 0.8:
            emoji = "🟡"
        else:
            emoji = "🟢"
        msg += f"{emoji} {bname}: *${budget_remaining:,.2f} {t('remaining', lang)}*\n"

    return msg


def format_summary_navigation_buttons_simple(
    current_month_date: date,
    lang: str = "en",
) -> InlineKeyboardMarkup:
    """
    Simplified navigation buttons for extra users — prev/next only, no planning toggle.
    Uses the same callback format so the existing handler works unchanged.
    """
    prev_month = current_month_date - relativedelta(months=1)
    next_month = current_month_date + relativedelta(months=1)

    prev_callback = f"summary:{prev_month.strftime('%Y-%m')}:budget"
    next_callback = f"summary:{next_month.strftime('%Y-%m')}:budget"

    keyboard = [
        [
            InlineKeyboardButton(f"⬅️ {t('btn_prev', lang)}", callback_data=prev_callback),
            InlineKeyboardButton(f"{t('btn_next', lang)} ➡️", callback_data=next_callback),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def parse_month_from_args(args: str) -> Optional[date]:
    """
    Parse month from command arguments.

    Supports formats:
    - Month names: "October", "oct", "november" (English + Spanish)
    - Explicit: "2024-10", "Oct 2024"

    Args:
        args: Command arguments string

    Returns:
        Date object set to first day of month, or None if unparseable
    """
    import re
    from datetime import datetime

    if not args:
        return None

    args = args.strip().lower()

    # Month name mapping (English + Spanish)
    month_names = {
        # English
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
        # Spanish
        'ene': 1, 'enero': 1,
        'febrero': 2,
        'marzo': 3,
        'abr': 4, 'abril': 4,
        'mayo': 5,
        'junio': 6,
        'julio': 7,
        'ago': 8, 'agosto': 8,
        'septiembre': 9,
        'octubre': 10,
        'noviembre': 11,
        'dic': 12, 'diciembre': 12,
    }

    # Try format: YYYY-MM
    match = re.match(r'^(\d{4})-(\d{1,2})$', args)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)

    # Try format: "Month YYYY" or "Month"
    current_year = date.today().year

    # Match month name with optional year
    match = re.match(r'^([a-z]+)\s*(\d{4})?$', args)
    if match:
        month_str = match.group(1)
        year_str = match.group(2)

        if month_str in month_names:
            month = month_names[month_str]
            year = int(year_str) if year_str else current_year
            return date(year, month, 1)

    return None

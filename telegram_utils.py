from typing import Dict, Any
from datetime import date

def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters for Telegram.

    Telegram MarkdownV1 special characters: _ * ` [
    """
    if not text:
        return text
    # Escape special characters
    text = str(text)
    text = text.replace('_', r'\_')
    text = text.replace('*', r'\*')
    text = text.replace('`', r'\`')
    text = text.replace('[', r'\[')
    return text

def format_transaction_preview(
    transaction_json: Dict[str, Any],
    payment_date: date
) -> str:
    """Format transaction as Telegram message with emoji and formatting."""

    tx_type = transaction_json.get('type', 'simple')

    if tx_type == 'simple':
        amount = transaction_json.get('amount', 0)
        amount_str = f"+${abs(amount):.2f}" if transaction_json.get('is_income') else f"-${abs(amount):.2f}"

        status_emoji = "⏳" if transaction_json.get('is_pending') else "💰"

        message = f"{status_emoji} *Transaction Preview*\n\n"
        message += f"📅 *Date Created:* {transaction_json.get('date_created', 'today')}\n"
        message += f"💳 *Payment Date:* {payment_date.strftime('%Y-%m-%d')}\n"
        message += f"📝 *Description:* {escape_markdown(transaction_json.get('description', 'N/A'))}\n"
        message += f"💵 *Amount:* `{amount_str}`\n"
        message += f"🏦 *Account:* {escape_markdown(transaction_json.get('account', 'N/A'))}\n"

        if transaction_json.get('category'):
            message += f"🏷️ *Category:* {escape_markdown(transaction_json['category'])}\n"

        if transaction_json.get('budget'):
            message += f"📊 *Budget:* {escape_markdown(transaction_json['budget'])}\n"

        if transaction_json.get('is_pending'):
            message += f"\n⚠️ *Status:* Pending (won't affect balance until cleared)\n"

        return message

    elif tx_type == 'installment':
        total = transaction_json.get('total_amount', 0)
        installments = transaction_json.get('installments', 1)
        per_installment = total / installments

        message = f"🔄 *Installment Transaction Preview*\n\n"
        message += f"📝 *Description:* {escape_markdown(transaction_json.get('description', 'N/A'))}\n"
        message += f"💰 *Total Amount:* `${abs(total):.2f}`\n"
        message += f"📊 *Installments:* {installments} × ${per_installment:.2f}\n"
        message += f"📅 *First Payment:* {payment_date.strftime('%Y-%m-%d')}\n"
        message += f"🏦 *Account:* {escape_markdown(transaction_json.get('account', 'N/A'))}\n"

        if transaction_json.get('category'):
            message += f"🏷️ *Category:* {escape_markdown(transaction_json['category'])}\n"

        return message

    elif tx_type == 'split':
        message = f"✂️ *Split Transaction Preview*\n\n"
        message += f"📝 *Description:* {escape_markdown(transaction_json.get('description', 'N/A'))}\n"
        message += f"📅 *Date:* {transaction_json.get('date_created', 'today')}\n"
        message += f"🏦 *Account:* {escape_markdown(transaction_json.get('account', 'N/A'))}\n\n"

        for i, split in enumerate(transaction_json.get('splits', []), 1):
            message += f"  *{i}.* ${abs(split.get('amount', 0)):.2f} - {escape_markdown(split.get('category', 'N/A'))}\n"

        return message

    return "❌ Unknown transaction type"

def format_error_message(error_msg: str) -> str:
    """Format error messages for user display."""
    return f"❌ *Error*\n\n{error_msg}\n\nPlease try again or type /help for assistance."

def format_success_message(description: str, balance: float = None) -> str:
    """Format success confirmation."""
    message = f"✅ *Transaction Saved!*\n\n📝 {escape_markdown(description)}"

    if balance is not None:
        message += f"\n\n💰 Current balance: ${balance:,.2f}"

    return message

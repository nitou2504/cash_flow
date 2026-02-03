import logging
import asyncio
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from database import create_connection, initialize_database
import repository
import llm_parser
import main as controller
import transactions as tx_module
from telegram_utils import (
    format_transaction_preview,
    format_error_message,
    format_success_message,
)
from bot_config import TELEGRAM_BOT_TOKEN, DB_PATH

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global database connection (initialized on startup)
db_conn = None


# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_text = (
        "👋 *Welcome to Cash Flow Bot!*\n\n"
        "I help you track expenses easily. Just send me a message like:\n\n"
        "💬 _\"Spent 50 on groceries today\"_\n"
        "💬 _\"Bought laptop for 1200 in 12 installments on Visa\"_\n"
        "💬 _\"Income 3000 on Cash\"_\n\n"
        "I'll parse it, show you a preview, and you can confirm or revise before saving.\n\n"
        "Commands:\n"
        "/help - Show this help message\n"
        "/cancel - Cancel current transaction"
    )

    await update.message.reply_text(welcome_text, parse_mode='Markdown')

    # Clear any pending state
    context.user_data.clear()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "📖 *How to Use Cash Flow Bot*\n\n"
        "*Adding Expenses:*\n"
        "Just send a natural language message:\n"
        "• \"Spent 45.50 on groceries\"\n"
        "• \"Bought TV for 600 in 12 installments\"\n"
        "• \"Split purchase: 30 on groceries, 15 on snacks\"\n\n"
        "*Confirmation:*\n"
        "I'll show a preview with buttons:\n"
        "• ✅ Confirm - Save the transaction\n"
        "• ✍️ Revise - Make corrections\n\n"
        "*Making Corrections:*\n"
        "After clicking Revise, tell me what to change:\n"
        "• \"Actually it was 45.50 on Visa\"\n"
        "• \"Change category to entertainment\"\n\n"
        "*Commands:*\n"
        "/start - Restart bot\n"
        "/cancel - Cancel current transaction"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    context.user_data.clear()
    await update.message.reply_text(
        "🛑 Current transaction cancelled.",
        parse_mode='Markdown'
    )


# ==================== MESSAGE PROCESSING ====================

async def process_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text messages (expense descriptions or corrections)."""
    user_message = update.message.text
    chat_id = update.effective_chat.id

    # Check if awaiting correction
    if context.user_data.get('awaiting_correction'):
        await handle_correction(update, context, user_message)
    else:
        await handle_new_expense(update, context, user_message)


async def handle_new_expense(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str):
    """Parse a new expense description and show preview."""
    chat_id = update.effective_chat.id

    # Show processing indicator
    processing_msg = await update.message.reply_text("🔄 Processing...", parse_mode='Markdown')

    try:
        # Get accounts and budgets for parsing context
        accounts = repository.get_all_accounts(db_conn)
        budgets = repository.get_all_budgets(db_conn)

        if not accounts:
            await processing_msg.edit_text(
                format_error_message("No accounts found. Please set up accounts via CLI first."),
                parse_mode='Markdown'
            )
            return

        # Calculate payment month for budget filtering
        payment_month = tx_module.calculate_payment_month(user_message, accounts)

        # Full parse
        request_json = llm_parser.parse_transaction_string(
            db_conn, user_message, accounts, budgets, payment_month
        )

        if not request_json:
            await processing_msg.edit_text(
                format_error_message("I couldn't understand that. Please try rephrasing."),
                parse_mode='Markdown'
            )
            return

        # Calculate payment date for preview
        trans_date = date.fromisoformat(request_json.get('date_created', date.today().isoformat()))
        account = next((a for a in accounts if a['account_id'] == request_json.get('account')), None)

        if account:
            payment_date = tx_module.simulate_payment_date(account, trans_date)
        else:
            payment_date = trans_date

        # Format preview message
        preview_text = format_transaction_preview(request_json, payment_date)

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm"),
                InlineKeyboardButton("✍️ Revise", callback_data="revise"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Store pending transaction
        context.user_data['pending_transaction'] = request_json
        context.user_data['original_message'] = user_message
        context.user_data['awaiting_correction'] = False

        # Send preview
        preview_msg = await processing_msg.edit_text(
            preview_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        context.user_data['preview_message_id'] = preview_msg.message_id

    except ValueError as e:
        await processing_msg.edit_text(
            format_error_message(str(e)),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error processing expense: {e}", exc_info=True)
        await processing_msg.edit_text(
            format_error_message("An unexpected error occurred. Please try again."),
            parse_mode='Markdown'
        )


async def handle_correction(update: Update, context: ContextTypes.DEFAULT_TYPE, correction_text: str):
    """Process user correction and re-parse."""
    chat_id = update.effective_chat.id

    # Show processing indicator
    processing_msg = await update.message.reply_text("🔄 Updating...", parse_mode='Markdown')

    try:
        # Combine original message + correction for re-parsing
        original = context.user_data.get('original_message', '')
        combined_input = f"{original}. Change: {correction_text}"

        # Re-parse with correction context
        accounts = repository.get_all_accounts(db_conn)
        budgets = repository.get_all_budgets(db_conn)

        # Calculate payment month for budget filtering (same as initial parse)
        payment_month = tx_module.calculate_payment_month(combined_input, accounts)

        request_json = llm_parser.parse_transaction_string(
            db_conn, combined_input, accounts, budgets, payment_month
        )

        if not request_json:
            await processing_msg.edit_text(
                format_error_message("I couldn't apply that correction. Please try rephrasing."),
                parse_mode='Markdown'
            )
            return

        # Calculate payment date
        trans_date = date.fromisoformat(request_json.get('date_created', date.today().isoformat()))
        account = next((a for a in accounts if a['account_id'] == request_json.get('account')), None)
        payment_date = tx_module.simulate_payment_date(account, trans_date) if account else trans_date

        # Format updated preview
        preview_text = format_transaction_preview(request_json, payment_date)

        # Create keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm"),
                InlineKeyboardButton("✍️ Revise", callback_data="revise"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Update state
        context.user_data['pending_transaction'] = request_json
        context.user_data['awaiting_correction'] = False

        # Delete processing message and send new preview
        await processing_msg.delete()

        preview_msg = await update.message.reply_text(
            preview_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        context.user_data['preview_message_id'] = preview_msg.message_id

    except Exception as e:
        logger.error(f"Error processing correction: {e}", exc_info=True)
        await processing_msg.edit_text(
            format_error_message("An error occurred while updating. Please try again."),
            parse_mode='Markdown'
        )


# ==================== BUTTON CALLBACK HANDLER ====================

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks."""
    query = update.callback_query
    await query.answer()  # Acknowledge button click

    callback_data = query.data

    if callback_data == "confirm":
        await handle_confirm(query, context)
    elif callback_data == "revise":
        await handle_revise(query, context)


async def handle_confirm(query, context: ContextTypes.DEFAULT_TYPE):
    """Save the transaction to database."""
    try:
        pending_tx = context.user_data.get('pending_transaction')

        if not pending_tx:
            await query.edit_message_text(
                format_error_message("No pending transaction found. Please start over."),
                parse_mode='Markdown'
            )
            return

        # Process transaction
        trans_date = None
        if "date_created" in pending_tx:
            trans_date = date.fromisoformat(pending_tx["date_created"])

        controller.process_transaction_request(db_conn, pending_tx, transaction_date=trans_date)

        # Get updated balance (optional - could query from DB)
        # For now, just show success without balance
        success_msg = format_success_message(pending_tx.get('description', 'Transaction'))

        # Edit message to show success (remove buttons)
        await query.edit_message_text(
            success_msg,
            parse_mode='Markdown'
        )

        # Clear state
        context.user_data.clear()

    except ValueError as e:
        await query.edit_message_text(
            format_error_message(str(e)),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error saving transaction: {e}", exc_info=True)
        await query.edit_message_text(
            format_error_message("Failed to save transaction. Please try again."),
            parse_mode='Markdown'
        )


async def handle_revise(query, context: ContextTypes.DEFAULT_TYPE):
    """Enable correction mode."""
    # Remove buttons and prompt for correction
    await query.edit_message_reply_markup(reply_markup=None)

    await query.message.reply_text(
        "✍️ *What would you like to change?*\n\n"
        "Tell me in natural language, like:\n"
        "• \"Change amount to 45.50\"\n"
        "• \"Use Visa card instead\"\n"
        "• \"Change category to entertainment\"",
        parse_mode='Markdown'
    )

    # Set flag to await correction
    context.user_data['awaiting_correction'] = True


# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and notify user."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again or contact support.",
            parse_mode='Markdown'
        )


# ==================== MAIN ====================

def main():
    """Start the bot."""
    global db_conn

    # Initialize database
    initialize_database(DB_PATH)
    db_conn = create_connection(DB_PATH)

    # Run monthly rollover (sync state)
    controller.run_monthly_rollover(db_conn, date.today())

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_message))

    # Register error handler
    application.add_error_handler(error_handler)

    # Start bot
    logger.info("Bot starting...")

    # Python 3.10+ compatibility: explicitly create event loop
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

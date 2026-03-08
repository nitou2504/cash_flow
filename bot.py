import logging
import asyncio
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from cashflow.database import create_connection, initialize_database
from cashflow import repository
from llm import parser as llm_parser
from cashflow import controller
from cashflow import transactions as tx_module
from ui.telegram_format import (
    format_transaction_preview,
    format_error_message,
    format_success_message,
    format_budget_envelopes,
    format_planning_pending,
    format_summary_navigation_buttons,
    parse_month_from_args,
)
from cashflow.config import (
    TELEGRAM_BOT_TOKEN, DB_PATH, TELEGRAM_ALLOWED_USERS, TELEGRAM_EXTRA_USERS,
    BACKUP_ENABLED, BACKUP_DIR, BACKUP_KEEP_TODAY, BACKUP_RECENT_DAYS, BACKUP_MAX_DAYS,
    BACKUP_LOG_RETENTION_DAYS,
)
from cashflow import backup as db_backup

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global database connection (initialized on startup)
db_conn = None


# ==================== AUTH ====================

def is_authorized(update: Update) -> bool:
    """Check if the user is in the allowlist or extra users. Empty allowlist = open access."""
    if not TELEGRAM_ALLOWED_USERS:
        return True
    user_id = update.effective_user.id if update.effective_user else None
    return user_id in TELEGRAM_ALLOWED_USERS or user_id in TELEGRAM_EXTRA_USERS


def get_extra_user_info(update: Update) -> dict | None:
    """Returns extra user config if the sender is an extra user, None otherwise."""
    user_id = update.effective_user.id if update.effective_user else None
    return TELEGRAM_EXTRA_USERS.get(user_id)


async def reject_unauthorized(update: Update):
    """Send rejection message and log the attempt."""
    user = update.effective_user
    logger.warning(f"Unauthorized access attempt from user {user.id} (@{user.username})")
    if update.effective_message:
        await update.effective_message.reply_text("You are not authorized to use this bot.")


# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    welcome_text = (
        "👋 *Welcome to Cash Flow Bot!*\n\n"
        "I help you track expenses easily. Just send me a message like:\n\n"
        "💬 _\"Spent 50 on groceries today\"_\n"
        "💬 _\"Bought laptop for 1200 in 12 installments on Visa\"_\n"
        "💬 _\"Income 3000 on Cash\"_\n\n"
        "I'll parse it, show you a preview, and you can confirm or revise before saving.\n\n"
        "Commands:\n"
        "/help - Show help message\n"
        "/summary - View monthly summary\n"
        "/cancel - Cancel current transaction"
    )

    await update.message.reply_text(welcome_text, parse_mode='Markdown')

    # Clear any pending state
    context.user_data.clear()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

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
        "/help - Show this help message\n"
        "/summary - View last 3 months summary\n"
        "/summary [month] - View specific month (e.g., /summary October)\n"
        "/cancel - Cancel current transaction"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    context.user_data.clear()
    await update.message.reply_text(
        "🛑 Current transaction cancelled.",
        parse_mode='Markdown'
    )


# ==================== MESSAGE PROCESSING ====================

async def process_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text messages (expense descriptions or corrections)."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

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

        # Inject extra user defaults
        extra_user = get_extra_user_info(update)
        if extra_user:
            request_json["source"] = extra_user["name"]
            request_json["needs_review"] = True
            # Set account if LLM didn't pick one or picked the default
            if not request_json.get("account") or request_json["account"] == accounts[0]["account_id"]:
                request_json["account"] = extra_user["account"]
            # Resolve budget name to active budget period
            budget_name = extra_user["budget"]
            matched_budget = next(
                (b["id"] for b in budgets if b["name"].lower() == budget_name.lower()),
                None,
            )
            if matched_budget and not request_json.get("budget"):
                request_json["budget"] = matched_budget

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
    if not is_authorized(update):
        return await reject_unauthorized(update)

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

        # Auto-backup before mutating
        if BACKUP_ENABLED:
            db_backup.auto_backup(DB_PATH, BACKUP_DIR, BACKUP_KEEP_TODAY, BACKUP_RECENT_DAYS,
                                     BACKUP_MAX_DAYS, operation="telegram add",
                                     log_retention_days=BACKUP_LOG_RETENTION_DAYS)

        # Process transaction
        trans_date = None
        if "date_created" in pending_tx:
            trans_date = date.fromisoformat(pending_tx["date_created"])

        original_input = context.user_data.get('original_message', '')
        controller.process_transaction_request(db_conn, pending_tx, transaction_date=trans_date, user_input=original_input, source="telegram")

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


# ==================== SUMMARY VIEW HANDLERS ====================

def get_balance_at_date(
    transactions: list,
    target_date: date
) -> float:
    """
    Get running balance at end of target_date.

    Args:
        transactions: List of transaction dicts with running_balance field
        target_date: Date to get balance for

    Returns:
        Running balance at end of date, or 0.0 if no transactions
    """
    relevant = [t for t in transactions if t['date_payed'] <= target_date]
    if relevant:
        # Transactions already sorted by date_payed
        return relevant[-1]['running_balance']
    return 0.0


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /summary [month] command."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    target_month = None
    if context.args:
        args_str = ' '.join(context.args)
        target_month = parse_month_from_args(args_str)

    if target_month is None:
        today = date.today()
        target_month = date(today.year, today.month, 1)

    await handle_summary_request(update, context, target_month, from_callback=False)


async def handle_summary_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_month: date,
    show_planning: bool = False,
    from_callback: bool = False
):
    """
    Unified handler for summary requests showing a single month.

    Args:
        update: Telegram update object
        context: Context object
        target_month: First day of month to display
        show_planning: If True, show planning/pending view; if False, show budget envelope view
        from_callback: True if called from button callback
    """
    try:
        if from_callback:
            await update.callback_query.answer("Loading...")
        else:
            processing_msg = await update.message.reply_text("🔄 Loading...", parse_mode='Markdown')

        period_end = (target_month + relativedelta(months=1)) - timedelta(days=1)

        if show_planning:
            all_transactions = repository.get_transactions_with_running_balance(db_conn)
            all_pending = []
            month_planning = []
            for t in all_transactions:
                dp = t['date_payed']
                if isinstance(dp, str):
                    dp = date.fromisoformat(dp)
                t['date_payed'] = dp
                if t.get('status') == 'pending':
                    all_pending.append(t)
                elif t.get('status') == 'planning' and target_month <= dp <= period_end:
                    month_planning.append(t)
            message_text = format_planning_pending(
                all_pending, month_planning, target_month.strftime('%B %Y')
            )
        else:
            # Budget envelope view using repository functions
            all_budgets = repository.get_all_budgets(db_conn)
            budget_data = []

            for budget in all_budgets:
                allocation = repository.get_budget_allocation_for_month(
                    db_conn, budget['id'], target_month
                )
                if not allocation:
                    continue

                spent = repository.get_total_spent_for_budget_in_month(
                    db_conn, budget['id'], target_month
                )
                allocated = budget['monthly_amount']
                remaining = allocated - spent

                budget_data.append({
                    'name': budget['name'],
                    'allocated': allocated,
                    'spent': spent,
                    'remaining': remaining,
                    'status': allocation['status'],
                })

            message_text = format_budget_envelopes(budget_data, target_month)

        buttons = format_summary_navigation_buttons(target_month, show_planning)

        if from_callback:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=buttons,
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                message_text,
                reply_markup=buttons,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        error_msg = format_error_message("Failed to generate summary. Please try again.")

        if from_callback:
            await update.callback_query.edit_message_text(
                error_msg,
                parse_mode='Markdown'
            )
        else:
            if 'processing_msg' in locals():
                await processing_msg.edit_text(error_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(error_msg, parse_mode='Markdown')


async def summary_navigation_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Handle month navigation and view toggle button clicks."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    query = update.callback_query
    await query.answer()  # Acknowledge button click

    callback_data = query.data
    parts = callback_data.split(':')

    if len(parts) < 2:
        await query.edit_message_text(
            format_error_message("Invalid callback format."),
            parse_mode='Markdown'
        )
        return

    month_str = parts[1]
    view_type = parts[2] if len(parts) > 2 else "budget"

    try:
        year, month = map(int, month_str.split('-'))
        target_month = date(year, month, 1)
        show_planning = (view_type == "plan")

        await handle_summary_request(
            update, context, target_month,
            show_planning=show_planning,
            from_callback=True
        )

    except Exception as e:
        logger.error(f"Error parsing navigation callback: {e}", exc_info=True)
        await query.edit_message_text(
            format_error_message("Invalid selection. Please try again."),
            parse_mode='Markdown'
        )


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

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in .env")

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
    application.add_handler(CommandHandler("summary", summary_command))

    # Summary navigation (must come BEFORE generic CallbackQueryHandler)
    application.add_handler(CallbackQueryHandler(
        summary_navigation_callback,
        pattern=r'^summary:\d{4}-\d{2}(:(budget|plan))?$'
    ))

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

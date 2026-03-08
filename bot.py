import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
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
    format_summary_navigation_buttons_simple,
    format_auto_confirm_message,
    format_review_card,
    format_review_diff,
    format_review_buttons,
    format_review_confirm_buttons,
    parse_month_from_args,
    month_name,
)
from ui.strings import t, LANG_DISPLAY_NAMES
from cashflow.config import (
    TELEGRAM_BOT_TOKEN, DB_PATH, TELEGRAM_ALLOWED_USERS, TELEGRAM_EXTRA_USERS,
    TELEGRAM_AUTO_CONFIRM, TELEGRAM_DEFAULT_LANG,
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


def get_user_lang(update: Update) -> str:
    """DB setting > env default > 'en'."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        stored = repository.get_setting(db_conn, f"lang:{user_id}")
        if stored in ("en", "es"):
            return stored
    return TELEGRAM_DEFAULT_LANG


async def reject_unauthorized(update: Update):
    """Send rejection message and log the attempt."""
    user = update.effective_user
    logger.warning(f"Unauthorized access attempt from user {user.id} (@{user.username})")
    if update.effective_message:
        lang = get_user_lang(update)
        await update.effective_message.reply_text(t("unauthorized", lang))


def should_auto_confirm(extra_user: dict | None) -> bool:
    """Check if the current transaction should skip the confirm/revise flow."""
    if TELEGRAM_AUTO_CONFIRM == "all":
        return True
    if TELEGRAM_AUTO_CONFIRM == "extra_users_only" and extra_user is not None:
        return True
    return False


def _describe_telegram_op(action: str, request_json: dict = None, tx: dict = None,
                          extra_user: dict = None, changes: dict = None) -> str:
    """Build a descriptive operation string for backup logs."""
    parts = [f"telegram {action}"]
    if extra_user:
        parts.append(f"[{extra_user['name']}]")
    source = request_json or tx
    if source:
        desc = source.get('description', '')
        amount = source.get('amount', 0)
        if desc:
            parts.append(desc)
        if amount:
            parts.append(f"${abs(amount):.2f}")
    if changes:
        edits = [f"{k}→{v}" for k, v in changes.items()]
        parts.append(f"({', '.join(edits)})")
    return " ".join(parts)[:120]


def _get_budget_remaining(budget_id: str, payment_date: date) -> tuple[float | None, str | None, float | None]:
    """Return (remaining_amount, display_name, allocated) for a budget in the payment month."""
    if not budget_id:
        return None, None, None
    budget_sub = repository.get_subscription_by_id(db_conn, budget_id)
    if not budget_sub:
        return None, None, None
    payment_month = payment_date.replace(day=1)
    spent = repository.get_total_spent_for_budget_in_month(db_conn, budget_id, payment_month)
    allocated = budget_sub['monthly_amount']
    remaining = allocated - spent
    return remaining, budget_sub['name'], allocated


# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    lang = get_user_lang(update)

    welcome_text = (
        f"👋 *{t('welcome_header', lang)}*\n\n"
        + t("welcome", lang,
            example_simple='💬 _"Spent 50 on groceries today"_',
            example_installment='💬 _"Bought laptop for 1200 in 12 installments on Visa"_',
            example_income='💬 _"Income 3000 on Cash"_',
        )
    )

    await update.message.reply_text(welcome_text, parse_mode='Markdown')

    # Clear any pending state
    context.user_data.clear()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    lang = get_user_lang(update)
    extra_user = get_extra_user_info(update)

    help_text = f"📖 *{t('help_header', lang)}*\n\n{t('help_adding', lang)}\n\n"

    if should_auto_confirm(extra_user):
        help_text += t("help_confirm_auto", lang) + "\n\n"
    else:
        help_text += t("help_confirm_manual", lang,
                       btn_confirm="✅", btn_revise="✍️") + "\n\n"

    help_text += t("help_commands", lang)

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    lang = get_user_lang(update)
    context.user_data.clear()
    await update.message.reply_text(
        f"🛑 {t('cancel', lang)}",
        parse_mode='Markdown'
    )


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /lang command — show current language and choice buttons."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    lang = get_user_lang(update)
    lang_name = LANG_DISPLAY_NAMES.get(lang, lang)

    keyboard = [
        [
            InlineKeyboardButton("English", callback_data="lang:en"),
            InlineKeyboardButton("Español", callback_data="lang:es"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = t("lang_current", lang, lang_name=lang_name) + "\n\n" + t("lang_choose", lang)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection button clicks."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    query = update.callback_query
    await query.answer()

    new_lang = query.data.split(":")[1]
    user_id = update.effective_user.id

    repository.set_setting(db_conn, f"lang:{user_id}", new_lang)

    lang_name = LANG_DISPLAY_NAMES.get(new_lang, new_lang)
    await query.edit_message_text(
        t("lang_switched", new_lang, lang_name=lang_name),
        parse_mode='Markdown'
    )


# ==================== MESSAGE PROCESSING ====================

async def process_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text messages (expense descriptions or corrections)."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    user_message = update.message.text
    chat_id = update.effective_chat.id

    # Check if in review edit mode first
    if context.user_data.get('review_state') == 'editing':
        await handle_review_edit_input(update, context, user_message)
    # Check if awaiting correction
    elif context.user_data.get('awaiting_correction'):
        await handle_correction(update, context, user_message)
    else:
        await handle_new_expense(update, context, user_message)


async def handle_new_expense(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str):
    """Parse a new expense description and show preview."""
    chat_id = update.effective_chat.id
    lang = get_user_lang(update)

    # Show processing indicator
    processing_msg = await update.message.reply_text(f"🔄 {t('processing', lang)}", parse_mode='Markdown')

    try:
        # Get accounts and budgets for parsing context
        accounts = repository.get_all_accounts(db_conn)
        budgets = repository.get_all_budgets(db_conn)

        if not accounts:
            await processing_msg.edit_text(
                format_error_message(t("error_no_accounts", lang), lang),
                parse_mode='Markdown'
            )
            return

        # For extra users, append only their account so the LLM resolves
        # the correct payment date. Budget is set in code after parsing
        # to avoid the LLM conflating budget name with category.
        extra_user = get_extra_user_info(update)
        llm_message = user_message
        if extra_user:
            llm_message = f"{user_message}, {extra_user['account']}"

        # Calculate payment month for budget filtering
        payment_month = tx_module.calculate_payment_month(llm_message, accounts)

        # Full parse — run no-budget check in parallel if configured
        no_budget_phrase = extra_user.get('no_budget_phrase') if extra_user else None
        if no_budget_phrase:
            loop = asyncio.get_event_loop()
            parse_future = loop.run_in_executor(
                None, llm_parser.parse_transaction_string,
                db_conn, llm_message, accounts, budgets, payment_month
            )
            no_budget_future = loop.run_in_executor(
                None, llm_parser.check_no_budget,
                user_message, no_budget_phrase
            )
            request_json, skip_budget = await asyncio.gather(parse_future, no_budget_future)
        else:
            request_json = llm_parser.parse_transaction_string(
                db_conn, llm_message, accounts, budgets, payment_month
            )
            skip_budget = False

        if not request_json:
            await processing_msg.edit_text(
                format_error_message(t("error_parse_failed", lang), lang),
                parse_mode='Markdown'
            )
            return

        # Tag extra user transactions for review
        if extra_user:
            request_json["source"] = extra_user["name"]
            request_json["needs_review"] = True

        # Calculate payment date for preview
        trans_date = date.fromisoformat(request_json.get('date_created', date.today().isoformat()))
        account = next((a for a in accounts if a['account_id'] == request_json.get('account')), None)

        if account:
            payment_date = tx_module.simulate_payment_date(account, trans_date)
        else:
            payment_date = trans_date

        # Resolve budget for extra users by matching their configured
        # budget prefix to the active budget for the payment month
        if extra_user and extra_user.get('budget') and not skip_budget:
            prefix = extra_user['budget'].lower()
            payment_month = payment_date.replace(day=1)
            best_budget = None
            for b in budgets:
                if not b['name'].lower().startswith(prefix):
                    continue
                start = date.fromisoformat(str(b['start_date'])) if b.get('start_date') else date.min
                end = date.fromisoformat(str(b['end_date'])) if b.get('end_date') else date.max
                if start <= payment_month <= end:
                    best_budget = b['id']
                    break
            if best_budget:
                request_json['budget'] = best_budget

        # Auto-confirm for extra users (or all, depending on config)
        if should_auto_confirm(extra_user):
            if BACKUP_ENABLED:
                op = _describe_telegram_op("add", request_json=request_json, extra_user=extra_user)
                db_backup.auto_backup(DB_PATH, BACKUP_DIR, BACKUP_KEEP_TODAY, BACKUP_RECENT_DAYS,
                                         BACKUP_MAX_DAYS, operation=op,
                                         log_retention_days=BACKUP_LOG_RETENTION_DAYS)
            controller.process_transaction_request(
                db_conn, request_json, transaction_date=trans_date,
                user_input=user_message, source="telegram"
            )
            budget_remaining, budget_name, budget_allocated = _get_budget_remaining(
                request_json.get('budget'), payment_date
            )
            reply = format_auto_confirm_message(
                request_json, payment_date, budget_remaining, budget_name, budget_allocated, lang=lang
            )
            await processing_msg.edit_text(reply, parse_mode='Markdown')

            # Notify the owner about extra user transactions
            if extra_user and TELEGRAM_ALLOWED_USERS:
                owner_id = next(iter(TELEGRAM_ALLOWED_USERS))
                amount = request_json.get('amount', 0)
                amount_str = f"+${abs(amount):.2f}" if request_json.get('is_income') else f"-${abs(amount):.2f}"
                # Use owner's language preference
                owner_lang = repository.get_setting(db_conn, f"lang:{owner_id}") or TELEGRAM_DEFAULT_LANG
                notify_text = t("extra_user_notify", owner_lang,
                    source=extra_user['name'].title(),
                    description=request_json.get('description', 'N/A'),
                    amount=amount_str,
                )
                try:
                    await context.bot.send_message(
                        chat_id=owner_id, text=notify_text, parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify owner {owner_id}: {e}")

            return

        # Format preview message
        preview_text = format_transaction_preview(request_json, payment_date, lang=lang)

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton(f"✅ {t('btn_confirm', lang)}", callback_data="confirm"),
                InlineKeyboardButton(f"✍️ {t('btn_revise', lang)}", callback_data="revise"),
                InlineKeyboardButton(f"🛑 {t('btn_cancel', lang)}", callback_data="cancel"),
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
            format_error_message(str(e), lang),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error processing expense: {e}", exc_info=True)
        await processing_msg.edit_text(
            format_error_message(t("error_unexpected", lang), lang),
            parse_mode='Markdown'
        )


async def handle_correction(update: Update, context: ContextTypes.DEFAULT_TYPE, correction_text: str):
    """Process user correction and re-parse."""
    chat_id = update.effective_chat.id
    lang = get_user_lang(update)

    # Show processing indicator
    processing_msg = await update.message.reply_text(f"🔄 {t('updating', lang)}", parse_mode='Markdown')

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
                format_error_message(t("error_correction_failed", lang), lang),
                parse_mode='Markdown'
            )
            return

        # Calculate payment date
        trans_date = date.fromisoformat(request_json.get('date_created', date.today().isoformat()))
        account = next((a for a in accounts if a['account_id'] == request_json.get('account')), None)
        payment_date = tx_module.simulate_payment_date(account, trans_date) if account else trans_date

        # Format updated preview
        preview_text = format_transaction_preview(request_json, payment_date, lang=lang)

        # Create keyboard
        keyboard = [
            [
                InlineKeyboardButton(f"✅ {t('btn_confirm', lang)}", callback_data="confirm"),
                InlineKeyboardButton(f"✍️ {t('btn_revise', lang)}", callback_data="revise"),
                InlineKeyboardButton(f"🛑 {t('btn_cancel', lang)}", callback_data="cancel"),
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
            format_error_message(t("error_correction_update", lang), lang),
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
        await handle_confirm(update, query, context)
    elif callback_data == "revise":
        await handle_revise(update, query, context)
    elif callback_data == "cancel":
        lang = get_user_lang(update)
        context.user_data.clear()
        await query.edit_message_text(f"🛑 {t('cancel', lang)}", parse_mode='Markdown')


async def handle_confirm(update: Update, query, context: ContextTypes.DEFAULT_TYPE):
    """Save the transaction to database."""
    lang = get_user_lang(update)
    try:
        pending_tx = context.user_data.get('pending_transaction')

        if not pending_tx:
            await query.edit_message_text(
                format_error_message(t("error_no_pending", lang), lang),
                parse_mode='Markdown'
            )
            return

        # Auto-backup before mutating
        if BACKUP_ENABLED:
            op = _describe_telegram_op("add", request_json=pending_tx)
            db_backup.auto_backup(DB_PATH, BACKUP_DIR, BACKUP_KEEP_TODAY, BACKUP_RECENT_DAYS,
                                     BACKUP_MAX_DAYS, operation=op,
                                     log_retention_days=BACKUP_LOG_RETENTION_DAYS)

        # Process transaction
        trans_date = None
        if "date_created" in pending_tx:
            trans_date = date.fromisoformat(pending_tx["date_created"])

        original_input = context.user_data.get('original_message', '')
        controller.process_transaction_request(db_conn, pending_tx, transaction_date=trans_date, user_input=original_input, source="telegram")

        # Get updated balance (optional - could query from DB)
        # For now, just show success without balance
        success_msg = format_success_message(pending_tx.get('description', 'Transaction'), lang=lang)

        # Edit message to show success (remove buttons)
        await query.edit_message_text(
            success_msg,
            parse_mode='Markdown'
        )

        # Clear state
        context.user_data.clear()

    except ValueError as e:
        await query.edit_message_text(
            format_error_message(str(e), lang),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error saving transaction: {e}", exc_info=True)
        await query.edit_message_text(
            format_error_message(t("error_save_failed", lang), lang),
            parse_mode='Markdown'
        )


async def handle_revise(update: Update, query, context: ContextTypes.DEFAULT_TYPE):
    """Enable correction mode."""
    lang = get_user_lang(update)
    # Remove buttons and prompt for correction
    await query.edit_message_reply_markup(reply_markup=None)

    await query.message.reply_text(
        f"✍️ {t('revise_prompt', lang)}",
        parse_mode='Markdown'
    )

    # Set flag to await correction
    context.user_data['awaiting_correction'] = True


# ==================== REVIEW HANDLERS ====================

def _clear_review_state(context: ContextTypes.DEFAULT_TYPE):
    """Remove all review-related keys from user_data."""
    for key in ('review_state', 'review_transactions', 'review_index',
                'review_edit_changes', 'review_edit_new_date', 'review_count'):
        context.user_data.pop(key, None)


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /review command — show transactions needing review."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    lang = get_user_lang(update)

    # Clear any existing review/expense state
    _clear_review_state(context)
    context.user_data.pop('pending_transaction', None)
    context.user_data.pop('awaiting_correction', None)

    transactions = repository.get_transactions_needing_review(db_conn)
    if not transactions:
        await update.message.reply_text(
            f"✅ {t('review_empty', lang)}", parse_mode='Markdown'
        )
        return

    context.user_data['review_transactions'] = transactions
    context.user_data['review_index'] = 0
    context.user_data['review_state'] = 'viewing'
    context.user_data['review_count'] = 0

    await _send_review_card(update, context, from_callback=False)


async def _send_review_card(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
    """Display the current review transaction or the 'all done' message."""
    lang = get_user_lang(update)
    transactions = context.user_data.get('review_transactions', [])
    index = context.user_data.get('review_index', 0)

    if index >= len(transactions):
        # All done
        count = context.user_data.get('review_count', 0)
        done_msg = f"✅ {t('review_all_done', lang, count=count)}"
        _clear_review_state(context)
        if from_callback:
            await update.callback_query.edit_message_text(done_msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(done_msg, parse_mode='Markdown')
        return

    tx = transactions[index]
    text = format_review_card(tx, index, len(transactions), lang)
    buttons = format_review_buttons(lang)

    context.user_data['review_state'] = 'viewing'

    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=buttons, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=buttons, parse_mode='Markdown')


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle review inline button clicks."""
    if not is_authorized(update):
        return await reject_unauthorized(update)

    query = update.callback_query
    await query.answer()

    lang = get_user_lang(update)
    action = query.data.split(':')[1]

    transactions = context.user_data.get('review_transactions', [])
    index = context.user_data.get('review_index', 0)

    if action == 'approve':
        if index < len(transactions):
            tx_id = transactions[index]['id']
            tx = repository.get_transaction_by_id(db_conn, tx_id)
            if tx:
                if BACKUP_ENABLED:
                    op = _describe_telegram_op("review approve", tx=tx)
                    db_backup.auto_backup(DB_PATH, BACKUP_DIR, BACKUP_KEEP_TODAY,
                                         BACKUP_RECENT_DAYS, BACKUP_MAX_DAYS,
                                         operation=op,
                                         log_retention_days=BACKUP_LOG_RETENTION_DAYS)
                repository.mark_reviewed(db_conn, tx_id)
                context.user_data['review_count'] = context.user_data.get('review_count', 0) + 1
            # else: tx gone, just advance
        context.user_data['review_index'] = index + 1
        await _send_review_card(update, context, from_callback=True)

    elif action == 'skip':
        context.user_data['review_index'] = index + 1
        await _send_review_card(update, context, from_callback=True)

    elif action == 'edit':
        context.user_data['review_state'] = 'editing'
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✍️ {t('review_edit_prompt', lang)}", parse_mode='Markdown'
        )

    elif action == 'confirm':
        changes = context.user_data.get('review_edit_changes', {})
        new_date = context.user_data.get('review_edit_new_date')
        if index < len(transactions):
            tx_id = transactions[index]['id']
            tx = repository.get_transaction_by_id(db_conn, tx_id)
            if tx:
                if BACKUP_ENABLED:
                    log_changes = dict(changes)
                    if new_date:
                        log_changes['date'] = str(new_date)
                    op = _describe_telegram_op("review edit", tx=tx, changes=log_changes)
                    db_backup.auto_backup(DB_PATH, BACKUP_DIR, BACKUP_KEEP_TODAY,
                                         BACKUP_RECENT_DAYS, BACKUP_MAX_DAYS,
                                         operation=op,
                                         log_retention_days=BACKUP_LOG_RETENTION_DAYS)
                controller.process_transaction_edit(db_conn, tx_id, changes, new_date)
                repository.mark_reviewed(db_conn, tx_id)
                context.user_data['review_count'] = context.user_data.get('review_count', 0) + 1
        context.user_data.pop('review_edit_changes', None)
        context.user_data.pop('review_edit_new_date', None)
        context.user_data['review_index'] = index + 1
        await _send_review_card(update, context, from_callback=True)

    elif action == 'cancel_edit':
        context.user_data.pop('review_edit_changes', None)
        context.user_data.pop('review_edit_new_date', None)
        context.user_data['review_state'] = 'viewing'
        await _send_review_card(update, context, from_callback=True)


async def handle_review_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str):
    """Process natural language edit instruction during review flow."""
    lang = get_user_lang(update)
    processing_msg = await update.message.reply_text(
        f"🔄 {t('processing', lang)}", parse_mode='Markdown'
    )

    try:
        transactions = context.user_data.get('review_transactions', [])
        index = context.user_data.get('review_index', 0)

        if index >= len(transactions):
            await processing_msg.edit_text(
                format_error_message(t('review_tx_not_found', lang), lang),
                parse_mode='Markdown'
            )
            _clear_review_state(context)
            return

        tx_id = transactions[index]['id']
        tx = repository.get_transaction_by_id(db_conn, tx_id)
        if not tx:
            await processing_msg.edit_text(
                f"⚠️ {t('review_tx_not_found', lang)}", parse_mode='Markdown'
            )
            context.user_data['review_index'] = index + 1
            context.user_data['review_state'] = 'viewing'
            return

        accounts = repository.get_all_accounts(db_conn)
        budgets = repository.get_all_budgets(db_conn)

        changes = llm_parser.parse_edit_instruction(
            db_conn, tx, user_message, accounts, budgets
        )

        if changes is None:
            await processing_msg.edit_text(
                f"❌ {t('review_edit_failed', lang)}", parse_mode='Markdown'
            )
            # Stay in editing state so user can retry
            return

        if not changes:
            await processing_msg.edit_text(
                f"⚠️ {t('review_edit_no_changes', lang)}", parse_mode='Markdown'
            )
            return

        # Extract date_created into new_date
        new_date = None
        if 'date_created' in changes:
            new_date = date.fromisoformat(changes.pop('date_created'))

        context.user_data['review_edit_changes'] = changes
        context.user_data['review_edit_new_date'] = new_date
        context.user_data['review_state'] = 'confirming'

        # Build diff message
        diff_changes = dict(changes)
        if new_date:
            diff_changes['date_created'] = str(new_date)
        diff_text = format_review_diff(tx, diff_changes, lang)
        buttons = format_review_confirm_buttons(lang)

        await processing_msg.edit_text(diff_text, reply_markup=buttons, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error processing review edit: {e}", exc_info=True)
        await processing_msg.edit_text(
            format_error_message(t('error_unexpected', lang), lang),
            parse_mode='Markdown'
        )


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

    extra_user = get_extra_user_info(update)

    target_month = None
    if context.args:
        args_str = ' '.join(context.args)
        target_month = parse_month_from_args(args_str)

    if target_month is None:
        today = date.today()
        if extra_user:
            account = next((a for a in repository.get_all_accounts(db_conn)
                            if a['account_id'] == extra_user['account']), None)
            if account:
                pd = tx_module.simulate_payment_date(account, today)
                target_month = date(pd.year, pd.month, 1)
        if target_month is None:
            target_month = date(today.year, today.month, 1)

    await handle_summary_request(update, context, target_month, from_callback=False, extra_user=extra_user)


async def handle_summary_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_month: date,
    show_planning: bool = False,
    from_callback: bool = False,
    extra_user: dict | None = None,
):
    """
    Unified handler for summary requests showing a single month.

    Args:
        update: Telegram update object
        context: Context object
        target_month: First day of month to display
        show_planning: If True, show planning/pending view; if False, show budget envelope view
        from_callback: True if called from button callback
        extra_user: Extra user config dict, or None for owner
    """
    lang = get_user_lang(update)
    if extra_user:
        show_planning = False
    try:
        if from_callback:
            await update.callback_query.answer(f"{t('loading', lang)}")
        else:
            processing_msg = await update.message.reply_text(f"🔄 {t('loading', lang)}", parse_mode='Markdown')

        period_end = (target_month + relativedelta(months=1)) - timedelta(days=1)

        if show_planning:
            all_transactions = repository.get_transactions_with_running_balance(db_conn)
            all_pending = []
            month_planning = []
            for tx in all_transactions:
                dp = tx['date_payed']
                if isinstance(dp, str):
                    dp = date.fromisoformat(dp)
                tx['date_payed'] = dp
                if tx.get('status') == 'pending':
                    all_pending.append(tx)
                elif tx.get('status') == 'planning' and target_month <= dp <= period_end:
                    month_planning.append(tx)

            m_name = month_name(target_month.month, lang)
            month_label = f"{m_name} {target_month.year}"
            message_text = format_planning_pending(
                all_pending, month_planning, month_label, lang=lang
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

            if extra_user:
                prefix = extra_user['budget'].lower()
                budget_data = [b for b in budget_data if b['name'].lower().startswith(prefix)]

            message_text = format_budget_envelopes(budget_data, target_month, lang=lang)

        if extra_user:
            buttons = format_summary_navigation_buttons_simple(target_month, lang=lang)
        else:
            buttons = format_summary_navigation_buttons(target_month, show_planning, lang=lang)

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
        error_msg = format_error_message(t("error_summary_failed", lang), lang)

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

    lang = get_user_lang(update)
    query = update.callback_query
    await query.answer()  # Acknowledge button click

    callback_data = query.data
    parts = callback_data.split(':')

    if len(parts) < 2:
        await query.edit_message_text(
            format_error_message(t("error_invalid_callback", lang), lang),
            parse_mode='Markdown'
        )
        return

    month_str = parts[1]
    view_type = parts[2] if len(parts) > 2 else "budget"

    try:
        year, month = map(int, month_str.split('-'))
        target_month = date(year, month, 1)
        extra_user = get_extra_user_info(update)
        show_planning = False if extra_user else (view_type == "plan")

        await handle_summary_request(
            update, context, target_month,
            show_planning=show_planning,
            from_callback=True,
            extra_user=extra_user,
        )

    except Exception as e:
        logger.error(f"Error parsing navigation callback: {e}", exc_info=True)
        await query.edit_message_text(
            format_error_message(t("error_invalid_selection", lang), lang),
            parse_mode='Markdown'
        )


# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and notify user."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

    if update and update.effective_message:
        lang = get_user_lang(update) if update.effective_user else "en"
        await update.effective_message.reply_text(
            f"❌ {t('error_generic', lang)}",
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
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("review", review_command))

    # Language selection callback (must come BEFORE generic CallbackQueryHandler)
    application.add_handler(CallbackQueryHandler(
        lang_callback,
        pattern=r'^lang:(en|es)$'
    ))

    # Review callbacks (must come BEFORE generic CallbackQueryHandler)
    application.add_handler(CallbackQueryHandler(
        review_callback,
        pattern=r'^rv:(approve|edit|skip|confirm|cancel_edit)$'
    ))

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

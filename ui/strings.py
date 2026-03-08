"""
Internationalization strings for the Telegram bot.

Usage:
    from ui.strings import t, month_name
    t("welcome", lang)
    t("tx_saved", lang, description="Groceries")
    month_name(3, lang)  # "March" / "Marzo"
"""

STRINGS = {
    "en": {
        # Commands
        "welcome": (
            "I help you track expenses easily. Just send me a message like:\n\n"
            "{example_simple}\n"
            "{example_installment}\n"
            "{example_income}\n\n"
            "I'll parse it and save it for you.\n\n"
            "Commands:\n"
            "/help - Show help message\n"
            "/summary - View monthly summary\n"
            "/lang - Change language\n"
            "/cancel - Cancel current transaction"
        ),
        "welcome_header": "Welcome to Cash Flow Bot!",
        "help_header": "How to Use Cash Flow Bot",
        "help_adding": (
            "*Adding Expenses:*\n"
            "Just send a natural language message:\n"
            '• "Spent 45.50 on groceries"\n'
            '• "Bought TV for 600 in 12 installments"\n'
            '• "Split purchase: 30 on groceries, 15 on snacks"'
        ),
        "help_confirm_auto": (
            "*Saving:*\n"
            "Transactions are saved automatically.\n"
            "You'll see a confirmation with the amount and remaining budget."
        ),
        "help_confirm_manual": (
            "*Confirmation:*\n"
            "I'll show a preview with buttons:\n"
            "• {btn_confirm} Confirm - Save the transaction\n"
            "• {btn_revise} Revise - Make corrections\n\n"
            "*Making Corrections:*\n"
            "After clicking Revise, tell me what to change:\n"
            '• "Actually it was 45.50 on Visa"\n'
            '• "Change category to entertainment"'
        ),
        "help_commands": (
            "*Commands:*\n"
            "/start - Restart bot\n"
            "/help - Show this help message\n"
            "/summary - View monthly budget summary\n"
            "/summary [month] - View specific month (e.g., /summary October)\n"
            "/review - Review flagged transactions\n"
            "/lang - Change language\n"
            "/cancel - Cancel current transaction"
        ),
        "cancel": "Current transaction cancelled.",
        "unauthorized": "You are not authorized to use this bot.",

        # Processing
        "processing": "Processing...",
        "updating": "Updating...",
        "loading": "Loading...",

        # Buttons
        "btn_confirm": "Confirm",
        "btn_revise": "Revise",
        "btn_prev": "Prev",
        "btn_next": "Next",
        "btn_budget_view": "Budget View",
        "btn_cancel": "Cancel",
        "btn_planning": "Planning",

        # Errors
        "error_no_accounts": "No accounts found. Please set up accounts via CLI first.",
        "error_parse_failed": "I couldn't understand that. Please try rephrasing.",
        "error_correction_failed": "I couldn't apply that correction. Please try rephrasing.",
        "error_no_pending": "No pending transaction found. Please start over.",
        "error_save_failed": "Failed to save transaction. Please try again.",
        "error_unexpected": "An unexpected error occurred. Please try again.",
        "error_generic": "An error occurred. Please try again or contact support.",
        "error_summary_failed": "Failed to generate summary. Please try again.",
        "error_invalid_callback": "Invalid callback format.",
        "error_invalid_selection": "Invalid selection. Please try again.",
        "error_header": "Error",
        "error_footer": "Please try again or type /help for assistance.",
        "error_correction_update": "An error occurred while updating. Please try again.",

        # Preview labels
        "tx_preview": "Transaction Preview",
        "tx_installment_preview": "Installment Transaction Preview",
        "tx_split_preview": "Split Transaction Preview",
        "date_created": "Date Created",
        "payment_date": "Payment Date",
        "description": "Description",
        "amount": "Amount",
        "account": "Account",
        "category": "Category",
        "budget_label": "Budget",
        "status_pending": "Pending (won't affect balance until cleared)",
        "total_amount": "Total Amount",
        "installments": "Installments",
        "first_payment": "First Payment",
        "date_label": "Date",
        "unknown_tx_type": "Unknown transaction type",

        # Format labels
        "tx_saved": "Transaction Saved!",
        "saved": "Saved!",
        "current_balance": "Current balance",
        "budgets_title": "Budgets",
        "no_budgets": "No budget allocations this month",
        "forecast_tag": "forecast",
        "over": "over",
        "left": "left",
        "pending_header": "Pending",
        "none_label": "None",
        "planning_header": "Planning",
        "remaining": "remaining",

        # Revise
        "revise_prompt": (
            "What would you like to change?\n\n"
            "Tell me in natural language, like:\n"
            '• "Change amount to 45.50"\n'
            '• "Use Visa card instead"\n'
            '• "Change category to entertainment"'
        ),

        # Review
        "review_header": "Review",
        "review_empty": "No transactions need review.",
        "review_counter": "{current} of {total}",
        "review_all_done": "All done! {count} transaction(s) reviewed.",
        "review_source": "Source",
        "btn_approve": "Approve",
        "btn_edit": "Edit",
        "btn_skip": "Skip",
        "review_edit_prompt": (
            "What would you like to change?\n"
            "Describe the edit in natural language:"
        ),
        "review_edit_preview": "Edit Preview",
        "review_edit_no_changes": "No changes detected. Try again or press Cancel.",
        "review_edit_failed": "Could not parse the edit instruction. Try rephrasing.",
        "review_approved": "Approved.",
        "review_edited": "Edited and approved.",
        "review_tx_not_found": "Transaction no longer exists, skipping.",

        # Lang command
        "lang_current": "Current language: *{lang_name}*",
        "lang_switched": "Language changed to *{lang_name}*",
        "lang_choose": "Choose your language:",
    },
    "es": {
        # Commands
        "welcome": (
            "Te ayudo a registrar gastos. Solo manda un mensaje como:\n\n"
            "{example_simple}\n"
            "{example_installment}\n"
            "{example_income}\n\n"
            "Lo interpreto y lo guardo por ti.\n\n"
            "Comandos:\n"
            "/help - Mostrar ayuda\n"
            "/summary - Ver resumen mensual\n"
            "/lang - Cambiar idioma\n"
            "/cancel - Cancelar transacción actual"
        ),
        "welcome_header": "Bienvenido a Cash Flow Bot!",
        "help_header": "Cómo Usar Cash Flow Bot",
        "help_adding": (
            "*Agregar Gastos:*\n"
            "Solo manda un mensaje en lenguaje natural:\n"
            '• "Gasté 45.50 en comida"\n'
            '• "Compré TV por 600 en 12 cuotas"\n'
            '• "Dividir compra: 30 en comida, 15 en snacks"'
        ),
        "help_confirm_auto": (
            "*Guardado:*\n"
            "Las transacciones se guardan automáticamente.\n"
            "Verás una confirmación con el monto y presupuesto restante."
        ),
        "help_confirm_manual": (
            "*Confirmación:*\n"
            "Te muestro una vista previa con botones:\n"
            "• {btn_confirm} Confirmar - Guardar la transacción\n"
            "• {btn_revise} Revisar - Hacer correcciones\n\n"
            "*Hacer Correcciones:*\n"
            "Después de hacer clic en Revisar, dime qué cambiar:\n"
            '• "En realidad fueron 45.50 en Visa"\n'
            '• "Cambiar categoría a entretenimiento"'
        ),
        "help_commands": (
            "*Comandos:*\n"
            "/start - Reiniciar bot\n"
            "/help - Mostrar esta ayuda\n"
            "/summary - Ver resumen mensual de presupuestos\n"
            "/summary [mes] - Ver mes específico (ej., /summary octubre)\n"
            "/review - Revisar transacciones marcadas\n"
            "/lang - Cambiar idioma\n"
            "/cancel - Cancelar transacción actual"
        ),
        "cancel": "Transacción actual cancelada.",
        "unauthorized": "No estás autorizado para usar este bot.",

        # Processing
        "processing": "Procesando...",
        "updating": "Actualizando...",
        "loading": "Cargando...",

        # Buttons
        "btn_confirm": "Confirmar",
        "btn_revise": "Revisar",
        "btn_prev": "Ant",
        "btn_next": "Sig",
        "btn_budget_view": "Presupuestos",
        "btn_cancel": "Cancelar",
        "btn_planning": "Planificación",

        # Errors
        "error_no_accounts": "No se encontraron cuentas. Configura cuentas desde el CLI primero.",
        "error_parse_failed": "No pude entender eso. Intenta reformularlo.",
        "error_correction_failed": "No pude aplicar esa corrección. Intenta reformularla.",
        "error_no_pending": "No hay transacción pendiente. Por favor empieza de nuevo.",
        "error_save_failed": "No se pudo guardar la transacción. Intenta de nuevo.",
        "error_unexpected": "Ocurrió un error inesperado. Intenta de nuevo.",
        "error_generic": "Ocurrió un error. Intenta de nuevo o contacta soporte.",
        "error_summary_failed": "No se pudo generar el resumen. Intenta de nuevo.",
        "error_invalid_callback": "Formato de callback inválido.",
        "error_invalid_selection": "Selección inválida. Intenta de nuevo.",
        "error_header": "Error",
        "error_footer": "Intenta de nuevo o escribe /help para ayuda.",
        "error_correction_update": "Ocurrió un error al actualizar. Intenta de nuevo.",

        # Preview labels
        "tx_preview": "Vista Previa de Transacción",
        "tx_installment_preview": "Vista Previa de Cuotas",
        "tx_split_preview": "Vista Previa de Transacción Dividida",
        "date_created": "Fecha de Creación",
        "payment_date": "Fecha de Pago",
        "description": "Descripción",
        "amount": "Monto",
        "account": "Cuenta",
        "category": "Categoría",
        "budget_label": "Presupuesto",
        "status_pending": "Pendiente (no afecta el saldo hasta que se procese)",
        "total_amount": "Monto Total",
        "installments": "Cuotas",
        "first_payment": "Primer Pago",
        "date_label": "Fecha",
        "unknown_tx_type": "Tipo de transacción desconocido",

        # Format labels
        "tx_saved": "Transacción Guardada!",
        "saved": "Guardado!",
        "current_balance": "Saldo actual",
        "budgets_title": "Presupuestos",
        "no_budgets": "Sin asignaciones de presupuesto este mes",
        "forecast_tag": "proyección",
        "over": "excedido",
        "left": "restante",
        "pending_header": "Pendientes",
        "none_label": "Ninguno",
        "planning_header": "Planificación",
        "remaining": "restante",

        # Revise
        "revise_prompt": (
            "Qué te gustaría cambiar?\n\n"
            "Dímelo en lenguaje natural, como:\n"
            '• "Cambiar monto a 45.50"\n'
            '• "Usar tarjeta Visa en vez"\n'
            '• "Cambiar categoría a entretenimiento"'
        ),

        # Review
        "review_header": "Revisión",
        "review_empty": "No hay transacciones por revisar.",
        "review_counter": "{current} de {total}",
        "review_all_done": "Listo! {count} transacción(es) revisada(s).",
        "review_source": "Origen",
        "btn_approve": "Aprobar",
        "btn_edit": "Editar",
        "btn_skip": "Omitir",
        "review_edit_prompt": (
            "Qué te gustaría cambiar?\n"
            "Describe la edición en lenguaje natural:"
        ),
        "review_edit_preview": "Vista Previa de Edición",
        "review_edit_no_changes": "No se detectaron cambios. Intenta de nuevo o presiona Cancelar.",
        "review_edit_failed": "No pude interpretar la instrucción. Intenta reformularla.",
        "review_approved": "Aprobada.",
        "review_edited": "Editada y aprobada.",
        "review_tx_not_found": "La transacción ya no existe, omitiendo.",

        # Lang command
        "lang_current": "Idioma actual: *{lang_name}*",
        "lang_switched": "Idioma cambiado a *{lang_name}*",
        "lang_choose": "Elige tu idioma:",
    },
}

MONTH_NAMES = {
    "en": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
    "es": [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ],
}

LANG_DISPLAY_NAMES = {
    "en": "English",
    "es": "Español",
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Lookup a translated string with English fallback and optional .format(**kwargs)."""
    text = STRINGS.get(lang, STRINGS["en"]).get(key)
    if text is None:
        text = STRINGS["en"].get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text


def month_name(month: int, lang: str = "en") -> str:
    """Return 1-indexed month name in the given language."""
    names = MONTH_NAMES.get(lang, MONTH_NAMES["en"])
    return names[month - 1]

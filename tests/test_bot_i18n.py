"""
Tests for Telegram bot i18n (English + Spanish).

Covers:
- ui/strings.py: t() lookup, fallback, kwargs, month_name
- cashflow/repository.py: set_setting insert and update
- ui/telegram_format.py: format functions with lang param
- bot.py: get_user_lang resolution
- parse_month_from_args: Spanish month names
"""

import unittest
import sqlite3
from unittest.mock import patch, MagicMock
from datetime import date

from cashflow.database import create_test_db
from cashflow import repository
from ui.strings import t, month_name, STRINGS, LANG_DISPLAY_NAMES
from ui.telegram_format import (
    format_error_message,
    format_success_message,
    format_budget_envelopes,
    format_transaction_preview,
    format_auto_confirm_message,
    format_planning_pending,
    format_summary_navigation_buttons,
    format_summary_navigation_buttons_simple,
    parse_month_from_args,
)


# ==================== ui/strings.py ====================

class TestTranslationLookup(unittest.TestCase):

    def test_t_english_lookup(self):
        self.assertEqual(t("cancel", "en"), "Current transaction cancelled.")

    def test_t_spanish_lookup(self):
        self.assertEqual(t("cancel", "es"), "Transacción actual cancelada.")

    def test_t_fallback_to_english(self):
        """Unknown lang falls back to English."""
        self.assertEqual(t("cancel", "fr"), "Current transaction cancelled.")

    def test_t_missing_key_returns_key(self):
        self.assertEqual(t("nonexistent_key_xyz", "en"), "nonexistent_key_xyz")

    def test_t_with_format_kwargs(self):
        result = t("lang_switched", "en", lang_name="English")
        self.assertIn("English", result)

    def test_t_spanish_with_kwargs(self):
        result = t("lang_switched", "es", lang_name="Español")
        self.assertIn("Español", result)

    def test_all_en_keys_exist_in_es(self):
        """Every English key should have a Spanish translation."""
        en_keys = set(STRINGS["en"].keys())
        es_keys = set(STRINGS["es"].keys())
        missing = en_keys - es_keys
        self.assertEqual(missing, set(), f"Missing Spanish translations: {missing}")


class TestMonthName(unittest.TestCase):

    def test_month_name_en(self):
        self.assertEqual(month_name(1, "en"), "January")
        self.assertEqual(month_name(12, "en"), "December")

    def test_month_name_es(self):
        self.assertEqual(month_name(1, "es"), "Enero")
        self.assertEqual(month_name(3, "es"), "Marzo")
        self.assertEqual(month_name(12, "es"), "Diciembre")

    def test_month_name_fallback(self):
        self.assertEqual(month_name(6, "fr"), "June")


# ==================== cashflow/repository.py ====================

class TestSetSetting(unittest.TestCase):

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def test_insert_new_setting(self):
        repository.set_setting(self.conn, "lang:123", "es")
        self.assertEqual(repository.get_setting(self.conn, "lang:123"), "es")

    def test_update_existing_setting(self):
        repository.set_setting(self.conn, "lang:123", "es")
        repository.set_setting(self.conn, "lang:123", "en")
        self.assertEqual(repository.get_setting(self.conn, "lang:123"), "en")


# ==================== ui/telegram_format.py ====================

class TestFormatErrorMessage(unittest.TestCase):

    def test_english(self):
        result = format_error_message("Something broke", "en")
        self.assertIn("Error", result)
        self.assertIn("Something broke", result)
        self.assertIn("/help", result)

    def test_spanish(self):
        result = format_error_message("Algo se rompio", "es")
        self.assertIn("Error", result)
        self.assertIn("Algo se rompio", result)
        self.assertIn("/help", result)


class TestFormatSuccessMessage(unittest.TestCase):

    def test_english(self):
        result = format_success_message("Groceries", lang="en")
        self.assertIn("Transaction Saved", result)

    def test_spanish(self):
        result = format_success_message("Comida", lang="es")
        self.assertIn("Transacción Guardada", result)

    def test_with_balance(self):
        result = format_success_message("Test", balance=1234.56, lang="es")
        self.assertIn("Saldo actual", result)
        self.assertIn("1,234.56", result)


class TestFormatBudgetEnvelopes(unittest.TestCase):

    def test_empty_english(self):
        result = format_budget_envelopes([], date(2026, 3, 1), "en")
        self.assertIn("Budgets: March 2026", result)
        self.assertIn("No budget allocations", result)

    def test_empty_spanish(self):
        result = format_budget_envelopes([], date(2026, 3, 1), "es")
        self.assertIn("Presupuestos: Marzo 2026", result)
        self.assertIn("Sin asignaciones", result)

    def test_over_budget_spanish(self):
        data = [{'name': 'food', 'allocated': 100, 'spent': 120, 'remaining': -20, 'status': 'committed'}]
        result = format_budget_envelopes(data, date(2026, 1, 1), "es")
        self.assertIn("excedido", result)

    def test_under_budget_spanish(self):
        data = [{'name': 'food', 'allocated': 100, 'spent': 30, 'remaining': 70, 'status': 'committed'}]
        result = format_budget_envelopes(data, date(2026, 1, 1), "es")
        self.assertIn("restante", result)

    def test_forecast_tag_spanish(self):
        data = [{'name': 'food', 'allocated': 100, 'spent': 0, 'remaining': 100, 'status': 'forecast'}]
        result = format_budget_envelopes(data, date(2026, 5, 1), "es")
        self.assertIn("proyección", result)


class TestFormatTransactionPreview(unittest.TestCase):

    def test_simple_spanish(self):
        tx = {'type': 'simple', 'amount': -25, 'description': 'Test', 'account': 'Cash', 'date_created': '2026-03-01'}
        result = format_transaction_preview(tx, date(2026, 3, 1), "es")
        self.assertIn("Vista Previa de Transacción", result)
        self.assertIn("Fecha de Creación", result)
        self.assertIn("Cuenta", result)

    def test_installment_spanish(self):
        tx = {'type': 'installment', 'total_amount': 600, 'installments': 12, 'description': 'TV', 'account': 'Visa'}
        result = format_transaction_preview(tx, date(2026, 3, 1), "es")
        self.assertIn("Vista Previa de Cuotas", result)
        self.assertIn("Monto Total", result)

    def test_split_spanish(self):
        tx = {'type': 'split', 'description': 'Compras', 'account': 'Cash', 'date_created': 'today',
              'splits': [{'amount': 30, 'category': 'food'}, {'amount': 15, 'category': 'snacks'}]}
        result = format_transaction_preview(tx, date(2026, 3, 1), "es")
        self.assertIn("Vista Previa de Transacción Dividida", result)

    def test_unknown_type_spanish(self):
        tx = {'type': 'unknown_thing'}
        result = format_transaction_preview(tx, date(2026, 3, 1), "es")
        self.assertIn("Tipo de transacción desconocido", result)


class TestFormatAutoConfirmMessage(unittest.TestCase):

    def test_spanish(self):
        tx = {'date_created': '2026-03-01', 'amount': -10, 'description': 'Pan'}
        result = format_auto_confirm_message(tx, date(2026, 3, 5), lang="es")
        self.assertIn("Guardado!", result)

    def test_spanish_with_budget(self):
        tx = {'date_created': '2026-03-01', 'amount': -10, 'description': 'Pan'}
        result = format_auto_confirm_message(
            tx, date(2026, 3, 5),
            budget_remaining=50.0, budget_name="food", budget_allocated=100.0, lang="es"
        )
        self.assertIn("restante", result)


class TestFormatPlanningPending(unittest.TestCase):

    def test_spanish_empty(self):
        result = format_planning_pending([], [], "Marzo 2026", lang="es")
        self.assertIn("Pendientes", result)
        self.assertIn("Ninguno", result)
        self.assertIn("Planificación", result)


class TestFormatNavigationButtons(unittest.TestCase):

    def test_spanish_labels(self):
        markup = format_summary_navigation_buttons(date(2026, 3, 1), lang="es")
        buttons = markup.inline_keyboard[0]
        labels = [b.text for b in buttons]
        self.assertTrue(any("Ant" in l for l in labels))
        self.assertTrue(any("Sig" in l for l in labels))
        self.assertTrue(any("Planificación" in l for l in labels))

    def test_spanish_simple_labels(self):
        markup = format_summary_navigation_buttons_simple(date(2026, 3, 1), lang="es")
        buttons = markup.inline_keyboard[0]
        labels = [b.text for b in buttons]
        self.assertTrue(any("Ant" in l for l in labels))
        self.assertTrue(any("Sig" in l for l in labels))


# ==================== parse_month_from_args: Spanish ====================

class TestParseMonthSpanish(unittest.TestCase):

    def test_marzo(self):
        result = parse_month_from_args("marzo")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 3)

    def test_enero(self):
        result = parse_month_from_args("enero")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 1)

    def test_diciembre(self):
        result = parse_month_from_args("diciembre")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 12)

    def test_ene_abbreviation(self):
        result = parse_month_from_args("ene")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 1)

    def test_octubre_with_year(self):
        result = parse_month_from_args("octubre 2025")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.year, 2025)

    def test_english_still_works(self):
        result = parse_month_from_args("march")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 3)


# ==================== bot.py: get_user_lang ====================

class TestGetUserLang(unittest.TestCase):

    def _make_update(self, user_id=12345):
        update = MagicMock()
        update.effective_user.id = user_id
        return update

    @patch('bot.db_conn')
    @patch('bot.TELEGRAM_DEFAULT_LANG', 'en')
    def test_db_override(self, mock_conn):
        """DB setting wins over env default."""
        from bot import get_user_lang
        with patch('bot.repository.get_setting', return_value='es'):
            result = get_user_lang(self._make_update())
        self.assertEqual(result, 'es')

    @patch('bot.db_conn')
    @patch('bot.TELEGRAM_DEFAULT_LANG', 'es')
    def test_env_default(self, mock_conn):
        """When no DB setting, use env default."""
        from bot import get_user_lang
        with patch('bot.repository.get_setting', return_value=None):
            result = get_user_lang(self._make_update())
        self.assertEqual(result, 'es')

    @patch('bot.db_conn')
    @patch('bot.TELEGRAM_DEFAULT_LANG', 'en')
    def test_fallback(self, mock_conn):
        """When DB returns invalid lang, use env default."""
        from bot import get_user_lang
        with patch('bot.repository.get_setting', return_value='fr'):
            result = get_user_lang(self._make_update())
        self.assertEqual(result, 'en')


if __name__ == '__main__':
    unittest.main()

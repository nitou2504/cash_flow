"""
Tests for Telegram bot /review flow.

Covers:
- i18n: review strings exist in both EN and ES
- format_review_card: display of transactions for review
- format_review_diff: before/after edit preview
- format_review_buttons / format_review_confirm_buttons: button factories
"""

import unittest
from datetime import date

from ui.strings import t, STRINGS
from ui.telegram_format import (
    format_review_card,
    format_review_diff,
    format_review_buttons,
    format_review_confirm_buttons,
)


class TestReviewI18nStrings(unittest.TestCase):
    """All review string keys must exist in both EN and ES."""

    REVIEW_KEYS = [
        "review_header", "review_empty", "review_counter", "review_all_done",
        "review_source", "btn_approve", "btn_edit", "btn_skip",
        "review_edit_prompt", "review_edit_preview", "review_edit_no_changes",
        "review_edit_failed", "review_approved", "review_edited",
        "review_tx_not_found", "extra_user_notify",
    ]

    def test_en_keys_exist(self):
        for key in self.REVIEW_KEYS:
            self.assertIn(key, STRINGS["en"], f"Missing EN key: {key}")

    def test_es_keys_exist(self):
        for key in self.REVIEW_KEYS:
            self.assertIn(key, STRINGS["es"], f"Missing ES key: {key}")

    def test_review_counter_format(self):
        result = t("review_counter", "en", current=2, total=5)
        self.assertEqual(result, "2 of 5")

    def test_review_counter_format_es(self):
        result = t("review_counter", "es", current=2, total=5)
        self.assertEqual(result, "2 de 5")

    def test_review_all_done_format(self):
        result = t("review_all_done", "en", count=3)
        self.assertIn("3", result)

    def test_help_commands_mentions_review(self):
        self.assertIn("/review", STRINGS["en"]["help_commands"])
        self.assertIn("/review", STRINGS["es"]["help_commands"])


class TestFormatReviewCard(unittest.TestCase):
    """Test format_review_card output."""

    def _make_tx(self, **overrides):
        tx = {
            'id': 42,
            'date_created': '2026-03-05',
            'description': 'Supermaxi Groceries',
            'amount': -25.00,
            'account': 'Visa Pichincha',
            'category': 'Home Groceries',
            'budget': 'budget_groceries_mar_apr',
            'status': 'committed',
            'source': 'mom',
        }
        tx.update(overrides)
        return tx

    def test_basic_card_en(self):
        tx = self._make_tx()
        result = format_review_card(tx, 0, 3, lang="en")
        self.assertIn("Review", result)
        self.assertIn("1 of 3", result)
        self.assertIn("Supermaxi Groceries", result)
        self.assertIn("-$25.00", result)
        self.assertIn("mom", result)

    def test_basic_card_es(self):
        tx = self._make_tx()
        result = format_review_card(tx, 0, 3, lang="es")
        self.assertIn("Revisión", result)
        self.assertIn("1 de 3", result)

    def test_income_shows_plus(self):
        tx = self._make_tx(amount=100.00)
        result = format_review_card(tx, 0, 1, lang="en")
        self.assertIn("+$100.00", result)

    def test_no_source_omits_line(self):
        tx = self._make_tx(source=None)
        result = format_review_card(tx, 0, 1, lang="en")
        self.assertNotIn("Source", result)

    def test_no_budget_omits_line(self):
        tx = self._make_tx(budget=None)
        result = format_review_card(tx, 0, 1, lang="en")
        self.assertNotIn("Budget", result)


class TestFormatReviewDiff(unittest.TestCase):
    """Test format_review_diff output."""

    def _make_tx(self):
        return {
            'id': 42,
            'description': 'Supermaxi Groceries',
            'amount': -25.00,
            'account': 'Visa Pichincha',
            'category': 'Home Groceries',
            'budget': 'budget_food',
            'date_created': '2026-03-05',
        }

    def test_single_field_diff(self):
        tx = self._make_tx()
        result = format_review_diff(tx, {'amount': -45.50}, lang="en")
        self.assertIn("Edit Preview", result)
        self.assertIn("$25.00", result)  # old
        self.assertIn("$45.50", result)  # new
        self.assertIn("→", result)

    def test_multi_field_diff(self):
        tx = self._make_tx()
        changes = {'description': 'Amazon Books', 'category': 'Personal'}
        result = format_review_diff(tx, changes, lang="en")
        self.assertIn("Amazon Books", result)
        self.assertIn("Personal", result)

    def test_budget_display_name(self):
        tx = self._make_tx()
        result = format_review_diff(tx, {'budget': 'budget_groceries_mar_apr'}, lang="en")
        # display_name converts underscores to spaces and title-cases
        self.assertIn("Budget Groceries Mar Apr", result)

    def test_date_diff(self):
        tx = self._make_tx()
        result = format_review_diff(tx, {'date_created': '2026-03-10'}, lang="en")
        self.assertIn("2026-03-05", result)
        self.assertIn("2026-03-10", result)


class TestReviewButtons(unittest.TestCase):
    """Test button factory helpers."""

    def test_review_buttons_has_three(self):
        markup = format_review_buttons(lang="en")
        buttons = markup.inline_keyboard[0]
        self.assertEqual(len(buttons), 3)
        callbacks = [b.callback_data for b in buttons]
        self.assertIn("rv:approve", callbacks)
        self.assertIn("rv:edit", callbacks)
        self.assertIn("rv:skip", callbacks)

    def test_confirm_buttons_has_two(self):
        markup = format_review_confirm_buttons(lang="en")
        buttons = markup.inline_keyboard[0]
        self.assertEqual(len(buttons), 2)
        callbacks = [b.callback_data for b in buttons]
        self.assertIn("rv:confirm", callbacks)
        self.assertIn("rv:cancel_edit", callbacks)

    def test_buttons_es_labels(self):
        markup = format_review_buttons(lang="es")
        labels = [b.text for b in markup.inline_keyboard[0]]
        self.assertTrue(any("Aprobar" in l for l in labels))
        self.assertTrue(any("Editar" in l for l in labels))
        self.assertTrue(any("Omitir" in l for l in labels))


if __name__ == '__main__':
    unittest.main()

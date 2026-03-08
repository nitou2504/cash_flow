"""
Tests for the no-budget phrase detection flow.

Covers:
- check_no_budget() LLM classification (mocked)
- Config parsing of the 4th field
- Bot flow: budget omitted when phrase detected
- Bot flow: budget assigned when phrase absent
"""

import unittest
import json
import asyncio
from datetime import date
from unittest.mock import patch, MagicMock, AsyncMock

from cashflow.database import create_test_db
from cashflow.repository import (
    add_subscription, get_all_accounts, get_all_budgets,
)
from llm.parser import check_no_budget


class TestCheckNoBudget(unittest.TestCase):
    """Tests for check_no_budget() in llm/parser.py."""

    @patch('llm.parser._call_llm', return_value='true')
    def test_phrase_detected(self, mock_llm):
        result = check_no_budget("supermaxi carnes de sthefano", "de sthefano")
        self.assertTrue(result)
        mock_llm.assert_called_once()
        # Verify it routes to the right function
        self.assertEqual(mock_llm.call_args.kwargs['function_name'], 'check_no_budget')

    @patch('llm.parser._call_llm', return_value='false')
    def test_phrase_not_detected(self, mock_llm):
        result = check_no_budget("supermaxi carnes 15", "de sthefano")
        self.assertFalse(result)

    @patch('llm.parser._call_llm', return_value='True')
    def test_case_insensitive_response(self, mock_llm):
        result = check_no_budget("algo de estefano", "de sthefano")
        self.assertTrue(result)

    @patch('llm.parser._call_llm', return_value='  true  ')
    def test_whitespace_in_response(self, mock_llm):
        result = check_no_budget("algo de estefano", "de sthefano")
        self.assertTrue(result)

    @patch('llm.parser._call_llm', return_value=None)
    def test_llm_failure_returns_false(self, mock_llm):
        """On LLM failure, default to keeping the budget (safe default)."""
        result = check_no_budget("supermaxi de sthefano", "de sthefano")
        self.assertFalse(result)

    @patch('llm.parser._call_llm', return_value='maybe')
    def test_unexpected_response_returns_false(self, mock_llm):
        result = check_no_budget("supermaxi de sthefano", "de sthefano")
        self.assertFalse(result)

    @patch('llm.parser._call_llm', return_value='true')
    def test_prompt_contains_phrase(self, mock_llm):
        """The system prompt should include the configured phrase."""
        check_no_budget("some input", "de sthefano")
        system_prompt = mock_llm.call_args.kwargs['system_prompt']
        self.assertIn("de sthefano", system_prompt)

    @patch('llm.parser._call_llm', return_value='true')
    def test_user_input_passed_as_message(self, mock_llm):
        """The user's original message should be the user_input arg."""
        check_no_budget("supermaxi carnes de estefano", "de sthefano")
        user_input = mock_llm.call_args.kwargs['user_input']
        self.assertEqual(user_input, "supermaxi carnes de estefano")


class TestConfigParsing(unittest.TestCase):
    """Test that the 4th field is parsed from extra user config."""

    @patch.dict('os.environ', {
        'TELEGRAM_EXTRA_USER_MOM': '123456,Visa Pichincha,Home Groceries,de sthefano'
    })
    def test_no_budget_phrase_parsed(self):
        # Re-import to pick up the patched env
        import importlib
        import cashflow.config as config_mod
        importlib.reload(config_mod)

        self.assertIn(123456, config_mod.TELEGRAM_EXTRA_USERS)
        user = config_mod.TELEGRAM_EXTRA_USERS[123456]
        self.assertEqual(user['no_budget_phrase'], 'de sthefano')
        self.assertEqual(user['account'], 'Visa Pichincha')
        self.assertEqual(user['budget'], 'Home Groceries')

    @patch.dict('os.environ', {
        'TELEGRAM_EXTRA_USER_MOM': '123456,Visa Pichincha,Home Groceries'
    })
    def test_no_budget_phrase_absent(self):
        import importlib
        import cashflow.config as config_mod
        importlib.reload(config_mod)

        user = config_mod.TELEGRAM_EXTRA_USERS[123456]
        self.assertIsNone(user['no_budget_phrase'])


class TestBotNoBudgetFlow(unittest.TestCase):
    """Simulate the bot flow to verify budget is omitted/kept correctly."""

    def setUp(self):
        self.conn = create_test_db()
        add_subscription(self.conn, {
            "id": "budget_groceries_mar_apr", "name": "Home Groceries Mar-Apr",
            "category": "Home Groceries", "monthly_amount": 300.00,
            "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1), "end_date": date(2026, 5, 30),
            "is_budget": True
        })
        self.accounts = get_all_accounts(self.conn)
        self.budgets = get_all_budgets(self.conn)
        self.today = date(2026, 3, 8)

    def tearDown(self):
        self.conn.close()

    def _simulate_budget_resolution(self, extra_user, skip_budget, request_json):
        """Replicate the bot's budget resolution logic."""
        if extra_user and extra_user.get('budget') and not skip_budget:
            prefix = extra_user['budget'].lower()
            payment_month = self.today.replace(day=1)
            for b in self.budgets:
                if not b['name'].lower().startswith(prefix):
                    continue
                start = date.fromisoformat(str(b['start_date'])) if b.get('start_date') else date.min
                end = date.fromisoformat(str(b['end_date'])) if b.get('end_date') else date.max
                if start <= payment_month <= end:
                    request_json['budget'] = b['id']
                    break
        return request_json

    def test_budget_assigned_when_no_phrase(self):
        """Normal extra user flow — budget gets assigned."""
        extra_user = {
            'name': 'mom', 'account': 'Cash',
            'budget': 'Home Groceries', 'no_budget_phrase': None,
        }
        request_json = {'description': 'Supermaxi', 'amount': -25.0, 'category': 'Home Groceries'}

        result = self._simulate_budget_resolution(extra_user, skip_budget=False, request_json=request_json)
        self.assertEqual(result.get('budget'), 'budget_groceries_mar_apr')

    def test_budget_assigned_when_phrase_not_detected(self):
        """Phrase configured but not found in message — budget still assigned."""
        extra_user = {
            'name': 'mom', 'account': 'Cash',
            'budget': 'Home Groceries', 'no_budget_phrase': 'de sthefano',
        }
        request_json = {'description': 'Supermaxi', 'amount': -25.0, 'category': 'Home Groceries'}

        result = self._simulate_budget_resolution(extra_user, skip_budget=False, request_json=request_json)
        self.assertEqual(result.get('budget'), 'budget_groceries_mar_apr')

    def test_budget_omitted_when_phrase_detected(self):
        """Phrase detected — budget NOT assigned."""
        extra_user = {
            'name': 'mom', 'account': 'Cash',
            'budget': 'Home Groceries', 'no_budget_phrase': 'de sthefano',
        }
        request_json = {'description': 'Supermaxi de Sthefano', 'amount': -25.0, 'category': 'Home Groceries'}

        result = self._simulate_budget_resolution(extra_user, skip_budget=True, request_json=request_json)
        self.assertNotIn('budget', result)

    def test_no_extra_user_no_budget_resolution(self):
        """Non-extra-user flow — budget resolution is skipped entirely."""
        request_json = {'description': 'Supermaxi', 'amount': -25.0, 'budget': 'budget_food'}

        result = self._simulate_budget_resolution(extra_user=None, skip_budget=False, request_json=request_json)
        # Budget stays as the LLM set it
        self.assertEqual(result.get('budget'), 'budget_food')


if __name__ == '__main__':
    unittest.main()

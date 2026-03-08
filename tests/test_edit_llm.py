import unittest
import json
from datetime import date
from unittest.mock import patch, MagicMock

from cashflow.database import create_test_db
from cashflow.repository import (
    add_transactions, get_transaction_by_id, get_all_accounts,
    add_subscription, get_all_budgets
)
from cashflow.controller import process_transaction_request
from llm.parser import parse_edit_instruction


class TestParseEditInstruction(unittest.TestCase):
    """Tests for parse_edit_instruction() in llm/parser.py."""

    def setUp(self):
        self.conn = create_test_db()
        self.today = date(2026, 3, 8)

        # Add a budget
        add_subscription(self.conn, {
            "id": "budget_food", "name": "Food Budget", "category": "Food",
            "monthly_amount": 400.00, "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1), "is_budget": True
        })
        add_subscription(self.conn, {
            "id": "budget_groceries_mar_apr", "name": "Home Groceries Mar-Apr",
            "category": "Home Groceries", "monthly_amount": 300.00,
            "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1), "is_budget": True
        })

        # Create a transaction
        with patch('cashflow.controller.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, {
                "type": "simple", "description": "Supermaxi Groceries",
                "amount": 25.00, "account": "Cash", "category": "Home Groceries",
                "budget": "budget_groceries_mar_apr"
            })

        # Get the created transaction
        from cashflow.repository import get_all_transactions
        txs = get_all_transactions(self.conn)
        self.tx = [t for t in txs if t['description'] == 'Supermaxi Groceries'][0]

        self.accounts = get_all_accounts(self.conn)
        self.budgets = get_all_budgets(self.conn)

    def tearDown(self):
        self.conn.close()

    def _mock_llm(self, response_dict):
        """Helper to mock _call_llm returning a JSON string."""
        return patch('llm.parser._call_llm', return_value=json.dumps(response_dict))

    @patch('llm.parser.date')
    def test_single_field_amount(self, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"amount": -45.50}):
            result = parse_edit_instruction(
                self.conn, self.tx, "change amount to 45.50",
                self.accounts, self.budgets
            )
        self.assertEqual(result, {"amount": -45.50})

    @patch('llm.parser.date')
    def test_single_field_description(self, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"description": "Amazon Books"}):
            result = parse_edit_instruction(
                self.conn, self.tx, "change description to Amazon Books",
                self.accounts, self.budgets
            )
        self.assertEqual(result, {"description": "Amazon Books"})

    @patch('llm.parser.date')
    def test_single_field_date(self, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"date_created": "2026-03-05"}):
            result = parse_edit_instruction(
                self.conn, self.tx, "change date to march 5",
                self.accounts, self.budgets
            )
        self.assertEqual(result, {"date_created": "2026-03-05"})

    @patch('llm.parser.date')
    def test_single_field_budget(self, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"budget": "budget_food"}):
            result = parse_edit_instruction(
                self.conn, self.tx, "move to food budget",
                self.accounts, self.budgets
            )
        self.assertEqual(result, {"budget": "budget_food"})

    @patch('llm.parser.date')
    def test_single_field_category(self, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"category": "Dining-Snacks"}):
            result = parse_edit_instruction(
                self.conn, self.tx, "change category to Dining-Snacks",
                self.accounts, self.budgets
            )
        self.assertEqual(result, {"category": "Dining-Snacks"})

    @patch('llm.parser.date')
    def test_amount_sign_preserved(self, mock_date):
        """Expense amount stays negative."""
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"amount": -99.99}):
            result = parse_edit_instruction(
                self.conn, self.tx, "change amount to 99.99",
                self.accounts, self.budgets
            )
        self.assertLess(result["amount"], 0)

    @patch('llm.parser.date')
    def test_empty_response(self, mock_date):
        """Empty dict means no changes."""
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({}):
            result = parse_edit_instruction(
                self.conn, self.tx, "do nothing",
                self.accounts, self.budgets
            )
        self.assertEqual(result, {})

    @patch('llm.parser.date')
    def test_llm_failure_returns_none(self, mock_date):
        """None from _call_llm means failure."""
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with patch('llm.parser._call_llm', return_value=None):
            result = parse_edit_instruction(
                self.conn, self.tx, "change amount to 50",
                self.accounts, self.budgets
            )
        self.assertIsNone(result)

    @patch('llm.parser.date')
    def test_invalid_json_returns_none(self, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with patch('llm.parser._call_llm', return_value="not json at all"):
            result = parse_edit_instruction(
                self.conn, self.tx, "change amount to 50",
                self.accounts, self.budgets
            )
        self.assertIsNone(result)

    @patch('llm.parser.date')
    def test_account_resolution(self, mock_date):
        """LLM returns partial name, gets resolved to full name."""
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"account": "Visa Produbanco"}):
            result = parse_edit_instruction(
                self.conn, self.tx, "move to visa produbanco",
                self.accounts, self.budgets
            )
        self.assertEqual(result["account"], "Visa Produbanco")

    @patch('llm.parser.date')
    def test_invalid_category_dropped(self, mock_date):
        """Invalid category from LLM gets dropped from result."""
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"category": "NonExistentCategory", "amount": -50}):
            result = parse_edit_instruction(
                self.conn, self.tx, "change category and amount",
                self.accounts, self.budgets
            )
        self.assertNotIn("category", result)
        self.assertEqual(result["amount"], -50)

    @patch('llm.parser.date')
    def test_multi_field_edit(self, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        with self._mock_llm({"description": "New Desc", "amount": -12.00}):
            result = parse_edit_instruction(
                self.conn, self.tx, "change description to New Desc and amount to 12",
                self.accounts, self.budgets
            )
        self.assertEqual(result["description"], "New Desc")
        self.assertEqual(result["amount"], -12.00)


class TestHandleEditLlm(unittest.TestCase):
    """Tests for handle_edit_llm() in cli.py."""

    def setUp(self):
        self.conn = create_test_db()
        self.today = date(2026, 3, 8)

        add_subscription(self.conn, {
            "id": "budget_food", "name": "Food Budget", "category": "Food",
            "monthly_amount": 400.00, "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1), "is_budget": True
        })

        with patch('cashflow.controller.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, {
                "type": "simple", "description": "Test Expense",
                "amount": 30.00, "account": "Cash", "category": "Home Groceries",
            })

        from cashflow.repository import get_all_transactions
        txs = get_all_transactions(self.conn)
        self.tx = [t for t in txs if t['description'] == 'Test Expense'][0]

    def tearDown(self):
        self.conn.close()

    def _make_args(self, **kwargs):
        """Build a mock argparse.Namespace."""
        defaults = {
            'transaction_id': self.tx['id'],
            'instruction': 'change amount to 50',
            'yes': False,
            'all': False,
            'interactive': False,
        }
        defaults.update(kwargs)
        import argparse
        return argparse.Namespace(**defaults)

    @patch('llm.parser.date')
    @patch('llm.parser._call_llm')
    def test_yes_flag_skips_confirmation(self, mock_llm, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_llm.return_value = json.dumps({"amount": -50.00})

        from cli import handle_edit_llm
        args = self._make_args(yes=True)
        handle_edit_llm(self.conn, args)

        updated = get_transaction_by_id(self.conn, self.tx['id'])
        self.assertAlmostEqual(updated['amount'], -50.00)

    @patch('llm.parser.date')
    @patch('llm.parser._call_llm')
    def test_date_extracted_into_new_date(self, mock_llm, mock_date):
        """date_created in updates should be passed as new_date to controller."""
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_llm.return_value = json.dumps({"date_created": "2026-03-01"})

        from cli import handle_edit_llm
        args = self._make_args(instruction="change date to march 1", yes=True)
        handle_edit_llm(self.conn, args)

        # Date change uses delete+recreate, so find by description
        from cashflow.repository import get_all_transactions
        txs = get_all_transactions(self.conn)
        updated = [t for t in txs if t['description'] == 'Test Expense'][0]
        self.assertEqual(str(updated['date_created']), "2026-03-01")

    @patch('llm.parser.date')
    @patch('llm.parser._call_llm')
    def test_not_found_transaction(self, mock_llm, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        from cli import handle_edit_llm
        args = self._make_args(transaction_id=99999)
        handle_edit_llm(self.conn, args)
        # Should not crash, just print error
        mock_llm.assert_not_called()

    @patch('llm.parser.date')
    @patch('llm.parser._call_llm')
    def test_empty_updates_no_edit(self, mock_llm, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_llm.return_value = json.dumps({})

        from cli import handle_edit_llm
        args = self._make_args(instruction="do nothing", yes=True)
        handle_edit_llm(self.conn, args)

        # Transaction should be unchanged
        updated = get_transaction_by_id(self.conn, self.tx['id'])
        self.assertAlmostEqual(updated['amount'], self.tx['amount'])

    @patch('llm.parser.date')
    @patch('llm.parser._call_llm')
    @patch('builtins.input', return_value='n')
    def test_user_declines_confirmation(self, mock_input, mock_llm, mock_date):
        mock_date.today.return_value = self.today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_llm.return_value = json.dumps({"amount": -99.00})

        from cli import handle_edit_llm
        args = self._make_args(yes=False)
        handle_edit_llm(self.conn, args)

        # Transaction should be unchanged
        updated = get_transaction_by_id(self.conn, self.tx['id'])
        self.assertAlmostEqual(updated['amount'], self.tx['amount'])


if __name__ == '__main__':
    unittest.main()

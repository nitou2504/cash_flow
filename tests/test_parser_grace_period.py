import unittest
import json
from unittest.mock import patch, call
from datetime import date

from cashflow.database import create_test_db
from cashflow.repository import get_all_accounts, get_all_budgets
from llm.parser import parse_transaction_string


class TestParserGracePeriod(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()
        self.accounts = get_all_accounts(self.conn)
        self.budgets = get_all_budgets(self.conn)

    def tearDown(self):
        self.conn.close()

    @patch("llm.parser._call_llm")
    def test_grace_period_months_passes_through(self, mock_call_llm):
        """When the LLM returns grace_period_months, it should appear in the parsed result."""
        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "TV",
            "amount": 500,
            "account": "Visa Produbanco",
            "category": "Personal",
            "grace_period_months": 3
        })

        result = parse_transaction_string(
            self.conn, "Bought a TV for 500 on Visa Produbanco with 3 months grace period",
            self.accounts, self.budgets
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["grace_period_months"], 3)
        self.assertEqual(result["type"], "simple")
        self.assertEqual(result["amount"], 500)
        self.assertEqual(result["account"], "Visa Produbanco")

    @patch("llm.parser._call_llm")
    def test_no_grace_period_months_backward_compat(self, mock_call_llm):
        """When the LLM does not return grace_period_months, the field should be absent."""
        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "Lunch",
            "amount": 15.75,
            "account": "Cash",
            "category": "Dining-Snacks"
        })

        result = parse_transaction_string(
            self.conn, "lunch at cafe 15.75 cash",
            self.accounts, self.budgets
        )

        self.assertIsNotNone(result)
        self.assertNotIn("grace_period_months", result)
        self.assertEqual(result["type"], "simple")
        self.assertEqual(result["amount"], 15.75)

    @patch("llm.parser._call_llm")
    def test_grace_period_with_installments(self, mock_call_llm):
        """grace_period_months should also work with installment type transactions."""
        mock_call_llm.return_value = json.dumps({
            "type": "installment",
            "description": "New Phone",
            "total_amount": 900,
            "installments": 3,
            "account": "Visa Produbanco",
            "category": "Personal",
            "grace_period_months": 2
        })

        result = parse_transaction_string(
            self.conn, "New phone 900 in 3 installments on Visa Produbanco with 2 months grace",
            self.accounts, self.budgets
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["grace_period_months"], 2)
        self.assertEqual(result["type"], "installment")
        self.assertEqual(result["installments"], 3)


    @patch("llm.parser._call_llm")
    def test_prompt_includes_grace_period_schema(self, mock_call_llm):
        """The system prompt sent to the LLM should mention grace_period_months."""
        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "Test",
            "amount": 10,
            "account": "Cash",
            "category": "Personal"
        })

        parse_transaction_string(
            self.conn, "test input", self.accounts, self.budgets
        )

        # Verify _call_llm was called and the prompt mentions grace_period_months
        mock_call_llm.assert_called_once()
        system_prompt = mock_call_llm.call_args[1].get("system_prompt") or mock_call_llm.call_args[0][0]
        self.assertIn("grace_period_months", system_prompt)


if __name__ == "__main__":
    unittest.main()

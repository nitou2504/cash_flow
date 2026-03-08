import unittest
import json
from unittest.mock import patch

from cashflow.database import create_test_db


ACCOUNTS = [
    {'account_id': 'Cash'},
    {'account_id': 'Visa Pichincha'},
    {'account_id': 'Visa Produbanco'},
    {'account_id': 'Diners'},
]

BUDGETS = [
    {
        'id': 'budget_food',
        'name': 'Food Budget',
        'category': 'Dining-Snacks',
        'start_date': '2026-01-01',
        'end_date': '2026-12-31',
    },
]


class TestCategoryDescriptionsInPrompt(unittest.TestCase):
    """Tests that parse_transaction_string includes category descriptions in the LLM prompt."""

    def setUp(self):
        """Set up an in-memory database with categories."""
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch("llm.parser._call_llm")
    def test_prompt_contains_category_descriptions(self, mock_call_llm):
        """The system prompt should contain category descriptions in parentheses."""
        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "Supermaxi groceries",
            "amount": 25.0,
            "account": "Cash",
            "category": "Home Groceries",
        })

        from llm.parser import parse_transaction_string
        parse_transaction_string(self.conn, "supermaxi groceries 25 cash", ACCOUNTS, BUDGETS)

        mock_call_llm.assert_called_once()
        system_prompt = mock_call_llm.call_args[1].get("system_prompt") or mock_call_llm.call_args[0][0]

        # Verify descriptions appear in parenthesized format
        self.assertIn("Home Groceries (Food and household items for home)", system_prompt)
        self.assertIn("Dining-Snacks (Eating out, takeout, coffee, and social food/drinks)", system_prompt)
        self.assertIn("Personal (Discretionary spending, entertainment, hobbies, self-care)", system_prompt)
        self.assertIn("Income (Money received from work or investments)", system_prompt)

    @patch("llm.parser._call_llm")
    def test_prompt_contains_categories_without_descriptions_gracefully(self, mock_call_llm):
        """Categories without descriptions should appear by name only (no empty parens)."""
        # Insert a category with empty description
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO categories VALUES (?, ?)", ("TestCat", ""))
        self.conn.commit()

        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "test",
            "amount": 10.0,
            "account": "Cash",
            "category": "TestCat",
        })

        from llm.parser import parse_transaction_string
        parse_transaction_string(self.conn, "test 10 cash", ACCOUNTS, BUDGETS)

        mock_call_llm.assert_called_once()
        system_prompt = mock_call_llm.call_args[1].get("system_prompt") or mock_call_llm.call_args[0][0]

        # Category without description should appear without parentheses
        # It should NOT show "TestCat ()" — just "TestCat"
        self.assertNotIn("TestCat ()", system_prompt)
        self.assertIn("TestCat", system_prompt)

    @patch("llm.parser._call_llm")
    def test_category_names_still_in_schema_section(self, mock_call_llm):
        """The schema section should still reference category_names list for exact matching."""
        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "lunch",
            "amount": 12.0,
            "account": "Cash",
            "category": "Dining-Snacks",
        })

        from llm.parser import parse_transaction_string
        parse_transaction_string(self.conn, "lunch 12 cash", ACCOUNTS, BUDGETS)

        mock_call_llm.assert_called_once()
        system_prompt = mock_call_llm.call_args[1].get("system_prompt") or mock_call_llm.call_args[0][0]

        # The schema section should still list exact category names for the LLM to match
        # Look for the schema line that says "Must be one of {category_names}"
        self.assertIn("Must be one of [", system_prompt)
        self.assertIn("'Dining-Snacks'", system_prompt)
        self.assertIn("'Home Groceries'", system_prompt)

    @patch("llm.parser._call_llm")
    def test_parsed_result_returns_correct_category(self, mock_call_llm):
        """The parsed JSON should still have the correct exact category name."""
        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "Supermaxi - carnes",
            "amount": 9.99,
            "account": "Visa Pichincha",
            "category": "Home Groceries",
            "budget": "budget_food",
        })

        from llm.parser import parse_transaction_string
        result = parse_transaction_string(
            self.conn, "pichincha supermaxi carnes 9.99 home groceries budget", ACCOUNTS, BUDGETS
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "Home Groceries")
        self.assertEqual(result["type"], "simple")
        self.assertEqual(result["amount"], 9.99)

    @patch("llm.parser._call_llm")
    def test_prompt_has_help_text_for_descriptions(self, mock_call_llm):
        """The prompt should tell the LLM that descriptions are provided to help choose."""
        mock_call_llm.return_value = json.dumps({
            "type": "simple",
            "description": "test",
            "amount": 5.0,
            "account": "Cash",
            "category": "Others",
        })

        from llm.parser import parse_transaction_string
        parse_transaction_string(self.conn, "misc stuff 5 cash", ACCOUNTS, BUDGETS)

        mock_call_llm.assert_called_once()
        system_prompt = mock_call_llm.call_args[1].get("system_prompt") or mock_call_llm.call_args[0][0]

        # The rule text should mention descriptions help choose
        self.assertIn("descriptions in parentheses", system_prompt)


if __name__ == "__main__":
    unittest.main()

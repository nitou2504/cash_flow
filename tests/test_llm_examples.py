import json
import unittest
from datetime import date

from cashflow.database import create_test_db
from cashflow.repository import (
    add_transactions,
    get_all_transactions,
    save_llm_example,
)
from cashflow.controller import process_transaction_request


class TestAddTransactionsReturnsIds(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def test_returns_single_id(self):
        transaction = {
            "date_created": "2025-10-17",
            "date_payed": "2025-10-17",
            "description": "Coffee",
            "account": "Cash",
            "amount": -5.00,
            "category": "cafe",
            "budget": None,
            "status": "committed",
            "origin_id": None,
        }
        ids = add_transactions(self.conn, [transaction])
        self.assertEqual(len(ids), 1)
        self.assertIsInstance(ids[0], int)

    def test_returns_multiple_ids(self):
        txns = [
            {
                "date_created": "2025-10-18",
                "date_payed": "2025-11-25",
                "description": f"Item {i}",
                "account": "Cash",
                "amount": -10.00,
                "category": None,
                "budget": None,
                "status": "committed",
                "origin_id": "batch-1",
            }
            for i in range(3)
        ]
        ids = add_transactions(self.conn, txns)
        self.assertEqual(len(ids), 3)
        # IDs should be sequential
        self.assertEqual(ids[1], ids[0] + 1)
        self.assertEqual(ids[2], ids[0] + 2)

    def test_returned_ids_match_database(self):
        transaction = {
            "date_created": "2025-10-17",
            "date_payed": "2025-10-17",
            "description": "Lunch",
            "account": "Cash",
            "amount": -12.00,
            "category": None,
            "budget": None,
            "status": "committed",
            "origin_id": None,
        }
        ids = add_transactions(self.conn, [transaction])
        all_txns = get_all_transactions(self.conn)
        self.assertEqual(all_txns[0]["id"], ids[0])


class TestSaveLlmExample(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def _get_all_examples(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM llm_examples")
        return [dict(row) for row in cursor.fetchall()]

    def test_saves_example(self):
        parsed = {"type": "simple", "description": "Coffee", "amount": 3.50, "account": "Cash"}
        save_llm_example(self.conn, "cash, coffee, 3.50", parsed, [1], source="cli")

        examples = self._get_all_examples()
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["user_input"], "cash, coffee, 3.50")
        self.assertEqual(examples[0]["source"], "cli")
        self.assertEqual(examples[0]["transaction_ids"], "1")

        stored_json = json.loads(examples[0]["parsed_json"])
        self.assertEqual(stored_json["description"], "Coffee")
        self.assertEqual(stored_json["amount"], 3.50)

    def test_saves_multiple_transaction_ids(self):
        parsed = {"type": "installment", "description": "TV", "total_amount": 900}
        save_llm_example(self.conn, "visa, tv 900 in 3", parsed, [10, 11, 12])

        examples = self._get_all_examples()
        self.assertEqual(examples[0]["transaction_ids"], "10,11,12")

    def test_saves_telegram_source(self):
        parsed = {"type": "simple", "description": "Taxi", "amount": 5}
        save_llm_example(self.conn, "taxi 5 dollars", parsed, [1], source="telegram")

        examples = self._get_all_examples()
        self.assertEqual(examples[0]["source"], "telegram")

    def test_default_source_is_cli(self):
        parsed = {"type": "simple", "description": "Bus", "amount": 0.30}
        save_llm_example(self.conn, "bus 0.30", parsed, [1])

        examples = self._get_all_examples()
        self.assertEqual(examples[0]["source"], "cli")


class TestProcessTransactionSavesLlmExample(unittest.TestCase):
    """Integration tests: process_transaction_request saves LLM examples."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def _get_all_examples(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM llm_examples")
        return [dict(row) for row in cursor.fetchall()]

    def test_saves_example_on_simple_transaction(self):
        request = {
            "type": "simple",
            "description": "Supermaxi carnes",
            "amount": 9.99,
            "account": "Cash",
            "category": "Home Groceries",
            "budget": None,
        }
        user_input = "cash, supermaxi carnes, home groceries, 9.99"

        process_transaction_request(
            self.conn, request, user_input=user_input, source="cli"
        )

        examples = self._get_all_examples()
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["user_input"], user_input)
        self.assertEqual(examples[0]["source"], "cli")

        # transaction_ids should reference the actual inserted transaction
        txns = get_all_transactions(self.conn)
        self.assertEqual(examples[0]["transaction_ids"], str(txns[0]["id"]))

        # parsed_json should contain the original request
        stored = json.loads(examples[0]["parsed_json"])
        self.assertEqual(stored["description"], "Supermaxi carnes")

    def test_saves_example_on_installment_transaction(self):
        request = {
            "type": "installment",
            "description": "New TV",
            "total_amount": 900.00,
            "installments": 3,
            "account": "Visa Produbanco",
            "category": "Personal",
            "budget": None,
        }
        user_input = "visa produbanco, new tv 900 in 3 installments"

        process_transaction_request(
            self.conn, request, user_input=user_input, source="telegram"
        )

        examples = self._get_all_examples()
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["source"], "telegram")

        # Should have 3 comma-separated IDs
        id_parts = examples[0]["transaction_ids"].split(",")
        self.assertEqual(len(id_parts), 3)

    def test_no_example_saved_without_user_input(self):
        """When user_input is None (batch import, manual create), no example is saved."""
        request = {
            "type": "simple",
            "description": "Imported transaction",
            "amount": 25.00,
            "account": "Cash",
            "category": "Others",
            "budget": None,
        }

        process_transaction_request(self.conn, request)

        examples = self._get_all_examples()
        self.assertEqual(len(examples), 0)

    def test_saves_example_on_split_transaction(self):
        request = {
            "type": "split",
            "description": "Supermaxi mixed",
            "account": "Cash",
            "splits": [
                {"amount": 30, "category": "Home Groceries", "budget": None},
                {"amount": 15, "category": "Personal Groceries", "budget": None},
            ],
        }
        user_input = "cash, supermaxi 30 home groceries + 15 personal groceries"

        process_transaction_request(
            self.conn, request, user_input=user_input, source="cli"
        )

        examples = self._get_all_examples()
        self.assertEqual(len(examples), 1)

        id_parts = examples[0]["transaction_ids"].split(",")
        self.assertEqual(len(id_parts), 2)


if __name__ == "__main__":
    unittest.main()


import unittest
import sqlite3
from repository import (
    get_account_by_name,
    add_transactions,
    get_all_transactions,
)

# Placeholder for database setup logic
from database import create_tables, insert_initial_data


class TestRepository(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_tables(self.conn)
        insert_initial_data(self.conn)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_get_account_by_name(self):
        """
        Tests that an account can be retrieved by its name.
        """
        cash_account = get_account_by_name(self.conn, "Cash")
        self.assertIsNotNone(cash_account)
        self.assertEqual(cash_account["account_id"], "Cash")
        self.assertEqual(cash_account["account_type"], "cash")

        cc_account = get_account_by_name(self.conn, "Visa Produbanco")
        self.assertIsNotNone(cc_account)
        self.assertEqual(cc_account["cut_off_day"], 14)

    def test_add_single_transaction(self):
        """
        Tests adding a single transaction to the database.
        """
        transaction = {
            "date_created": "2025-10-17",
            "date_payed": "2025-10-17",
            "description": "Coffee",
            "account": "Cash",
            "amount": -5.00,
            "category": "cafe",
            "budget_category": "food",
            "status": "committed",
            "origin_id": None,
        }
        add_transactions(self.conn, [transaction])

        transactions = get_all_transactions(self.conn)
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]["description"], "Coffee")

    def test_add_multiple_transactions(self):
        """
        Tests adding multiple transactions in a single batch.
        """
        new_transactions = [
            {
                "date_created": "2025-10-18",
                "date_payed": "2025-11-25",
                "description": "Groceries",
                "account": "Visa Produbanco",
                "amount": -150.00,
                "category": "groceries",
                "budget_category": "food",
                "status": "committed",
                "origin_id": "20251018-A1",
            },
            {
                "date_created": "2025-10-18",
                "date_payed": "2025-11-25",
                "description": "Snacks",
                "account": "Visa Produbanco",
                "amount": -25.00,
                "category": "snacks",
                "budget_category": "personal",
                "status": "committed",
                "origin_id": "20251018-A1",
            },
        ]
        add_transactions(self.conn, new_transactions)

        transactions = get_all_transactions(self.conn)
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0]["origin_id"], "20251018-A1")
        self.assertEqual(transactions[1]["origin_id"], "20251018-A1")

    def test_get_all_transactions_empty(self):
        """
        Tests that retrieving from an empty transactions table returns an empty list.
        """
        # Clear the table first
        self.conn.execute("DELETE FROM transactions")
        self.conn.commit()
        
        transactions = get_all_transactions(self.conn)
        self.assertEqual(len(transactions), 0)


if __name__ == "__main__":
    unittest.main()

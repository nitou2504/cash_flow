import unittest
import sqlite3
import os
import csv
from datetime import date
from unittest.mock import patch

from database import create_connection, create_tables, insert_mock_data
from interface import export_transactions_to_csv
from main import process_transaction_request, run_monthly_rollover
from repository import add_subscription

class TestExport(unittest.TestCase):
    def setUp(self):
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.today = date(2025, 10, 15)
        self.test_csv_path = "test_transactions.csv"

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_export_transactions_to_csv_with_balance(self):
        """
        Tests that transactions are correctly exported to a CSV file
        with all columns, including the running balance.
        """
        print("\n--- Test: Export Transactions with Balance ---")
        
        # --- Setup ---
        add_subscription(self.conn, {
            "id": "budget_food", "name": "Food Budget", "category": "Food",
            "monthly_amount": 400, "payment_account_id": "Cash",
            "start_date": self.today.replace(day=1), "is_budget": True
        })
        
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.today)

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Movie ticket", "amount": 20,
            "account": "Cash", "category": "Entertainment"
        }, transaction_date=date(2025, 10, 10))

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Groceries", "amount": 80,
            "account": "Cash", "budget": "budget_food"
        }, transaction_date=date(2025, 10, 12))

        # --- Action ---
        export_transactions_to_csv(self.conn, self.test_csv_path, include_balance=True)

        # --- Verification ---
        self.assertTrue(os.path.exists(self.test_csv_path))
        
        with open(self.test_csv_path, 'r') as f:
            reader = csv.reader(f)
            lines = list(reader)
        
        print("\n--- CSV Content ---")
        for i, line in enumerate(lines):
            print(f"Line {i}: {line}")
        print("-------------------")

        # Header + 7 forecasts + 2 committed transactions = 10 lines
        self.assertEqual(len(lines), 10)
        
        # Check header
        expected_header = ["id", "date_created", "date_payed", "description", "account", "amount", "category", "budget", "status", "origin_id", "running_balance"]
        self.assertEqual(lines[0], expected_header)
        
        # Check the first data row (Food Budget)
        # Note: Amount is now -320 because of the grocery expense
        self.assertEqual(lines[1][3], "Food Budget")
        self.assertEqual(lines[1][5], "-320.0")
        self.assertEqual(lines[1][10], "-320.0")
        
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

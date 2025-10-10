
import unittest
import sqlite3
from unittest.mock import patch, MagicMock

from main import process_transaction_request

# Placeholder for database setup logic
from database import create_tables, insert_initial_data, create_connection


class TestMainController(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    @patch("main.repository")
    @patch("main.transactions")
    def test_process_transaction_request_simple(
        self, mock_transactions, mock_repository
    ):
        """
        Tests that a 'simple' transaction request correctly calls the
        'create_single_transaction' logic.
        """
        request = {
            "type": "simple",
            "description": "Taxi",
            "amount": 4.50,
            "account": "Cash",
            "category": "taxi",
            "budget": "transport",
        }
        mock_repository.get_account_by_name.return_value = {
            "account_id": "Cash",
            "account_type": "cash",
        }
        mock_transactions.create_single_transaction.return_value = {
            "description": "Test"
        }  # Dummy return

        process_transaction_request(self.conn, request)

        # Verify that the correct functions were called
        mock_repository.get_account_by_name.assert_called_once_with(
            self.conn, "Cash"
        )
        mock_transactions.create_single_transaction.assert_called_once()
        mock_repository.add_transactions.assert_called_once()

    @patch("main.repository")
    @patch("main.transactions")
    def test_process_transaction_request_installment(
        self, mock_transactions, mock_repository
    ):
        """
        Tests that an 'installment' transaction request correctly calls the
        'create_installment_transactions' logic.
        """
        request = {
            "type": "installment",
            "description": "New TV",
            "total_amount": 900.00,
            "installments": 3,
            "account": "Visa Produbanco",
            "category": "electronics",
            "budget": "shopping",
        }
        mock_repository.get_account_by_name.return_value = {
            "account_id": "Visa Produbanco",
            "account_type": "credit_card",
        }
        mock_transactions.create_installment_transactions.return_value = [
            {},
            {},
            {},
        ]  # Dummy

        process_transaction_request(self.conn, request)

        mock_repository.get_account_by_name.assert_called_once_with(
            self.conn, "Visa Produbanco"
        )
        mock_transactions.create_installment_transactions.assert_called_once()
        mock_repository.add_transactions.assert_called_once()

    @patch("main.repository")
    @patch("main.transactions")
    def test_process_transaction_request_split(
        self, mock_transactions, mock_repository
    ):
        """
        Tests that a 'split' transaction request correctly calls the
        'create_split_transactions' logic.
        """
        request = {
            "type": "split",
            "description": "Supermaxi",
            "account": "Visa Produbanco",
            "splits": [
                {"amount": 100, "category": "groceries", "budget": "food"},
                {"amount": 20, "category": "snacks", "budget": "personal"},
            ],
        }
        mock_repository.get_account_by_name.return_value = {
            "account_id": "Visa Produbanco",
            "account_type": "credit_card",
        }
        mock_transactions.create_split_transactions.return_value = [
            {},
            {},
        ]  # Dummy

        process_transaction_request(self.conn, request)

        mock_repository.get_account_by_name.assert_called_once_with(
            self.conn, "Visa Produbanco"
        )
        mock_transactions.create_split_transactions.assert_called_once()
        mock_repository.add_transactions.assert_called_once()


class TestMonthlyRollover(unittest.TestCase):
    def setUp(self):
        """Set up a full in-memory database for an integration test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        # Explicitly create the settings table for the test
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_run_monthly_rollover_integration(self):
        """
        An integration test for the entire monthly rollover process that
        simulates moving into a new month.
        """
        from main import generate_forecasts, run_monthly_rollover
        from repository import get_all_transactions, add_subscription
        from datetime import date
        from dateutil.relativedelta import relativedelta

        print("\n\n--- Running Test: test_run_monthly_rollover_integration ---")

        # --- Setup: Simulate a fixed point in time ---
        TEST_TODAY = date(2025, 10, 9)
        NEXT_MONTH = TEST_TODAY + relativedelta(months=1)
        print(f"--- Test: Simulated 'today' is {TEST_TODAY}. We will roll over to {NEXT_MONTH.strftime('%Y-%m')}. ---")

        # 1. Set a 3-month forecast horizon
        self.conn.execute(
            "UPDATE settings SET value = ? WHERE key = ?",
            ("3", "forecast_horizon_months")
        )
        self.conn.commit()
        print("--- Test: Set forecast horizon to 3 months. ---")

        # 2. Add a budget that started last month
        food_budget = {
            "id": "budget_food", "name": "Food", "category": "Food",
            "monthly_amount": 400, "payment_account_id": "Cash",
            "start_date": (TEST_TODAY - relativedelta(months=1)).replace(day=1),
            "is_budget": True
        }
        add_subscription(self.conn, food_budget)
        print(f"--- Test: Added 'Food' budget starting on {food_budget['start_date']}. ---")

        # 3. Generate initial forecasts from our simulated "today"
        print("\n--- Test Action: Generating initial forecasts (for Oct, Nov, Dec)... ---")
        generate_forecasts(self.conn, horizon_months=3, from_date=TEST_TODAY)
        
        # --- Action: Simulate running the process chronologically ---
        print(f"\n--- Test Action: Running rollover for {TEST_TODAY.strftime('%Y-%m')}... ---")
        run_monthly_rollover(self.conn, TEST_TODAY)
        
        print(f"\n--- Test Action: Running rollover for {NEXT_MONTH.strftime('%Y-%m')}... ---")
        run_monthly_rollover(self.conn, NEXT_MONTH)

        # --- Assertions ---
        print("\n--- Test Assertions: Verifying the results... ---")
        transactions = get_all_transactions(self.conn)
        
        # a) Check that NEXT month's budget (November) is now committed
        next_month_budget = next(
            t for t in transactions 
            if t['origin_id'] == 'budget_food' 
            and t['date_created'].month == NEXT_MONTH.month
        )
        self.assertEqual(next_month_budget['status'], 'committed')
        print(f"--- Test OK: Budget for {NEXT_MONTH.strftime('%Y-%m')} is now 'committed'. ---")

        # b) Check that the forecast horizon is still maintained
        new_forecast_count = sum(1 for t in transactions if t['status'] == 'forecast')
        self.assertEqual(new_forecast_count, 3)
        print(f"--- Test OK: Found {new_forecast_count} future forecasts, maintaining the 3-month horizon. ---")

        # c) Verify the new latest forecast is for the correct future month
        latest_forecast = max(t['date_created'] for t in transactions if t['status'] == 'forecast')
        expected_latest_month = (NEXT_MONTH + relativedelta(months=3))
        self.assertEqual(latest_forecast.month, expected_latest_month.month)
        print(f"--- Test OK: The latest forecast is correctly set for {latest_forecast.strftime('%Y-%m')}. ---")
        print("--- Test Finished Successfully ---\n")


if __name__ == "__main__":
    unittest.main()

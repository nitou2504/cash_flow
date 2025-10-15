import unittest
import sqlite3
from datetime import date

from repository import (
    get_account_by_name,
    add_transactions,
    get_all_transactions,
    add_subscription,
    get_subscription_by_id,
    get_all_active_subscriptions,
    delete_future_budget_allocations,
    update_future_forecasts_account,
    get_setting,
    commit_past_and_current_forecasts,
)
from database import create_tables, insert_mock_data, create_connection


class TestRepository(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_connection(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_tables(self.conn)
        insert_mock_data(self.conn)

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
            "budget": "food",
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
                "budget": "food",
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
                "budget": "personal",
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


class TestSubscriptionRepository(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_tables(self.conn)
        insert_mock_data(self.conn)

        # Sample subscriptions
        self.sub1 = {
            "id": "sub_spotify",
            "name": "Spotify",
            "category": "entertainment",
            "monthly_amount": 9.99,
            "payment_account_id": "Visa Produbanco",
            "start_date": date(2025, 1, 15),
            "end_date": None,
        }
        self.sub2 = {
            "id": "sub_gym",
            "name": "Gym Membership",
            "category": "health",
            "monthly_amount": 50.00,
            "payment_account_id": "Amex Produbanco",
            "start_date": date(2025, 3, 1),
            "end_date": date(2025, 8, 31),
        }
        add_subscription(self.conn, self.sub1)
        add_subscription(self.conn, self.sub2)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_add_and_get_subscription(self):
        """Tests that a subscription can be added and retrieved by its ID."""
        retrieved_sub = get_subscription_by_id(self.conn, "sub_spotify")
        self.assertIsNotNone(retrieved_sub)
        self.assertEqual(retrieved_sub["name"], "Spotify")

    def test_get_all_active_subscriptions(self):
        """Tests retrieving all subscriptions that are active on a given date."""
        # Active in April 2025
        active_subs = get_all_active_subscriptions(self.conn, date(2025, 4, 10))
        self.assertEqual(len(active_subs), 2)

        # Active in September 2025 (gym membership has ended)
        active_subs = get_all_active_subscriptions(self.conn, date(2025, 9, 1))
        self.assertEqual(len(active_subs), 1)
        self.assertEqual(active_subs[0]["id"], "sub_spotify")

    def test_delete_future_budget_allocations(self):
        """Tests deleting forecast transactions from a specific date."""
        # Add some forecast transactions
        forecasts = [
            {"date_created": "2025-10-15", "date_payed": "2025-11-10", "description": "Spotify", "account": "Visa Produbanco", "amount": -9.99, "category": "entertainment", "budget": None, "status": "forecast", "origin_id": "sub_spotify"},
            {"date_created": "2025-11-15", "date_payed": "2025-12-10", "description": "Spotify", "account": "Visa Produbanco", "amount": -9.99, "category": "entertainment", "budget": None, "status": "forecast", "origin_id": "sub_spotify"},
            {"date_created": "2025-12-15", "date_payed": "2026-01-10", "description": "Spotify", "account": "Visa Produbanco", "amount": -9.99, "category": "entertainment", "budget": None, "status": "forecast", "origin_id": "sub_spotify"},
        ]
        add_transactions(self.conn, forecasts)

        delete_future_budget_allocations(self.conn, "sub_spotify", date(2025, 11, 1))
        
        remaining_forecasts = get_all_transactions(self.conn)
        self.assertEqual(len(remaining_forecasts), 1)
        self.assertEqual(remaining_forecasts[0]["date_created"], "2025-10-15")

    def test_update_future_forecasts_account(self):
        """Tests updating the payment account for future forecast transactions."""
        forecasts = [
            {"date_created": "2025-10-15", "date_payed": "2025-11-10", "description": "Spotify", "account": "Visa Produbanco", "amount": -9.99, "category": "entertainment", "budget": None, "status": "forecast", "origin_id": "sub_spotify"},
            {"date_created": "2025-11-15", "date_payed": "2025-12-10", "description": "Spotify", "account": "Visa Produbanco", "amount": -9.99, "category": "entertainment", "budget": None, "status": "forecast", "origin_id": "sub_spotify"},
        ]
        add_transactions(self.conn, forecasts)

        update_future_forecasts_account(self.conn, "sub_spotify", date(2025, 11, 1), "Amex Produbanco")

        updated_forecasts = get_all_transactions(self.conn)
        self.assertEqual(updated_forecasts[0]["account"], "Visa Produbanco") # Unchanged
        self.assertEqual(updated_forecasts[1]["account"], "Amex Produbanco") # Changed


class TestSettingsRepository(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_tables(self.conn)
        # The settings table needs to be created for these tests
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_get_and_set_setting(self):
        """Tests that a setting can be saved and retrieved."""
        self.conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)",
                          ("forecast_horizon", "6"))
        self.conn.commit()

        horizon = get_setting(self.conn, "forecast_horizon")
        self.assertEqual(horizon, "6")

    def test_commit_forecasts_for_month(self):
        """
        Tests that all forecast transactions for a specific month are
        updated to 'committed'.
        """
        forecasts = [
            # Older past month → should be committed
            {"date_created": date(2025, 9, 25), "date_payed": "2025-09-30", "description": "September Forecast", "account": "Cash", "amount": -5, "category": "test", "budget": None, "status": "forecast", "origin_id": "E"},
            # Previous month → should be committed
            {"date_created": date(2025, 10, 5), "date_payed": "2025-10-15", "description": "October Forecast", "account": "Cash", "amount": -10, "category": "test", "budget": None, "status": "forecast", "origin_id": "A"},
            # Current month → should be committed
            {"date_created": date(2025, 11, 1), "date_payed": "2025-11-10", "description": "November Forecast", "account": "Cash", "amount": -15, "category": "test", "budget": None, "status": "forecast", "origin_id": "B"},
            # Future month → should NOT be committed
            {"date_created": date(2025, 12, 1), "date_payed": "2025-12-05", "description": "December Forecast", "account": "Cash", "amount": -20, "category": "test", "budget": None, "status": "forecast", "origin_id": "C"},
            # Already committed → should remain committed
            {"date_created": date(2025, 10, 1), "date_payed": "2025-10-05", "description": "October Committed", "account": "Cash", "amount": -5, "category": "test", "budget": None, "status": "committed", "origin_id": "D"},
        ]

        add_transactions(self.conn, forecasts)

        commit_past_and_current_forecasts(self.conn, date(2025, 11, 1))

        transactions = get_all_transactions(self.conn)
        
        status_map = {t['origin_id']: t['status'] for t in transactions}

        self.assertEqual(status_map['E'], 'committed')  # September → past month
        self.assertEqual(status_map['A'], 'committed')  # October → past month
        self.assertEqual(status_map['B'], 'committed')  # November → current month
        self.assertEqual(status_map['C'], 'forecast')   # December → future month
        self.assertEqual(status_map['D'], 'committed')  # Already committed → unchanged


if __name__ == "__main__":
    unittest.main()
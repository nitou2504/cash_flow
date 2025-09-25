
import unittest
from unittest.mock import patch
import sqlite3
from datetime import date
from dateutil.relativedelta import relativedelta

from main import generate_forecasts
from database import create_tables, insert_initial_data, create_connection
from repository import add_subscription, get_all_transactions, add_transactions

class TestScheduler(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)

        # Sample subscription that runs indefinitely
        self.sub_indefinite = {
            "id": "sub_spotify", "name": "Spotify", "category": "entertainment",
            "monthly_amount": 9.99, "payment_account_id": "Visa Produbanco",
            "start_date": date(2025, 1, 15), "end_date": None, "is_budget": False
        }
        
        # Sample subscription with a defined end date
        self.sub_limited = {
            "id": "sub_gym", "name": "Gym", "category": "health",
            "monthly_amount": 45.00, "payment_account_id": "Amex Produbanco",
            "start_date": date(2025, 1, 1), "end_date": date(2025, 3, 31), "is_budget": False
        }

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    @patch('main.date')
    def test_generate_forecasts_initial_creation(self, mock_date):
        """
        Tests that forecasts are created correctly for a new subscription.
        """
        # Pin 'today' to a specific date for predictable results
        mock_date.today.return_value = date(2025, 1, 1)
        add_subscription(self.conn, self.sub_indefinite)

        generate_forecasts(self.conn, horizon_months=3)

        transactions = get_all_transactions(self.conn)
        # Should generate for Jan, Feb, Mar
        self.assertEqual(len(transactions), 3)
        self.assertEqual(transactions[0]['origin_id'], 'sub_spotify')
        self.assertEqual(transactions[2]['date_created'], date(2025, 3, 15))

    @patch('main.date')
    def test_generate_forecasts_extends_existing(self, mock_date):
        """
        Tests that generate_forecasts only adds missing future forecasts.
        """
        mock_date.today.return_value = date(2025, 2, 1)
        add_subscription(self.conn, self.sub_indefinite)
        
        # Pre-add a forecast for Feb
        existing_forecast = {
            "date_created": date(2025, 2, 15), "date_payed": date(2025, 3, 25),
            "description": "Spotify", "account": "Visa Produbanco", "amount": -9.99,
            "category": "entertainment", "budget": None, "status": "forecast",
            "origin_id": "sub_spotify"
        }
        add_transactions(self.conn, [existing_forecast])

        # Horizon is 3 months: Feb, Mar, Apr
        generate_forecasts(self.conn, horizon_months=3)

        transactions = get_all_transactions(self.conn)
        # Should have the existing Feb forecast + new ones for Mar, Apr
        self.assertEqual(len(transactions), 3)
        # Check that the last one is for April
        self.assertEqual(transactions[2]['date_created'], date(2025, 4, 15))

    @patch('main.date')
    def test_generate_forecasts_respects_end_date(self, mock_date):
        """
        Tests that forecasts are not created after a subscription's end_date.
        """
        mock_date.today.return_value = date(2025, 1, 1)
        add_subscription(self.conn, self.sub_limited)

        # Horizon is 6 months, but subscription ends in March
        generate_forecasts(self.conn, horizon_months=6)

        transactions = get_all_transactions(self.conn)
        # Should only generate for Jan, Feb, Mar
        self.assertEqual(len(transactions), 3)
        self.assertEqual(transactions[2]['date_created'], date(2025, 3, 1))

    @patch('main.date')
    def test_generate_forecasts_no_duplicates(self, mock_date):
        """
        Tests that running the function multiple times doesn't create duplicates.
        """
        mock_date.today.return_value = date(2025, 1, 1)
        add_subscription(self.conn, self.sub_indefinite)

        generate_forecasts(self.conn, horizon_months=2)
        transactions = get_all_transactions(self.conn)
        self.assertEqual(len(transactions), 2)

        # Run it again with the same horizon
        generate_forecasts(self.conn, horizon_months=2)
        transactions = get_all_transactions(self.conn)
        self.assertEqual(len(transactions), 2)

if __name__ == '__main__':
    unittest.main()

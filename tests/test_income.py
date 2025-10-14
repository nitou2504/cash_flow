import unittest
from datetime import date
from unittest.mock import patch

from database import create_connection, create_tables, insert_initial_data
from repository import add_subscription, get_transactions_by_origin_id
from main import generate_forecasts

class TestIncomeTransactions(unittest.TestCase):
    def setUp(self):
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        self.today = date(2025, 11, 5)

    def tearDown(self):
        self.conn.close()

    def test_income_subscription_creates_positive_transactions(self):
        """
        Tests that a subscription marked as income generates transactions
        with positive amounts.
        """
        print("\n--- Test: Income Subscription ---")
        
        # 1. Add a salary subscription
        add_subscription(self.conn, {
            "id": "sub_salary",
            "name": "Monthly Salary",
            "category": "Income",
            "monthly_amount": 3000,
            "payment_account_id": "Cash",
            "start_date": self.today.replace(day=15),
            "is_income": True
        })

        # 2. Generate forecasts
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            generate_forecasts(self.conn, horizon_months=2)

        # 3. Verify the created transactions
        forecasts = get_transactions_by_origin_id(self.conn, "sub_salary")
        
        self.assertGreater(len(forecasts), 0, "No forecast transactions were created.")
        
        # Check that all generated transactions have a positive amount
        for t in forecasts:
            print(f"  - Generated transaction: {t['description']}, Amount: {t['amount']:.2f}")
            self.assertGreater(t['amount'], 0, "Income transaction should have a positive amount.")
            
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

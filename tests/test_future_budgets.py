import unittest
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_initial_data
from repository import (
    add_subscription, get_budget_allocation_for_month, get_all_transactions,
    get_setting, add_transactions
)
from main import process_transaction_request, generate_forecasts, run_monthly_rollover

class TestFutureBudgetImpact(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database and seed it for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        self.today = date(2025, 10, 15)

        # --- Setup Subscriptions ---
        # 1. Shopping Budget
        self.shopping_budget = {
            "id": "budget_shopping", "name": "Shopping Budget", "category": "Shopping",
            "monthly_amount": 250.00, "payment_account_id": "Visa Produbanco",
            "start_date": self.today.replace(day=1), "is_budget": True
        }
        add_subscription(self.conn, self.shopping_budget)

        # --- Initial State ---
        # Run a rollover to commit current month and generate forecasts
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.today)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_installment_deducts_from_existing_future_budget_forecast(self):
        """
        Tests that an installment purchase correctly reduces the balance of a future, forecasted budget.
        """
        print("\n--- Test: Installment deducts from EXISTING future budget ---")
        next_month = self.today + relativedelta(months=1)
        
        budget_before = get_budget_allocation_for_month(self.conn, "budget_shopping", next_month)
        print(f"STEP 1: Pre-Condition Verification")
        print(f"  - November's forecasted budget exists and has a balance of {budget_before['amount']:.2f}.")
        self.assertIsNotNone(budget_before)
        self.assertEqual(budget_before["amount"], -250.00)

        print("\nSTEP 2: Action")
        print("  - Logging a $300 purchase in 3 installments ($100/month).")
        installment_request = {
            "type": "installment", "description": "New Phone", "total_amount": 300.00,
            "installments": 3, "account": "Visa Produbanco", "budget": "budget_shopping"
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, installment_request)
        
        print("\nSTEP 3: Post-Condition Verification")
        budget_after = get_budget_allocation_for_month(self.conn, "budget_shopping", next_month)
        print(f"  - November's budget is now {budget_after['amount']:.2f}. Expected: -150.00 (-250 + 100).")
        self.assertAlmostEqual(budget_after["amount"], -150.00)

        month_after_next = self.today + relativedelta(months=2)
        budget_month_3 = get_budget_allocation_for_month(self.conn, "budget_shopping", month_after_next)
        print(f"  - December's budget is now {budget_month_3['amount']:.2f}. Expected: -150.00 (-250 + 100).")
        self.assertAlmostEqual(budget_month_3["amount"], -150.00)
        print("--- Test Complete ---")

    def test_installment_auto_creates_budget_allocation_if_missing(self):
        """
        Tests that an installment purchase for a future month where no budget forecast exists
        will automatically create that budget allocation.
        """
        print("\n--- Test: Installment AUTO-CREATES missing future budget ---")
        far_future_month = self.today + relativedelta(months=7)

        print("STEP 1: Pre-Condition Verification")
        budget_before = get_budget_allocation_for_month(self.conn, "budget_shopping", far_future_month)
        print(f"  - Budget for {far_future_month.strftime('%B %Y')} does not exist yet (is None).")
        self.assertIsNone(budget_before)

        print("\nSTEP 2: Action")
        print("  - Logging a $1200 purchase in 12 installments ($100/month).")
        installment_request = {
            "type": "installment", "description": "New Laptop", "total_amount": 1200.00,
            "installments": 12, "account": "Visa Produbanco", "budget": "budget_shopping"
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, installment_request)

        print("\nSTEP 3: Post-Condition Verification")
        budget_after = get_budget_allocation_for_month(self.conn, "budget_shopping", far_future_month)
        print(f"  - Budget for {far_future_month.strftime('%B %Y')} has been auto-created.")
        self.assertIsNotNone(budget_after)
        
        print(f"  - Its balance is {budget_after['amount']:.2f}. Expected: -150.00 (-250 + 100).")
        self.assertAlmostEqual(budget_after["amount"], -150.00)
        
        print(f"  - Its status is '{budget_after['status']}'. Expected: 'forecast'.")
        self.assertEqual(budget_after["status"], "forecast")
        print("--- Test Complete ---")

    def test_generate_forecasts_respects_existing_committed_installments(self):
        """
        Tests that when the forecast generator runs, it correctly calculates a new budget's
        starting balance if committed expenses for that month already exist.
        """
        print("\n--- Test: Forecast Generator RESPECTS existing commitments ---")
        target_month = self.today + relativedelta(months=7)
        
        print("STEP 1: Setup")
        print(f"  - Manually inserting a committed $75.00 expense for {target_month.strftime('%B %Y')}.")
        committed_expense = {
            "date_created": self.today, "date_payed": target_month,
            "description": "Old Installment (7/12)", "account": "Visa Produbanco",
            "amount": -75.00, "category": "electronics", "budget": "budget_shopping",
            "status": "committed", "origin_id": "old_purchase"
        }
        add_transactions(self.conn, [committed_expense])

        print("\nSTEP 2: Action")
        print("  - Moving time forward one month and running forecast generation.")
        new_today = self.today + relativedelta(months=1)
        with patch('main.date') as mock_date:
            mock_date.today.return_value = new_today
            horizon = int(get_setting(self.conn, "forecast_horizon_months"))
            generate_forecasts(self.conn, horizon, from_date=new_today)
        print(f"  - This brings {target_month.strftime('%B %Y')} into the forecast window.")

        print("\nSTEP 3: Post-Condition Verification")
        budget_allocation = get_budget_allocation_for_month(self.conn, "budget_shopping", target_month)
        print(f"  - The newly created budget for {target_month.strftime('%B %Y')} should have a starting balance that accounts for the old expense.")
        self.assertIsNotNone(budget_allocation)
        print(f"  - Its balance is {budget_allocation['amount']:.2f}. Expected: -175.00 (-250 + 75).")
        self.assertAlmostEqual(budget_allocation["amount"], -175.00)
        print("--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

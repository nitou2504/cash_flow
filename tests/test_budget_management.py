import unittest
import sqlite3
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_initial_data
from repository import (
    add_subscription, get_all_transactions, get_subscription_by_id,
    get_budget_allocation_for_month, commit_forecasts_for_month
)
from main import generate_forecasts, process_transaction_request, process_budget_update

class TestBudgetUpdate(unittest.TestCase):
    def setUp(self):
        """Set up a consistent scenario for testing budget updates."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        self.today = date(2025, 10, 15)
        self.current_month = self.today.replace(day=1)
        self.next_month = (self.today + relativedelta(months=1)).replace(day=1)

        # 1. Create a "Shopping" budget subscription
        self.budget_id = "budget_shopping"
        shopping_budget = {
            "id": self.budget_id, "name": "Shopping Budget", "category": "Shopping",
            "monthly_amount": 200.00, "payment_account_id": "Visa Produbanco",
            "start_date": self.today - relativedelta(months=2), "is_budget": True
        }
        add_subscription(self.conn, shopping_budget)

        # 2. Generate forecasts for the next 6 months
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            generate_forecasts(self.conn, 6)

        # 3. Commit the current month's forecast to make it "live"
        commit_forecasts_for_month(self.conn, self.current_month)

        # 4. Log an expense against the current month's budget
        expense_request = {
            "type": "simple", "description": "New Shoes", "amount": 50.00,
            "account": "Visa Produbanco", "budget": self.budget_id
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, expense_request)

    def tearDown(self):
        self.conn.close()

    def test_update_budget_for_current_month(self):
        """
        Tests increasing a budget for the current, active month.
        It should update the live balance and all future forecasts.
        """
        # Action: Increase budget from 200 to 300, effective this month
        process_budget_update(self.conn, self.budget_id, 300.00, self.today)

        # Assertion 1: The subscription definition is updated
        sub = get_subscription_by_id(self.conn, self.budget_id)
        self.assertAlmostEqual(sub['monthly_amount'], 300.00)

        # Assertion 2: The current month's live allocation is recalculated
        # Initial state was -200 + 50 = -150. New state should be -300 + 50 = -250.
        current_allocation = get_budget_allocation_for_month(self.conn, self.budget_id, self.current_month)
        self.assertAlmostEqual(current_allocation['amount'], -250.00)

        # Assertion 3: Future forecasts are wiped and regenerated with the new amount
        future_allocation = get_budget_allocation_for_month(self.conn, self.budget_id, self.next_month)
        self.assertIsNotNone(future_allocation)
        self.assertAlmostEqual(future_allocation['amount'], -300.00)
        self.assertEqual(future_allocation['status'], 'forecast')

    def test_update_budget_for_future_month(self):
        """
        Tests changing a budget for a future month.
        It should NOT affect the current month's live balance.
        """
        # Action: Increase budget from 200 to 250, effective NEXT month
        process_budget_update(self.conn, self.budget_id, 250.00, self.next_month)

        # Assertion 1: The subscription definition is updated
        sub = get_subscription_by_id(self.conn, self.budget_id)
        self.assertAlmostEqual(sub['monthly_amount'], 250.00)

        # Assertion 2: The current month's live allocation is UNCHANGED
        current_allocation = get_budget_allocation_for_month(self.conn, self.budget_id, self.current_month)
        self.assertAlmostEqual(current_allocation['amount'], -150.00) # -200 + 50

        # Assertion 3: Future forecasts are regenerated with the new amount
        future_allocation = get_budget_allocation_for_month(self.conn, self.budget_id, self.next_month)
        self.assertIsNotNone(future_allocation)
        self.assertAlmostEqual(future_allocation['amount'], -250.00)

    def test_update_budget_makes_current_month_overspent(self):
        """
        Tests decreasing a budget for the current month, causing it to become overspent.
        """
        # Action: Decrease budget from 200 to 40 (less than the 50 already spent)
        process_budget_update(self.conn, self.budget_id, 40.00, self.today)

        # Assertion 1: The subscription is updated
        sub = get_subscription_by_id(self.conn, self.budget_id)
        self.assertAlmostEqual(sub['monthly_amount'], 40.00)

        # Assertion 2: The current month's allocation is capped at 0
        # New balance would be -40 + 50 = +10, which should be capped at 0.
        current_allocation = get_budget_allocation_for_month(self.conn, self.budget_id, self.current_month)
        self.assertAlmostEqual(current_allocation['amount'], 0)

        # Assertion 3: Future forecasts are regenerated with the new, lower amount
        future_allocation = get_budget_allocation_for_month(self.conn, self.budget_id, self.next_month)
        self.assertAlmostEqual(future_allocation['amount'], -40.00)

    def test_decrease_budget_while_already_overspent(self):
        """
        Tests decreasing a budget that is already overspent for the current month.
        """
        # 1. Log another expense to ensure we are significantly overspent
        over_expense = {
            "type": "simple", "description": "Luxury Item", "amount": 200.00,
            "account": "Visa Produbanco", "budget": self.budget_id
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, over_expense)
        
        # Initial state check: budget is 200, spent is 250. Allocation should be 0.
        allocation_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.current_month)
        self.assertAlmostEqual(allocation_before['amount'], 0)

        # 2. Action: Decrease budget from 200 to 150
        process_budget_update(self.conn, self.budget_id, 150.00, self.today)

        # 3. Assertions
        sub = get_subscription_by_id(self.conn, self.budget_id)
        self.assertAlmostEqual(sub['monthly_amount'], 150.00)

        # Current allocation should remain 0 (-150 + 250 = +100 -> capped at 0)
        allocation_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.current_month)
        self.assertAlmostEqual(allocation_after['amount'], 0)

        # Future forecasts should be the new, lower amount
        future_allocation = get_budget_allocation_for_month(self.conn, self.budget_id, self.next_month)
        self.assertAlmostEqual(future_allocation['amount'], -150.00)

if __name__ == "__main__":
    unittest.main()

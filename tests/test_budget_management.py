import unittest
import sqlite3
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_mock_data
from repository import (
    add_subscription, get_all_transactions, get_subscription_by_id,
    get_budget_allocation_for_month, commit_past_and_current_forecasts
)
from main import generate_forecasts, process_transaction_request, process_budget_update

class TestBudgetUpdate(unittest.TestCase):
    def setUp(self):
        """Set up a consistent scenario for testing budget updates."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.today = date(2025, 10, 10)
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
        commit_past_and_current_forecasts(self.conn, self.current_month)

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


class TestFutureDatedBudgetUpdate(unittest.TestCase):
    def setUp(self):
        """Set up a scenario where an expense is pushed to a future budget."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        # Transaction date is AFTER the Visa cut-off day (14th)
        self.today = date(2025, 10, 15)
        self.current_month = self.today.replace(day=1)
        self.next_month = (self.today + relativedelta(months=1)).replace(day=1)
        self.month_after_next = (self.today + relativedelta(months=2)).replace(day=1)

        self.budget_id = "budget_shopping"
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Shopping Budget", "category": "Shopping",
            "monthly_amount": 200.00, "payment_account_id": "Visa Produbanco",
            "start_date": self.current_month, "is_budget": True
        })

        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            generate_forecasts(self.conn, 6)
        
        commit_past_and_current_forecasts(self.conn, self.current_month)

        print("\n--- Test: Future-Dated Budget Update ---")
        print(f"SETUP: Today is {self.today}. Visa cut-off is day 14.")
        
        # This expense is created on Oct 15, but its date_payed will be in November
        expense_request = {
            "type": "simple", "description": "Late Month Purchase", "amount": 50.00,
            "account": "Visa Produbanco", "budget": self.budget_id
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, expense_request)
        
        print("SETUP: Logged a $50.00 expense. Because it's after the cut-off, its 'date_payed' is in November.")


    def tearDown(self):
        self.conn.close()

    def test_budget_update_affects_correct_future_month(self):
        """
        Tests that updating a budget correctly recalculates a future month's balance
        that has been affected by a credit card purchase from the current month.
        """
        # Pre-condition check: Current month is untouched, next month is affected
        allocation_current = get_budget_allocation_for_month(self.conn, self.budget_id, self.current_month)
        allocation_next = get_budget_allocation_for_month(self.conn, self.budget_id, self.next_month)
        
        print("\nSTEP 1: Pre-Condition Verification")
        print(f"  - October Budget ('current'): {allocation_current['amount']:.2f}. Expected: -200.00 (Correct, expense was for Nov).")
        print(f"  - November Budget ('next'): {allocation_next['amount']:.2f}. Expected: -150.00 (Correct, -200 + 50 expense).")
        
        self.assertAlmostEqual(allocation_current['amount'], -200.00)
        self.assertAlmostEqual(allocation_next['amount'], -150.00)

        # Action: Update the budget to 300, effective for the NEXT month
        print("\nSTEP 2: Action")
        print(f"  - Calling process_budget_update for November with new amount: 300.00")
        process_budget_update(self.conn, self.budget_id, 300.00, self.next_month)

        # Assertion 1: Current month's allocation remains untouched
        allocation_current_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.current_month)
        print("\nSTEP 3: Post-Condition Verification")
        print(f"  - October Budget: {allocation_current_after['amount']:.2f}. Expected: -200.00 (Correct, update was for the future).")
        self.assertAlmostEqual(allocation_current_after['amount'], -200.00)

        # Assertion 2: Next month's allocation is correctly recalculated
        # New balance should be -300 + 50 = -250
        allocation_next_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.next_month)
        print(f"  - November Budget: {allocation_next_after['amount']:.2f}. Expected: -250.00 (Correct, new base of -300 + 50 expense).")
        self.assertAlmostEqual(allocation_next_after['amount'], -250.00)

        # Assertion 3: The forecast for the month after next is updated
        allocation_future = get_budget_allocation_for_month(self.conn, self.budget_id, self.month_after_next)
        print(f"  - December Budget: {allocation_future['amount']:.2f}. Expected: -300.00 (Correct, future forecasts regenerated).")
        self.assertAlmostEqual(allocation_future['amount'], -300.00)
        print("\n--- Test Complete ---")


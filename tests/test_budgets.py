
import unittest
import sqlite3
from datetime import date
from unittest.mock import patch

from main import process_transaction_request, run_monthly_budget_reconciliation
from database import create_connection, create_tables, insert_initial_data
from repository import add_subscription, get_all_transactions, add_transactions, get_budget_allocation_for_month

class TestBudgetLogic(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)

        # 1. Create a budget subscription for "Food"
        self.food_budget_sub = {
            "id": "budget_food", "name": "Food Budget", "category": "Food",
            "monthly_amount": 300.00, "payment_account_id": "Cash",
            "start_date": date(2025, 1, 1), "is_budget": True,
            "underspend_behavior": "return"
        }
        add_subscription(self.conn, self.food_budget_sub)

        # 2. Create the initial budget allocation transaction for the current month
        self.current_month_start = date.today().replace(day=1)
        self.initial_allocation = {
            "date_created": self.current_month_start,
            "date_payed": self.current_month_start,
            "description": "Food Budget", "account": "Cash", "amount": -300.00,
            "category": "Food", "budget": "budget_food", "status": "committed",
            "origin_id": "budget_food"
        }
        add_transactions(self.conn, [self.initial_allocation])

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_expense_reduces_budget_allocation(self):
        """
        Tests that a committed expense correctly reduces the amount of the
        corresponding budget allocation transaction for the month.
        """
        # A $50 grocery expense
        expense_request = {
            "type": "simple", "description": "Groceries", "amount": 50.00,
            "account": "Cash", "category": "groceries", "budget": "budget_food"
        }
        process_transaction_request(self.conn, expense_request)

        # Verify the budget allocation was updated
        allocation = get_budget_allocation_for_month(self.conn, "budget_food", self.current_month_start)
        self.assertAlmostEqual(allocation["amount"], -250.00)

    def test_overspending_caps_budget_at_zero(self):
        """
        Tests that if an expense exceeds the remaining budget, the allocation
        amount is capped at 0 and does not become positive.
        """
        # A $400 expense, which is $100 over budget
        over_expense_request = {
            "type": "simple", "description": "Fancy Dinner", "amount": 400.00,
            "account": "Cash", "category": "dining", "budget": "budget_food"
        }
        process_transaction_request(self.conn, over_expense_request)

        # Verify the budget allocation is now 0
        allocation = get_budget_allocation_for_month(self.conn, "budget_food", self.current_month_start)
        self.assertAlmostEqual(allocation["amount"], 0)

    def test_underspend_return_creates_release_transaction(self):
        """
        Tests the month-end reconciliation for an underspent budget with the
        'return' policy. It should create a positive "Budget Release"
        transaction and zero out the original allocation.
        """
        # Log a $100 expense, leaving $200 in the budget
        expense = {
            "type": "simple", "description": "Groceries", "amount": 100.00,
            "account": "Cash", "category": "groceries", "budget": "budget_food"
        }
        process_transaction_request(self.conn, expense)

        # Run month-end reconciliation
        run_monthly_budget_reconciliation(self.conn, self.current_month_start)

        # Verify results
        transactions = get_all_transactions(self.conn)
        original_allocation = next(t for t in transactions if t["description"] == "Food Budget")
        release_transaction = next(t for t in transactions if "Budget Release" in t["description"])

        self.assertEqual(len(transactions), 3) # Initial Allocation + Expense + Release
        self.assertAlmostEqual(original_allocation["amount"], 0)
        self.assertAlmostEqual(release_transaction["amount"], 200.00) # Positive inflow
        self.assertEqual(release_transaction["status"], "committed")

    def test_underspend_keep_does_nothing(self):
        """
        Tests the month-end reconciliation for an underspent budget with the
        'keep' policy. It should not create any new transactions and the
        original allocation should remain untouched.
        """
        # Update subscription to 'keep'
        self.conn.execute("UPDATE subscriptions SET underspend_behavior = 'keep' WHERE id = 'budget_food'")
        self.conn.commit()

        # Log a $100 expense, leaving $200
        expense = {
            "type": "simple", "description": "Groceries", "amount": 100.00,
            "account": "Cash", "category": "groceries", "budget": "budget_food"
        }
        process_transaction_request(self.conn, expense)

        # Run month-end reconciliation
        run_monthly_budget_reconciliation(self.conn, self.current_month_start)

        # Verify results
        transactions = get_all_transactions(self.conn)
        original_allocation = get_budget_allocation_for_month(self.conn, "budget_food", self.current_month_start)

        self.assertEqual(len(transactions), 2) # Initial Allocation + Expense
        self.assertAlmostEqual(original_allocation["amount"], -200.00) # Unchanged


if __name__ == "__main__":
    unittest.main()

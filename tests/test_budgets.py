
import unittest
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from cashflow.controller import process_transaction_request, run_monthly_budget_reconciliation, run_monthly_rollover
from cashflow.database import create_test_db
from cashflow.repository import add_subscription, get_all_transactions, add_transactions, get_budget_allocation_for_month

class TestBudgetLogic(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_test_db()

        # 1. Create a budget subscription for "Home Groceries"
        self.food_budget_sub = {
            "id": "budget_food", "name": "Food Budget", "category": "Home Groceries",
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
            "category": "Home Groceries", "budget": "budget_food", "status": "committed",
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
            "account": "Cash", "category": "Home Groceries", "budget": "budget_food"
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
            "account": "Cash", "category": "Dining-Snacks", "budget": "budget_food"
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
            "account": "Cash", "category": "Home Groceries", "budget": "budget_food"
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
            "account": "Cash", "category": "Home Groceries", "budget": "budget_food"
        }
        process_transaction_request(self.conn, expense)

        # Run month-end reconciliation
        run_monthly_budget_reconciliation(self.conn, self.current_month_start)

        # Verify results
        transactions = get_all_transactions(self.conn)
        original_allocation = get_budget_allocation_for_month(self.conn, "budget_food", self.current_month_start)

        self.assertEqual(len(transactions), 2) # Initial Allocation + Expense
        self.assertAlmostEqual(original_allocation["amount"], -200.00) # Unchanged


class TestRolloverBudgetReconciliation(unittest.TestCase):
    """Integration tests for budget reconciliation triggered via run_monthly_rollover."""

    def setUp(self):
        self.conn = create_test_db()

        # "return" budget starting two months ago
        self.two_months_ago = date.today().replace(day=1) - relativedelta(months=2)
        self.last_month = date.today().replace(day=1) - relativedelta(months=1)
        self.current_month = date.today().replace(day=1)

        self.budget_sub = {
            "id": "budget_food", "name": "Food Budget", "category": "Home Groceries",
            "monthly_amount": 300.00, "payment_account_id": "Cash",
            "start_date": self.last_month, "is_budget": True,
            "underspend_behavior": "return"
        }
        add_subscription(self.conn, self.budget_sub)

    def tearDown(self):
        self.conn.close()

    def _create_allocation(self, month, amount=-300.00):
        add_transactions(self.conn, [{
            "date_created": month, "date_payed": month,
            "description": "Food Budget", "account": "Cash",
            "amount": amount, "category": "Home Groceries", "budget": "budget_food",
            "status": "committed", "origin_id": "budget_food"
        }])

    def _create_expense(self, month, amount):
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Groceries",
            "amount": amount, "account": "Cash",
            "category": "Home Groceries", "budget": "budget_food",
        }, transaction_date=month.replace(day=15))

    def test_rollover_triggers_return_for_past_month(self):
        """run_monthly_rollover reconciles past months with 'return' underspend."""
        # Allocation for last month, with $100 spent => $200 underspend
        self._create_allocation(self.last_month)
        self._create_expense(self.last_month, 100.00)

        # Allocation for current month (should NOT be touched)
        self._create_allocation(self.current_month)

        run_monthly_rollover(self.conn, date.today())

        transactions = get_all_transactions(self.conn)
        releases = [t for t in transactions if "Budget Release" in t["description"]]
        self.assertEqual(len(releases), 1)
        self.assertAlmostEqual(releases[0]["amount"], 200.00)

        # Current month allocation untouched
        current_alloc = get_budget_allocation_for_month(self.conn, "budget_food", self.current_month)
        self.assertAlmostEqual(current_alloc["amount"], -300.00)

    def test_rollover_skips_current_month(self):
        """Current month budget should NOT be reconciled."""
        self._create_allocation(self.current_month)
        self._create_expense(self.current_month, 100.00)

        run_monthly_rollover(self.conn, date.today())

        transactions = get_all_transactions(self.conn)
        releases = [t for t in transactions if "Budget Release" in t["description"]]
        self.assertEqual(len(releases), 0)

        # Allocation still has underspend (not zeroed)
        alloc = get_budget_allocation_for_month(self.conn, "budget_food", self.current_month)
        self.assertAlmostEqual(alloc["amount"], -200.00)

    def test_rollover_idempotent_for_return(self):
        """Running rollover twice should not create duplicate releases."""
        self._create_allocation(self.last_month)
        self._create_expense(self.last_month, 100.00)

        run_monthly_rollover(self.conn, date.today())
        run_monthly_rollover(self.conn, date.today())

        transactions = get_all_transactions(self.conn)
        releases = [t for t in transactions if "Budget Release" in t["description"]]
        self.assertEqual(len(releases), 1)


if __name__ == "__main__":
    unittest.main()

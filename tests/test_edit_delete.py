import unittest
import sqlite3
from datetime import date
from unittest.mock import patch

from database import create_connection, create_tables, insert_mock_data
from repository import (
    add_transactions, get_all_transactions, get_transaction_by_id,
    add_subscription, get_budget_allocation_for_month
)
from main import process_transaction_update, process_transaction_deletion, process_transaction_request

class TestTransactionEditingAndDeletion(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database and seed it with initial data for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.today = date(2025, 10, 10)

        # --- Setup a consistent scenario for testing ---
        # 1. Create a budget subscription
        add_subscription(self.conn, {
            "id": "budget_food", "name": "Food Budget", "category": "Food",
            "monthly_amount": 400.00, "payment_account_id": "Cash",
            "start_date": self.today.replace(day=1), "is_budget": True
        })

        # 2. Create a budget allocation for "Food"
        self.food_budget_allocation = {
            "date_created": self.today.replace(day=1),
            "date_payed": self.today.replace(day=1),
            "description": "Food Budget", "account": "Cash", "amount": -400.00,
            "category": "Food", "budget": "budget_food", "status": "committed",
            "origin_id": "budget_food",
        }
        add_transactions(self.conn, [self.food_budget_allocation])

        # 3. Create a simple transaction to be edited/deleted
        self.initial_expense = {
            "type": "simple", "description": "Weekly Groceries", "amount": 50.00,
            "account": "Cash", "budget": "budget_food"
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, self.initial_expense)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_update_transaction_amount_increase_and_adjusts_budget(self):
        """
        Tests that increasing an expense's amount correctly adjusts the linked budget's live balance.
        """
        expense_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Weekly Groceries')
        
        updates = {"amount": -75.00}
        process_transaction_update(self.conn, expense_to_update['id'], updates)

        budget_after = get_budget_allocation_for_month(self.conn, "budget_food", self.today)
        self.assertAlmostEqual(budget_after["amount"], -325.00)

    def test_update_transaction_amount_decrease_and_adjusts_budget(self):
        """
        Tests that decreasing an expense's amount correctly adjusts the linked budget's live balance.
        """
        expense_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Weekly Groceries')
        
        updates = {"amount": -25.00}
        process_transaction_update(self.conn, expense_to_update['id'], updates)

        budget_after = get_budget_allocation_for_month(self.conn, "budget_food", self.today)
        self.assertAlmostEqual(budget_after["amount"], -375.00)

    def test_delete_transaction_and_reverses_budget_impact(self):
        """
        Tests that deleting an expense correctly "returns" the amount to the linked budget.
        """
        expense_to_delete = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Weekly Groceries')
        
        process_transaction_deletion(self.conn, expense_to_delete['id'])

        budget_after = get_budget_allocation_for_month(self.conn, "budget_food", self.today)
        self.assertAlmostEqual(budget_after["amount"], -400.00)

    def test_add_budget_to_existing_transaction(self):
        """
        Tests that adding a budget link to a transaction correctly updates the budget.
        """
        # 1. Create a transaction with no budget
        no_budget_expense = {
            "type": "simple", "description": "Snacks", "amount": 20.00,
            "account": "Cash", "budget": None
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, no_budget_expense)

        # Verify budget is initially untouched
        budget_before = get_budget_allocation_for_month(self.conn, "budget_food", self.today)
        self.assertAlmostEqual(budget_before["amount"], -350.00)

        # 2. Update the transaction to add the budget link
        expense_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Snacks')
        process_transaction_update(self.conn, expense_to_update['id'], {"budget": "budget_food"})

        # 3. Verify the budget was reduced
        budget_after = get_budget_allocation_for_month(self.conn, "budget_food", self.today)
        # Should be -350 (from initial expense) - 20 (from new expense) = -330, but recalculation is total
        # Total spent is now 50 + 20 = 70. New balance is -400 + 70 = -330
        self.assertAlmostEqual(budget_after["amount"], -330.00)

    def test_remove_budget_from_existing_transaction(self):
        """
        Tests that removing a budget link from a transaction correctly "returns" the money.
        """
        # Initial state: budget is -350 from the -50 expense
        expense_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Weekly Groceries')

        # Update the transaction to remove the budget link
        process_transaction_update(self.conn, expense_to_update['id'], {"budget": None})

        # Verify the budget was restored
        budget_after = get_budget_allocation_for_month(self.conn, "budget_food", self.today)
        # After removing the expense, there is no spending, so budget should be -400
        self.assertAlmostEqual(budget_after["amount"], -400.00)


class TestOverspendingScenarios(unittest.TestCase):
    def setUp(self):
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.today = date(2025, 10, 10)

        # Setup a -100 budget
        add_subscription(self.conn, {
            "id": "budget_transport", "name": "Transport Budget", "category": "Transport",
            "monthly_amount": 100, "payment_account_id": "Cash",
            "start_date": self.today.replace(day=1), "is_budget": True
        })
        
        add_transactions(self.conn, [{
            "date_created": self.today.replace(day=1), "date_payed": self.today.replace(day=1),
            "description": "Transport Budget", "account": "Cash", "amount": -100,
            "category": "Transport", "budget": "budget_transport", "status": "committed", "origin_id": "budget_transport"
        }])

        # Log expenses to be overspent (-120 total)
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            process_transaction_request(self.conn, {"type": "simple", "description": "Gas", "amount": 90, "account": "Cash", "budget": "budget_transport"})
            process_transaction_request(self.conn, {"type": "simple", "description": "Tires", "amount": 30, "account": "Cash", "budget": "budget_transport"})
        
    def tearDown(self):
        self.conn.close()

    def test_setup_correctly_caps_budget_at_zero(self):
        """Verify that the initial state is correct: budget is overspent and capped at 0."""
        budget_after_setup = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        self.assertAlmostEqual(budget_after_setup["amount"], 0)

    def test_update_expense_while_still_overspent(self):
        """Tests updating an expense when the budget remains overspent (e.g., -120 -> -130)."""
        expense_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Tires') # is -30
        
        process_transaction_update(self.conn, expense_to_update['id'], {"amount": -40})
        
        budget_after = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        self.assertAlmostEqual(budget_after["amount"], 0)

    def test_update_expense_from_over_to_underspent(self):
        """Tests updating an expense that brings the budget from overspent to underspent (e.g., -120 -> -90)."""
        expense_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Tires') # is -30
        
        process_transaction_update(self.conn, expense_to_update['id'], {"amount": -10}) # Total spend is now 90+10=100
        
        budget_after = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        # Total spend is now 100, so budget should be -100 + 100 = 0
        self.assertAlmostEqual(budget_after["amount"], 0)

        # Second case: make it clearly underspent
        process_transaction_update(self.conn, expense_to_update['id'], {"amount": -5}) # Total spend is now 90+5=95
        budget_after = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        self.assertAlmostEqual(budget_after["amount"], -5)


    def test_update_expense_from_under_to_overspent(self):
        """Tests updating an expense that brings the budget from underspent to overspent."""
        # First, reduce an expense to make it underspent
        expense_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Tires') # is -30
        process_transaction_update(self.conn, expense_to_update['id'], {"amount": -5}) # Total spend is 95
        
        budget_before = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        self.assertAlmostEqual(budget_before["amount"], -5) # Verify underspent state

        # Now, increase an expense to make it overspent again
        process_transaction_update(self.conn, expense_to_update['id'], {"amount": -20}) # Total spend is 90+20=110
        
        budget_after = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        self.assertAlmostEqual(budget_after["amount"], 0)

    def test_delete_expense_while_still_overspent(self):
        """Tests deleting an expense when the budget remains overspent (e.g., -120 -> -90)."""
        expense_to_delete = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Tires') # -30
        
        process_transaction_deletion(self.conn, expense_to_delete['id'])
        
        # New total spend is -90. New balance should be -100 + 90 = -10.
        budget_after = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        self.assertAlmostEqual(budget_after["amount"], -10)

    def test_delete_expense_that_brings_budget_underspent(self):
        """Tests deleting an expense that makes the budget go from overspent to underspent (e.g., -120 -> -30)."""
        expense_to_delete = next(t for t in get_all_transactions(self.conn) if t['description'] == 'Gas') # -90
        
        process_transaction_deletion(self.conn, expense_to_delete['id'])
        
        # New total spend is -30. New balance should be -100 + 30 = -70.
        budget_after = get_budget_allocation_for_month(self.conn, "budget_transport", self.today)
        self.assertAlmostEqual(budget_after["amount"], -70)

if __name__ == "__main__":
    unittest.main()

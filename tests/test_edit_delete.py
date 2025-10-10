import unittest
import sqlite3
from datetime import date

from database import create_connection, create_tables, insert_initial_data
from repository import add_transactions, get_all_transactions, get_transaction_by_id
from main import process_transaction_update, process_transaction_deletion

class TestTransactionEditingAndDeletion(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database and seed it with initial data for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        self.today = date(2025, 10, 10)

        # --- Setup a consistent scenario for testing ---
        # 1. Create a budget allocation for "Food"
        self.food_budget_allocation = {
            "date_created": self.today.replace(day=1),
            "date_payed": self.today.replace(day=1),
            "description": "Food Budget",
            "account": "Cash",
            "amount": -400.00,
            "category": "Food",
            "budget": "budget_food",
            "status": "committed",
            "origin_id": "budget_food",
        }
        add_transactions(self.conn, [self.food_budget_allocation])

        # 2. Create a simple transaction to be edited/deleted
        self.initial_expense = {
            "date_created": self.today,
            "date_payed": self.today,
            "description": "Weekly Groceries",
            "account": "Cash",
            "amount": -50.00,
            "category": "Groceries",
            "budget": "budget_food",
            "status": "committed",
            "origin_id": "TX123",
        }
        add_transactions(self.conn, [self.initial_expense])

        # 3. Manually apply the initial expense to the budget for a correct starting state
        budget_id = next(t['id'] for t in get_all_transactions(self.conn) if t['origin_id'] == 'budget_food')
        # This logic simulates what process_transaction_request does
        initial_budget_balance = self.food_budget_allocation['amount'] + abs(self.initial_expense['amount'])
        self.conn.execute(
            "UPDATE transactions SET amount = ? WHERE id = ?",
            (initial_budget_balance, budget_id)
        )
        self.conn.commit()

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_update_transaction_amount_increase_and_adjusts_budget(self):
        """
        Tests that increasing an expense's amount correctly adjusts the linked budget's live balance.
        """
        all_trans = get_all_transactions(self.conn)
        expense_to_update = next(t for t in all_trans if t['description'] == 'Weekly Groceries')
        
        # --- Debugging ---
        print("\n--- Running Test: test_update_transaction_amount_increase_and_adjusts_budget ---")
        budget_before = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        print(f"  - Initial State: Expense amount is {expense_to_update['amount']:.2f}, Budget balance is {budget_before:.2f}")

        updates = {"amount": -75.00}
        print(f"  - Action: Updating expense ID {expense_to_update['id']} with new amount {updates['amount']:.2f}")
        process_transaction_update(self.conn, expense_to_update['id'], updates)

        updated_expense = get_transaction_by_id(self.conn, expense_to_update['id'])
        budget_after = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        print(f"  - Final State: Expense amount is {updated_expense['amount']:.2f}, Budget balance is {budget_after:.2f}")
        
        # Correct expectation: -400 (base) + 75 (new expense) = -325
        correct_balance = -325.00
        print(f"  - Assertion: Checking if {budget_after:.2f} == {correct_balance:.2f}")

        self.assertEqual(updated_expense['amount'], -75.00)
        self.assertEqual(budget_after, correct_balance)
        print("--- Test Passed ---")

    def test_update_transaction_amount_decrease_and_adjusts_budget(self):
        """
        Tests that decreasing an expense's amount correctly adjusts the linked budget's live balance.
        """
        all_trans = get_all_transactions(self.conn)
        expense_to_update = next(t for t in all_trans if t['description'] == 'Weekly Groceries')
        
        # --- Debugging ---
        print("\n--- Running Test: test_update_transaction_amount_decrease_and_adjusts_budget ---")
        budget_before = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        print(f"  - Initial State: Expense amount is {expense_to_update['amount']:.2f}, Budget balance is {budget_before:.2f}")

        updates = {"amount": -25.00}
        print(f"  - Action: Updating expense ID {expense_to_update['id']} with new amount {updates['amount']:.2f}")
        process_transaction_update(self.conn, expense_to_update['id'], updates)

        updated_expense = get_transaction_by_id(self.conn, expense_to_update['id'])
        budget_after = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        print(f"  - Final State: Expense amount is {updated_expense['amount']:.2f}, Budget balance is {budget_after:.2f}")
        
        # Correct expectation: -400 (base) + 25 (new expense) = -375
        correct_balance = -375.00
        print(f"  - Assertion: Checking if {budget_after:.2f} == {correct_balance:.2f}")

        self.assertEqual(updated_expense['amount'], -25.00)
        self.assertEqual(budget_after, correct_balance)
        print("--- Test Passed ---")


    def test_update_transaction_description_only(self):
        """
        Tests that updating only a non-financial field does not affect the budget.
        """
        all_trans = get_all_transactions(self.conn)
        expense_to_update = next(t for t in all_trans if t['description'] == 'Weekly Groceries')
        
        updates = {"description": "Groceries from the market"}
        process_transaction_update(self.conn, expense_to_update['id'], updates)

        updated_expense = get_transaction_by_id(self.conn, expense_to_update['id'])
        self.assertEqual(updated_expense['description'], "Groceries from the market")

        budget_allocation = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        self.assertEqual(budget_allocation, -350.00)

    def test_delete_transaction_and_reverses_budget_impact(self):
        """
        Tests that deleting an expense correctly "returns" the amount to the linked budget.
        """
        all_trans = get_all_transactions(self.conn)
        expense_to_delete = next(t for t in all_trans if t['description'] == 'Weekly Groceries')
        
        # --- Debugging ---
        print("\n--- Running Test: test_delete_transaction_and_reverses_budget_impact ---")
        budget_before = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        print(f"  - Initial State: Expense amount is {expense_to_delete['amount']:.2f}, Budget balance is {budget_before:.2f}")
        
        print(f"  - Action: Deleting expense ID {expense_to_delete['id']}")
        process_transaction_deletion(self.conn, expense_to_delete['id'])

        deleted_expense = get_transaction_by_id(self.conn, expense_to_delete['id'])
        budget_after = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        print(f"  - Final State: Expense deleted, Budget balance is {budget_after:.2f}")
        
        # Correct expectation: -350 (current) - 50 (impact of deleted tx) = -400
        correct_balance = -400.00
        print(f"  - Assertion: Checking if {budget_after:.2f} == {correct_balance:.2f}")

        self.assertIsNone(deleted_expense)
        self.assertEqual(budget_after, correct_balance)
        print("--- Test Passed ---")


    def test_delete_transaction_with_no_budget(self):
        """
        Tests that deleting a transaction without a budget link runs without error.
        """
        no_budget_expense = {
            "date_created": self.today, "date_payed": self.today,
            "description": "Coffee", "account": "Cash", "amount": -5.00,
            "category": "Coffee", "budget": None, "status": "committed", "origin_id": "TX456"
        }
        add_transactions(self.conn, [no_budget_expense])
        
        all_trans = get_all_transactions(self.conn)
        expense_to_delete = next(t for t in all_trans if t['description'] == 'Coffee')

        process_transaction_deletion(self.conn, expense_to_delete['id'])

        deleted_expense = get_transaction_by_id(self.conn, expense_to_delete['id'])
        self.assertIsNone(deleted_expense)
        
        budget_allocation = self.conn.execute("SELECT amount FROM transactions WHERE origin_id = ?", ("budget_food",)).fetchone()[0]
        self.assertEqual(budget_allocation, -350.00)

if __name__ == "__main__":
    unittest.main()
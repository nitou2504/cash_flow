import unittest
import sqlite3
from datetime import date, timedelta

from database import create_connection, create_tables
import repository
import main as controller
from transactions import create_single_transaction

class TestPendingTransactions(unittest.TestCase):

    def setUp(self):
        """Set up a fresh, in-memory database for each test."""
        self.conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        create_tables(self.conn)
        # Add a cash account for transactions
        repository.add_account(self.conn, "Cash", "cash")
        self.cash_account = repository.get_account_by_name(self.conn, "Cash")

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    def test_pending_expense_does_not_affect_running_balance(self):
        """
        Verify that a transaction with 'pending' status is listed but does not
        alter the running balance.
        """
        # Arrange: Create an initial committed transaction
        initial_income = {
            "type": "simple", "description": "Initial Balance", "amount": 1000,
            "account": "Cash", "is_income": True
        }
        controller.process_transaction_request(self.conn, initial_income)

        # Act: Create a pending expense
        pending_expense = {
            "type": "simple", "description": "Pending Purchase", "amount": 50,
            "account": "Cash", "is_pending": True
        }
        controller.process_transaction_request(self.conn, pending_expense)

        # Assert
        transactions = repository.get_transactions_with_running_balance(self.conn)
        self.assertEqual(len(transactions), 2)
        
        # The first transaction (income) sets the balance
        self.assertEqual(transactions[0]['running_balance'], 1000)
        
        # The second transaction (pending) should be listed, but the balance should not change
        self.assertEqual(transactions[1]['description'], "Pending Purchase")
        self.assertEqual(transactions[1]['status'], "pending")
        self.assertEqual(transactions[1]['running_balance'], 1000, "Running balance should not include pending transactions.")

    def test_pending_expense_does_not_affect_budget(self):
        """
        Verify that a pending expense linked to a budget does not decrease the
        budget's available balance.
        """
        # Arrange: Create a budget allocation for the current month
        today = date.today()
        budget_id = "budget_food"
        food_budget_sub = {
            "id": budget_id, "name": "Food Budget", "category": "Food",
            "monthly_amount": 400, "payment_account_id": "Cash",
            "start_date": today.replace(day=1), "is_budget": True
        }
        repository.add_subscription(self.conn, food_budget_sub)
        
        # Manually create the budget allocation transaction
        budget_allocation = create_single_transaction("Food Budget", 400, "Food", budget_id, self.cash_account, today.replace(day=1))
        budget_allocation['origin_id'] = budget_id
        repository.add_transactions(self.conn, [budget_allocation])

        # Act: Create a pending expense against the food budget
        pending_expense = {
            "type": "simple", "description": "Future Groceries", "amount": 75,
            "account": "Cash", "budget": budget_id, "is_pending": True
        }
        controller.process_transaction_request(self.conn, pending_expense)

        # Assert
        allocation = repository.get_budget_allocation_for_month(self.conn, budget_id, today)
        self.assertIsNotNone(allocation)
        self.assertEqual(allocation['amount'], -400, "Budget allocation should not be affected by a pending expense.")

    def test_clearing_a_pending_expense_updates_balance_and_budget(self):
        """
        Verify that changing a transaction's status from 'pending' to 'committed'
        correctly updates the running balance and the linked budget.
        """
        # Arrange: Create a budget and a pending expense
        today = date.today()
        budget_id = "budget_food"
        food_budget_sub = {
            "id": budget_id, "name": "Food Budget", "category": "Food",
            "monthly_amount": 400, "payment_account_id": "Cash",
            "start_date": today.replace(day=1), "is_budget": True
        }
        repository.add_subscription(self.conn, food_budget_sub)
        
        budget_allocation = create_single_transaction("Food Budget", 400, "Food", budget_id, self.cash_account, today.replace(day=1))
        budget_allocation['origin_id'] = budget_id
        repository.add_transactions(self.conn, [budget_allocation])

        pending_expense_req = {
            "type": "simple", "description": "Groceries", "amount": 75,
            "account": "Cash", "budget": budget_id, "is_pending": True
        }
        controller.process_transaction_request(
            self.conn, pending_expense_req, transaction_date=today.replace(day=2)
        )
        
        # Find the pending transaction's ID
        pending_trans = repository.get_all_transactions(self.conn)[-1]
        self.assertEqual(pending_trans['status'], 'pending')

        # Act: Clear the pending transaction
        controller.process_transaction_clearance(self.conn, pending_trans['id'])

        # Assert
        # 1. Transaction status is now 'committed'
        cleared_trans = repository.get_transaction_by_id(self.conn, pending_trans['id'])
        self.assertEqual(cleared_trans['status'], 'committed')

        # 2. Budget balance is now updated
        allocation = repository.get_budget_allocation_for_month(self.conn, budget_id, today)
        self.assertEqual(allocation['amount'], -325, "Budget should be reduced after clearing the expense.")

        # 3. Running balance reflects the cleared expense
        transactions = repository.get_transactions_with_running_balance(self.conn)
        # Balance = -325 (updated budget) - 75 (expense) = -400
        self.assertEqual(transactions[-1]['running_balance'], -400, "Running balance should be the total of the updated budget and the expense.")

if __name__ == '__main__':
    unittest.main()

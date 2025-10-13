import unittest
from datetime import date
from unittest.mock import patch

from database import create_connection, create_tables, insert_initial_data
from repository import add_subscription, get_transactions_with_running_balance
from main import process_transaction_request, run_monthly_rollover

class TestRunningBalance(unittest.TestCase):
    def setUp(self):
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        self.today = date(2025, 10, 15)

    def tearDown(self):
        self.conn.close()

    def test_running_balance_calculation(self):
        """
        Tests that the running balance is calculated correctly, ignoring
        expenses that are covered by a budget.
        """
        print("\n--- Test: Running Balance Calculation ---")
        
        # --- Setup: Create a budget and some transactions ---
        # 1. Food Budget for October
        add_subscription(self.conn, {
            "id": "budget_food", "name": "Food Budget", "category": "Food",
            "monthly_amount": 400, "payment_account_id": "Cash",
            "start_date": self.today.replace(day=1), "is_budget": True
        })
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.today)

        # 2. A regular expense (not on budget)
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Movie ticket", "amount": 20,
            "account": "Cash", "category": "Entertainment"
        }, transaction_date=date(2025, 10, 10))

        # 3. An expense against the food budget
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Groceries", "amount": 80,
            "account": "Cash", "budget": "budget_food"
        }, transaction_date=date(2025, 10, 12))
        
        # --- Action: Get transactions with running balance ---
        all_transactions = get_transactions_with_running_balance(self.conn)

        print("\n--- Debug: All Transactions Before Filtering ---")
        for t in all_transactions:
            print(f"  - Desc: {t['description']}, Amount: {t['amount']:.2f}")
        print("--------------------------------------------")

        # Filter for only the transactions relevant to this test
        print("\n--- Debug: Filtering Transactions ---")
        transactions = [
            t for t in all_transactions 
            if print(f"Checking: {t['description']} ({t['status']})") or
               t['description'] == "Movie ticket" or 
               t['description'] == "Groceries" or
               (t['description'] == "Food Budget" and t['status'] == 'committed')
        ]
        print("-----------------------------------")
        
        # --- Verification ---
        self.assertEqual(len(transactions), 3, "Should be 3 relevant transactions.")
        
        # Sort by date_payed to ensure order
        transactions.sort(key=lambda x: x['date_payed'])

        # Expected balances based on simple cumulative sum of the 'amount' column.
        # The Food Budget's amount is -320 because the 80 from Groceries was added back to it.
        # 1. Food Budget Allocation (updated): -320.00
        # 2. Movie Ticket: -320.00 + (-20.00) = -340.00
        # 3. Groceries: -340.00 + (-80.00) = -420.00
        
        balances = [t['running_balance'] for t in transactions]
        expected_balances = [-320.00, -340.00, -420.00]
        
        descriptions = [t['description'] for t in transactions]
        print(f"  - Transactions: {descriptions}")
        print(f"  - Calculated Balances: {balances}")
        print(f"  - Expected Balances:   {expected_balances}")

        # Verify the descriptions to ensure we have the right transactions in the right order
        self.assertEqual(descriptions[0], "Food Budget")
        self.assertEqual(descriptions[1], "Movie ticket")
        self.assertEqual(descriptions[2], "Groceries")

        for i, (balance, expected) in enumerate(zip(balances, expected_balances)):
            self.assertAlmostEqual(balance, expected, f"Balance for transaction '{descriptions[i]}' is incorrect.")
            
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

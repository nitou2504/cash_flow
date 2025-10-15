import unittest
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_mock_data
from repository import (
    add_subscription, get_budget_allocation_for_month, get_all_transactions
)
from main import (
    process_transaction_request, process_transaction_deletion, run_monthly_rollover
)

class TestTransactionCorrection(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for the correction scenario."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        
        # We are operating in October, but will correct a transaction from September
        self.today = date(2025, 10, 5)
        self.september = self.today - relativedelta(months=1)
        self.october = self.today
        self.november = self.today + relativedelta(months=1)

        # 1. Create a Shopping budget
        self.budget_id = "budget_shopping"
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Shopping Budget", "category": "Shopping",
            "monthly_amount": 200.00, "payment_account_id": "Cash",
            "start_date": self.september.replace(day=1), "is_budget": True
        })

        # 2. Generate forecasts and commit September and October
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.september)
            run_monthly_rollover(self.conn, self.october)

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    def test_correcting_simple_expense_to_installments(self):
        """
        Tests the full workflow of deleting an incorrect simple transaction from a past
        month and replacing it with a correct installment transaction.
        """
        print("\n--- Test: Correcting a Past Transaction ---")
        
        # --- STEP 1: Initial State ---
        print("\nSTEP 1: Initial State Setup")
        print("  - Logging an incorrect simple expense of $90 for September.")
        incorrect_expense_req = {
            "type": "simple", "description": "Mistake Purchase", "amount": 90.00,
            "account": "Cash", "budget": self.budget_id
        }
        # We patch 'today' to be in September for the creation of this transaction
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.september
            process_transaction_request(self.conn, incorrect_expense_req)

        # Verification of initial state
        sept_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.september)
        print(f"  - September budget is now {sept_budget_before['amount']:.2f}. Expected: -110.00 (-200 + 90).")
        self.assertAlmostEqual(sept_budget_before['amount'], -110.00)

        # --- STEP 2: Deletion ---
        print("\nSTEP 2: Deleting the incorrect transaction")
        # Find the transaction we just created
        tx_to_delete = next(t for t in get_all_transactions(self.conn) if t['description'] == "Mistake Purchase")
        process_transaction_deletion(self.conn, tx_to_delete['id'])

        # Verification of deletion
        sept_budget_after_delete = get_budget_allocation_for_month(self.conn, self.budget_id, self.september)
        print(f"  - September budget is restored to {sept_budget_after_delete['amount']:.2f}. Expected: -200.00.")
        self.assertAlmostEqual(sept_budget_after_delete['amount'], -200.00)

        # --- STEP 3: Re-creation as Installments ---
        print("\nSTEP 3: Logging the correct installment transaction")
        print("  - Re-logging the $90 purchase as 3 installments of $30.")
        correct_installment_req = {
            "type": "installment", "description": "Corrected Purchase", "total_amount": 90.00,
            "installments": 3, "account": "Cash", "budget": self.budget_id
        }
        # The purchase date is still in September
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.september
            process_transaction_request(self.conn, correct_installment_req)

        # --- STEP 4: Final Verification ---
        print("\nSTEP 4: Final State Verification")
        sept_budget_final = get_budget_allocation_for_month(self.conn, self.budget_id, self.september)
        oct_budget_final = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_final = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)

        print(f"  - September budget is now {sept_budget_final['amount']:.2f}. Expected: -170.00 (-200 + 30).")
        self.assertAlmostEqual(sept_budget_final['amount'], -170.00)
        
        print(f"  - October budget is now {oct_budget_final['amount']:.2f}. Expected: -170.00 (-200 + 30).")
        self.assertAlmostEqual(oct_budget_final['amount'], -170.00)

        print(f"  - November budget is now {nov_budget_final['amount']:.2f}. Expected: -170.00 (-200 + 30).")
        self.assertAlmostEqual(nov_budget_final['amount'], -170.00)
        print("\n--- Test Complete: Scenario handled correctly. ---")

if __name__ == "__main__":
    unittest.main()

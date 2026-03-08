import unittest
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from cashflow.database import create_test_db
from cashflow.repository import (
    add_subscription, get_budget_allocation_for_month, get_account_by_name
)
from cashflow.controller import (
    process_transaction_request, process_budget_update, run_monthly_rollover
)

class TestFutureBudgetUpdates(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_test_db()
        
        self.today = date(2025, 10, 15)
        self.october = self.today
        self.november = self.today + relativedelta(months=1)
        self.december = self.today + relativedelta(months=2)

        # Create a Shopping budget
        self.budget_id = "budget_shopping"
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Shopping Budget", "category": "Others",
            "monthly_amount": 200.00, "payment_account_id": "Visa Produbanco",
            "start_date": self.october.replace(day=1), "is_budget": True
        })

        # Generate forecasts and commit months up to December
        with patch('cashflow.controller.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.october)
            run_monthly_rollover(self.conn, self.november)
            run_monthly_rollover(self.conn, self.december)

        self.account = get_account_by_name(self.conn, "Visa Produbanco")

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    def test_update_budget_amount_with_future_committed_expenses(self):
        """
        Tests that updating a budget's amount correctly recalculates future
        allocations that already have committed expenses against them.
        """
        print("\n--- Test: Update budget with future committed expenses ---")
        
        # --- Initial State: Create future-dated installments against the budget ---
        print("\nSTEP 1: Creating future installments against the $200 budget.")
        # This creates installments for Nov, Dec, Jan.
        # With a Visa card (cut-off 14), a purchase on Oct 20th means the
        # first payment is on Nov 25, second on Dec 25, etc.
        process_transaction_request(self.conn, {
            "type": "installment", "description": "New Coat", "total_amount": 150,
            "installments": 3, "account": self.account['account_id'],
            "budget": self.budget_id
        }, transaction_date=date(2025, 10, 20))

        oct_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        dec_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.december)
        
        msg_before = (f"Budgets before: Oct={oct_budget_before['amount']:.2f}, "
                      f"Nov={nov_budget_before['amount']:.2f}, "
                      f"Dec={dec_budget_before['amount']:.2f}")
        print(f"  - {msg_before}")
        
        # Verification: Initial budget is $200, installment is $50. Remaining should be $150.
        self.assertAlmostEqual(oct_budget_before['amount'], -200.00, msg="October budget should be untouched.")
        self.assertAlmostEqual(nov_budget_before['amount'], -150.00, msg="November budget should be -200 + 50.")
        self.assertAlmostEqual(dec_budget_before['amount'], -150.00, msg="December budget should be -200 + 50.")

        # --- Act: Update the budget amount ---
        print("\nSTEP 2: Updating budget from $200 to $120.")
        with patch('cashflow.controller.date') as mock_date:
            mock_date.today.return_value = self.today
            process_budget_update(self.conn, self.budget_id, {"monthly_amount": 120.00})

        # --- Final Verification ---
        print("\nSTEP 3: Verifying budgets are correctly recalculated.")
        oct_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        dec_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.december)

        msg_after = (f"Budgets after: Oct={oct_budget_after['amount']:.2f}, "
                     f"Nov={nov_budget_after['amount']:.2f}, "
                     f"Dec={dec_budget_after['amount']:.2f}")
        print(f"  - {msg_after}")

        # Verification: New budget is $120, installment is $50/month.
        # Oct has no spending (installments start in Nov), so Oct = -120.
        # Nov and Dec each have a $50 installment: -120 + 50 = -70.
        self.assertAlmostEqual(oct_budget_after['amount'], -120.00, msg="October budget should be recalculated with new amount.")
        self.assertAlmostEqual(nov_budget_after['amount'], -70.00, msg="November budget should be the new amount minus the expense: -120 + 50.")
        self.assertAlmostEqual(dec_budget_after['amount'], -70.00, msg="December budget should also be the new amount minus its expense: -120 + 50.")
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_initial_data
from repository import (
    add_subscription, get_budget_allocation_for_month, get_all_transactions,
    get_account_by_name
)
from main import (
    process_transaction_request, process_transaction_date_update, run_monthly_rollover
)

class TestBudgetCappingOnDateChange(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        
        self.today = date(2025, 10, 15)
        self.october = self.today
        self.november = self.today + relativedelta(months=1)

        # Create a Transport budget
        self.budget_id = "budget_transport"
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Transport Budget", "category": "Transport",
            "monthly_amount": 100.00, "payment_account_id": "Visa Produbanco",
            "start_date": self.october.replace(day=1), "is_budget": True
        })

        # Generate forecasts and commit months
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.october)
            run_monthly_rollover(self.conn, self.november)

        self.account = get_account_by_name(self.conn, "Visa Produbanco")

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    def test_move_transaction_forward_uncaps_budget(self):
        """
        Tests that moving a transaction to a future month correctly "uncaps"
        an overspent budget from the original month.
        """
        print("\n--- Test: Move transaction FORWARD to uncap a budget ---")
        
        # --- Initial State: Overspend and cap the October budget ---
        print("\nSTEP 1: Overspending October budget to cap it at zero.")
        # These two purchases (Oct 10 and Oct 12) both fall in the Oct payment cycle
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Gasoline", "amount": 80,
            "account": self.account['account_id'], "budget": self.budget_id
        }, transaction_date=date(2025, 10, 10))
        
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Uber Ride", "amount": 40,
            "account": self.account['account_id'], "budget": self.budget_id
        }, transaction_date=date(2025, 10, 12))

        oct_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        
        msg_before = f"Budgets before: Oct={oct_budget_before['amount']:.2f}, Nov={nov_budget_before['amount']:.2f}"
        print(f"  - {msg_before}")
        self.assertAlmostEqual(oct_budget_before['amount'], 0.00, msg="October budget should be capped at 0.")
        self.assertAlmostEqual(nov_budget_before['amount'], -100.00, msg="November budget should be untouched.")

        # --- Date Change: Move the $40 transaction to the next payment cycle ---
        print("\nSTEP 2: Moving the $40 transaction to the November cycle.")
        tx_to_move = next(t for t in get_all_transactions(self.conn) if t['description'] == "Uber Ride")
        
        # New date of Oct 15th pushes its payment date to November
        process_transaction_date_update(self.conn, tx_to_move['id'], date(2025, 10, 15))

        # --- Final Verification ---
        print("\nSTEP 3: Verifying budgets are correctly adjusted.")
        oct_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)

        msg_after = f"Budgets after: Oct={oct_budget_after['amount']:.2f}, Nov={nov_budget_after['amount']:.2f}"
        print(f"  - {msg_after}")
        
        self.assertAlmostEqual(oct_budget_after['amount'], -20.00, msg="October budget should be uncapped with $20 remaining.")
        self.assertAlmostEqual(nov_budget_after['amount'], -60.00, msg="November budget should now be debited by $40.")
        print("\n--- Test Complete ---")

    def test_move_transaction_backward_caps_budget(self):
        """
        Tests that moving a transaction from a future month correctly caps
        the budget of the new, earlier month.
        """
        print("\n--- Test: Move transaction BACKWARD to cap a budget ---")
        
        # --- Initial State: Partially spend both budgets ---
        print("\nSTEP 1: Partially spending October and November budgets.")
        # This purchase falls in the October payment cycle
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Gasoline", "amount": 80,
            "account": self.account['account_id'], "budget": self.budget_id
        }, transaction_date=date(2025, 10, 10))
        
        # This purchase (Oct 15) falls in the November payment cycle
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Uber Ride", "amount": 40,
            "account": self.account['account_id'], "budget": self.budget_id
        }, transaction_date=date(2025, 10, 15))

        oct_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        
        msg_before = f"Budgets before: Oct={oct_budget_before['amount']:.2f}, Nov={nov_budget_before['amount']:.2f}"
        print(f"  - {msg_before}")
        self.assertAlmostEqual(oct_budget_before['amount'], -20.00, msg="October budget should have $20 remaining.")
        self.assertAlmostEqual(nov_budget_before['amount'], -60.00, msg="November budget should have $60 remaining.")

        # --- Date Change: Move the $40 transaction back to the October payment cycle ---
        print("\nSTEP 2: Moving the $40 transaction to the October cycle.")
        tx_to_move = next(t for t in get_all_transactions(self.conn) if t['description'] == "Uber Ride")
        
        # New date of Oct 12th pulls its payment date back to October
        process_transaction_date_update(self.conn, tx_to_move['id'], date(2025, 10, 12))

        # --- Final Verification ---
        print("\nSTEP 3: Verifying budgets are correctly adjusted.")
        oct_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)

        msg_after = f"Budgets after: Oct={oct_budget_after['amount']:.2f}, Nov={nov_budget_after['amount']:.2f}"
        print(f"  - {msg_after}")
        
        self.assertAlmostEqual(oct_budget_after['amount'], 0.00, msg="October budget should now be capped at 0.")
        self.assertAlmostEqual(nov_budget_after['amount'], -100.00, msg="November budget should be fully restored.")
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

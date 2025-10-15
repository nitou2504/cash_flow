import unittest
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_mock_data
from repository import (
    add_subscription, get_budget_allocation_for_month, get_all_transactions,
    get_account_by_name
)
from main import (
    process_transaction_request, process_transaction_date_update, run_monthly_rollover
)

class TestTransactionDateChange(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        
        self.today = date(2025, 10, 15)
        self.september = self.today - relativedelta(months=1)
        self.october = self.today
        self.november = self.today + relativedelta(months=1)
        self.december = self.today + relativedelta(months=2)
        self.january = self.today + relativedelta(months=3)

        # Create a Shopping budget active for all relevant months
        self.budget_id = "budget_shopping"
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Shopping Budget", "category": "Shopping",
            "monthly_amount": 300.00, "payment_account_id": "Visa Produbanco",
            "start_date": self.september.replace(day=1), "is_budget": True
        })

        # Generate forecasts and commit months to simulate a live environment
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.september)
            run_monthly_rollover(self.conn, self.october)
            run_monthly_rollover(self.conn, self.november)
            run_monthly_rollover(self.conn, self.december)
            run_monthly_rollover(self.conn, self.january)

        # Get account details for transaction creation
        self.account = get_account_by_name(self.conn, "Visa Produbanco")

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    def test_simple_transaction_moves_to_next_month(self):
        """
        Tests that changing a simple transaction's date correctly moves its
        budget impact from the original month to the next.
        """
        print("\n--- Test: Simple transaction moves from Oct to Nov ---")
        
        # --- Initial State ---
        print("\nSTEP 1: Logging initial transaction in October.")
        # This purchase on Oct 13th falls into the October payment cycle (payed Nov 25)
        initial_date = date(2025, 10, 13)
        req = {
            "type": "simple", "description": "Initial Purchase", "amount": 100,
            "account": self.account['account_id'], "budget": self.budget_id
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = initial_date
            process_transaction_request(self.conn, req)

        oct_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        
        msg_before = f"Budgets before change: Oct={oct_budget_before['amount']:.2f}, Nov={nov_budget_before['amount']:.2f}"
        print(f"  - {msg_before}")
        self.assertAlmostEqual(oct_budget_before['amount'], -200.00, msg="October budget should be debited.")
        self.assertAlmostEqual(nov_budget_before['amount'], -300.00, msg="November budget should be untouched.")

        # --- Date Change ---
        print("\nSTEP 2: Changing transaction date to move it to the next cycle.")
        # This new date of Oct 15th pushes the payment date into the next cycle (Dec 25)
        new_date = date(2025, 10, 15)
        tx_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == "Initial Purchase")
        
        process_transaction_date_update(self.conn, tx_to_update['id'], new_date)

        # --- Final Verification ---
        print("\nSTEP 3: Verifying final budget states.")
        oct_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)

        msg_after = f"Budgets after change: Oct={oct_budget_after['amount']:.2f}, Nov={nov_budget_after['amount']:.2f}"
        print(f"  - {msg_after}")
        
        self.assertAlmostEqual(oct_budget_after['amount'], -300.00, msg="October budget should be fully restored.")
        self.assertAlmostEqual(nov_budget_after['amount'], -200.00, msg="November budget should now be debited.")
        print("\n--- Test Complete ---")


    def test_simple_transaction_moves_to_previous_month(self):
        """
        Tests that changing a simple transaction's date correctly moves its
        budget impact from the original month to the previous one.
        """
        print("\n--- Test: Simple transaction moves from Oct to Sep ---")
        
        # --- Initial State ---
        print("\nSTEP 1: Logging initial transaction in October.")
        # This purchase on Oct 15th falls into the November payment cycle (payed Nov 25)
        initial_date = date(2025, 10, 15)
        req = {
            "type": "simple", "description": "Initial Purchase", "amount": 75,
            "account": self.account['account_id'], "budget": self.budget_id
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = initial_date
            process_transaction_request(self.conn, req)

        oct_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)

        nov_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)        
        msg_before = f"Budgets before change: Oct={oct_budget_before['amount']:.2f}, Nov={nov_budget_before['amount']:.2f}"
        print(f"  - {msg_before}")
        self.assertAlmostEqual(oct_budget_before['amount'], -300.00, msg="October budget should be untouched.")
        self.assertAlmostEqual(nov_budget_before['amount'], -225.00, msg="November budget should be debited.")

        # --- Date Change ---
        print("\nSTEP 2: Changing transaction date to move it to the previous cycle.")
        # This new date of Oct 13th pushes the payment date into the previous cycle (Oct 25)
        new_date = date(2025, 10, 13)
        tx_to_update = next(t for t in get_all_transactions(self.conn) if t['description'] == "Initial Purchase")
        
        process_transaction_date_update(self.conn, tx_to_update['id'], new_date)

        # --- Final Verification ---
        print("\nSTEP 3: Verifying final budget states.")
        oct_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)

        msg_after = f"Budgets after change: Oct={oct_budget_after['amount']:.2f}, Nov={nov_budget_after['amount']:.2f}"
        print(f"  - {msg_after}")
        
        self.assertAlmostEqual(oct_budget_after['amount'], -225.00, msg="October budget should now be debited.")
        self.assertAlmostEqual(nov_budget_after['amount'], -300.00, msg="November budget should be fully restored.")
        print("\n--- Test Complete ---")


    def test_installment_transaction_moves_to_next_month(self):
        """
        Tests that changing an installment purchase's date correctly shifts
        all its payments and budget impacts to the next monthly cycle.
        """
        print("\n--- Test: Installment transaction moves forward a month ---")
        
        # --- Initial State ---
        print("\nSTEP 1: Logging initial 3-installment transaction.")
        # Purchase on Oct 13th -> Payments in Nov, Dec, Jan
        initial_date = date(2025, 10, 13)
        req = {
            "type": "installment", "description": "Big Purchase", "total_amount": 300,
            "installments": 3, "account": self.account['account_id'], "budget": self.budget_id
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = initial_date
            process_transaction_request(self.conn, req)

        oct_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        dec_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.december)
        
        msg_before = f"Budgets before change: Oct={oct_budget_before['amount']:.2f}, Nov={nov_budget_before['amount']:.2f}, Dec={dec_budget_before['amount']:.2f}"
        print(f"  - {msg_before}")
        self.assertAlmostEqual(oct_budget_before['amount'], -200.00, msg="Oct budget should have one installment.")
        self.assertAlmostEqual(nov_budget_before['amount'], -200.00, msg="Nov budget should have one installment.")
        self.assertAlmostEqual(dec_budget_before['amount'], -200.00, msg="Dec budget should have one installment.")

        # --- Date Change ---
        print("\nSTEP 2: Changing transaction date to shift all installments.")
        # New date of Oct 15th -> Payments in Nov, Dec, Jan
        new_date = date(2025, 10, 15)
        tx_to_update = next(t for t in get_all_transactions(self.conn) if "Big Purchase" in t['description'])
        
        process_transaction_date_update(self.conn, tx_to_update['id'], new_date)

        # --- Final Verification ---
        print("\nSTEP 3: Verifying final budget states.")
        oct_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        dec_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.december)

        msg_after = f"Budgets after change: Oct={oct_budget_after['amount']:.2f}, Nov={nov_budget_after['amount']:.2f}, Dec={dec_budget_after['amount']:.2f}"
        print(f"  - {msg_after}")
        
        self.assertAlmostEqual(oct_budget_after['amount'], -300.00, msg="Oct budget should be fully restored.")
        self.assertAlmostEqual(nov_budget_after['amount'], -200.00, msg="Nov budget should now have the first installment.")
        self.assertAlmostEqual(dec_budget_after['amount'], -200.00, msg="Dec budget should now have the second installment.")
        print("\n--- Test Complete ---")


    def test_installment_transaction_moves_to_previous_month(self):
        """
        Tests that changing an installment purchase's date correctly shifts
        all its payments and budget impacts to the previous monthly cycle.
        """
        print("\n--- Test: Installment transaction moves backward a month ---")
        
        # --- Initial State ---
        print("\nSTEP 1: Logging initial 3-installment transaction.")
        # Purchase on Oct 15th -> Payments in Nov, Dec, Jan
        initial_date = date(2025, 10, 15)
        req = {
            "type": "installment", "description": "Big Purchase", "total_amount": 300,
            "installments": 3, "account": self.account['account_id'], "budget": self.budget_id
        }
        with patch('main.date') as mock_date:
            mock_date.today.return_value = initial_date
            process_transaction_request(self.conn, req)

        nov_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        dec_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.december)
        jan_budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.january)
        
        msg_before = f"Budgets before: Nov={nov_budget_before['amount']:.2f}, Dec={dec_budget_before['amount']:.2f}, Jan={jan_budget_before['amount']:.2f}"
        print(f"  - {msg_before}")
        self.assertAlmostEqual(nov_budget_before['amount'], -200.00, msg="Nov budget should have one installment.")
        self.assertAlmostEqual(dec_budget_before['amount'], -200.00, msg="Dec budget should have one installment.")
        self.assertAlmostEqual(jan_budget_before['amount'], -200.00, msg="Jan budget should have one installment.")

        # --- Date Change ---
        print("\nSTEP 2: Changing transaction date to shift all installments.")
        # New date of Oct 13th -> Payments in Oct, Nov, Dec
        new_date = date(2025, 10, 13)
        tx_to_update = next(t for t in get_all_transactions(self.conn) if "Big Purchase" in t['description'])
        
        process_transaction_date_update(self.conn, tx_to_update['id'], new_date)

        # --- Final Verification ---
        print("\nSTEP 3: Verifying final budget states.")
        oct_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.october)
        nov_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.november)
        dec_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.december)
        jan_budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.january)

        msg_after = f"Budgets after: Oct={oct_budget_after['amount']:.2f}, Nov={nov_budget_after['amount']:.2f}, Dec={dec_budget_after['amount']:.2f}, Jan={jan_budget_after['amount']:.2f}"
        print(f"  - {msg_after}")
        
        self.assertAlmostEqual(oct_budget_after['amount'], -200.00, msg="Oct budget should now have the first installment.")
        self.assertAlmostEqual(nov_budget_after['amount'], -200.00, msg="Nov budget should now have the second installment.")
        self.assertAlmostEqual(dec_budget_after['amount'], -200.00, msg="Dec budget should now have the third installment.")
        self.assertAlmostEqual(jan_budget_after['amount'], -300.00, msg="Jan budget should be fully restored.")
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

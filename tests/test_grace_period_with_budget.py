import unittest
from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_mock_data
from main import process_transaction_request, run_monthly_rollover
from repository import add_subscription, get_budget_allocation_for_month, get_setting, get_all_transactions

class TestGracePeriodWithBudget(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for testing."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.today = date(2025, 10, 5)
        self.budget_id = "budget_shopping"

        # Create a Shopping budget
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Shopping Budget", "category": "Shopping",
            "monthly_amount": 300.00, "payment_account_id": "Visa Produbanco",
            "start_date": self.today.replace(day=1), "is_budget": True
        })

        # Generate forecasts for the next few months
        with patch('main.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.today)

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    def test_simple_transaction_with_grace_period_affects_future_budget(self):
        """
        Tests that a simple transaction with a grace period correctly reduces a future month's budget.
        """
        print("\n--- Test: Simple Transaction with Grace Period and Budget ---")
        
        request = {
            "type": "simple",
            "description": "Future purchase",
            "amount": 75.00,
            "account": "Visa Produbanco",
            "budget": self.budget_id,
            "grace_period_months": 2
        }
        
        process_transaction_request(self.conn, request, transaction_date=self.today)
        
        # Verification
        oct_budget = get_budget_allocation_for_month(self.conn, self.budget_id, self.today)
        dec_budget = get_budget_allocation_for_month(self.conn, self.budget_id, self.today + relativedelta(months=2))

        self.assertAlmostEqual(oct_budget['amount'], -300.00, 
                               msg="October budget should be unaffected")
        self.assertAlmostEqual(dec_budget['amount'], -225.00, 
                               msg="December budget should be reduced by the transaction amount")

    def test_installment_transaction_with_grace_period_affects_future_budgets(self):
        """
        Tests that an installment transaction with a grace period correctly reduces multiple future budgets.
        """
        print("\n--- Test: Installment Transaction with Grace Period and Budget ---")
        
        request = {
            "type": "installment",
            "description": "Financed Gadget",
            "total_amount": 180.00,
            "installments": 3,
            "account": "Visa Produbanco",
            "budget": self.budget_id,
            "grace_period_months": 1
        }
        
        process_transaction_request(self.conn, request, transaction_date=self.today)
        
        # Verification
        oct_budget = get_budget_allocation_for_month(self.conn, self.budget_id, self.today)
        nov_budget = get_budget_allocation_for_month(self.conn, self.budget_id, self.today + relativedelta(months=1))
        dec_budget = get_budget_allocation_for_month(self.conn, self.budget_id, self.today + relativedelta(months=2))
        jan_budget = get_budget_allocation_for_month(self.conn, self.budget_id, self.today + relativedelta(months=3))

        self.assertAlmostEqual(oct_budget['amount'], -300.00,
                               msg="October budget should be unaffected")
        self.assertAlmostEqual(nov_budget['amount'], -240.00,
                               msg="November budget should be reduced by the first installment (300 - 60)")
        self.assertAlmostEqual(dec_budget['amount'], -240.00,
                               msg="December budget should be reduced by the second installment (300 - 60)")
        self.assertAlmostEqual(jan_budget['amount'], -240.00,
                               msg="January budget should be reduced by the third installment (300 - 60)")


if __name__ == "__main__":
    unittest.main()

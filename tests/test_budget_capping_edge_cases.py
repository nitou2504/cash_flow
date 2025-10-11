import unittest
from datetime import date
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_initial_data
from repository import (
    add_subscription, add_transactions, get_budget_allocation_for_month,
    get_all_transactions
)
from main import (
    process_transaction_request, process_transaction_conversion,
    process_transaction_deletion
)

class TestBudgetCappingEdgeCases(unittest.TestCase):
    def setUp(self):
        """Set up a database with a budget for edge case testing."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
        
        self.start_date = date(2025, 10, 10)
        self.budget_id = "budget_test"
        self.budget_amount = 100.00

        # 1. Create a Test budget
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Test Budget", "category": "Testing",
            "monthly_amount": self.budget_amount, "payment_account_id": "Cash",
            "start_date": self.start_date.replace(day=1), "is_budget": True
        })

        # 2. Create the initial budget allocation for the month
        add_transactions(self.conn, [{
            "date_created": self.start_date.replace(day=1),
            "date_payed": self.start_date.replace(day=1),
            "description": "Test Budget", "account": "Cash", "amount": -self.budget_amount,
            "category": "Testing", "budget": self.budget_id, "status": "committed",
            "origin_id": self.budget_id
        }])

    def tearDown(self):
        self.conn.close()

    def test_convert_installments_to_simple_in_overspent_month(self):
        """
        Tests that converting installments to a simple TX in an already overspent
        month keeps the budget correctly capped at 0.
        """
        # --- STEP 1: Overspend the budget ---
        overspend_req = {
            "type": "simple", "description": "Initial Overspend", "amount": 120.00,
            "account": "Cash", "budget": self.budget_id
        }
        process_transaction_request(self.conn, overspend_req, transaction_date=self.start_date)
        
        budget_after_overspend = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_after_overspend['amount'], 0, msg="Budget should be capped at 0 after overspending.")

        # --- STEP 2: Add an installment transaction ---
        installment_req = {
            "type": "installment", "description": "Gadget", "total_amount": 60.00,
            "installments": 3, "account": "Cash", "budget": self.budget_id
        }
        process_transaction_request(self.conn, installment_req, transaction_date=self.start_date)

        # The budget for the first month should remain 0
        budget_after_installment = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_after_installment['amount'], 0, msg="Budget should remain capped at 0.")

        # --- STEP 3: Convert the installment back to a simple transaction ---
        tx_to_convert = next(t for t in get_all_transactions(self.conn) if "Gadget" in t['description'])
        conversion_details = {
            "target_type": "simple", "description": "Gadget (Simple)", "amount": 60.00,
            "account": "Cash", "category": "Testing", "budget": self.budget_id
        }
        process_transaction_conversion(self.conn, tx_to_convert['id'], conversion_details)

        # --- STEP 4: Verification ---
        # The budget for the first month should still be 0, as the total spend is now 120 + 60 = 180.
        budget_final = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_final['amount'], 0, msg="Budget should still be 0 after conversion.")

        # The budgets for the next two months should be fully restored.
        budget_month2 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=1))
        budget_month3 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=2))
        self.assertAlmostEqual(budget_month2['amount'], -self.budget_amount, msg="Budget for month 2 was not restored.")
        self.assertAlmostEqual(budget_month3['amount'], -self.budget_amount, msg="Budget for month 3 was not restored.")

    def test_convert_simple_to_installments_releases_overspent_budget(self):
        """
        Tests that converting a large simple transaction (that caused an overspend)
        into installments correctly "uncaps" and recalculates the budget.
        """
        # --- STEP 1: Overspend the budget with a single transaction ---
        overspend_req = {
            "type": "simple", "description": "Big Purchase", "amount": 150.00,
            "account": "Cash", "budget": self.budget_id
        }
        process_transaction_request(self.conn, overspend_req, transaction_date=self.start_date)

        budget_after_overspend = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_after_overspend['amount'], 0, msg="Budget should be capped at 0.")

        # --- STEP 2: Convert the large transaction to installments ---
        tx_to_convert = next(t for t in get_all_transactions(self.conn) if t['description'] == "Big Purchase")
        conversion_details = {
            "target_type": "installment", "description": "Big Purchase (Installments)",
            "total_amount": 150.00, "installments": 3, "account": "Cash",
            "category": "Testing", "budget": self.budget_id
        }
        process_transaction_conversion(self.conn, tx_to_convert['id'], conversion_details)

        # --- STEP 3: Verification ---
        # The first month is no longer overspent (100 - 50), so the budget should be recalculated.
        budget_month1 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_month1['amount'], -50.00, msg="Budget for month 1 should be -50.") # 100 - 50

        # The next two months should also reflect the new installment payments.
        budget_month2 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=1))
        budget_month3 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=2))
        self.assertIsNotNone(budget_month2)
        self.assertAlmostEqual(budget_month2['amount'], -50.00, msg="Budget for month 2 should be -50.")
        self.assertIsNotNone(budget_month3)
        self.assertAlmostEqual(budget_month3['amount'], -50.00, msg="Budget for month 3 should be -50.")

    def test_deleting_transaction_from_overspent_month_restores_budget(self):
        """
        Tests that deleting a transaction from an overspent month correctly
        recalculates the budget, potentially "uncapping" it.
        """
        # --- STEP 1: Overspend the budget with two transactions ---
        req1 = {"type": "simple", "description": "Expense 1", "amount": 70.00, "account": "Cash", "budget": self.budget_id}
        req2 = {"type": "simple", "description": "Expense 2", "amount": 80.00, "account": "Cash", "budget": self.budget_id}
        process_transaction_request(self.conn, req1, transaction_date=self.start_date)
        process_transaction_request(self.conn, req2, transaction_date=self.start_date)

        budget_after_overspend = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_after_overspend['amount'], 0, msg="Budget should be capped at 0.")

        # --- STEP 2: Delete one of the transactions ---
        tx_to_delete = next(t for t in get_all_transactions(self.conn) if t['description'] == "Expense 1")
        process_transaction_deletion(self.conn, tx_to_delete['id'])

        # --- STEP 3: Verification ---
        # The total spend is now only 80, so the budget should be 100 - 80 = 20.
        budget_after_delete = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_after_delete['amount'], -20.00, msg="Budget should be restored to -20.")

if __name__ == '__main__':
    unittest.main()

import unittest
import sqlite3
from datetime import date
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_mock_data
from repository import add_subscription, add_transactions, get_budget_allocation_for_month, get_all_transactions
from main import _get_transaction_group_info, process_transaction_request, process_transaction_conversion


class TestTransactionGroupIdentifier(unittest.TestCase):
    def setUp(self):
        """Set up a database with all types of transactions."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.today = date(2025, 10, 15)

        # 1. Simple Transaction (no origin_id)
        add_transactions(self.conn, [{
            "date_created": self.today, "date_payed": self.today, "description": "Simple Meal",
            "account": "Cash", "amount": -20, "category": "Food", "budget": None,
            "status": "committed", "origin_id": None
        }])
        self.simple_tx_id = 1

        # 2. Split Transaction (shared origin_id, same date_payed)
        add_transactions(self.conn, [
            {"date_created": self.today, "date_payed": self.today, "description": "Groceries", "account": "Cash", "amount": -80, "category": "Food", "budget": None, "status": "committed", "origin_id": "SPLIT1"},
            {"date_created": self.today, "date_payed": self.today, "description": "Groceries", "account": "Cash", "amount": -15, "category": "Home", "budget": None, "status": "committed", "origin_id": "SPLIT1"}
        ])
        self.split_tx_id = 2

        # 3. Installment Transaction (shared origin_id, different date_payed)
        add_transactions(self.conn, [
            {"date_created": self.today, "date_payed": self.today, "description": "Phone (1/3)", "account": "Visa Produbanco", "amount": -100, "category": "Electronics", "budget": None, "status": "committed", "origin_id": "INSTALL1"},
            {"date_created": self.today, "date_payed": self.today + relativedelta(months=1), "description": "Phone (2/3)", "account": "Visa Produbanco", "amount": -100, "category": "Electronics", "budget": None, "status": "committed", "origin_id": "INSTALL1"}
        ])
        self.installment_tx_id = 4

        # 4. Subscription Transaction (origin_id matches a subscription)
        add_subscription(self.conn, {"id": "sub_netflix", "name": "Netflix", "category": "Entertainment", "monthly_amount": 15.99, "payment_account_id": "Visa Produbanco", "start_date": self.today})
        add_transactions(self.conn, [{
            "date_created": self.today, "date_payed": self.today, "description": "Netflix",
            "account": "Visa Produbanco", "amount": -15.99, "category": "Entertainment", "budget": None,
            "status": "committed", "origin_id": "sub_netflix"
        }])
        self.subscription_tx_id = 6

    def tearDown(self):
        self.conn.close()

    def test_identifies_simple_transaction(self):
        info = _get_transaction_group_info(self.conn, self.simple_tx_id)
        self.assertIsNotNone(info)
        self.assertEqual(info['type'], 'simple')
        self.assertEqual(len(info['siblings']), 1)

    def test_identifies_split_transaction(self):
        info = _get_transaction_group_info(self.conn, self.split_tx_id)
        self.assertIsNotNone(info)
        self.assertEqual(info['type'], 'split')
        self.assertEqual(len(info['siblings']), 2)
        self.assertEqual(info['origin_id'], 'SPLIT1')

    def test_identifies_installment_transaction(self):
        info = _get_transaction_group_info(self.conn, self.installment_tx_id)
        self.assertIsNotNone(info)
        self.assertEqual(info['type'], 'installment')
        self.assertEqual(len(info['siblings']), 2)
        self.assertEqual(info['origin_id'], 'INSTALL1')

    def test_identifies_subscription_transaction(self):
        info = _get_transaction_group_info(self.conn, self.subscription_tx_id)
        self.assertIsNotNone(info)
        self.assertEqual(info['type'], 'subscription')
        self.assertEqual(info['origin_id'], 'sub_netflix')

class TestTransactionConversions(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for conversion scenarios."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        
        self.start_date = date(2025, 9, 15)
        self.budget_id = "budget_shopping"

        # 1. Create a Shopping budget
        add_subscription(self.conn, {
            "id": self.budget_id, "name": "Shopping Budget", "category": "Shopping",
            "monthly_amount": 300.00, "payment_account_id": "Cash",
            "start_date": self.start_date.replace(day=1), "is_budget": True
        })

        # 2. Create a budget allocation for the month of the transaction
        add_transactions(self.conn, [{
            "date_created": self.start_date.replace(day=1), "date_payed": self.start_date.replace(day=1),
            "description": "Shopping Budget", "account": "Cash", "amount": -300,
            "category": "Shopping", "budget": self.budget_id, "status": "committed", "origin_id": self.budget_id
        }])

    def tearDown(self):
        self.conn.close()

    def test_convert_simple_to_installment(self):
        """
        Tests converting a simple transaction from a past month into a 3-month
        installment plan, ensuring budgets are retroactively corrected.
        """
        # --- STEP 1: Initial State ---
        # Log a simple transaction of $120 in the past
        simple_req = {
            "type": "simple", "description": "Single Purchase", "amount": 120.00,
            "account": "Cash", "budget": self.budget_id
        }
        process_transaction_request(self.conn, simple_req, transaction_date=self.start_date)
        
        # Verify initial budget impact
        budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_before['amount'], -180.00) # -300 + 120

        # --- STEP 2: Conversion ---
        # Find the transaction to convert
        tx_to_convert = next(t for t in get_all_transactions(self.conn) if t['description'] == "Single Purchase")
        
        conversion_details = {
            "target_type": "installment",
            "description": "Converted to Installments",
            "total_amount": 120.00,
            "installments": 3,
            "account": "Cash", # Must provide all necessary details for creation
            "category": "Shopping",
            "budget": self.budget_id
        }
        
        # This function doesn't exist yet, so this will fail
        process_transaction_conversion(self.conn, tx_to_convert['id'], conversion_details)

        # --- STEP 3: Verification ---
        # 1. The original transaction should be gone
        original_gone = all(t['description'] != "Single Purchase" for t in get_all_transactions(self.conn))
        self.assertTrue(original_gone, "The original simple transaction was not deleted.")

        # 2. Three new installment transactions should exist
        installments = [t for t in get_all_transactions(self.conn) if "Converted to Installments" in t['description']]
        self.assertEqual(len(installments), 3, "Incorrect number of installment transactions created.")

        # 3. Verify budget recalculations
        budget_month1 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        budget_month2 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=1))
        budget_month3 = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=2))

        # The original budget should be restored and then debited by the new, smaller amount
        self.assertAlmostEqual(budget_month1['amount'], -260.00, msg="Budget for month 1 is incorrect.") # -300 + 40
        
        # Future months should have new budget allocations created on-the-fly and debited
        self.assertIsNotNone(budget_month2, msg="Budget for month 2 was not created.")
        self.assertAlmostEqual(budget_month2['amount'], -260.00, msg="Budget for month 2 is incorrect.") # -300 + 40
        
        self.assertIsNotNone(budget_month3, msg="Budget for month 3 was not created.")
        self.assertAlmostEqual(budget_month3['amount'], -260.00, msg="Budget for month 3 is incorrect.") # -300 + 40

    def test_convert_installment_to_simple(self):
        """
        Tests converting a 3-month installment plan back into a single transaction,
        ensuring future month budgets are restored.
        """
        # --- STEP 1: Initial State ---
        # Log a 3-month installment plan of $150 total
        installment_req = {
            "type": "installment", "description": "Installment Purchase", "total_amount": 150.00,
            "installments": 3, "account": "Cash", "budget": self.budget_id
        }
        process_transaction_request(self.conn, installment_req, transaction_date=self.start_date)

        # Verify initial state for all three affected months
        budget1_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        budget2_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=1))
        budget3_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=2))
        
        self.assertAlmostEqual(budget1_before['amount'], -250.00) # -300 + 50
        self.assertIsNotNone(budget2_before)
        self.assertAlmostEqual(budget2_before['amount'], -250.00) # -300 + 50
        self.assertIsNotNone(budget3_before)
        self.assertAlmostEqual(budget3_before['amount'], -250.00) # -300 + 50

        # --- STEP 2: Conversion ---
        tx_to_convert = next(t for t in get_all_transactions(self.conn) if "Installment Purchase" in t['description'])
        
        conversion_details = {
            "target_type": "simple",
            "description": "Converted to Simple",
            "amount": 150.00,
            "account": "Cash",
            "category": "Shopping",
            "budget": self.budget_id
        }
        process_transaction_conversion(self.conn, tx_to_convert['id'], conversion_details)

        # --- STEP 3: Verification ---
        # 1. The installment transactions should be gone
        installments_gone = all("Installment Purchase" not in t['description'] for t in get_all_transactions(self.conn))
        self.assertTrue(installments_gone, "The original installment transactions were not deleted.")

        # 2. One new simple transaction should exist
        simple_tx = [t for t in get_all_transactions(self.conn) if t['description'] == "Converted to Simple"]
        self.assertEqual(len(simple_tx), 1, "Incorrect number of simple transactions created.")
        self.assertEqual(simple_tx[0]['date_created'], self.start_date)

        # 3. Verify budget recalculations
        budget1_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        budget2_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=1))
        budget3_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date + relativedelta(months=2))

        # The first month's budget should reflect the full single payment
        self.assertAlmostEqual(budget1_after['amount'], -150.00, msg="Budget for month 1 is incorrect.") # -300 + 150

        # The budgets for the following months should be restored to their original full allocation
        self.assertAlmostEqual(budget2_after['amount'], -300.00, msg="Budget for month 2 was not restored.")
        self.assertAlmostEqual(budget3_after['amount'], -300.00, msg="Budget for month 3 was not restored.")

    def test_add_retroactive_transaction_updates_past_budget(self):
        """
        Tests that adding a new transaction to a past, committed month correctly
        recalculates and updates the budget for that month.
        """
        # --- STEP 1: Initial State ---
        # The budget for self.start_date (September) is -300.
        budget_before = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_before['amount'], -300.00)

        # --- STEP 2: Action ---
        # Add a new transaction retroactively to September
        retroactive_req = {
            "type": "simple", "description": "Forgotten Purchase", "amount": 75.00,
            "account": "Cash", "budget": self.budget_id
        }
        process_transaction_request(self.conn, retroactive_req, transaction_date=self.start_date)

        # --- STEP 3: Verification ---
        budget_after = get_budget_allocation_for_month(self.conn, self.budget_id, self.start_date)
        self.assertAlmostEqual(budget_after['amount'], -225.00, msg="Retroactive addition did not update past budget.") # -300 + 75

    def test_prevent_invalid_conversions(self):
        """
        Tests that attempting to convert a subscription-linked transaction
        raises a ValueError.
        """
        # Create a subscription-linked transaction
        add_transactions(self.conn, [{
            "date_created": self.start_date, "date_payed": self.start_date, "description": "Netflix",
            "account": "Cash", "amount": -15.99, "category": "Entertainment", "budget": None,
            "status": "committed", "origin_id": self.budget_id # Link to the budget subscription
        }])
        
        sub_tx = get_all_transactions(self.conn)[-1]

        conversion_details = { "target_type": "simple", "amount": 15.99, "account": "Cash" }

        with self.assertRaisesRegex(ValueError, "Cannot convert a subscription-linked transaction."):
            process_transaction_conversion(self.conn, sub_tx['id'], conversion_details)

if __name__ == '__main__':
    unittest.main()
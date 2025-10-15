import unittest
from datetime import date
from dateutil.relativedelta import relativedelta

from database import create_connection, create_tables, insert_mock_data
from main import process_transaction_request
from repository import get_all_transactions

class TestGracePeriod(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for testing."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.today = date(2025, 10, 5)

    def tearDown(self):
        """Close the database connection."""
        self.conn.close()

    def test_simple_transaction_with_grace_period(self):
        """
        Tests creating a simple transaction with a 2-month grace period.
        The payment date should be two months after the transaction date.
        """
        print("\n--- Test: Simple Transaction with Grace Period ---")
        
        request = {
            "type": "simple",
            "description": "Buy now, pay later purchase",
            "amount": 150.00,
            "account": "Visa Produbanco",
            "grace_period_months": 2
        }
        
        process_transaction_request(self.conn, request, transaction_date=self.today)
        
        transactions = get_all_transactions(self.conn)
        self.assertEqual(len(transactions), 1, msg="Should create exactly one transaction")
        
        created_transaction = transactions[0]
        effective_date = self.today + relativedelta(months=2)
        
        # The payment date for a credit card is on a specific day, so we just check year and month
        self.assertEqual(created_transaction['date_payed'].year, effective_date.year, 
                         msg="Payment year should be two months in the future")
        self.assertEqual(created_transaction['date_payed'].month, effective_date.month, 
                         msg="Payment month should be two months in the future")
        self.assertEqual(created_transaction['date_created'], self.today, 
                         msg="Creation date should be today")

    def test_installment_transaction_with_grace_period(self):
        """
        Tests creating an installment transaction with a 2-month grace period.
        The payment dates for each installment should be correctly offset.
        """
        print("\n--- Test: Installment Transaction with Grace Period ---")
        
        request = {
            "type": "installment",
            "description": "New Phone",
            "total_amount": 900.00,
            "installments": 3,
            "account": "Visa Produbanco",
            "grace_period_months": 2
        }
        
        process_transaction_request(self.conn, request, transaction_date=self.today)
        
        transactions = get_all_transactions(self.conn)
        self.assertEqual(len(transactions), 3, msg="Should create three installment transactions")
        
        # Check payment dates for each installment
        for i in range(3):
            effective_date = self.today + relativedelta(months=2 + i)
            self.assertEqual(transactions[i]['date_payed'].year, effective_date.year,
                             msg=f"Payment year for installment {i+1} should be correctly offset")
            self.assertEqual(transactions[i]['date_payed'].month, effective_date.month,
                             msg=f"Payment month for installment {i+1} should be correctly offset")
            self.assertEqual(transactions[i]['date_created'], self.today,
                             msg=f"Creation date for installment {i+1} should be today")

if __name__ == "__main__":
    unittest.main()

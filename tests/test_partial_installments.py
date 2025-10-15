import unittest
from datetime import date

from database import create_connection, create_tables, insert_mock_data
from repository import get_all_transactions, get_account_by_name
from main import process_transaction_request

class TestPartialInstallments(unittest.TestCase):
    def setUp(self):
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_mock_data(self.conn)
        self.account = get_account_by_name(self.conn, "Visa Produbanco")
        self.today = date(2025, 10, 15)

    def tearDown(self):
        self.conn.close()

    def test_create_installments_starting_from_middle(self):
        """
        Tests creating installment transactions that start from a specific number,
        not from 1.
        """
        print("\n--- Test: Create partial installments ---")
        
        # Scenario: A purchase of $600 was made in 6 total installments.
        # The user is now logging the remaining 4, starting from installment #3.
        request = {
            "type": "installment",
            "description": "New Phone",
            "total_amount": 600.00, # The ORIGINAL total amount of the purchase
            "installments": 4,      # The number of installments to log now
            "account": self.account['account_id'],
            "category": "electronics",
            "start_from_installment": 3,
            "total_installments": 6 # The total number of installments in the plan
        }
        
        process_transaction_request(self.conn, request, transaction_date=self.today)

        transactions = get_all_transactions(self.conn)
        
        self.assertEqual(len(transactions), 4, "Should create 4 transactions.")
        
        # Sort by date_payed to ensure order
        transactions.sort(key=lambda x: x['date_payed'])
        
        descriptions = [t['description'] for t in transactions]
        expected_descriptions = [
            "New Phone (3/6)",
            "New Phone (4/6)",
            "New Phone (5/6)",
            "New Phone (6/6)"
        ]
        self.assertListEqual(descriptions, expected_descriptions, msg="Descriptions should be correctly numbered.")

        for t in transactions:
            self.assertAlmostEqual(t['amount'], -100.00, msg="Installment amount should be correct.")

        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

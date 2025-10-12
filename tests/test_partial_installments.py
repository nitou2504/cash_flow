import unittest
from datetime import date

from database import create_connection, create_tables, insert_initial_data
from repository import get_all_transactions, get_account_by_name
from main import process_transaction_request

class TestPartialInstallments(unittest.TestCase):
    def setUp(self):
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)
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
        
        # Scenario: A purchase was made in 6 total installments.
        # The user is logging the remaining 4, starting from installment #3.
        # The remaining amount is 400.
        request = {
            "type": "installment",
            "description": "New Phone",
            "total_amount": 400.00,
            "installments": 4,  # The number of installments to log
            "account": self.account['account_id'],
            "category": "electronics",
            "start_from_installment": 3,
            "total_installments": 6
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
        self.assertListEqual(descriptions, expected_descriptions, "Descriptions should be correctly numbered.")

        for t in transactions:
            self.assertAlmostEqual(t['amount'], -100.00, "Installment amount should be correct.")
        
        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

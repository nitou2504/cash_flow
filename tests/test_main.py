
import unittest
import sqlite3
from unittest.mock import patch, MagicMock

from main import process_transaction_request

# Placeholder for database setup logic
from database import create_tables, insert_initial_data, create_connection


class TestMainController(unittest.TestCase):
    def setUp(self):
        """Set up an in-memory database for each test."""
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        insert_initial_data(self.conn)

    def tearDown(self):
        """Close the database connection after each test."""
        self.conn.close()

    @patch("main.repository")
    @patch("main.transactions")
    def test_process_transaction_request_simple(
        self, mock_transactions, mock_repository
    ):
        """
        Tests that a 'simple' transaction request correctly calls the
        'create_single_transaction' logic.
        """
        request = {
            "type": "simple",
            "description": "Taxi",
            "amount": 4.50,
            "account": "Cash",
            "category": "taxi",
            "budget": "transport",
        }
        mock_repository.get_account_by_name.return_value = {
            "account_id": "Cash",
            "account_type": "cash",
        }
        mock_transactions.create_single_transaction.return_value = {
            "description": "Test"
        }  # Dummy return

        process_transaction_request(self.conn, request)

        # Verify that the correct functions were called
        mock_repository.get_account_by_name.assert_called_once_with(
            self.conn, "Cash"
        )
        mock_transactions.create_single_transaction.assert_called_once()
        mock_repository.add_transactions.assert_called_once()

    @patch("main.repository")
    @patch("main.transactions")
    def test_process_transaction_request_installment(
        self, mock_transactions, mock_repository
    ):
        """
        Tests that an 'installment' transaction request correctly calls the
        'create_installment_transactions' logic.
        """
        request = {
            "type": "installment",
            "description": "New TV",
            "total_amount": 900.00,
            "installments": 3,
            "account": "Visa Produbanco",
            "category": "electronics",
            "budget": "shopping",
        }
        mock_repository.get_account_by_name.return_value = {
            "account_id": "Visa Produbanco",
            "account_type": "credit_card",
        }
        mock_transactions.create_installment_transactions.return_value = [
            {},
            {},
            {},
        ]  # Dummy

        process_transaction_request(self.conn, request)

        mock_repository.get_account_by_name.assert_called_once_with(
            self.conn, "Visa Produbanco"
        )
        mock_transactions.create_installment_transactions.assert_called_once()
        mock_repository.add_transactions.assert_called_once()

    @patch("main.repository")
    @patch("main.transactions")
    def test_process_transaction_request_split(
        self, mock_transactions, mock_repository
    ):
        """
        Tests that a 'split' transaction request correctly calls the
        'create_split_transactions' logic.
        """
        request = {
            "type": "split",
            "description": "Supermaxi",
            "account": "Visa Produbanco",
            "splits": [
                {"amount": 100, "category": "groceries", "budget": "food"},
                {"amount": 20, "category": "snacks", "budget": "personal"},
            ],
        }
        mock_repository.get_account_by_name.return_value = {
            "account_id": "Visa Produbanco",
            "account_type": "credit_card",
        }
        mock_transactions.create_split_transactions.return_value = [
            {},
            {},
        ]  # Dummy

        process_transaction_request(self.conn, request)

        mock_repository.get_account_by_name.assert_called_once_with(
            self.conn, "Visa Produbanco"
        )
        mock_transactions.create_split_transactions.assert_called_once()
        mock_repository.add_transactions.assert_called_once()


if __name__ == "__main__":
    unittest.main()

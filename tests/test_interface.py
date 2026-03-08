import unittest
from unittest.mock import patch, MagicMock

from cashflow.database import create_test_db
from ui.cli_display import view_transactions
from cashflow.controller import process_transaction_request, run_monthly_rollover
from cashflow.repository import add_subscription
from datetime import date

class TestInterface(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()
        self.today = date(2025, 10, 15)

    def tearDown(self):
        self.conn.close()

    @patch('ui.cli_display.Table')
    @patch('ui.cli_display.Console')
    def test_view_transactions_displays_correctly(self, mock_console, mock_table):
        """
        Tests that the view_transactions function calls the rich library
        to print a table with the correct data.
        """
        print("\n--- Test: View Transactions ---")
        
        # --- Setup: Create a budget and some transactions ---
        add_subscription(self.conn, {
            "id": "budget_food", "name": "Food Budget", "category": "Food",
            "monthly_amount": 400, "payment_account_id": "Cash",
            "start_date": self.today.replace(day=1), "is_budget": True
        })
        
        with patch('cashflow.controller.date') as mock_date:
            mock_date.today.return_value = self.today
            run_monthly_rollover(self.conn, self.today)

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Movie ticket", "amount": 20,
            "account": "Cash", "category": "Personal"
        }, transaction_date=date(2025, 10, 10))

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Groceries", "amount": 80,
            "account": "Cash", "budget": "budget_food"
        }, transaction_date=date(2025, 10, 12))

        # --- Debug: Print the raw data ---
        from cashflow import repository
        transactions_for_view = repository.get_transactions_with_running_balance(self.conn)
        print("\n--- Raw Transaction Data for View ---")
        for t in transactions_for_view:
            print(dict(t))
        print("------------------------------------")

        # --- Action ---
        view_transactions(self.conn, months=12, start_from="2025-10")

        # --- Verification ---
        # 1. Check that Console and Table were used
        mock_console.assert_called_once()
        mock_table.assert_called_once()
        
        table_instance = mock_table.return_value
        
        # --- Debug: Print the rendered data ---
        print("\n--- Data Passed to rich.table.add_row ---")
        for call in table_instance.add_row.call_args_list:
            print(call.args)
        print("-----------------------------------------")

        # 2. Verify the number of rows (1 starting balance + 9 transactions)
        self.assertEqual(table_instance.add_row.call_count, 10)

        # 3. Verify the content of the first data row (after starting balance)
        first_data_args = table_instance.add_row.call_args_list[1].args
        self.assertEqual(first_data_args[1], "2025-10-01") # Date
        self.assertEqual(first_data_args[3], "Food Budget") # Description
        self.assertEqual(first_data_args[5], "-320.00") # Amount

        print("\n--- Test Complete ---")

if __name__ == "__main__":
    unittest.main()

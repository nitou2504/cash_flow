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

class TestSummaryByCategory(unittest.TestCase):
    """Tests for the --by-category (-bc) summary modifier."""

    def setUp(self):
        self.conn = create_test_db()
        self.today = date(2025, 10, 15)

    def tearDown(self):
        self.conn.close()

    @patch('ui.cli_display.Table')
    @patch('ui.cli_display.Console')
    def test_by_category_groups_cc_by_category(self, mock_console, mock_table):
        """CC transactions with different categories produce separate summary rows."""
        # Add CC transactions with different categories on same account
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Supermaxi", "amount": 50,
            "account": "Visa Produbanco", "category": "Home Groceries"
        }, transaction_date=date(2025, 10, 5))

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Pharmacy", "amount": 30,
            "account": "Visa Produbanco", "category": "Health"
        }, transaction_date=date(2025, 10, 8))

        process_transaction_request(self.conn, {
            "type": "simple", "description": "More groceries", "amount": 20,
            "account": "Visa Produbanco", "category": "Home Groceries"
        }, transaction_date=date(2025, 10, 10))

        # --- Action: summary with by_category ---
        view_transactions(self.conn, months=12, summary=True, start_from="2025-10", by_category=True)

        table_instance = mock_table.return_value
        rows = [call.args for call in table_instance.add_row.call_args_list]

        # Find summary rows (id == '--')
        summary_rows = [r for r in rows if r[0] == '--']

        # Should have 2 summary rows: one for Home Groceries, one for Health
        self.assertEqual(len(summary_rows), 2)

        # Extract descriptions and amounts
        summaries = {r[3]: r[5] for r in summary_rows}  # description -> amount

        self.assertIn("Visa Produbanco - Home Groceries", summaries)
        self.assertIn("Visa Produbanco - Health", summaries)
        self.assertEqual(summaries["Visa Produbanco - Home Groceries"], "-70.00")
        self.assertEqual(summaries["Visa Produbanco - Health"], "-30.00")

    @patch('ui.cli_display.Table')
    @patch('ui.cli_display.Console')
    def test_by_category_cash_unchanged(self, mock_console, mock_table):
        """Cash transactions pass through individually, not grouped."""
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Bus fare", "amount": 5,
            "account": "Cash", "category": "Transportation"
        }, transaction_date=date(2025, 10, 5))

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Lunch", "amount": 10,
            "account": "Cash", "category": "Dining-Snacks"
        }, transaction_date=date(2025, 10, 6))

        view_transactions(self.conn, months=12, summary=True, start_from="2025-10", by_category=True)

        table_instance = mock_table.return_value
        rows = [call.args for call in table_instance.add_row.call_args_list]

        # Cash transactions should appear individually (not summarized)
        descriptions = [r[3] for r in rows]
        self.assertIn("Bus fare", descriptions)
        self.assertIn("Lunch", descriptions)

        # No summary rows for cash
        summary_rows = [r for r in rows if r[0] == '--']
        self.assertEqual(len(summary_rows), 0)

    @patch('ui.cli_display.Table')
    @patch('ui.cli_display.Console')
    def test_by_category_created_mode(self, mock_console, mock_table):
        """In created-date mode, groups by (account, creation_month, category)."""
        # Two transactions in same creation month, different categories
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Groceries", "amount": 40,
            "account": "Visa Produbanco", "category": "Home Groceries"
        }, transaction_date=date(2025, 10, 3))

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Medicine", "amount": 25,
            "account": "Visa Produbanco", "category": "Health"
        }, transaction_date=date(2025, 10, 7))

        view_transactions(self.conn, months=12, summary=True, start_from="2025-10",
                         sort_by="date_created", by_category=True)

        table_instance = mock_table.return_value
        rows = [call.args for call in table_instance.add_row.call_args_list]

        summary_rows = [r for r in rows if r[0] == '--']

        # Should have 2 rows: one per category in the same month
        self.assertEqual(len(summary_rows), 2)

        descriptions = {r[3] for r in summary_rows}
        self.assertIn("Visa Produbanco - Home Groceries (Oct)", descriptions)
        self.assertIn("Visa Produbanco - Health (Oct)", descriptions)

    @patch('ui.cli_display.Table')
    @patch('ui.cli_display.Console')
    def test_plain_summary_unchanged(self, mock_console, mock_table):
        """Plain -s without -bc still groups all CC into one row per payment date."""
        process_transaction_request(self.conn, {
            "type": "simple", "description": "Supermaxi", "amount": 50,
            "account": "Visa Produbanco", "category": "Home Groceries"
        }, transaction_date=date(2025, 10, 5))

        process_transaction_request(self.conn, {
            "type": "simple", "description": "Pharmacy", "amount": 30,
            "account": "Visa Produbanco", "category": "Health"
        }, transaction_date=date(2025, 10, 8))

        view_transactions(self.conn, months=12, summary=True, start_from="2025-10", by_category=False)

        table_instance = mock_table.return_value
        rows = [call.args for call in table_instance.add_row.call_args_list]

        summary_rows = [r for r in rows if r[0] == '--']

        # Should be 1 combined row, not 2 per category
        self.assertEqual(len(summary_rows), 1)
        self.assertIn("Payment", summary_rows[0][3])


if __name__ == "__main__":
    unittest.main()

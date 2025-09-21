
import unittest
from datetime import date, timedelta

# This is a placeholder for the actual transaction creation logic.
# We will develop the real module later.
from transactions import (
    create_single_transaction,
    create_installment_transactions,
    create_split_transactions,
    _calculate_credit_card_payment_date,
)


class TestTransactions(unittest.TestCase):
    def setUp(self):
        """Set up common test data."""
        self.cash_account = {"account_type": "cash"}
        self.credit_card_account = {
            "account_type": "credit_card",
            "cut_off_day": 15,
            "payment_day": 25,
        }
        self.transaction_date = date(2025, 10, 17)

    def test_create_single_transaction_cash(self):
        """
        Tests that a single cash transaction has the same creation and payment date.
        """
        transaction = create_single_transaction(
            description="Taxi",
            amount=4.50,
            category="taxi",
            budget_category="transport",
            account=self.cash_account,
            transaction_date=self.transaction_date,
        )
        self.assertEqual(transaction["date_created"], self.transaction_date)
        self.assertEqual(transaction["date_payed"], self.transaction_date)
        self.assertEqual(transaction["amount"], -4.50)
        self.assertEqual(transaction["status"], "committed")

    def test_create_single_transaction_credit_card_after_cutoff(self):
        """
        Tests that a credit card transaction made after the cut-off day
        has its payment date correctly pushed to the next month.
        """
        transaction = create_single_transaction(
            description="Dinner",
            amount=45.00,
            category="restaurant",
            budget_category="food",
            account=self.credit_card_account,
            transaction_date=self.transaction_date,  # Oct 17th, after Oct 15th cut-off
        )
        self.assertEqual(transaction["date_created"], self.transaction_date)
        self.assertEqual(
            transaction["date_payed"], date(2025, 11, 25)
        )  # Payment in November
        self.assertEqual(transaction["amount"], -45.00)

    def test_create_single_transaction_credit_card_before_cutoff(self):
        """
        Tests that a credit card transaction made before the cut-off day
        has its payment date in the same month.
        """
        transaction_date = date(2025, 10, 14)  # Before Oct 15th cut-off
        transaction = create_single_transaction(
            description="Coffee",
            amount=5.00,
            category="cafe",
            budget_category="food",
            account=self.credit_card_account,
            transaction_date=transaction_date,
        )
        self.assertEqual(transaction["date_created"], transaction_date)
        self.assertEqual(
            transaction["date_payed"], date(2025, 10, 25)
        )  # Payment in October

    def test_create_installment_transactions(self):
        """
        Tests the creation of a series of transactions for an installment purchase.
        """
        transactions = create_installment_transactions(
            description="New TV",
            total_amount=900.00,
            installments=3,
            category="electronics",
            budget_category="shopping",
            account=self.credit_card_account,
            transaction_date=self.transaction_date,
        )
        self.assertEqual(len(transactions), 3)
        self.assertIsNotNone(transactions[0].get("origin_id"))
        self.assertEqual(
            transactions[0]["origin_id"], transactions[1]["origin_id"]
        )

        # Check amounts and descriptions
        self.assertEqual(transactions[0]["amount"], -300.00)
        self.assertIn("(1/3)", transactions[0]["description"])
        self.assertEqual(transactions[2]["amount"], -300.00)
        self.assertIn("(3/3)", transactions[2]["description"])

        # Check payment dates
        self.assertEqual(transactions[0]["date_payed"], date(2025, 11, 25))
        self.assertEqual(transactions[1]["date_payed"], date(2025, 12, 25))
        self.assertEqual(transactions[2]["date_payed"], date(2026, 1, 25))

    def test_create_split_transactions(self):
        """
        Tests the creation of multiple transactions from a single split purchase.
        """
        splits = [
            {"amount": 100, "category": "groceries", "budget_category": "food"},
            {"amount": 20, "category": "snacks", "budget_category": "personal"},
        ]
        transactions = create_split_transactions(
            description="Supermaxi",
            splits=splits,
            account=self.credit_card_account,
            transaction_date=self.transaction_date,
        )
        self.assertEqual(len(transactions), 2)
        self.assertIsNotNone(transactions[0].get("origin_id"))
        self.assertEqual(
            transactions[0]["origin_id"], transactions[1]["origin_id"]
        )

        # Check details of each split transaction
        self.assertEqual(transactions[0]["amount"], -100.00)
        self.assertEqual(transactions[0]["category"], "groceries")
        self.assertEqual(transactions[1]["amount"], -20.00)
        self.assertEqual(transactions[1]["category"], "snacks")
        self.assertEqual(transactions[0]["date_payed"], date(2025, 11, 25))

    def test_calculate_credit_card_payment_date(self):
        """
        Directly tests the payment date calculation logic for various scenarios.
        """
        # Transaction after cut-off -> next month
        self.assertEqual(
            _calculate_credit_card_payment_date(date(2025, 10, 17), 15, 25),
            date(2025, 11, 25),
        )
        # Transaction before cut-off -> same month
        self.assertEqual(
            _calculate_credit_card_payment_date(date(2025, 10, 14), 15, 25),
            date(2025, 10, 25),
        )
        # Transaction on cut-off day -> next month
        self.assertEqual(
            _calculate_credit_card_payment_date(date(2025, 10, 15), 15, 25),
            date(2025, 11, 25),
        )
        # December transaction -> January next year
        self.assertEqual(
            _calculate_credit_card_payment_date(date(2025, 12, 20), 15, 10),
            date(2026, 1, 10),
        )


if __name__ == "__main__":
    unittest.main()

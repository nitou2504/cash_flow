"""Tests for interactive entity flows: accounts, categories, subscriptions, edit, fix.

Follows the same test DB and mocking patterns as test_interactive.py.

Test DB ordering (alphabetical):
  Accounts:  1=Amex Produbanco, 2=Cash, 3=Visa Produbanco
  Categories: 1=Dining-Snacks, 2=Health, 3=Home Groceries, 4=Housing,
              5=Income, 6=Loans, 7=Others, 8=Personal, 9=Personal Groceries,
              10=Savings, 11=Transportation
  Budgets: none (unless added in setUp)
"""

import unittest
from unittest.mock import patch
from datetime import date

from cashflow.database import create_test_db
from cashflow import repository, controller
from ui.interactive import (
    prompt_amount,
    prompt_choice,
    prompt_date,
    interactive_add_account,
    interactive_add_category,
    interactive_add_subscription,
    interactive_edit_transaction,
    interactive_edit_subscription,
    interactive_statement_fix,
)

# Shortcuts
CASH = '2'
VISA = '3'
AMEX = '1'
CAT_DINING = '1'
CAT_HOME_GROC = '3'
CAT_INCOME = '5'
CAT_HOUSING = '4'
CAT_PERSONAL = '8'
DEFAULT = ''  # press Enter for default
NO = ''
YES = 'y'


# ==================== PROMPT_AMOUNT DEFAULT ====================

class TestPromptAmountDefault(unittest.TestCase):
    """Test prompt_amount with the new default parameter."""

    @patch('builtins.input', return_value='')
    def test_default_returned_on_enter(self, _):
        result = prompt_amount("Amount", default=99.50)
        self.assertEqual(result, 99.50)

    @patch('builtins.input', return_value='42.00')
    def test_override_default(self, _):
        result = prompt_amount("Amount", default=99.50)
        self.assertEqual(result, 42.00)

    @patch('builtins.input', side_effect=['-5', '0', ''])
    def test_rejects_invalid_then_accepts_default(self, _):
        result = prompt_amount("Amount", default=10.0)
        self.assertEqual(result, 10.0)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_ctrl_c_returns_none(self, _):
        self.assertIsNone(prompt_amount("Amount", default=50.0))


# ==================== INTERACTIVE ADD ACCOUNT ====================

class TestInteractiveAddAccount(unittest.TestCase):
    """Test interactive account creation flow."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'Savings',      # name
        DEFAULT,        # type: cash (default)
        DEFAULT,        # confirm: yes
    ])
    def test_cash_account(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNotNone(result)
        name, acc_type, cut_off, payment = result
        self.assertEqual(name, 'Savings')
        self.assertEqual(acc_type, 'cash')
        self.assertIsNone(cut_off)
        self.assertIsNone(payment)

    @patch('builtins.input', side_effect=[
        'Mastercard',   # name
        'credit_card',  # type
        '20',           # cut-off day
        '5',            # payment day
        DEFAULT,        # confirm: yes
    ])
    def test_credit_card_account(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNotNone(result)
        name, acc_type, cut_off, payment = result
        self.assertEqual(name, 'Mastercard')
        self.assertEqual(acc_type, 'credit_card')
        self.assertEqual(cut_off, 20)
        self.assertEqual(payment, 5)

    @patch('builtins.input', side_effect=[
        'Test',         # name
        DEFAULT,        # type: cash
        'n',            # confirm: no
    ])
    def test_cancel_at_confirmation(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_cancel_at_name(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        'Test',         # name
        KeyboardInterrupt,
    ])
    def test_cancel_at_type(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        'CC Test',      # name
        'credit_card',  # type
        KeyboardInterrupt,
    ])
    def test_cancel_at_cutoff(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNone(result)


class TestInteractiveAddAccountE2E(unittest.TestCase):
    """End-to-end: interactive account flow + database persistence."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'New Savings',  # name
        DEFAULT,        # type: cash
        DEFAULT,        # confirm
    ])
    def test_e2e_cash_account(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNotNone(result)
        name, acc_type, cut_off, payment = result
        repository.add_account(self.conn, name, acc_type, cut_off, payment)

        accounts = repository.get_all_accounts(self.conn)
        names = [a['account_id'] for a in accounts]
        self.assertIn('New Savings', names)

    @patch('builtins.input', side_effect=[
        'Mastercard',   # name
        'credit_card',  # type
        '25',           # cut-off day
        '10',           # payment day
        DEFAULT,        # confirm
    ])
    def test_e2e_credit_card(self, _):
        result = interactive_add_account(self.conn)
        self.assertIsNotNone(result)
        name, acc_type, cut_off, payment = result
        repository.add_account(self.conn, name, acc_type, cut_off, payment)

        acc = repository.get_account_by_name(self.conn, 'Mastercard')
        self.assertIsNotNone(acc)
        self.assertEqual(acc['account_type'], 'credit_card')
        self.assertEqual(acc['cut_off_day'], 25)
        self.assertEqual(acc['payment_day'], 10)


# ==================== INTERACTIVE ADD CATEGORY ====================

class TestInteractiveAddCategory(unittest.TestCase):
    """Test interactive category creation flow."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'entertainment',                    # name
        'Movies, concerts, streaming',      # description
        DEFAULT,                            # confirm: yes
    ])
    def test_basic_category(self, _):
        result = interactive_add_category(self.conn)
        self.assertIsNotNone(result)
        name, description = result
        self.assertEqual(name, 'entertainment')
        self.assertEqual(description, 'Movies, concerts, streaming')

    @patch('builtins.input', side_effect=[
        'test_cat',     # name
        'Test desc',    # description
        'n',            # confirm: no
    ])
    def test_cancel_at_confirmation(self, _):
        result = interactive_add_category(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_cancel_at_name(self, _):
        result = interactive_add_category(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        'test',
        KeyboardInterrupt,
    ])
    def test_cancel_at_description(self, _):
        result = interactive_add_category(self.conn)
        self.assertIsNone(result)


class TestInteractiveAddCategoryE2E(unittest.TestCase):
    """End-to-end: interactive category flow + database persistence."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'entertainment',
        'Movies and concerts',
        DEFAULT,
    ])
    def test_e2e_creates_category(self, _):
        result = interactive_add_category(self.conn)
        self.assertIsNotNone(result)
        name, description = result
        repository.add_category(self.conn, name, description)

        categories = repository.get_all_categories(self.conn)
        cat_names = [c['name'] for c in categories]
        self.assertIn('entertainment', cat_names)

        cat = next(c for c in categories if c['name'] == 'entertainment')
        self.assertEqual(cat['description'], 'Movies and concerts')


# ==================== INTERACTIVE ADD SUBSCRIPTION ====================

class TestInteractiveAddSubscription(unittest.TestCase):
    """Test interactive subscription/budget creation flow."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        DEFAULT,            # kind: subscription (default)
        'Netflix',          # name
        '15.99',            # amount
        CASH,               # account: Cash
        CAT_PERSONAL,       # category: Personal
        DEFAULT,            # start date: today's 1st
        DEFAULT,            # end date: no
        DEFAULT,            # confirm: yes
    ])
    def test_subscription(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'sub_netflix')
        self.assertEqual(result['name'], 'Netflix')
        self.assertEqual(result['monthly_amount'], 15.99)
        self.assertEqual(result['payment_account_id'], 'Cash')
        self.assertEqual(result['category'], 'Personal')
        self.assertFalse(result['is_budget'])
        self.assertFalse(result['is_income'])
        self.assertIsNone(result['end_date'])

    @patch('builtins.input', side_effect=[
        'budget',           # kind
        'Food Budget',      # name
        '300',              # amount
        CASH,               # account: Cash
        CAT_HOME_GROC,      # category: Home Groceries
        DEFAULT,            # start date
        DEFAULT,            # end date: no
        DEFAULT,            # underspend: keep (default)
        DEFAULT,            # confirm: yes
    ])
    def test_budget(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'budget_food_budget')
        self.assertTrue(result['is_budget'])
        self.assertFalse(result['is_income'])
        self.assertEqual(result['underspend_behavior'], 'keep')

    @patch('builtins.input', side_effect=[
        'budget',           # kind
        'Rent',             # name
        '500',              # amount
        CASH,               # account
        CAT_HOUSING,        # category: Housing
        DEFAULT,            # start date
        DEFAULT,            # end date: no
        'return',           # underspend: return
        DEFAULT,            # confirm
    ])
    def test_budget_return_underspend(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)
        self.assertEqual(result['underspend_behavior'], 'return')

    @patch('builtins.input', side_effect=[
        'income',           # kind
        'Salary',           # name
        '2000',             # amount
        CASH,               # account
        CAT_INCOME,         # category: Income
        DEFAULT,            # start date
        DEFAULT,            # end date: no
        DEFAULT,            # confirm
    ])
    def test_income(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'budget_salary')
        self.assertTrue(result['is_budget'])
        self.assertTrue(result['is_income'])

    @patch('builtins.input', side_effect=[
        DEFAULT,            # kind: subscription
        'Temp Sub',         # name
        '50',               # amount
        CASH,               # account
        CAT_PERSONAL,       # category
        DEFAULT,            # start date
        YES,                # end date: yes
        '2026-12-31',       # end date value
        DEFAULT,            # confirm
    ])
    def test_subscription_with_end_date(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)
        self.assertEqual(result['end_date'], date(2026, 12, 31))

    @patch('builtins.input', side_effect=[
        DEFAULT,            # kind
        'Test',             # name
        '10',               # amount
        CASH,               # account
        CAT_PERSONAL,       # category
        DEFAULT,            # start date
        DEFAULT,            # end date: no
        'n',                # confirm: no
    ])
    def test_cancel_at_confirmation(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_cancel_at_kind(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        DEFAULT,            # kind
        'Test',             # name
        KeyboardInterrupt,
    ])
    def test_cancel_at_amount(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNone(result)


class TestInteractiveAddSubscriptionE2E(unittest.TestCase):
    """End-to-end: interactive subscription flow + database + forecasts."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'budget',           # kind
        'Groceries',        # name
        '300',              # amount
        CASH,               # account: Cash
        CAT_HOME_GROC,      # category: Home Groceries
        '2026-03-01',       # start date
        DEFAULT,            # end date: no
        DEFAULT,            # underspend: keep
        DEFAULT,            # confirm
    ])
    def test_e2e_budget_with_forecasts(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)

        repository.add_subscription(self.conn, result)
        controller.generate_forecasts(self.conn, horizon_months=6, from_date=result['start_date'])

        sub = repository.get_subscription_by_id(self.conn, 'budget_groceries')
        self.assertIsNotNone(sub)
        self.assertEqual(sub['name'], 'Groceries')
        self.assertEqual(sub['monthly_amount'], 300.0)

        # Should have forecast transactions
        txns = repository.get_all_transactions(self.conn)
        forecast_txns = [t for t in txns if t.get('origin_id') == 'budget_groceries']
        self.assertGreater(len(forecast_txns), 0)

    @patch('builtins.input', side_effect=[
        DEFAULT,            # kind: subscription
        'Spotify',          # name
        '5.99',             # amount
        CASH,               # account
        CAT_PERSONAL,       # category
        '2026-03-01',       # start date
        DEFAULT,            # end date: no
        DEFAULT,            # confirm
    ])
    def test_e2e_subscription(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)

        repository.add_subscription(self.conn, result)

        sub = repository.get_subscription_by_id(self.conn, 'sub_spotify')
        self.assertIsNotNone(sub)
        self.assertFalse(sub['is_budget'])
        self.assertEqual(sub['monthly_amount'], 5.99)


# ==================== INTERACTIVE EDIT TRANSACTION ====================

class TestInteractiveEditTransaction(unittest.TestCase):
    """Test interactive transaction edit flow."""

    def setUp(self):
        self.conn = create_test_db()
        # Add a transaction to edit
        controller.process_transaction_request(self.conn, {
            'type': 'simple',
            'description': 'Original purchase',
            'account': 'Cash',
            'amount': 50.0,
            'category': 'Personal',
            'budget': None,
            'is_income': False,
            'is_pending': False,
            'is_planning': False,
        }, transaction_date=date(2026, 3, 1))
        txns = repository.get_all_transactions(self.conn)
        self.tx_id = txns[0]['id']

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'Updated purchase', # description (changed)
        DEFAULT,            # amount: keep 50.0
        DEFAULT,            # date: keep 2026-03-01
        DEFAULT,            # category: skip (keep current)
        # no budget prompt (no active budgets in test DB)
        DEFAULT,            # status: keep committed
        DEFAULT,            # confirm: yes
    ])
    def test_edit_description_only(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNotNone(result)
        updates, new_date = result
        self.assertEqual(updates['description'], 'Updated purchase')
        self.assertNotIn('amount', updates)
        self.assertIsNone(new_date)

    @patch('builtins.input', side_effect=[
        'New desc',         # description
        '-75.00',           # amount (changed, explicit sign)
        '2026-03-05',       # date (changed)
        DEFAULT,            # category: skip
        # no budget prompt
        'pending',          # status (changed)
        DEFAULT,            # confirm
    ])
    def test_edit_multiple_fields(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNotNone(result)
        updates, new_date = result
        self.assertEqual(updates['description'], 'New desc')
        self.assertAlmostEqual(updates['amount'], -75.0)  # negative (expense)
        self.assertEqual(updates['status'], 'pending')
        self.assertEqual(new_date, date(2026, 3, 5))

    @patch('builtins.input', side_effect=[
        DEFAULT,            # description: keep
        DEFAULT,            # amount: keep
        DEFAULT,            # date: keep
        DEFAULT,            # category: skip
        # no budget prompt
        DEFAULT,            # status: keep
    ])
    def test_no_changes(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        'Changed',          # description
        DEFAULT,            # amount
        DEFAULT,            # date
        DEFAULT,            # category
        # no budget prompt
        DEFAULT,            # status
        'n',                # confirm: no
    ])
    def test_cancel_at_confirmation(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_cancel_at_description(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNone(result)

    def test_nonexistent_transaction(self):
        result = interactive_edit_transaction(self.conn, 99999)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        DEFAULT,            # description: keep
        '99.99',            # amount: bare number keeps original sign (-expense)
        DEFAULT,            # date
        DEFAULT,            # category
        # no budget prompt
        DEFAULT,            # status
        DEFAULT,            # confirm
    ])
    def test_edit_amount_preserves_sign(self, _):
        """Bare number preserves original sign (expense stays negative)."""
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNotNone(result)
        updates, _ = result
        self.assertAlmostEqual(updates['amount'], -99.99)

    @patch('builtins.input', side_effect=[
        DEFAULT,            # description
        DEFAULT,            # amount
        DEFAULT,            # date
        CAT_HOME_GROC,      # category: select Home Groceries
        # no budget prompt
        DEFAULT,            # status
        DEFAULT,            # confirm
    ])
    def test_edit_category(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNotNone(result)
        updates, _ = result
        self.assertEqual(updates['category'], 'Home Groceries')


class TestInteractiveEditTransactionE2E(unittest.TestCase):
    """End-to-end: interactive edit flow + controller persistence."""

    def setUp(self):
        self.conn = create_test_db()
        controller.process_transaction_request(self.conn, {
            'type': 'simple',
            'description': 'Original',
            'account': 'Cash',
            'amount': 50.0,
            'category': 'Personal',
            'budget': None,
            'is_income': False,
            'is_pending': False,
            'is_planning': False,
        }, transaction_date=date(2026, 3, 1))
        txns = repository.get_all_transactions(self.conn)
        self.tx_id = txns[0]['id']

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'Edited desc',      # description
        '99.00',            # amount: bare number, keeps negative sign
        DEFAULT,            # date
        DEFAULT,            # category: skip
        # no budget prompt
        DEFAULT,            # status
        DEFAULT,            # confirm
    ])
    def test_e2e_edit_persists(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNotNone(result)
        updates, new_date = result
        controller.process_transaction_edit(self.conn, self.tx_id, updates, new_date)

        tx = repository.get_transaction_by_id(self.conn, self.tx_id)
        self.assertEqual(tx['description'], 'Edited desc')
        self.assertAlmostEqual(tx['amount'], -99.0)

    @patch('builtins.input', side_effect=[
        DEFAULT,            # description
        DEFAULT,            # amount
        '2026-03-10',       # date changed
        DEFAULT,            # category
        # no budget prompt
        DEFAULT,            # status
        DEFAULT,            # confirm
    ])
    def test_e2e_date_change(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNotNone(result)
        updates, new_date = result
        self.assertEqual(new_date, date(2026, 3, 10))
        controller.process_transaction_edit(self.conn, self.tx_id, updates, new_date)

        # Date change deletes + recreates, so find the new transaction
        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 1)
        self.assertEqual(str(txns[0]['date_created']), '2026-03-10')

    @patch('builtins.input', side_effect=[
        DEFAULT,            # description
        DEFAULT,            # amount
        DEFAULT,            # date
        DEFAULT,            # category: skip
        # no budget prompt
        'pending',          # status changed
        DEFAULT,            # confirm
    ])
    def test_e2e_status_change(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNotNone(result)
        updates, new_date = result
        controller.process_transaction_edit(self.conn, self.tx_id, updates, new_date)

        tx = repository.get_transaction_by_id(self.conn, self.tx_id)
        self.assertEqual(tx['status'], 'pending')


class TestInteractiveEditTransactionWithBudget(unittest.TestCase):
    """Test interactive edit when budgets exist."""

    def setUp(self):
        self.conn = create_test_db()
        # Add a budget
        repository.add_subscription(self.conn, {
            "id": "budget_food",
            "name": "Food Budget",
            "category": "Home Groceries",
            "monthly_amount": 300.0,
            "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1),
            "end_date": date(2026, 3, 31),
            "is_budget": 1,
            "underspend_behavior": "keep",
            "is_income": 0,
        })
        controller.generate_forecasts(self.conn, horizon_months=1, from_date=date(2026, 3, 1))
        controller.run_monthly_rollover(self.conn, date(2026, 3, 5))

        # Add a transaction in the budget period
        controller.process_transaction_request(self.conn, {
            'type': 'simple',
            'description': 'Groceries',
            'account': 'Cash',
            'amount': 50.0,
            'category': 'Home Groceries',
            'budget': 'budget_food',
            'is_income': False,
            'is_pending': False,
            'is_planning': False,
        }, transaction_date=date(2026, 3, 5))

        txns = repository.get_all_transactions(self.conn)
        # Find the user transaction (not the allocation)
        user_txns = [t for t in txns if t['description'] == 'Groceries']
        self.tx_id = user_txns[0]['id']

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        DEFAULT,            # description: keep
        DEFAULT,            # amount: keep
        DEFAULT,            # date: keep
        DEFAULT,            # category: skip (keep)
        DEFAULT,            # budget: skip (keep current)
        DEFAULT,            # status: keep
    ])
    def test_no_changes_with_budget(self, _):
        result = interactive_edit_transaction(self.conn, self.tx_id)
        self.assertIsNone(result)


# ==================== INTERACTIVE EDIT SUBSCRIPTION ====================

class TestInteractiveEditSubscription(unittest.TestCase):
    """Test interactive subscription edit flow."""

    def setUp(self):
        self.conn = create_test_db()
        repository.add_subscription(self.conn, {
            "id": "budget_food",
            "name": "Food Budget",
            "category": "Home Groceries",
            "monthly_amount": 300.0,
            "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1),
            "end_date": None,
            "is_budget": 1,
            "underspend_behavior": "keep",
            "is_income": 0,
        })

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'Updated Food Budget',  # name (changed)
        DEFAULT,                # amount: keep 300
        DEFAULT,                # account: skip (keep Cash)
        DEFAULT,                # change end date: no
        DEFAULT,                # underspend: keep (default)
        DEFAULT,                # confirm
    ])
    def test_edit_name(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Updated Food Budget')
        self.assertNotIn('monthly_amount', result)

    @patch('builtins.input', side_effect=[
        DEFAULT,                # name: keep
        '400',                  # amount: changed
        DEFAULT,                # account: skip
        DEFAULT,                # change end date: no
        DEFAULT,                # underspend: keep
        DEFAULT,                # confirm
    ])
    def test_edit_amount(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNotNone(result)
        self.assertEqual(result['monthly_amount'], 400.0)
        self.assertNotIn('name', result)

    @patch('builtins.input', side_effect=[
        DEFAULT,                # name: keep
        DEFAULT,                # amount: keep
        DEFAULT,                # account: skip
        YES,                    # change end date: yes
        NO,                     # remove end date: no
        '2026-12-31',           # end date
        DEFAULT,                # underspend: keep
        DEFAULT,                # confirm
    ])
    def test_set_end_date(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNotNone(result)
        self.assertEqual(result['end_date'], date(2026, 12, 31))

    @patch('builtins.input', side_effect=[
        DEFAULT,                # name: keep
        DEFAULT,                # amount: keep
        DEFAULT,                # account: skip
        DEFAULT,                # change end date: no
        'return',               # underspend: changed to return
        DEFAULT,                # confirm
    ])
    def test_edit_underspend(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNotNone(result)
        self.assertEqual(result['underspend_behavior'], 'return')

    @patch('builtins.input', side_effect=[
        DEFAULT,                # name: keep
        DEFAULT,                # amount: keep
        DEFAULT,                # account: skip
        DEFAULT,                # change end date: no
        DEFAULT,                # underspend: keep
    ])
    def test_no_changes(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        'Changed',              # name
        DEFAULT,                # amount
        DEFAULT,                # account
        DEFAULT,                # end date
        DEFAULT,                # underspend
        'n',                    # confirm: no
    ])
    def test_cancel_at_confirmation(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_cancel_at_name(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNone(result)

    def test_nonexistent_subscription(self):
        result = interactive_edit_subscription(self.conn, 'nonexistent')
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        DEFAULT,                # name
        DEFAULT,                # amount
        AMEX,                   # account: select Amex Produbanco
        DEFAULT,                # change end date: no
        DEFAULT,                # underspend: keep
        DEFAULT,                # confirm
    ])
    def test_edit_account(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNotNone(result)
        self.assertEqual(result['payment_account_id'], 'Amex Produbanco')


class TestInteractiveEditSubscriptionWithEndDate(unittest.TestCase):
    """Test edit subscription that already has an end date."""

    def setUp(self):
        self.conn = create_test_db()
        repository.add_subscription(self.conn, {
            "id": "budget_temp",
            "name": "Temp Budget",
            "category": "Personal",
            "monthly_amount": 100.0,
            "payment_account_id": "Cash",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 6, 30),
            "is_budget": 1,
            "underspend_behavior": "keep",
            "is_income": 0,
        })

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        DEFAULT,                # name: keep
        DEFAULT,                # amount: keep
        DEFAULT,                # account: skip
        YES,                    # change end date: yes
        YES,                    # remove end date: yes (make ongoing)
        DEFAULT,                # underspend: keep
        DEFAULT,                # confirm
    ])
    def test_remove_end_date(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_temp')
        self.assertIsNotNone(result)
        self.assertIsNone(result['end_date'])


class TestInteractiveEditSubscriptionE2E(unittest.TestCase):
    """End-to-end: interactive subscription edit + controller persistence."""

    def setUp(self):
        self.conn = create_test_db()
        repository.add_subscription(self.conn, {
            "id": "budget_food",
            "name": "Food Budget",
            "category": "Home Groceries",
            "monthly_amount": 300.0,
            "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1),
            "end_date": None,
            "is_budget": 1,
            "underspend_behavior": "keep",
            "is_income": 0,
        })
        controller.generate_forecasts(self.conn, horizon_months=6, from_date=date(2026, 3, 1))

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'Updated Food',         # name changed
        '350',                  # amount changed
        DEFAULT,                # account: skip
        DEFAULT,                # change end date: no
        DEFAULT,                # underspend: keep
        DEFAULT,                # confirm
    ])
    def test_e2e_edit_persists(self, _):
        result = interactive_edit_subscription(self.conn, 'budget_food')
        self.assertIsNotNone(result)
        controller.process_budget_update(self.conn, 'budget_food', result)

        sub = repository.get_subscription_by_id(self.conn, 'budget_food')
        self.assertEqual(sub['name'], 'Updated Food')
        self.assertEqual(sub['monthly_amount'], 350.0)


class TestInteractiveEditNonBudgetSubscription(unittest.TestCase):
    """Test that non-budget subscriptions skip the underspend prompt."""

    def setUp(self):
        self.conn = create_test_db()
        repository.add_subscription(self.conn, {
            "id": "sub_netflix",
            "name": "Netflix",
            "category": "Personal",
            "monthly_amount": 15.99,
            "payment_account_id": "Cash",
            "start_date": date(2026, 1, 1),
            "end_date": None,
            "is_budget": 0,
            "underspend_behavior": "keep",
            "is_income": 0,
        })

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'Netflix HD',           # name: changed
        DEFAULT,                # amount: keep
        DEFAULT,                # account: skip
        DEFAULT,                # change end date: no
        # NO underspend prompt (not a budget)
        DEFAULT,                # confirm
    ])
    def test_edit_non_budget_skips_underspend(self, _):
        result = interactive_edit_subscription(self.conn, 'sub_netflix')
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Netflix HD')
        self.assertNotIn('underspend_behavior', result)


# ==================== INTERACTIVE STATEMENT FIX ====================

class TestInteractiveStatementFix(unittest.TestCase):
    """Test interactive statement fix flow."""

    def setUp(self):
        self.conn = create_test_db()
        # Add some CC transactions for Visa Produbanco (cut-off=14, pay=25)
        # Transaction before cut-off -> pays this month
        controller.process_transaction_request(self.conn, {
            'type': 'simple',
            'description': 'CC Purchase 1',
            'account': 'Visa Produbanco',
            'amount': 100.0,
            'category': 'Personal',
            'budget': None,
            'is_income': False,
            'is_pending': False,
            'is_planning': False,
        }, transaction_date=date(2026, 3, 10))  # before cut-off 14 -> pays March 25

        controller.process_transaction_request(self.conn, {
            'type': 'simple',
            'description': 'CC Purchase 2',
            'account': 'Visa Produbanco',
            'amount': 50.0,
            'category': 'Personal',
            'budget': None,
            'is_income': False,
            'is_pending': False,
            'is_planning': False,
        }, transaction_date=date(2026, 3, 12))  # before cut-off 14 -> pays March 25

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        '160',              # statement amount (actual is 150, so +10 difference)
        DEFAULT,            # confirm: yes
    ])
    def test_returns_statement_amount(self, _):
        result = interactive_statement_fix(self.conn, 'Visa Produbanco', date(2026, 3, 1))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -160.0)  # negative for expense

    @patch('builtins.input', side_effect=[
        '160',              # statement amount
        'n',                # confirm: no
    ])
    def test_cancel_at_confirmation(self, _):
        result = interactive_statement_fix(self.conn, 'Visa Produbanco', date(2026, 3, 1))
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_cancel_at_amount(self, _):
        result = interactive_statement_fix(self.conn, 'Visa Produbanco', date(2026, 3, 1))
        self.assertIsNone(result)

    def test_nonexistent_account(self):
        result = interactive_statement_fix(self.conn, 'Nonexistent', date(2026, 3, 1))
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        '150',              # exact match: 100 + 50 = 150
    ])
    def test_no_adjustment_needed(self, _):
        """When statement matches current total, returns None."""
        result = interactive_statement_fix(self.conn, 'Visa Produbanco', date(2026, 3, 1))
        self.assertIsNone(result)


class TestInteractiveStatementFixE2E(unittest.TestCase):
    """End-to-end: interactive statement fix + controller adjustment."""

    def setUp(self):
        self.conn = create_test_db()
        controller.process_transaction_request(self.conn, {
            'type': 'simple',
            'description': 'CC Purchase',
            'account': 'Visa Produbanco',
            'amount': 100.0,
            'category': 'Personal',
            'budget': None,
            'is_income': False,
            'is_pending': False,
            'is_planning': False,
        }, transaction_date=date(2026, 3, 10))

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        '120',              # statement says 120, tracked is 100
        DEFAULT,            # confirm
    ])
    def test_e2e_adjustment_created(self, _):
        month = date(2026, 3, 1)
        statement_amount = interactive_statement_fix(self.conn, 'Visa Produbanco', month)
        self.assertIsNotNone(statement_amount)

        result = controller.process_statement_adjustment(
            self.conn, 'Visa Produbanco', month, statement_amount
        )
        self.assertIsNotNone(result)

        # Check adjustment transaction was created
        txns = repository.get_all_transactions(self.conn)
        adj_txns = [t for t in txns if 'Adjustment' in t['description']]
        self.assertEqual(len(adj_txns), 1)


class TestInteractiveStatementFixCashAccount(unittest.TestCase):
    """Test interactive statement fix with a cash account."""

    def setUp(self):
        self.conn = create_test_db()
        controller.process_transaction_request(self.conn, {
            'type': 'simple',
            'description': 'Cash expense',
            'account': 'Cash',
            'amount': 75.0,
            'category': 'Personal',
            'budget': None,
            'is_income': False,
            'is_pending': False,
            'is_planning': False,
        }, transaction_date=date(2026, 3, 15))

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        '80',               # statement amount (tracked is 75)
        DEFAULT,            # confirm
    ])
    def test_cash_account_fix(self, _):
        result = interactive_statement_fix(self.conn, 'Cash', date(2026, 3, 1))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -80.0)


# ==================== INTERACTIVE ADD SUBSCRIPTION (no categories) ====================

class TestInteractiveAddSubscriptionNoCategories(unittest.TestCase):
    """Test that subscription add handles missing prerequisites."""

    def setUp(self):
        # Minimal DB with no categories
        from cashflow.database import create_connection, create_tables
        self.conn = create_connection(":memory:")
        create_tables(self.conn)
        # Add an account but no categories
        repository.add_account(self.conn, "Cash", "cash")

    def tearDown(self):
        self.conn.close()

    def test_no_categories_shows_error(self):
        result = interactive_add_subscription(self.conn)
        self.assertIsNone(result)


class TestInteractiveAddSubscriptionNoAccounts(unittest.TestCase):
    """Test that subscription add handles no accounts."""

    def setUp(self):
        from cashflow.database import create_connection, create_tables
        self.conn = create_connection(":memory:")
        create_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_no_accounts_shows_error(self):
        result = interactive_add_subscription(self.conn)
        self.assertIsNone(result)


# ==================== PROMPT_CHOICE SHORTCUTS ====================

class TestPromptChoiceShortcuts(unittest.TestCase):
    """Tests for prompt_choice number and prefix support."""

    # --- Number selection ---

    @patch('builtins.input', return_value='2')
    def test_by_number(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertEqual(result, "credit_card")

    @patch('builtins.input', return_value='1')
    def test_first_by_number(self, _):
        result = prompt_choice("Kind", ["subscription", "budget", "income"], default="subscription")
        self.assertEqual(result, "subscription")

    @patch('builtins.input', return_value='3')
    def test_last_by_number(self, _):
        result = prompt_choice("Kind", ["subscription", "budget", "income"], default="subscription")
        self.assertEqual(result, "income")

    @patch('builtins.input', side_effect=['0', '1'])
    def test_zero_out_of_range_retries(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertEqual(result, "cash")

    @patch('builtins.input', side_effect=['5', '2'])
    def test_too_high_number_retries(self, _):
        result = prompt_choice("Kind", ["subscription", "budget", "income"], default="subscription")
        self.assertEqual(result, "budget")

    # --- Prefix matching ---

    @patch('builtins.input', return_value='cr')
    def test_prefix_unique(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertEqual(result, "credit_card")

    @patch('builtins.input', return_value='b')
    def test_single_char_unique(self, _):
        result = prompt_choice("Kind", ["subscription", "budget", "income"], default="subscription")
        self.assertEqual(result, "budget")

    @patch('builtins.input', return_value='i')
    def test_single_char_i_for_income(self, _):
        """'i' matches 'income' uniquely (not 'installment' in this list)."""
        result = prompt_choice("Kind", ["subscription", "budget", "income"], default="subscription")
        self.assertEqual(result, "income")

    @patch('builtins.input', side_effect=['c', 'ca'])
    def test_ambiguous_prefix_retries(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertEqual(result, "cash")

    @patch('builtins.input', side_effect=['s', 'sp'])
    def test_ambiguous_s_for_simple_split_then_sp(self, _):
        """'s' is ambiguous (simple/split), 'sp' resolves to split."""
        result = prompt_choice("Type", ["simple", "installment", "split"], default="simple")
        self.assertEqual(result, "split")

    @patch('builtins.input', return_value='i')
    def test_prefix_i_for_installment(self, _):
        result = prompt_choice("Type", ["simple", "installment", "split"], default="simple")
        self.assertEqual(result, "installment")

    # --- Status choices (real app sets) ---

    @patch('builtins.input', return_value='n')
    def test_status_n_for_normal(self, _):
        result = prompt_choice("Status", ["normal", "pending", "planning"], default="normal")
        self.assertEqual(result, "normal")

    @patch('builtins.input', return_value='pe')
    def test_status_pe_for_pending(self, _):
        result = prompt_choice("Status", ["normal", "pending", "planning"], default="normal")
        self.assertEqual(result, "pending")

    @patch('builtins.input', return_value='pl')
    def test_status_pl_for_planning(self, _):
        result = prompt_choice("Status", ["normal", "pending", "planning"], default="normal")
        self.assertEqual(result, "planning")

    @patch('builtins.input', side_effect=['p', 'pe'])
    def test_status_p_ambiguous_pending_planning(self, _):
        """'p' matches both pending and planning, retries."""
        result = prompt_choice("Status", ["normal", "pending", "planning"], default="normal")
        self.assertEqual(result, "pending")

    @patch('builtins.input', return_value='c')
    def test_edit_status_c_for_committed(self, _):
        result = prompt_choice("Status", ["committed", "pending", "planning"], default="committed")
        self.assertEqual(result, "committed")

    # --- Underspend choices ---

    @patch('builtins.input', return_value='k')
    def test_underspend_k_for_keep(self, _):
        result = prompt_choice("Underspend", ["keep", "return"], default="keep")
        self.assertEqual(result, "keep")

    @patch('builtins.input', return_value='r')
    def test_underspend_r_for_return(self, _):
        result = prompt_choice("Underspend", ["keep", "return"], default="keep")
        self.assertEqual(result, "return")

    # --- Exact match still works ---

    @patch('builtins.input', return_value='credit_card')
    def test_exact_match_full_word(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertEqual(result, "credit_card")

    @patch('builtins.input', return_value='planning')
    def test_exact_match_full_word_status(self, _):
        result = prompt_choice("Status", ["normal", "pending", "planning"], default="normal")
        self.assertEqual(result, "planning")

    # --- Default on empty ---

    @patch('builtins.input', return_value='')
    def test_default_on_empty(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertEqual(result, "cash")

    # --- Invalid input retries ---

    @patch('builtins.input', side_effect=['xyz', 'cash'])
    def test_invalid_string_retries(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertEqual(result, "cash")

    # --- Cancel ---

    @patch('builtins.input', side_effect=EOFError)
    def test_eof_returns_none(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_ctrl_c_returns_none(self, _):
        result = prompt_choice("Type", ["cash", "credit_card"], default="cash")
        self.assertIsNone(result)


# ==================== PROMPT_AMOUNT CLEANING ====================

class TestPromptAmountCleaning(unittest.TestCase):
    """Tests for prompt_amount $ and comma handling."""

    # --- Dollar sign ---

    @patch('builtins.input', return_value='$9.99')
    def test_dollar_sign_stripped(self, _):
        self.assertEqual(prompt_amount("Amount"), 9.99)

    @patch('builtins.input', return_value='$50')
    def test_dollar_sign_integer(self, _):
        self.assertEqual(prompt_amount("Amount"), 50.0)

    # --- Thousands separator ---

    @patch('builtins.input', return_value='1,234.50')
    def test_comma_thousands_with_decimals(self, _):
        self.assertEqual(prompt_amount("Amount"), 1234.50)

    @patch('builtins.input', return_value='1,234')
    def test_comma_thousands_no_decimals(self, _):
        self.assertEqual(prompt_amount("Amount"), 1234.0)

    @patch('builtins.input', return_value='1,000,000')
    def test_multiple_commas(self, _):
        self.assertEqual(prompt_amount("Amount"), 1000000.0)

    # --- Dollar + comma combined ---

    @patch('builtins.input', return_value='$1,234')
    def test_dollar_and_comma(self, _):
        self.assertEqual(prompt_amount("Amount"), 1234.0)

    @patch('builtins.input', return_value='$1,234.50')
    def test_dollar_comma_and_decimals(self, _):
        self.assertEqual(prompt_amount("Amount"), 1234.50)

    # --- Locale decimal (comma as decimal separator) ---

    @patch('builtins.input', return_value='9,99')
    def test_locale_comma_decimal(self, _):
        """European-style 9,99 → 9.99."""
        self.assertEqual(prompt_amount("Amount"), 9.99)

    @patch('builtins.input', return_value='15,50')
    def test_locale_comma_decimal_larger(self, _):
        self.assertEqual(prompt_amount("Amount"), 15.50)

    # --- Plain numbers still work ---

    @patch('builtins.input', return_value='42')
    def test_plain_integer(self, _):
        self.assertEqual(prompt_amount("Amount"), 42.0)

    @patch('builtins.input', return_value='9.99')
    def test_plain_decimal(self, _):
        self.assertEqual(prompt_amount("Amount"), 9.99)

    # --- Invalid input retries ---

    @patch('builtins.input', side_effect=['abc', '10'])
    def test_non_numeric_retries(self, _):
        self.assertEqual(prompt_amount("Amount"), 10.0)

    @patch('builtins.input', side_effect=['$', '5'])
    def test_dollar_only_retries(self, _):
        self.assertEqual(prompt_amount("Amount"), 5.0)

    @patch('builtins.input', side_effect=['0', '10'])
    def test_zero_rejected_retries(self, _):
        self.assertEqual(prompt_amount("Amount"), 10.0)

    @patch('builtins.input', side_effect=['-5', '10'])
    def test_negative_rejected_retries(self, _):
        self.assertEqual(prompt_amount("Amount"), 10.0)

    # --- Default with cleaning ---

    @patch('builtins.input', return_value='')
    def test_default_still_works(self, _):
        self.assertEqual(prompt_amount("Amount", default=25.0), 25.0)


# ==================== PROMPT_DATE +N MONTHS ====================

class TestPromptDatePlusMonths(unittest.TestCase):
    """Tests for prompt_date +N shortcut and end-of-month default."""

    @patch('builtins.input', return_value='+1')
    def test_plus_one_month(self, _):
        ref = date(2026, 3, 5)
        result = prompt_date("End date", default=date(2026, 3, 31), reference_date=ref)
        self.assertEqual(result, date(2026, 4, 30))

    @patch('builtins.input', return_value='+2')
    def test_plus_two_months(self, _):
        ref = date(2026, 3, 5)
        result = prompt_date("End date", default=date(2026, 3, 31), reference_date=ref)
        self.assertEqual(result, date(2026, 5, 31))

    @patch('builtins.input', return_value='+0')
    def test_plus_zero_same_month(self, _):
        ref = date(2026, 3, 5)
        result = prompt_date("End date", default=date(2026, 3, 31), reference_date=ref)
        self.assertEqual(result, date(2026, 3, 31))

    @patch('builtins.input', return_value='+12')
    def test_plus_twelve_months(self, _):
        ref = date(2026, 3, 15)
        result = prompt_date("End date", default=date(2026, 3, 31), reference_date=ref)
        self.assertEqual(result, date(2027, 3, 31))

    @patch('builtins.input', return_value='+1')
    def test_plus_one_from_january(self, _):
        """Jan 31 + 1 month → Feb 28."""
        ref = date(2026, 1, 31)
        result = prompt_date("End date", default=date(2026, 1, 31), reference_date=ref)
        self.assertEqual(result, date(2026, 2, 28))

    @patch('builtins.input', return_value='')
    def test_default_is_end_of_month(self, _):
        """Empty input returns the default (end of start month)."""
        result = prompt_date("End date", default=date(2026, 3, 31), reference_date=date(2026, 3, 5))
        self.assertEqual(result, date(2026, 3, 31))

    @patch('builtins.input', return_value='2026-06-15')
    def test_explicit_date_still_works(self, _):
        """Explicit YYYY-MM-DD bypasses +N logic."""
        ref = date(2026, 3, 5)
        result = prompt_date("End date", default=date(2026, 3, 31), reference_date=ref)
        self.assertEqual(result, date(2026, 6, 15))

    @patch('builtins.input', side_effect=['+1', '2026-06-01'])
    def test_plus_without_reference_retries(self, _):
        """+N without reference_date is not recognized, retries."""
        result = prompt_date("End date", default=date(2026, 3, 31))
        self.assertEqual(result, date(2026, 6, 1))


class TestEndDateDefaultInAddSubscription(unittest.TestCase):
    """Test that add subscription defaults end date to end of start month."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'budget',           # kind
        'Test',             # name
        '100',              # amount
        CASH,               # account
        CAT_PERSONAL,       # category
        '2026-03-05',       # start date
        YES,                # set end date: yes
        DEFAULT,            # end date: accept default (should be 2026-03-31)
        DEFAULT,            # underspend: keep
        DEFAULT,            # confirm
    ])
    def test_default_end_date_is_end_of_start_month(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)
        self.assertEqual(result['end_date'], date(2026, 3, 31))

    @patch('builtins.input', side_effect=[
        'budget',           # kind
        'Test',             # name
        '100',              # amount
        CASH,               # account
        CAT_PERSONAL,       # category
        '2026-01-15',       # start date
        YES,                # set end date: yes
        '+2',               # end date: +2 months from start → end of March
        DEFAULT,            # underspend: keep
        DEFAULT,            # confirm
    ])
    def test_plus_n_end_date(self, _):
        result = interactive_add_subscription(self.conn)
        self.assertIsNotNone(result)
        self.assertEqual(result['end_date'], date(2026, 3, 31))


if __name__ == '__main__':
    unittest.main()

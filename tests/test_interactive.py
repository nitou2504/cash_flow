"""Tests for interactive transaction entry flow (ui/interactive.py).

Test DB ordering (alphabetical):
  Accounts:  1=Amex Produbanco, 2=Cash, 3=Visa Produbanco
  Categories: 1=Dining-Snacks, 2=Health, 3=Home Groceries, 4=Housing,
              5=Income, 6=Loans, 7=Others, 8=Personal, 9=Personal Groceries,
              10=Savings, 11=Transportation
  Budgets: none (unless added in setUp)

When no budgets exist, the budget prompt is skipped entirely (no input consumed).
"""

import unittest
from unittest.mock import patch
from datetime import date

from cashflow.database import create_test_db
from cashflow import repository, controller
from ui.interactive import (
    interactive_add_transaction,
    prompt_select,
    prompt_amount,
    prompt_date,
    prompt_int,
    prompt_yes_no,
    prompt_choice,
    prompt_text,
    display_transaction_preview,
)

# Shortcuts for account/category indices in test DB
CASH = '2'
VISA = '3'
AMEX = '1'
CAT_DINING = '1'
CAT_HOME_GROC = '3'
CAT_INCOME = '5'
CAT_PERSONAL = '8'
CAT_HOUSING = '4'
CAT_HEALTH = '2'
NO = ''       # default No for yes/no prompts
YES_FLAG = 'y'
DEFAULT = ''  # press Enter for default

# Flag patterns: status choice + is_income yes/no
FLAGS_NORMAL = [DEFAULT, NO]           # normal status, not income
FLAGS_INCOME = [DEFAULT, YES_FLAG]     # normal status, income
FLAGS_PENDING = ['pending', NO]        # pending status, not income
FLAGS_PLANNING = ['planning', NO]      # planning status, not income


class TestPromptHelpers(unittest.TestCase):
    """Test individual prompt helper functions."""

    @patch('builtins.input', return_value='2')
    def test_prompt_select_by_number(self, _):
        items = [{'name': 'a'}, {'name': 'b'}, {'name': 'c'}]
        result = prompt_select("Test", items, lambda x: x['name'])
        self.assertEqual(result, {'name': 'b'})

    @patch('builtins.input', return_value='beta')
    def test_prompt_select_by_substring(self, _):
        items = [{'name': 'alpha'}, {'name': 'beta'}, {'name': 'gamma'}]
        result = prompt_select("Test", items, lambda x: x['name'])
        self.assertEqual(result, {'name': 'beta'})

    @patch('builtins.input', return_value='')
    def test_prompt_select_skip_allowed(self, _):
        items = [{'name': 'a'}]
        result = prompt_select("Test", items, lambda x: x['name'], allow_skip=True)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=['', '1'])
    def test_prompt_select_skip_not_allowed_retries(self, _):
        items = [{'name': 'valid'}]
        result = prompt_select("Test", items, lambda x: x['name'], allow_skip=False)
        self.assertEqual(result, {'name': 'valid'})

    def test_prompt_select_empty_items(self):
        result = prompt_select("Test", [], lambda x: x)
        self.assertIsNone(result)

    @patch('builtins.input', return_value='hello world')
    def test_prompt_text_required(self, _):
        result = prompt_text("Label")
        self.assertEqual(result, 'hello world')

    @patch('builtins.input', return_value='')
    def test_prompt_text_default(self, _):
        result = prompt_text("Label", default="fallback")
        self.assertEqual(result, 'fallback')

    @patch('builtins.input', return_value='')
    def test_prompt_text_optional_empty(self, _):
        result = prompt_text("Label", required=False)
        self.assertIsNone(result)

    @patch('builtins.input', return_value='42.50')
    def test_prompt_amount_valid(self, _):
        result = prompt_amount()
        self.assertEqual(result, 42.50)

    @patch('builtins.input', side_effect=['-5', '0', '10'])
    def test_prompt_amount_rejects_non_positive(self, _):
        result = prompt_amount()
        self.assertEqual(result, 10.0)

    @patch('builtins.input', side_effect=['abc', '25.00'])
    def test_prompt_amount_rejects_non_numeric(self, _):
        result = prompt_amount()
        self.assertEqual(result, 25.0)

    @patch('builtins.input', return_value='')
    def test_prompt_date_default(self, _):
        result = prompt_date("Date", default=date(2026, 3, 7))
        self.assertEqual(result, date(2026, 3, 7))

    @patch('builtins.input', return_value='2026-01-15')
    def test_prompt_date_iso(self, _):
        result = prompt_date("Date")
        self.assertEqual(result, date(2026, 1, 15))

    @patch('builtins.input', return_value='yesterday')
    def test_prompt_date_yesterday(self, _):
        from datetime import timedelta
        result = prompt_date("Date")
        self.assertEqual(result, date.today() - timedelta(days=1))

    @patch('builtins.input', return_value='03/15')
    def test_prompt_date_mm_dd(self, _):
        result = prompt_date("Date")
        self.assertEqual(result, date(date.today().year, 3, 15))

    @patch('builtins.input', return_value='5')
    def test_prompt_int_valid(self, _):
        result = prompt_int("Count")
        self.assertEqual(result, 5)

    @patch('builtins.input', return_value='')
    def test_prompt_int_default(self, _):
        result = prompt_int("Count", default=3)
        self.assertEqual(result, 3)

    @patch('builtins.input', side_effect=['0', '3'])
    def test_prompt_int_min_val(self, _):
        result = prompt_int("Count", min_val=1)
        self.assertEqual(result, 3)

    @patch('builtins.input', return_value='')
    def test_prompt_yes_no_default_true(self, _):
        self.assertTrue(prompt_yes_no("Ok?", default=True))

    @patch('builtins.input', return_value='n')
    def test_prompt_yes_no_no(self, _):
        self.assertFalse(prompt_yes_no("Ok?", default=True))

    @patch('builtins.input', return_value='')
    def test_prompt_choice_default(self, _):
        result = prompt_choice("Type", ["simple", "installment", "split"], default="simple")
        self.assertEqual(result, "simple")

    @patch('builtins.input', return_value='split')
    def test_prompt_choice_explicit(self, _):
        result = prompt_choice("Type", ["simple", "installment", "split"], default="simple")
        self.assertEqual(result, "split")

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_prompt_select_ctrl_c(self, _):
        self.assertIsNone(prompt_select("Test", [{'name': 'a'}], lambda x: x['name']))

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_prompt_amount_ctrl_c(self, _):
        self.assertIsNone(prompt_amount())

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_prompt_date_ctrl_c(self, _):
        self.assertIsNone(prompt_date("Date"))

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_prompt_yes_no_ctrl_c(self, _):
        self.assertIsNone(prompt_yes_no("Ok?"))


def _simple_inputs(account=CASH, amount='25.50', category=CAT_HOME_GROC,
                   tx_date=DEFAULT, description='Test purchase',
                   flags=None, confirm=DEFAULT):
    """Build input sequence for a simple transaction (no budgets)."""
    if flags is None:
        flags = FLAGS_NORMAL
    return [
        DEFAULT,      # type: simple
        tx_date,      # date
        description,  # description
        account,      # account
        amount,       # amount
        category,     # category (skippable)
        # NO budget prompt (no budgets in test DB)
        *flags,       # status + is_income
        confirm,      # confirm
    ]


class TestInteractiveSimple(unittest.TestCase):
    """Test simple transaction interactive flow (no budgets in test DB)."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=_simple_inputs())
    def test_simple_transaction(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['type'], 'simple')
        self.assertEqual(request['description'], 'Test purchase')
        self.assertEqual(request['account'], 'Cash')
        self.assertEqual(request['amount'], 25.50)
        self.assertEqual(request['category'], 'Home Groceries')
        self.assertIsNone(request['budget'])
        self.assertFalse(request['is_income'])
        self.assertFalse(request['is_pending'])
        self.assertFalse(request['is_planning'])
        self.assertEqual(request['_transaction_date'], date.today())

    @patch('builtins.input', side_effect=_simple_inputs(
        description='Salary', amount='1000', category=CAT_INCOME, flags=FLAGS_INCOME))
    def test_simple_income(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertTrue(request['is_income'])
        self.assertEqual(request['category'], 'Income')

    @patch('builtins.input', side_effect=_simple_inputs(
        description='Pending debt', amount='50', category=DEFAULT, flags=FLAGS_PENDING))
    def test_simple_pending(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertTrue(request['is_pending'])
        self.assertFalse(request['is_planning'])

    @patch('builtins.input', side_effect=_simple_inputs(
        description='What if TV', amount='800', category=DEFAULT, flags=FLAGS_PLANNING))
    def test_simple_planning(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertFalse(request['is_pending'])
        self.assertTrue(request['is_planning'])

    @patch('builtins.input', side_effect=_simple_inputs(
        account=VISA, tx_date='2026-01-15', description='CC Buy',
        amount='100', category='9'))  # 9=Personal Groceries
    def test_simple_credit_card_with_date(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['account'], 'Visa Produbanco')
        self.assertEqual(request['_transaction_date'], date(2026, 1, 15))
        self.assertEqual(request['category'], 'Personal Groceries')

    @patch('builtins.input', side_effect=_simple_inputs(
        description='No cat', amount='10', category=DEFAULT))
    def test_simple_no_category(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertIsNone(request['category'])
        self.assertIsNone(request['budget'])

    @patch('builtins.input', side_effect=_simple_inputs(confirm='n'))
    def test_cancel_at_confirmation(self, _):
        result = interactive_add_transaction(self.conn)
        self.assertIsNone(result)

    @patch('builtins.input', side_effect=[
        DEFAULT,            # type: simple
        DEFAULT,            # date
        'Substring test',   # description
        'cash',             # account by substring match
        '10',               # amount
        'home groc',        # category by substring: "Home Groceries"
        *FLAGS_NORMAL,       # flags
        DEFAULT,            # confirm
    ])
    def test_simple_substring_selection(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['account'], 'Cash')
        self.assertEqual(request['category'], 'Home Groceries')


class TestInteractiveInstallment(unittest.TestCase):
    """Test installment transaction interactive flow (no budgets)."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'installment',  # type
        DEFAULT,        # date: today
        'Laptop',       # description
        CASH,           # account
        '1200',         # total amount
        '12',           # installments
        DEFAULT,        # grace period: 0
        DEFAULT,        # start from: 1
        DEFAULT,        # category: skip
        # no budget prompt
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_installment_basic(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['type'], 'installment')
        self.assertEqual(request['total_amount'], 1200.0)
        self.assertEqual(request['installments'], 12)
        self.assertEqual(request['grace_period_months'], 0)
        self.assertNotIn('start_from_installment', request)

    @patch('builtins.input', side_effect=[
        'installment',  # type
        DEFAULT,        # date
        'Fridge',       # description
        VISA,           # account: Visa Produbanco
        '600',          # total amount
        '6',            # installments
        '3',            # grace period: 3
        DEFAULT,        # start from: 1
        DEFAULT,        # category: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_installment_with_grace_period(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['grace_period_months'], 3)
        self.assertEqual(request['account'], 'Visa Produbanco')

    @patch('builtins.input', side_effect=[
        'installment',  # type
        DEFAULT,        # date
        'Phone plan',   # description
        VISA,           # account
        '600',          # total amount
        '12',           # total installments
        DEFAULT,        # grace period: 0
        '5',            # start from: 5
        DEFAULT,        # category: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_installment_partial(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['start_from_installment'], 5)
        self.assertEqual(request['total_installments'], 12)
        self.assertEqual(request['installments'], 8)  # 12 - 5 + 1


class TestInteractiveSplit(unittest.TestCase):
    """Test split transaction interactive flow (no budgets)."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        'split',        # type
        DEFAULT,        # date
        'Supermarket',  # description
        CASH,           # account
        # Split 1
        '30',           # amount
        CAT_HOME_GROC,  # category: Home Groceries
        # no budget
        # Split 2
        '15',           # amount
        CAT_DINING,     # category: Dining-Snacks
        # no budget
        NO,             # add more: No
        # Flags
        *FLAGS_NORMAL,
        DEFAULT,        # confirm
    ])
    def test_split_two_items(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['type'], 'split')
        self.assertEqual(len(request['splits']), 2)
        self.assertEqual(request['splits'][0]['amount'], 30.0)
        self.assertEqual(request['splits'][0]['category'], 'Home Groceries')
        self.assertEqual(request['splits'][1]['amount'], 15.0)
        self.assertEqual(request['splits'][1]['category'], 'Dining-Snacks')

    @patch('builtins.input', side_effect=[
        'split',        # type
        DEFAULT,        # date
        'Big shop',     # description
        CASH,           # account
        # Split 1
        '30',           # amount
        CAT_HOME_GROC,  # category
        # Split 2
        '15',           # amount
        CAT_DINING,     # category
        YES_FLAG,       # add more: Yes
        # Split 3
        '10',           # amount
        CAT_PERSONAL,   # category: Personal
        NO,             # add more: No
        # Flags
        *FLAGS_NORMAL,
        DEFAULT,        # confirm
    ])
    def test_split_three_items(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(len(request['splits']), 3)
        self.assertEqual(request['splits'][2]['amount'], 10.0)
        self.assertEqual(request['splits'][2]['category'], 'Personal')


class TestInteractiveCancellation(unittest.TestCase):
    """Test cancellation at various stages."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_cancel_at_type(self, _):
        self.assertIsNone(interactive_add_transaction(self.conn))

    @patch('builtins.input', side_effect=[
        DEFAULT,   # type
        DEFAULT,   # date
        KeyboardInterrupt,  # cancel at description
    ])
    def test_cancel_at_description(self, _):
        self.assertIsNone(interactive_add_transaction(self.conn))

    @patch('builtins.input', side_effect=[
        DEFAULT,   # type
        DEFAULT,   # date
        'Test',    # description
        CASH,      # account
        KeyboardInterrupt,  # cancel at amount
    ])
    def test_cancel_at_amount(self, _):
        self.assertIsNone(interactive_add_transaction(self.conn))


class TestInteractiveEndToEnd(unittest.TestCase):
    """End-to-end: interactive flow + controller.process_transaction_request."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        DEFAULT,        # type: simple
        '2026-03-01',   # date
        'Groceries',    # description
        CASH,           # account: Cash
        '45.99',        # amount
        CAT_HOME_GROC,  # category: Home Groceries
        # no budget
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_simple(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)

        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0]['description'], 'Groceries')
        self.assertAlmostEqual(txns[0]['amount'], -45.99)
        self.assertEqual(txns[0]['account'], 'Cash')
        self.assertEqual(txns[0]['category'], 'Home Groceries')
        self.assertEqual(txns[0]['status'], 'committed')
        self.assertEqual(str(txns[0]['date_created']), '2026-03-01')
        self.assertEqual(str(txns[0]['date_payed']), '2026-03-01')

    @patch('builtins.input', side_effect=[
        DEFAULT,        # type: simple
        '2026-03-01',   # date
        'Salary',       # description
        CASH,           # account
        '2000',         # amount
        CAT_INCOME,     # category: Income
        *FLAGS_INCOME,  # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_income(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 1)
        self.assertAlmostEqual(txns[0]['amount'], 2000.0)
        self.assertEqual(txns[0]['status'], 'committed')

    @patch('builtins.input', side_effect=[
        DEFAULT,        # type: simple
        '2026-03-01',   # date
        'Pending debt', # description
        CASH,           # account
        '100',          # amount
        DEFAULT,        # category: skip
        *FLAGS_PENDING, # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_pending(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0]['status'], 'pending')

    @patch('builtins.input', side_effect=[
        DEFAULT,         # type: simple
        '2026-03-01',    # date
        'What if TV',    # description
        CASH,            # account
        '800',           # amount
        DEFAULT,         # category: skip
        *FLAGS_PLANNING, # flags
        DEFAULT,         # confirm
    ])
    def test_e2e_planning(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0]['status'], 'planning')

    @patch('builtins.input', side_effect=[
        DEFAULT,        # type: simple
        '2026-03-10',   # date: before cut-off 14
        'CC Purchase',  # description
        VISA,           # account: Visa Produbanco (cut-off=14, pay=25)
        '75',           # amount
        DEFAULT,        # category: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_credit_card_payment_date(self, _):
        """Credit card: date before cut-off -> payment same month."""
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 1)
        # March 10, before cut-off 14 -> payment March 25
        self.assertEqual(str(txns[0]['date_payed']), '2026-03-25')

    @patch('builtins.input', side_effect=[
        DEFAULT,        # type: simple
        '2026-03-20',   # date: AFTER cut-off 14
        'CC Late',      # description
        VISA,           # account: Visa Produbanco
        '50',           # amount
        DEFAULT,        # category: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_credit_card_after_cutoff(self, _):
        """Credit card: date after cut-off -> payment next month."""
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 1)
        # March 20, after cut-off 14 -> payment April 25
        self.assertEqual(str(txns[0]['date_payed']), '2026-04-25')

    @patch('builtins.input', side_effect=[
        'installment',  # type
        '2026-02-01',   # date
        'Laptop',       # description
        VISA,           # account: Visa Produbanco
        '1200',         # total amount
        '12',           # installments
        DEFAULT,        # grace period: 0
        DEFAULT,        # start from: 1
        DEFAULT,        # category: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_installment(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 12)
        for t in txns:
            self.assertAlmostEqual(t['amount'], -100.0)
        self.assertIn('(1/12)', txns[0]['description'])
        self.assertIn('(12/12)', txns[-1]['description'])
        # All share same origin_id
        origin_ids = {t['origin_id'] for t in txns}
        self.assertEqual(len(origin_ids), 1)

    @patch('builtins.input', side_effect=[
        'installment',  # type
        '2026-02-01',   # date
        'Phone plan',   # description
        VISA,           # account
        '600',          # total amount
        '12',           # total installments
        DEFAULT,        # grace period: 0
        '5',            # start from: 5
        DEFAULT,        # category: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_partial_installment(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 8)  # 12 - 5 + 1
        for t in txns:
            self.assertAlmostEqual(t['amount'], -50.0)  # 600/12
        self.assertIn('(5/12)', txns[0]['description'])
        self.assertIn('(12/12)', txns[-1]['description'])

    @patch('builtins.input', side_effect=[
        'installment',  # type
        '2026-02-01',   # date
        'Fridge',       # description
        CASH,           # account: Cash
        '300',          # total amount
        '3',            # installments
        '2',            # grace period: 2 months
        DEFAULT,        # start from: 1
        DEFAULT,        # category: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_installment_with_grace(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 3)
        # Cash + 2 month grace: first payment 2026-04-01
        self.assertEqual(str(txns[0]['date_payed']), '2026-04-01')
        self.assertEqual(str(txns[1]['date_payed']), '2026-05-01')
        self.assertEqual(str(txns[2]['date_payed']), '2026-06-01')

    @patch('builtins.input', side_effect=[
        'split',        # type
        '2026-03-01',   # date
        'Supermarket',  # description
        CASH,           # account
        '30',           # split 1 amount
        CAT_HOME_GROC,  # split 1 category
        '15',           # split 2 amount
        CAT_DINING,     # split 2 category
        NO,             # add more: No
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_split(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 2)
        self.assertAlmostEqual(txns[0]['amount'], -30.0)
        self.assertEqual(txns[0]['category'], 'Home Groceries')
        self.assertAlmostEqual(txns[1]['amount'], -15.0)
        self.assertEqual(txns[1]['category'], 'Dining-Snacks')
        origin_ids = {t['origin_id'] for t in txns}
        self.assertEqual(len(origin_ids), 1)

    @patch('builtins.input', side_effect=[
        'split',        # type
        '2026-03-01',   # date
        'Split pending',# description
        CASH,           # account
        '20',           # split 1 amount
        DEFAULT,        # split 1 category: skip
        '10',           # split 2 amount
        DEFAULT,        # split 2 category: skip
        NO,             # add more: No
        *FLAGS_PENDING, # flags
        DEFAULT,        # confirm
    ])
    def test_e2e_split_pending(self, _):
        request = interactive_add_transaction(self.conn)
        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        self.assertEqual(len(txns), 2)
        for t in txns:
            self.assertEqual(t['status'], 'pending')


class TestInteractiveWithBudget(unittest.TestCase):
    """Test interactive flow with budgets present."""

    def setUp(self):
        self.conn = create_test_db()
        # Add a budget active in March
        repository.add_subscription(self.conn, {
            "id": "budget_groceries_mar",
            "name": "Groceries Mar",
            "category": "Home Groceries",
            "monthly_amount": 300.0,
            "payment_account_id": "Cash",
            "start_date": date(2026, 3, 1),
            "end_date": date(2026, 3, 31),
            "is_budget": 1,
            "underspend_behavior": "keep",
            "is_income": 0,
        })

    def tearDown(self):
        self.conn.close()

    @patch('builtins.input', side_effect=[
        DEFAULT,        # type: simple
        '2026-03-05',   # date: within budget period
        'Weekly shop',  # description
        CASH,           # account: Cash -> payment_date = 2026-03-05
        '80',           # amount
        CAT_HOME_GROC,  # category: Home Groceries
        '1',            # budget: budget_groceries_mar (1st in list)
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_simple_with_budget(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['budget'], 'budget_groceries_mar')

        transaction_date = request.pop("_transaction_date")
        controller.process_transaction_request(self.conn, request, transaction_date=transaction_date)

        txns = repository.get_all_transactions(self.conn)
        budget_txns = [t for t in txns if t['budget'] == 'budget_groceries_mar']
        self.assertTrue(len(budget_txns) >= 1)

    @patch('builtins.input', side_effect=[
        DEFAULT,        # type: simple
        '2026-03-05',   # date
        'No budget',    # description
        CASH,           # account
        '40',           # amount
        DEFAULT,        # category: skip
        DEFAULT,        # budget: skip
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_skip_budget(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertIsNone(request['budget'])

    @patch('builtins.input', side_effect=[
        'split',        # type
        '2026-03-05',   # date
        'Split budget', # description
        CASH,           # account
        '30',           # split 1 amount
        CAT_HOME_GROC,  # split 1 category
        '1',            # split 1 budget: budget_groceries_mar
        '15',           # split 2 amount
        CAT_DINING,     # split 2 category
        DEFAULT,        # split 2 budget: skip
        NO,             # add more: No
        *FLAGS_NORMAL,   # flags
        DEFAULT,        # confirm
    ])
    def test_split_with_budget(self, _):
        request = interactive_add_transaction(self.conn)
        self.assertIsNotNone(request)
        self.assertEqual(request['splits'][0]['budget'], 'budget_groceries_mar')
        self.assertIsNone(request['splits'][1]['budget'])


class TestDisplayTransactionPreview(unittest.TestCase):
    """Test the shared preview display function doesn't raise."""

    def test_preview_simple(self):
        account = {'account_id': 'Cash', 'account_type': 'cash'}
        request = {'type': 'simple', 'description': 'Test', 'account': 'Cash',
                   'amount': 50.0, 'category': 'Personal', 'budget': None,
                   'is_income': False, 'is_pending': False, 'is_planning': False}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_income(self):
        account = {'account_id': 'Cash', 'account_type': 'cash'}
        request = {'type': 'simple', 'description': 'Salary', 'account': 'Cash',
                   'amount': 2000.0, 'is_income': True}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_installment(self):
        account = {'account_id': 'Visa', 'account_type': 'credit_card',
                   'cut_off_day': 14, 'payment_day': 25}
        request = {'type': 'installment', 'description': 'Laptop', 'account': 'Visa',
                   'total_amount': 1200.0, 'installments': 12, 'category': None, 'budget': None}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_installment_grace(self):
        account = {'account_id': 'Cash', 'account_type': 'cash'}
        request = {'type': 'installment', 'description': 'Fridge', 'account': 'Cash',
                   'total_amount': 600.0, 'installments': 6, 'grace_period_months': 3}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_installment_partial(self):
        account = {'account_id': 'Cash', 'account_type': 'cash'}
        request = {'type': 'installment', 'description': 'Phone', 'account': 'Cash',
                   'total_amount': 600.0, 'installments': 8,
                   'start_from_installment': 5, 'total_installments': 12}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_split(self):
        account = {'account_id': 'Cash', 'account_type': 'cash'}
        request = {'type': 'split', 'description': 'Shop', 'account': 'Cash',
                   'splits': [{'amount': 30, 'category': 'Food', 'budget': None},
                              {'amount': 15, 'category': 'Snacks', 'budget': 'bx'}]}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_pending(self):
        account = {'account_id': 'Cash', 'account_type': 'cash'}
        request = {'type': 'simple', 'description': 'P', 'account': 'Cash',
                   'amount': 50.0, 'is_pending': True, 'is_planning': False}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_planning(self):
        account = {'account_id': 'Cash', 'account_type': 'cash'}
        request = {'type': 'simple', 'description': 'P', 'account': 'Cash',
                   'amount': 50.0, 'is_pending': False, 'is_planning': True}
        display_transaction_preview(request, account, date(2026, 3, 1))

    def test_preview_no_account(self):
        request = {'type': 'simple', 'description': 'Test', 'account': 'X', 'amount': 50.0}
        display_transaction_preview(request, None, date(2026, 3, 1))


if __name__ == '__main__':
    unittest.main()

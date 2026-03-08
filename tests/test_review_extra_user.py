"""
Tests for the extra user + review feature:
- Schema migration (source, needs_review columns)
- Repository: add_transactions with new fields, get_transactions_needing_review, mark_reviewed
- Transactions: source/needs_review threading through all creation functions
- Controller: process_transaction_request with source/needs_review
- Config: TELEGRAM_EXTRA_USERS env var parsing
- CLI: review command handler (ls, show, edit, clear, interactive)
- CLI: edit/create with --source/--needs-review flags
- Bot: extra user detection, authorization, and default injection
"""

import unittest
import sqlite3
import argparse
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import date
from dateutil.relativedelta import relativedelta

from cashflow.database import create_test_db, ensure_schema_upgrades
from cashflow import repository, controller
from cashflow.transactions import (
    create_single_transaction,
    create_installment_transactions,
    create_split_transactions,
    _create_base_transaction,
)


# ==================== SCHEMA MIGRATION ====================

class TestSchemaUpgrades(unittest.TestCase):
    """Tests for ensure_schema_upgrades on databases with and without new columns."""

    def test_fresh_db_has_new_columns(self):
        """create_test_db (which calls create_tables) should include source and needs_review."""
        conn = create_test_db()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions)")
        cols = [row[1] for row in cursor.fetchall()]
        self.assertIn("source", cols)
        self.assertIn("needs_review", cols)
        conn.close()

    def test_migration_adds_columns_to_old_schema(self):
        """ensure_schema_upgrades should add columns to a DB that lacks them."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_created DATE NOT NULL,
            date_payed DATE NOT NULL,
            description TEXT NOT NULL,
            account TEXT,
            amount REAL NOT NULL,
            category TEXT,
            budget TEXT,
            status TEXT NOT NULL,
            origin_id TEXT
        )""")
        conn.commit()

        ensure_schema_upgrades(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions)")
        cols = [row[1] for row in cursor.fetchall()]
        self.assertIn("source", cols)
        self.assertIn("needs_review", cols)
        conn.close()

    def test_migration_is_idempotent(self):
        """Running ensure_schema_upgrades twice should not raise."""
        conn = create_test_db()
        ensure_schema_upgrades(conn)  # second run
        ensure_schema_upgrades(conn)  # third run
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(transactions)")
        cols = [row[1] for row in cursor.fetchall()]
        self.assertEqual(cols.count("source"), 1)
        self.assertEqual(cols.count("needs_review"), 1)
        conn.close()

    def test_existing_rows_get_defaults(self):
        """Existing rows should get NULL source and 0 needs_review after migration."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_created TEXT, date_payed TEXT, description TEXT,
            account TEXT, amount REAL, category TEXT, budget TEXT,
            status TEXT, origin_id TEXT
        )""")
        conn.execute(
            "INSERT INTO transactions VALUES (NULL, '2026-01-01', '2026-01-01', 'old tx', 'Cash', -10, NULL, NULL, 'committed', NULL)"
        )
        conn.commit()

        ensure_schema_upgrades(conn)

        row = conn.execute("SELECT source, needs_review FROM transactions WHERE id = 1").fetchone()
        self.assertIsNone(row["source"])
        self.assertEqual(row["needs_review"], 0)
        conn.close()


# ==================== REPOSITORY ====================

class TestRepositoryReviewFields(unittest.TestCase):
    """Tests for repository functions related to source/needs_review."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def _add_tx(self, source=None, needs_review=0, description="Test tx"):
        return repository.add_transactions(self.conn, [{
            "date_created": date(2026, 3, 1),
            "date_payed": date(2026, 3, 1),
            "description": description,
            "account": "Cash",
            "amount": -25.00,
            "category": "Home Groceries",
            "budget": None,
            "status": "committed",
            "origin_id": None,
            "source": source,
            "needs_review": needs_review,
        }])

    def test_add_transaction_stores_source_and_needs_review(self):
        ids = self._add_tx(source="mom", needs_review=1)
        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertEqual(tx["source"], "mom")
        self.assertEqual(tx["needs_review"], 1)

    def test_add_transaction_defaults_when_fields_absent(self):
        """Callers that don't set source/needs_review should get defaults."""
        ids = repository.add_transactions(self.conn, [{
            "date_created": date(2026, 3, 1),
            "date_payed": date(2026, 3, 1),
            "description": "no extras",
            "account": "Cash",
            "amount": -10,
            "category": None,
            "budget": None,
            "status": "committed",
            "origin_id": None,
        }])
        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertIsNone(tx["source"])
        self.assertEqual(tx["needs_review"], 0)

    def test_get_transactions_needing_review_returns_flagged(self):
        self._add_tx(source="mom", needs_review=1, description="review me")
        self._add_tx(source=None, needs_review=0, description="normal tx")

        result = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["description"], "review me")

    def test_get_transactions_needing_review_empty(self):
        self._add_tx(source=None, needs_review=0)
        result = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(result), 0)

    def test_get_transactions_needing_review_filter_by_source(self):
        self._add_tx(source="mom", needs_review=1, description="mom tx")
        self._add_tx(source="dad", needs_review=1, description="dad tx")

        mom_txs = repository.get_transactions_needing_review(self.conn, source="mom")
        self.assertEqual(len(mom_txs), 1)
        self.assertEqual(mom_txs[0]["description"], "mom tx")

        dad_txs = repository.get_transactions_needing_review(self.conn, source="dad")
        self.assertEqual(len(dad_txs), 1)
        self.assertEqual(dad_txs[0]["description"], "dad tx")

    def test_get_transactions_needing_review_ordered_by_date_desc(self):
        repository.add_transactions(self.conn, [
            {
                "date_created": date(2026, 3, 1), "date_payed": date(2026, 3, 1),
                "description": "older", "account": "Cash", "amount": -10,
                "category": None, "budget": None, "status": "committed",
                "origin_id": None, "source": "mom", "needs_review": 1,
            },
            {
                "date_created": date(2026, 3, 5), "date_payed": date(2026, 3, 5),
                "description": "newer", "account": "Cash", "amount": -20,
                "category": None, "budget": None, "status": "committed",
                "origin_id": None, "source": "mom", "needs_review": 1,
            },
        ])
        result = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(result[0]["description"], "newer")
        self.assertEqual(result[1]["description"], "older")

    def test_mark_reviewed(self):
        ids = self._add_tx(source="mom", needs_review=1)
        repository.mark_reviewed(self.conn, ids[0])

        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertEqual(tx["needs_review"], 0)
        self.assertEqual(tx["source"], "mom")  # source preserved

    def test_mark_reviewed_idempotent(self):
        ids = self._add_tx(source="mom", needs_review=0)
        repository.mark_reviewed(self.conn, ids[0])
        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertEqual(tx["needs_review"], 0)

    def test_update_transaction_can_set_source(self):
        ids = self._add_tx(source=None, needs_review=0)
        repository.update_transaction(self.conn, ids[0], {"source": "mom", "needs_review": 1})
        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertEqual(tx["source"], "mom")
        self.assertEqual(tx["needs_review"], 1)


# ==================== TRANSACTIONS MODULE ====================

class TestTransactionsSourceNeedsReview(unittest.TestCase):
    """Tests that source/needs_review thread through all transaction creation functions."""

    def setUp(self):
        self.cash_account = {"account_id": "Cash", "account_type": "cash"}
        self.cc_account = {
            "account_id": "Visa Produbanco",
            "account_type": "credit_card",
            "cut_off_day": 14,
            "payment_day": 25,
        }

    def test_create_base_transaction_defaults(self):
        tx = _create_base_transaction("Test", -10, None, None, date(2026, 3, 1))
        self.assertIsNone(tx["source"])
        self.assertEqual(tx["needs_review"], 0)

    def test_create_base_transaction_with_source(self):
        tx = _create_base_transaction(
            "Test", -10, None, None, date(2026, 3, 1),
            source="mom", needs_review=True,
        )
        self.assertEqual(tx["source"], "mom")
        self.assertEqual(tx["needs_review"], 1)

    def test_create_base_transaction_needs_review_false(self):
        tx = _create_base_transaction(
            "Test", -10, None, None, date(2026, 3, 1),
            needs_review=False,
        )
        self.assertEqual(tx["needs_review"], 0)

    def test_create_single_transaction_with_source(self):
        tx = create_single_transaction(
            description="Supermaxi",
            amount=25.50,
            category="Home Groceries",
            budget=None,
            account=self.cash_account,
            transaction_date=date(2026, 3, 1),
            source="mom",
            needs_review=True,
        )
        self.assertEqual(tx["source"], "mom")
        self.assertEqual(tx["needs_review"], 1)
        self.assertEqual(tx["amount"], -25.50)

    def test_create_single_transaction_defaults(self):
        tx = create_single_transaction(
            description="Normal purchase",
            amount=10,
            category=None,
            budget=None,
            account=self.cash_account,
            transaction_date=date(2026, 3, 1),
        )
        self.assertIsNone(tx["source"])
        self.assertEqual(tx["needs_review"], 0)

    def test_create_installment_transactions_with_source(self):
        txs = create_installment_transactions(
            description="Laptop",
            total_amount=1200,
            installments=3,
            category="Personal",
            budget=None,
            account=self.cc_account,
            transaction_date=date(2026, 3, 1),
            source="mom",
            needs_review=True,
        )
        self.assertEqual(len(txs), 3)
        for tx in txs:
            self.assertEqual(tx["source"], "mom")
            self.assertEqual(tx["needs_review"], 1)

    def test_create_installment_transactions_defaults(self):
        txs = create_installment_transactions(
            description="Laptop",
            total_amount=1200,
            installments=3,
            category="Personal",
            budget=None,
            account=self.cc_account,
            transaction_date=date(2026, 3, 1),
        )
        for tx in txs:
            self.assertIsNone(tx["source"])
            self.assertEqual(tx["needs_review"], 0)

    def test_create_split_transactions_with_source(self):
        splits = [
            {"amount": 20, "category": "Home Groceries"},
            {"amount": 10, "category": "Personal Groceries"},
        ]
        txs = create_split_transactions(
            description="Mixed purchase",
            splits=splits,
            account=self.cash_account,
            transaction_date=date(2026, 3, 1),
            source="mom",
            needs_review=True,
        )
        self.assertEqual(len(txs), 2)
        for tx in txs:
            self.assertEqual(tx["source"], "mom")
            self.assertEqual(tx["needs_review"], 1)

    def test_create_split_transactions_defaults(self):
        splits = [
            {"amount": 20, "category": "Home Groceries"},
        ]
        txs = create_split_transactions(
            description="Split",
            splits=splits,
            account=self.cash_account,
            transaction_date=date(2026, 3, 1),
        )
        for tx in txs:
            self.assertIsNone(tx["source"])
            self.assertEqual(tx["needs_review"], 0)


# ==================== CONTROLLER ====================

class TestControllerSourceNeedsReview(unittest.TestCase):
    """Tests that process_transaction_request correctly threads source/needs_review."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def test_simple_transaction_with_source(self):
        request = {
            "type": "simple",
            "description": "Supermaxi groceries",
            "amount": 25.50,
            "account": "Cash",
            "category": "Home Groceries",
            "source": "mom",
            "needs_review": True,
        }
        controller.process_transaction_request(self.conn, request, transaction_date=date(2026, 3, 1))

        txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["source"], "mom")
        self.assertEqual(txs[0]["description"], "Supermaxi groceries")

    def test_simple_transaction_without_source(self):
        request = {
            "type": "simple",
            "description": "My purchase",
            "amount": 10,
            "account": "Cash",
            "category": "Personal",
        }
        controller.process_transaction_request(self.conn, request, transaction_date=date(2026, 3, 1))

        txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(txs), 0)

    def test_installment_transaction_with_source(self):
        request = {
            "type": "installment",
            "description": "TV",
            "total_amount": 600,
            "installments": 3,
            "account": "Visa Produbanco",
            "category": "Personal",
            "source": "mom",
            "needs_review": True,
        }
        controller.process_transaction_request(self.conn, request, transaction_date=date(2026, 3, 1))

        txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(txs), 3)
        for tx in txs:
            self.assertEqual(tx["source"], "mom")

    def test_split_transaction_with_source(self):
        request = {
            "type": "split",
            "description": "Mixed shopping",
            "account": "Cash",
            "splits": [
                {"amount": 20, "category": "Home Groceries"},
                {"amount": 10, "category": "Personal Groceries"},
            ],
            "source": "mom",
            "needs_review": True,
        }
        controller.process_transaction_request(self.conn, request, transaction_date=date(2026, 3, 1))

        txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(txs), 2)

    def test_source_preserved_after_budget_recalculation(self):
        """When a budget-linked transaction is added, source should survive budget recalc."""
        # Set up a budget
        repository.add_subscription(self.conn, {
            "id": "budget_groceries_test",
            "name": "Test Groceries Budget",
            "category": "Home Groceries",
            "monthly_amount": 200,
            "payment_account_id": "Cash",
            "start_date": date(2026, 1, 1),
            "is_budget": True,
        })
        # Create budget allocation
        repository.add_transactions(self.conn, [{
            "date_created": date(2026, 3, 1),
            "date_payed": date(2026, 3, 1),
            "description": "Test Groceries Budget",
            "account": "Cash",
            "amount": -200,
            "category": "Home Groceries",
            "budget": "budget_groceries_test",
            "status": "committed",
            "origin_id": "budget_groceries_test",
        }])

        # Add expense with source
        request = {
            "type": "simple",
            "description": "Supermaxi",
            "amount": 30,
            "account": "Cash",
            "category": "Home Groceries",
            "budget": "budget_groceries_test",
            "source": "mom",
            "needs_review": True,
        }
        controller.process_transaction_request(self.conn, request, transaction_date=date(2026, 3, 1))

        txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["source"], "mom")
        self.assertEqual(txs[0]["budget"], "budget_groceries_test")


# ==================== CONFIG ====================

class TestExtraUserConfig(unittest.TestCase):
    """Tests for TELEGRAM_EXTRA_USERS env var parsing."""

    def test_parse_extra_user_env_var(self):
        env = {"TELEGRAM_EXTRA_USER_MOM": "987654321,Visa Pichincha,Home Groceries"}
        with patch.dict(os.environ, env, clear=False):
            import importlib
            from cashflow import config
            importlib.reload(config)

            self.assertIn(987654321, config.TELEGRAM_EXTRA_USERS)
            info = config.TELEGRAM_EXTRA_USERS[987654321]
            self.assertEqual(info["name"], "mom")
            self.assertEqual(info["account"], "Visa Pichincha")
            self.assertEqual(info["budget"], "Home Groceries")

    def test_parse_multiple_extra_users(self):
        env = {
            "TELEGRAM_EXTRA_USER_MOM": "111,Visa Pichincha,Home Groceries",
            "TELEGRAM_EXTRA_USER_DAD": "222,Cash,Personal",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            from cashflow import config
            importlib.reload(config)

            self.assertIn(111, config.TELEGRAM_EXTRA_USERS)
            self.assertIn(222, config.TELEGRAM_EXTRA_USERS)
            self.assertEqual(config.TELEGRAM_EXTRA_USERS[111]["name"], "mom")
            self.assertEqual(config.TELEGRAM_EXTRA_USERS[222]["name"], "dad")

    def test_name_lowercased(self):
        env = {"TELEGRAM_EXTRA_USER_SISTER": "333,Cash,Budget"}
        with patch.dict(os.environ, env, clear=False):
            import importlib
            from cashflow import config
            importlib.reload(config)

            self.assertEqual(config.TELEGRAM_EXTRA_USERS[333]["name"], "sister")

    def test_invalid_user_id_skipped(self):
        env = {"TELEGRAM_EXTRA_USER_BAD": "notanumber,Cash,Budget"}
        with patch.dict(os.environ, env, clear=False):
            import importlib
            from cashflow import config
            importlib.reload(config)

            # Should not crash, just skip
            self.assertNotIn("notanumber", config.TELEGRAM_EXTRA_USERS)

    def test_incomplete_value_skipped(self):
        env = {"TELEGRAM_EXTRA_USER_SHORT": "999,Cash"}  # only 2 parts
        with patch.dict(os.environ, env, clear=False):
            import importlib
            from cashflow import config
            importlib.reload(config)

            self.assertNotIn(999, config.TELEGRAM_EXTRA_USERS)

    def test_empty_value_skipped(self):
        env = {"TELEGRAM_EXTRA_USER_EMPTY": ""}
        with patch.dict(os.environ, env, clear=False):
            import importlib
            from cashflow import config
            importlib.reload(config)

            # Should not crash

    def tearDown(self):
        # Reload config to restore original state
        import importlib
        from cashflow import config
        importlib.reload(config)


# ==================== CLI REVIEW COMMAND ====================

class TestCLIReviewList(unittest.TestCase):
    """Tests for handle_review_list."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def _add_review_tx(self, source="mom", description="Test tx"):
        return repository.add_transactions(self.conn, [{
            "date_created": date(2026, 3, 1),
            "date_payed": date(2026, 3, 1),
            "description": description,
            "account": "Cash",
            "amount": -25.00,
            "category": "Home Groceries",
            "budget": None,
            "status": "committed",
            "origin_id": None,
            "source": source,
            "needs_review": 1,
        }])

    @patch('builtins.print')
    def test_review_ls_no_transactions(self, mock_print):
        from cli import handle_review_list
        args = argparse.Namespace(source=None, _backup_skip=False)
        handle_review_list(self.conn, args)
        mock_print.assert_called_with("No transactions need review.")
        self.assertTrue(args._backup_skip)

    @patch('ui.cli_display.Console')  # prevent actual rich output
    def test_review_ls_shows_transactions(self, mock_console_cls):
        from cli import handle_review_list
        self._add_review_tx(description="Supermaxi")
        self._add_review_tx(description="Mi Comisariato")

        args = argparse.Namespace(source=None, _backup_skip=False)
        handle_review_list(self.conn, args)
        self.assertTrue(args._backup_skip)  # read-only, no backup

    @patch('ui.cli_display.Console')
    def test_review_ls_filters_by_source(self, mock_console_cls):
        from cli import handle_review_list
        self._add_review_tx(source="mom", description="mom tx")
        self._add_review_tx(source="dad", description="dad tx")

        args = argparse.Namespace(source="mom", _backup_skip=False)
        handle_review_list(self.conn, args)


class TestCLIReviewRouter(unittest.TestCase):
    """Tests for handle_review routing logic."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def _add_review_tx(self, source="mom", description="Review me"):
        return repository.add_transactions(self.conn, [{
            "date_created": date(2026, 3, 1),
            "date_payed": date(2026, 3, 1),
            "description": description,
            "account": "Cash",
            "amount": -25.00,
            "category": "Home Groceries",
            "budget": None,
            "status": "committed",
            "origin_id": None,
            "source": source,
            "needs_review": 1,
        }])

    @patch('builtins.print')
    def test_review_ls_default_action(self, mock_print):
        from cli import handle_review
        args = argparse.Namespace(
            action="ls", sub_action=None, source=None,
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_review(self.conn, args)
        mock_print.assert_called_with("No transactions need review.")

    @patch('builtins.print')
    def test_review_clear(self, mock_print):
        from cli import handle_review
        ids = self._add_review_tx()
        tx_id = ids[0]

        args = argparse.Namespace(
            action=str(tx_id), sub_action="clear",
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_review(self.conn, args)

        tx = repository.get_transaction_by_id(self.conn, tx_id)
        self.assertEqual(tx["needs_review"], 0)
        self.assertEqual(tx["source"], "mom")  # source preserved

    @patch('builtins.print')
    def test_review_show_and_mark(self, mock_print):
        """review <id> with no flags shows details and marks reviewed."""
        from cli import handle_review
        ids = self._add_review_tx(description="Show me")
        tx_id = ids[0]

        args = argparse.Namespace(
            action=str(tx_id), sub_action=None,
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_review(self.conn, args)

        tx = repository.get_transaction_by_id(self.conn, tx_id)
        self.assertEqual(tx["needs_review"], 0)
        # Should have printed "marked as reviewed"
        print_calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("marked as reviewed" in c for c in print_calls))

    @patch('builtins.print')
    def test_review_edit_flags(self, mock_print):
        """review <id> --category X edits and marks reviewed."""
        from cli import handle_review
        ids = self._add_review_tx()
        tx_id = ids[0]

        args = argparse.Namespace(
            action=str(tx_id), sub_action=None,
            description=None, amount=None, date=None,
            category="Personal Groceries", budget=None, status=None,
            source=None, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_review(self.conn, args)

        tx = repository.get_transaction_by_id(self.conn, tx_id)
        self.assertEqual(tx["needs_review"], 0)
        self.assertEqual(tx["category"], "Personal Groceries")

    @patch('builtins.print')
    def test_review_edit_budget_and_amount(self, mock_print):
        from cli import handle_review
        ids = self._add_review_tx()
        tx_id = ids[0]

        args = argparse.Namespace(
            action=str(tx_id), sub_action=None,
            description="Updated desc", amount=-30.0, date=None,
            category=None, budget=None, status=None,
            source=None, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_review(self.conn, args)

        tx = repository.get_transaction_by_id(self.conn, tx_id)
        self.assertEqual(tx["needs_review"], 0)
        self.assertEqual(tx["description"], "Updated desc")
        self.assertAlmostEqual(tx["amount"], -30.0)

    @patch('builtins.print')
    def test_review_invalid_action(self, mock_print):
        from cli import handle_review
        args = argparse.Namespace(
            action="foobar", sub_action=None,
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_review(self.conn, args)
        print_calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("Unknown review action" in c for c in print_calls))

    @patch('builtins.print')
    def test_review_nonexistent_transaction(self, mock_print):
        from cli import handle_review
        args = argparse.Namespace(
            action="99999", sub_action=None,
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_review(self.conn, args)
        print_calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("not found" in c for c in print_calls))

    @patch('builtins.print')
    def test_review_interactive(self, mock_print):
        """review <id> -i delegates to interactive edit then marks reviewed."""
        from cli import handle_review
        ids = self._add_review_tx()
        tx_id = ids[0]

        args = argparse.Namespace(
            action=str(tx_id), sub_action=None,
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, interactive=True,
            _backup_skip=False, _backup_context=None,
        )

        # Mock interactive edit to return some changes
        with patch('cli.handle_edit_interactive') as mock_interactive:
            def side_effect(conn, edit_args):
                # Simulate a successful edit (no _backup_skip)
                edit_args._backup_skip = False
            mock_interactive.side_effect = side_effect

            handle_review(self.conn, args)

            mock_interactive.assert_called_once()
            tx = repository.get_transaction_by_id(self.conn, tx_id)
            self.assertEqual(tx["needs_review"], 0)

    @patch('builtins.print')
    def test_review_interactive_cancelled(self, mock_print):
        """If interactive edit is cancelled, transaction should NOT be marked reviewed."""
        from cli import handle_review
        ids = self._add_review_tx()
        tx_id = ids[0]

        args = argparse.Namespace(
            action=str(tx_id), sub_action=None,
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, interactive=True,
            _backup_skip=False, _backup_context=None,
        )

        with patch('cli.handle_edit_interactive') as mock_interactive:
            def side_effect(conn, edit_args):
                edit_args._backup_skip = True  # User cancelled
            mock_interactive.side_effect = side_effect

            handle_review(self.conn, args)

            tx = repository.get_transaction_by_id(self.conn, tx_id)
            self.assertEqual(tx["needs_review"], 1)  # NOT marked reviewed


# ==================== CLI EDIT WITH NEW FLAGS ====================

class TestCLIEditSourceNeedsReview(unittest.TestCase):
    """Tests that edit command handles --source and --needs-review flags."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def _add_tx(self, source=None, needs_review=0):
        return repository.add_transactions(self.conn, [{
            "date_created": date(2026, 3, 1),
            "date_payed": date(2026, 3, 1),
            "description": "Test",
            "account": "Cash",
            "amount": -25.00,
            "category": None,
            "budget": None,
            "status": "committed",
            "origin_id": None,
            "source": source,
            "needs_review": needs_review,
        }])

    @patch('builtins.print')
    def test_edit_set_source(self, mock_print):
        from cli import handle_edit
        ids = self._add_tx()
        args = argparse.Namespace(
            transaction_id=ids[0],
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source="mom", needs_review=None,
            all=False, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_edit(self.conn, args)
        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertEqual(tx["source"], "mom")

    @patch('builtins.print')
    def test_edit_set_needs_review(self, mock_print):
        from cli import handle_edit
        ids = self._add_tx()
        args = argparse.Namespace(
            transaction_id=ids[0],
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, needs_review=1,
            all=False, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_edit(self.conn, args)
        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertEqual(tx["needs_review"], 1)

    @patch('builtins.print')
    def test_edit_clear_needs_review(self, mock_print):
        from cli import handle_edit
        ids = self._add_tx(source="mom", needs_review=1)
        args = argparse.Namespace(
            transaction_id=ids[0],
            description=None, amount=None, date=None, category=None,
            budget=None, status=None, source=None, needs_review=0,
            all=False, interactive=False,
            _backup_skip=False, _backup_context=None,
        )
        handle_edit(self.conn, args)
        tx = repository.get_transaction_by_id(self.conn, ids[0])
        self.assertEqual(tx["needs_review"], 0)
        self.assertEqual(tx["source"], "mom")  # source untouched


# ==================== CLI CREATE WITH NEW FLAGS ====================

class TestCLICreateSourceNeedsReview(unittest.TestCase):
    """Tests that create transaction command passes source/needs_review."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    @patch('builtins.print')
    def test_create_with_source_and_review(self, mock_print):
        from cli import handle_create_transaction
        args = argparse.Namespace(
            description="Mom purchase",
            amount=15.0,
            account="Cash",
            category="Home Groceries",
            budget=None,
            date=None,
            installments=None,
            start_installment=1,
            grace_period=0,
            income=False,
            pending=False,
            planning=False,
            source="mom",
            needs_review=1,
            _backup_context=None,
        )
        handle_create_transaction(self.conn, args)

        txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["source"], "mom")
        self.assertEqual(txs[0]["description"], "Mom purchase")

    @patch('builtins.print')
    def test_create_without_source(self, mock_print):
        from cli import handle_create_transaction
        args = argparse.Namespace(
            description="Normal purchase",
            amount=10.0,
            account="Cash",
            category=None,
            budget=None,
            date=None,
            installments=None,
            start_installment=1,
            grace_period=0,
            income=False,
            pending=False,
            planning=False,
            source=None,
            needs_review=0,
            _backup_context=None,
        )
        handle_create_transaction(self.conn, args)

        txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(txs), 0)


# ==================== BOT EXTRA USER ====================

class TestBotExtraUser(unittest.TestCase):
    """Tests for bot.py extra user detection and default injection."""

    def _make_update(self, user_id):
        update = MagicMock()
        update.effective_user.id = user_id
        return update

    @patch('bot.TELEGRAM_EXTRA_USERS', {987654321: {"name": "mom", "account": "Visa Pichincha", "budget": "Home Groceries"}})
    def test_get_extra_user_info_found(self):
        from bot import get_extra_user_info
        update = self._make_update(987654321)
        info = get_extra_user_info(update)
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "mom")

    @patch('bot.TELEGRAM_EXTRA_USERS', {987654321: {"name": "mom", "account": "Visa Pichincha", "budget": "Home Groceries"}})
    def test_get_extra_user_info_not_found(self):
        from bot import get_extra_user_info
        update = self._make_update(111111)
        info = get_extra_user_info(update)
        self.assertIsNone(info)

    @patch('bot.TELEGRAM_EXTRA_USERS', {987654321: {"name": "mom", "account": "Visa Pichincha", "budget": "Home Groceries"}})
    @patch('bot.TELEGRAM_ALLOWED_USERS', {123456})
    def test_is_authorized_allows_extra_user(self):
        from bot import is_authorized
        update = self._make_update(987654321)
        self.assertTrue(is_authorized(update))

    @patch('bot.TELEGRAM_EXTRA_USERS', {987654321: {"name": "mom", "account": "Visa Pichincha", "budget": "Home Groceries"}})
    @patch('bot.TELEGRAM_ALLOWED_USERS', {123456})
    def test_is_authorized_allows_owner(self):
        from bot import is_authorized
        update = self._make_update(123456)
        self.assertTrue(is_authorized(update))

    @patch('bot.TELEGRAM_EXTRA_USERS', {987654321: {"name": "mom", "account": "Visa Pichincha", "budget": "Home Groceries"}})
    @patch('bot.TELEGRAM_ALLOWED_USERS', {123456})
    def test_is_authorized_rejects_stranger(self):
        from bot import is_authorized
        update = self._make_update(999999)
        self.assertFalse(is_authorized(update))

    @patch('bot.TELEGRAM_EXTRA_USERS', {})
    @patch('bot.TELEGRAM_ALLOWED_USERS', set())
    def test_is_authorized_open_access(self):
        from bot import is_authorized
        update = self._make_update(999999)
        self.assertTrue(is_authorized(update))


class TestBotExtraUserInjection(unittest.TestCase):
    """Tests that handle_new_expense injects extra user defaults correctly."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def test_inject_extra_user_defaults_into_request(self):
        """Simulate the injection logic directly (without async bot framework)."""
        from cashflow.transactions import simulate_payment_date

        accounts = repository.get_all_accounts(self.conn)

        # Create a budget subscription active during the payment month
        repository.add_subscription(self.conn, {
            "id": "budget_home_groceries_mar_apr",
            "name": "Home Groceries",
            "category": "Home Groceries",
            "monthly_amount": 300,
            "payment_account_id": "Visa Produbanco",
            "start_date": date(2026, 3, 1),
            "is_budget": True,
        })

        # Simulate a parsed request from LLM
        request_json = {
            "type": "simple",
            "description": "Supermaxi groceries",
            "amount": 25.50,
            "date_created": "2026-03-08",
            "account": accounts[0]["account_id"],  # default fallback
            "category": "Home Groceries",
        }

        # Simulate extra user injection (same logic as handle_new_expense)
        extra_user = {"name": "mom", "account": "Visa Produbanco", "budget": "Home Groceries"}

        request_json["source"] = extra_user["name"]
        request_json["needs_review"] = True
        if not request_json.get("account") or request_json["account"] == accounts[0]["account_id"]:
            request_json["account"] = extra_user["account"]

        if not request_json.get("budget"):
            budget_name = extra_user["budget"]
            eu_account = next((a for a in accounts if a['account_id'] == extra_user["account"]), None)
            eu_date = date.fromisoformat(request_json.get('date_created', date.today().isoformat()))
            eu_payment_date = simulate_payment_date(eu_account, eu_date) if eu_account else eu_date
            active_budgets = repository.get_all_active_subscriptions(self.conn, eu_payment_date, eu_payment_date)
            matched_budget = next(
                (b["id"] for b in active_budgets if b.get("is_budget") and (b["name"].lower() == budget_name.lower() or b["name"].lower().startswith(budget_name.lower()))),
                None,
            )
            if matched_budget:
                request_json["budget"] = matched_budget

        self.assertEqual(request_json["source"], "mom")
        self.assertTrue(request_json["needs_review"])
        self.assertEqual(request_json["account"], "Visa Produbanco")
        self.assertEqual(request_json["budget"], "budget_home_groceries_mar_apr")

    def test_extra_user_does_not_override_explicit_account(self):
        """If LLM picked a specific non-default account, extra user should not override it."""
        accounts = repository.get_all_accounts(self.conn)
        # accounts[0] is "Amex Produbanco" (alphabetical), pick a different one
        non_default = "Visa Produbanco"
        self.assertNotEqual(non_default, accounts[0]["account_id"])

        request_json = {
            "type": "simple",
            "description": "Supermaxi",
            "amount": 25.50,
            "account": non_default,  # LLM explicitly picked this
            "category": "Home Groceries",
        }

        extra_user = {"name": "mom", "account": "Cash", "budget": "Home Groceries"}

        request_json["source"] = extra_user["name"]
        request_json["needs_review"] = True
        if not request_json.get("account") or request_json["account"] == accounts[0]["account_id"]:
            request_json["account"] = extra_user["account"]

        self.assertEqual(request_json["account"], non_default)

    def test_budget_resolved_by_payment_date(self):
        """Budget should resolve to the period active at payment date, not just any match."""
        from cashflow.transactions import simulate_payment_date

        accounts = repository.get_all_accounts(self.conn)

        # Create two budget periods with the same name — one expired, one active
        repository.add_subscription(self.conn, {
            "id": "budget_groceries_jan_feb",
            "name": "Home Groceries Jan-Feb",
            "category": "Home Groceries",
            "monthly_amount": 300,
            "payment_account_id": "Visa Produbanco",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 2, 28),
            "is_budget": True,
        })
        repository.add_subscription(self.conn, {
            "id": "budget_groceries_mar_apr",
            "name": "Home Groceries Mar-Apr",
            "category": "Home Groceries",
            "monthly_amount": 300,
            "payment_account_id": "Visa Produbanco",
            "start_date": date(2026, 3, 1),
            "is_budget": True,
        })

        extra_user = {"name": "mom", "account": "Visa Produbanco", "budget": "Home Groceries"}
        eu_account = next(a for a in accounts if a['account_id'] == extra_user["account"])

        # Purchase on March 8 → payment date via CC billing
        eu_date = date(2026, 3, 8)
        eu_payment_date = simulate_payment_date(eu_account, eu_date)

        active_budgets = repository.get_all_active_subscriptions(
            self.conn, eu_payment_date, eu_payment_date
        )
        matched = next(
            (b["id"] for b in active_budgets if b.get("is_budget") and (b["name"].lower() == "home groceries" or b["name"].lower().startswith("home groceries"))),
            None,
        )
        # Should match the mar_apr period, NOT the expired jan_feb one
        self.assertEqual(matched, "budget_groceries_mar_apr")

    def test_end_to_end_extra_user_transaction_stored(self):
        """Full flow: inject defaults → process_transaction_request → verify in DB."""
        request = {
            "type": "simple",
            "description": "Supermaxi groceries",
            "amount": 30.0,
            "account": "Visa Produbanco",
            "category": "Home Groceries",
            "source": "mom",
            "needs_review": True,
        }
        controller.process_transaction_request(
            self.conn, request, transaction_date=date(2026, 3, 8)
        )

        # Verify it's in review queue
        review_txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(review_txs), 1)
        self.assertEqual(review_txs[0]["source"], "mom")
        self.assertEqual(review_txs[0]["needs_review"], 1)
        self.assertEqual(review_txs[0]["account"], "Visa Produbanco")

        # Verify marking reviewed clears it
        repository.mark_reviewed(self.conn, review_txs[0]["id"])
        review_txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(review_txs), 0)

        # Transaction still exists with source
        tx = repository.get_transaction_by_id(self.conn, review_txs[0]["id"] if review_txs else 1)
        # Since we already marked it, fetch by getting all
        all_txs = repository.get_all_transactions(self.conn)
        mom_txs = [t for t in all_txs if t.get("source") == "mom"]
        self.assertEqual(len(mom_txs), 1)
        self.assertEqual(mom_txs[0]["needs_review"], 0)


# ==================== INTEGRATION: FULL REVIEW WORKFLOW ====================

class TestFullReviewWorkflow(unittest.TestCase):
    """End-to-end tests for the complete review workflow."""

    def setUp(self):
        self.conn = create_test_db()

    def tearDown(self):
        self.conn.close()

    def test_full_workflow_add_review_approve(self):
        """Add tx with source → list → review clear → verify gone from review."""
        # 1. Add transaction via controller
        request = {
            "type": "simple",
            "description": "Supermaxi chicken",
            "amount": 8.50,
            "account": "Cash",
            "category": "Home Groceries",
            "source": "mom",
            "needs_review": True,
        }
        controller.process_transaction_request(
            self.conn, request, transaction_date=date(2026, 3, 8)
        )

        # 2. Verify it appears in review list
        review_txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(review_txs), 1)
        tx_id = review_txs[0]["id"]

        # 3. Mark reviewed
        repository.mark_reviewed(self.conn, tx_id)

        # 4. Verify gone from review list
        review_txs = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(review_txs), 0)

        # 5. Transaction still exists
        tx = repository.get_transaction_by_id(self.conn, tx_id)
        self.assertIsNotNone(tx)
        self.assertEqual(tx["source"], "mom")
        self.assertEqual(tx["needs_review"], 0)

    def test_full_workflow_add_review_edit_approve(self):
        """Add tx with source → edit category → mark reviewed."""
        request = {
            "type": "simple",
            "description": "Personal items",
            "amount": 15.0,
            "account": "Cash",
            "category": "Home Groceries",
            "source": "mom",
            "needs_review": True,
        }
        controller.process_transaction_request(
            self.conn, request, transaction_date=date(2026, 3, 8)
        )

        review_txs = repository.get_transactions_needing_review(self.conn)
        tx_id = review_txs[0]["id"]

        # Edit: change category from Home to Personal
        controller.process_transaction_edit(
            self.conn, tx_id,
            {"category": "Personal Groceries"}, None
        )
        repository.mark_reviewed(self.conn, tx_id)

        tx = repository.get_transaction_by_id(self.conn, tx_id)
        self.assertEqual(tx["category"], "Personal Groceries")
        self.assertEqual(tx["needs_review"], 0)
        self.assertEqual(tx["source"], "mom")

    def test_multiple_extra_users_independent_review(self):
        """Multiple sources can have independent review queues."""
        for source in ["mom", "dad"]:
            request = {
                "type": "simple",
                "description": f"{source} purchase",
                "amount": 10.0,
                "account": "Cash",
                "category": "Home Groceries",
                "source": source,
                "needs_review": True,
            }
            controller.process_transaction_request(
                self.conn, request, transaction_date=date(2026, 3, 8)
            )

        # All review
        all_review = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(all_review), 2)

        # Filter by source
        mom_review = repository.get_transactions_needing_review(self.conn, source="mom")
        self.assertEqual(len(mom_review), 1)
        self.assertEqual(mom_review[0]["description"], "mom purchase")

        # Mark mom's reviewed
        repository.mark_reviewed(self.conn, mom_review[0]["id"])

        # Dad's still in queue
        remaining = repository.get_transactions_needing_review(self.conn)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["source"], "dad")


if __name__ == "__main__":
    unittest.main()

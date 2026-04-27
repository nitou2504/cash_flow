"""Tests for consumo_repository CRUD operations."""
import unittest
from datetime import datetime

from cashflow.consumo_database import create_test_consumos_db
from cashflow.consumo_repository import (
    find_unmatched,
    get_ingested_msg_ids,
    get_latest_purchased_at,
    list_unparsed,
    record_unparsed,
    set_invoice_match,
    upsert_consumo,
)
from gmail_sync.parsers import EmailTxn


def _make_txn(msg_id="m1", amount=10.0, merchant="TEST", **overrides):
    defaults = dict(
        msg_id=msg_id, bank="Pichincha", account="Visa Pichincha",
        purchased_at=datetime(2026, 4, 22, 14, 30),
        amount=amount, merchant=merchant, card_last="1234",
        subject="Consumo", beneficiary=None, destination_account=None,
        concepto=None,
    )
    defaults.update(overrides)
    return EmailTxn(**defaults)


class TestUpsert(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_consumos_db()

    def test_insert(self):
        rid = upsert_consumo(self.conn, _make_txn(), "Consumos/Pichincha")
        assert rid is not None
        row = self.conn.execute("SELECT * FROM consumos WHERE msg_id = 'm1'").fetchone()
        assert row["amount"] == 10.0
        assert row["label"] == "Consumos/Pichincha"

    def test_idempotent(self):
        upsert_consumo(self.conn, _make_txn(), "Consumos/Pichincha")
        upsert_consumo(self.conn, _make_txn(amount=15.0), "Consumos/Pichincha")
        rows = self.conn.execute("SELECT * FROM consumos").fetchall()
        assert len(rows) == 1
        assert rows[0]["amount"] == 15.0

    def test_preserves_match_on_rerun(self):
        upsert_consumo(self.conn, _make_txn(), "Consumos/Pichincha")
        row = self.conn.execute("SELECT id FROM consumos WHERE msg_id = 'm1'").fetchone()
        set_invoice_match(self.conn, row["id"], "001-002-000000001")

        upsert_consumo(self.conn, _make_txn(amount=10.0), "Consumos/Pichincha")
        row = self.conn.execute("SELECT matched_invoice_number FROM consumos WHERE msg_id = 'm1'").fetchone()
        assert row["matched_invoice_number"] == "001-002-000000001"


class TestIngestedMsgIds(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_consumos_db()

    def test_includes_consumos_and_unparsed(self):
        upsert_consumo(self.conn, _make_txn("m1"), "Consumos/Pichincha")
        record_unparsed(self.conn, "m2", "Consumos/Diners", "fail", None, "parse_failed")
        ids = get_ingested_msg_ids(self.conn)
        assert ids == {"m1", "m2"}


class TestUnmatched(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_consumos_db()

    def test_find_unmatched(self):
        upsert_consumo(self.conn, _make_txn("m1"), "Consumos/Pichincha")
        upsert_consumo(self.conn, _make_txn("m2", amount=20.0), "Consumos/Diners")
        row = self.conn.execute("SELECT id FROM consumos WHERE msg_id = 'm1'").fetchone()
        set_invoice_match(self.conn, row["id"], "001-002-000000001")

        unmatched = find_unmatched(self.conn)
        assert len(unmatched) == 1
        assert unmatched[0]["msg_id"] == "m2"


class TestLatestPurchasedAt(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_consumos_db()

    def test_returns_latest(self):
        upsert_consumo(self.conn, _make_txn("m1", purchased_at=datetime(2026, 4, 20)), "L")
        upsert_consumo(self.conn, _make_txn("m2", purchased_at=datetime(2026, 4, 25)), "L")
        latest = get_latest_purchased_at(self.conn)
        assert latest is not None
        assert latest.day == 25

    def test_empty_db(self):
        assert get_latest_purchased_at(self.conn) is None


class TestUnparsed(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_consumos_db()

    def test_record_and_list(self):
        record_unparsed(self.conn, "m1", "Consumos/Cash", "subj", None, "parse_failed")
        rows = list_unparsed(self.conn)
        assert len(rows) == 1
        assert rows[0]["reason"] == "parse_failed"

    def test_filter_by_reason(self):
        record_unparsed(self.conn, "m1", "L", "s", None, "parse_failed")
        record_unparsed(self.conn, "m2", "L", "s", None, "empty_body")
        assert len(list_unparsed(self.conn, reason="parse_failed")) == 1


if __name__ == "__main__":
    unittest.main()

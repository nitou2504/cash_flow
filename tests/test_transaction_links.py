"""Tests for transaction ↔ consumo linking via consumos table."""
import unittest

from cashflow.database import create_test_db
from cashflow.repository import (
    add_transactions,
    find_linked_transaction,
    find_similar_transactions,
    get_transaction_link,
    get_unlinked_transactions,
    link_transaction,
)


def _insert_txn(conn, desc="Test", amount=-10.0, account="Cash", category="Others"):
    ids = add_transactions(conn, [{
        "date_created": "2026-04-22",
        "date_payed": "2026-04-22",
        "description": desc,
        "account": account,
        "amount": amount,
        "category": category,
        "budget": None,
        "status": "committed",
        "origin_id": None,
    }])
    return ids[0]


def _insert_consumo(conn, msg_id, merchant="STORE", amount=10.0):
    conn.execute("""
        INSERT INTO consumos (msg_id, bank, account, purchased_at, amount,
                              merchant, card_last, subject, label)
        VALUES (?, 'Pichincha', 'Visa Pichincha', '2026-04-22T14:00:00', ?,
                ?, '1234', 'subj', 'Consumos/Pichincha')
    """, (msg_id, amount, merchant))
    conn.commit()


class TestLinkTransaction(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()

    def test_link_consumo(self):
        tid = _insert_txn(self.conn)
        _insert_consumo(self.conn, "msg123")
        link_transaction(self.conn, tid, consumo_msg_id="msg123", source="auto_match")
        link = get_transaction_link(self.conn, tid)
        assert link is not None
        assert link["msg_id"] == "msg123"
        assert link["link_source"] == "auto_match"

    def test_link_consumo_and_invoice(self):
        tid = _insert_txn(self.conn)
        _insert_consumo(self.conn, "msg1")
        link_transaction(self.conn, tid, consumo_msg_id="msg1", invoice_number="001-002-003")
        link = get_transaction_link(self.conn, tid)
        assert link["msg_id"] == "msg1"
        assert link["matched_invoice_number"] == "001-002-003"

    def test_upsert_adds_invoice(self):
        tid = _insert_txn(self.conn)
        _insert_consumo(self.conn, "msg1")
        link_transaction(self.conn, tid, consumo_msg_id="msg1")
        link_transaction(self.conn, tid, consumo_msg_id="msg1", invoice_number="001-002-003")
        link = get_transaction_link(self.conn, tid)
        assert link["msg_id"] == "msg1"
        assert link["matched_invoice_number"] == "001-002-003"

    def test_find_linked_by_consumo(self):
        tid = _insert_txn(self.conn, desc="Coral groceries")
        _insert_consumo(self.conn, "msg_abc")
        link_transaction(self.conn, tid, consumo_msg_id="msg_abc")
        found = find_linked_transaction(self.conn, "msg_abc")
        assert found is not None
        assert found["id"] == tid
        assert found["description"] == "Coral groceries"

    def test_find_linked_returns_none(self):
        assert find_linked_transaction(self.conn, "nonexistent") is None

    def test_no_link_returns_none(self):
        tid = _insert_txn(self.conn)
        assert get_transaction_link(self.conn, tid) is None


class TestUnlinkedTransactions(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()

    def test_all_unlinked(self):
        _insert_txn(self.conn, desc="A")
        _insert_txn(self.conn, desc="B")
        unlinked = get_unlinked_transactions(self.conn)
        assert len(unlinked) == 2

    def test_linked_excluded(self):
        t1 = _insert_txn(self.conn, desc="A")
        t2 = _insert_txn(self.conn, desc="B")
        _insert_consumo(self.conn, "msg1")
        link_transaction(self.conn, t1, consumo_msg_id="msg1")
        unlinked = get_unlinked_transactions(self.conn)
        assert len(unlinked) == 1
        assert unlinked[0]["id"] == t2

    def test_filter_by_account(self):
        _insert_txn(self.conn, desc="A", account="Cash")
        _insert_txn(self.conn, desc="B", account="Visa Produbanco")
        unlinked = get_unlinked_transactions(self.conn, accounts=["Cash"])
        assert len(unlinked) == 1
        assert unlinked[0]["account"] == "Cash"


class TestFindSimilar(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_db()

    def test_keyword_match(self):
        _insert_txn(self.conn, desc="Coral - arroz, leche", category="Home Food & Supplies")
        _insert_txn(self.conn, desc="Coral - kefir, quinua", category="Personal Diet")
        _insert_txn(self.conn, desc="Titan - pollo", category="Home Food & Supplies")
        results = find_similar_transactions(self.conn, ["Coral"])
        assert len(results) == 2
        assert all("Coral" in r["description"] for r in results)

    def test_multiple_keywords(self):
        _insert_txn(self.conn, desc="Coral Carapungo - arroz", category="Home Food & Supplies")
        _insert_txn(self.conn, desc="Coral Norte - leche", category="Home Food & Supplies")
        results = find_similar_transactions(self.conn, ["Coral", "Carapungo"])
        assert len(results) == 1

    def test_empty_keywords(self):
        assert find_similar_transactions(self.conn, []) == []

    def test_limit(self):
        for i in range(5):
            _insert_txn(self.conn, desc=f"Coral item {i}", category="Home Food & Supplies")
        results = find_similar_transactions(self.conn, ["Coral"], limit=3)
        assert len(results) == 3


if __name__ == "__main__":
    unittest.main()

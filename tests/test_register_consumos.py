"""Tests for gmail_sync.register_consumos — deterministic rules and registration flow."""
import unittest
from datetime import datetime
from unittest.mock import patch

from cashflow.consumo_database import create_test_consumos_db
from cashflow.consumo_repository import upsert_consumo, find_unregistered, mark_registered
from cashflow.database import create_test_db
from cashflow.repository import (
    add_transactions,
    find_matching_forecast,
    get_transaction_link,
    get_transactions_needing_review,
    find_similar_transactions,
    link_transaction,
)
from gmail_sync.parsers import EmailTxn
from gmail_sync.register_consumos import (
    _extract_keywords,
    _match_rule,
    _match_transfer_rule,
    enrich_with_invoices,
    prepare_one,
    register_consumos,
    load_rules,
)

TEST_RULES = {
    "llm_model": "llama3.2:3b",
    "merchant_rules": {
        "UBER": {"category": "Family Support", "desc": "Uber for mom"},
        "GOOGLE": {"category": "Personal"},
        "KFC": {"category": "Dining-Snacks"},
    },
    "transfer_rules": {
        "6634": {"category": "Home Food", "desc_template": "Transfer to father (6634) - {concepto}"},
        "2210": {"category": "Personal", "desc_template": "Transfer to Ana (2210) - {concepto}"},
    },
}


class TestExtractKeywords(unittest.TestCase):
    def test_coral(self):
        assert _extract_keywords("CORAL CARAPUNGO") == ["CORAL", "CARAPUNGO"]

    def test_uber(self):
        kw = _extract_keywords("DLOCAL*UBER RIDES\\Mr")
        assert "UBER" in kw

    def test_google(self):
        kw = _extract_keywords("GOOGLE *Symfonium M")
        assert "GOOGLE" in kw

    def test_empty(self):
        assert _extract_keywords("") == []


class TestMerchantRules(unittest.TestCase):
    def test_uber(self):
        r = _match_rule("DLOCAL*UBER RIDES\\Mr", TEST_RULES["merchant_rules"])
        assert r is not None
        assert r["category"] == "Family Support"

    def test_google(self):
        r = _match_rule("GOOGLE *Symfonium M", TEST_RULES["merchant_rules"])
        assert r is not None
        assert r["category"] == "Personal"

    def test_kfc(self):
        r = _match_rule("KFC K148 CORAL", TEST_RULES["merchant_rules"])
        assert r is not None
        assert r["category"] == "Dining-Snacks"

    def test_unknown(self):
        assert _match_rule("SUPERMAXI EL JARDIN", TEST_RULES["merchant_rules"]) is None


class TestTransferRules(unittest.TestCase):
    def test_father(self):
        consumo = {"account": "Cash", "destination_account": "6634",
                    "concepto": "Mercado", "merchant": "Mercado"}
        r = _match_transfer_rule(consumo, TEST_RULES["transfer_rules"])
        assert r is not None
        assert r["category"] == "Home Food"
        assert "6634" in r["desc"]
        assert "Mercado" in r["desc"]

    def test_danna(self):
        consumo = {"account": "Cash", "destination_account": "2210",
                    "concepto": "Velas", "merchant": "Velas"}
        r = _match_transfer_rule(consumo, TEST_RULES["transfer_rules"])
        assert r is not None
        assert r["category"] == "Personal"

    def test_cc_not_transfer(self):
        consumo = {"account": "Visa Pichincha", "destination_account": "6634"}
        assert _match_transfer_rule(consumo, TEST_RULES["transfer_rules"]) is None

    def test_unknown_dest(self):
        consumo = {"account": "Cash", "destination_account": "1234",
                    "concepto": "test", "merchant": "test"}
        assert _match_transfer_rule(consumo, TEST_RULES["transfer_rules"]) is None


class TestPrepareOne(unittest.TestCase):
    def setUp(self):
        self.cf_conn = create_test_db()
        # Add some similar transactions for fuzzy matching
        add_transactions(self.cf_conn, [{
            "date_created": "2026-04-01", "date_payed": "2026-04-01",
            "description": "Coral Carapungo - arroz, leche", "account": "Cash",
            "amount": -30.0, "category": "Home Food", "budget": None,
            "status": "committed", "origin_id": None,
        }])

    def test_uber_rule(self):
        consumo = {"merchant": "DLOCAL*UBER RIDES\\Mr", "amount": 1.50,
                    "account": "Diners", "purchased_at": "2026-04-20"}
        result = prepare_one(consumo, self.cf_conn, None, use_llm=False, rules=TEST_RULES)
        assert result["method"] == "merchant_rule"
        assert result["category"] == "Family Support"

    def test_transfer_rule(self):
        consumo = {"merchant": "Mercado", "amount": 20.0, "account": "Cash",
                    "destination_account": "6634", "concepto": "Mercado",
                    "purchased_at": "2026-04-20"}
        result = prepare_one(consumo, self.cf_conn, None, use_llm=False, rules=TEST_RULES)
        assert result["method"] == "transfer_rule"
        assert "6634" in result["description"]

    def test_fuzzy_match(self):
        consumo = {"merchant": "CORAL CARAPUNGO", "amount": 25.0,
                    "account": "Visa Pichincha", "purchased_at": "2026-04-20"}
        result = prepare_one(consumo, self.cf_conn, None, use_llm=False, rules=TEST_RULES)
        assert result["method"] == "fuzzy_match"
        assert result["category"] == "Home Food"

    def test_fallback(self):
        consumo = {"merchant": "UNKNOWN STORE XYZ", "amount": 10.0,
                    "account": "Cash", "purchased_at": "2026-04-20"}
        result = prepare_one(consumo, self.cf_conn, None, use_llm=False, rules=TEST_RULES)
        assert result["method"] == "fallback"
        assert result["category"] == "Others"


def _make_txn(msg_id, merchant, amount, account="Visa Pichincha", label="Consumos/Pichincha"):
    return EmailTxn(
        msg_id=msg_id, bank="Pichincha", account=account,
        purchased_at=datetime(2026, 4, 22, 14, 0),
        amount=amount, merchant=merchant, card_last="1234",
        subject="test",
    )


class TestRegisterFlow(unittest.TestCase):
    def setUp(self):
        self.cf_conn = create_test_db()
        self.consumos_conn = create_test_consumos_db()
        # Add accounts that match consumo accounts
        self.cf_conn.execute(
            "INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?)",
            ("Visa Pichincha", "credit_card", 13, 1),
        )
        self.cf_conn.execute(
            "INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?)",
            ("Diners", "credit_card", 18, 3),
        )
        self.cf_conn.commit()

    def test_register_creates_reviewable_transaction(self):
        upsert_consumo(self.consumos_conn, _make_txn("m1", "CORAL CARAPUNGO", 25.0), "Consumos/Pichincha")
        stats = register_consumos(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, rules=TEST_RULES,
        )
        assert stats["registered"] == 1
        review = get_transactions_needing_review(self.cf_conn, source="gmail")
        assert len(review) == 1
        assert review[0]["needs_review"] == 1
        assert review[0]["source"] == "gmail"

    def test_register_links_consumo(self):
        upsert_consumo(self.consumos_conn, _make_txn("m1", "CORAL CARAPUNGO", 25.0), "Consumos/Pichincha")
        register_consumos(self.cf_conn, self.consumos_conn, None, use_llm=False)
        review = get_transactions_needing_review(self.cf_conn, source="gmail")
        link = get_transaction_link(self.cf_conn, review[0]["id"])
        assert link is not None
        assert link["consumo_msg_id"] == "m1"
        assert link["link_source"] == "auto_register"

    def test_register_marks_consumo_registered(self):
        upsert_consumo(self.consumos_conn, _make_txn("m1", "CORAL CARAPUNGO", 25.0), "Consumos/Pichincha")
        register_consumos(self.cf_conn, self.consumos_conn, None, use_llm=False)
        unreg = find_unregistered(self.consumos_conn)
        assert len(unreg) == 0

    def test_uber_rule_applied(self):
        txn = EmailTxn(
            msg_id="m2", bank="Diners", account="Diners",
            purchased_at=datetime(2026, 4, 22), amount=1.50,
            merchant="DLOCAL*UBER RIDES\\Mr", card_last="8811", subject="test",
        )
        upsert_consumo(self.consumos_conn, txn, "Consumos/Diners")
        register_consumos(self.cf_conn, self.consumos_conn, None, use_llm=False)
        review = get_transactions_needing_review(self.cf_conn, source="gmail")
        assert review[0]["category"] == "Family Support"
        assert "Uber" in review[0]["description"]

    def test_dry_run_no_writes(self):
        upsert_consumo(self.consumos_conn, _make_txn("m1", "STORE", 10.0), "Consumos/Pichincha")
        stats = register_consumos(
            self.cf_conn, self.consumos_conn, None,
            dry_run=True, use_llm=False, rules=TEST_RULES,
        )
        assert stats["registered"] == 1
        assert len(get_transactions_needing_review(self.cf_conn)) == 0
        assert len(find_unregistered(self.consumos_conn)) == 1

    def test_subscription_match_links_forecast(self):
        """Consumo matching a subscription forecast links to it instead of creating new txn."""
        self.cf_conn.execute(
            "INSERT INTO subscriptions (id, name, category, monthly_amount, payment_account_id, start_date, is_budget, is_income, underspend_behavior) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'keep')",
            ("sub_internet", "Internet", "Home", 22.43, "Visa Pichincha", "2026-01-01"),
        )
        self.cf_conn.execute(
            "INSERT INTO transactions (description, amount, account, date_created, date_payed, category, status, origin_id) "
            "VALUES (?, ?, ?, ?, ?, ?, 'forecast', ?)",
            ("Internet Subscription", -22.43, "Visa Pichincha", "2026-04-15", "2026-05-15", "Home", "sub_internet"),
        )
        self.cf_conn.commit()
        upsert_consumo(self.consumos_conn, _make_txn("m_inet", "HALLO NETWORK CIA", 22.43, account="Visa Pichincha"), "Consumos/Pichincha")
        stats = register_consumos(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, rules=TEST_RULES,
        )
        assert stats["registered"] == 1
        assert stats["by_method"].get("subscription_match") == 1
        review = get_transactions_needing_review(self.cf_conn, source="gmail")
        assert len(review) == 0

    def test_subscription_no_match_different_amount(self):
        """Consumo with different amount should NOT match subscription forecast."""
        self.cf_conn.execute(
            "INSERT INTO subscriptions (id, name, category, monthly_amount, payment_account_id, start_date, is_budget, is_income, underspend_behavior) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'keep')",
            ("sub_internet", "Internet", "Home", 22.43, "Visa Pichincha", "2026-01-01"),
        )
        self.cf_conn.execute(
            "INSERT INTO transactions (description, amount, account, date_created, date_payed, category, status, origin_id) "
            "VALUES (?, ?, ?, ?, ?, ?, 'forecast', ?)",
            ("Internet Subscription", -22.43, "Visa Pichincha", "2026-04-15", "2026-05-15", "Home", "sub_internet"),
        )
        self.cf_conn.commit()
        upsert_consumo(self.consumos_conn, _make_txn("m_other", "HALLO NETWORK", 50.00, account="Visa Pichincha"), "Consumos/Pichincha")
        stats = register_consumos(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, rules=TEST_RULES,
        )
        assert stats["by_method"].get("subscription_match") is None

    def test_existing_txn_match_links_instead_of_creating(self):
        """Consumo matching an existing committed transaction links to it."""
        add_transactions(self.cf_conn, [{
            "date_created": "2026-04-22", "date_payed": "2026-05-01",
            "description": "Coral Carapungo - groceries", "account": "Visa Pichincha",
            "amount": -25.0, "category": "Home Food", "budget": None,
            "status": "committed", "origin_id": None,
        }])
        upsert_consumo(self.consumos_conn, _make_txn("m1", "CORAL CARAPUNGO", 25.0), "Consumos/Pichincha")
        stats = register_consumos(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, rules=TEST_RULES,
        )
        assert stats["registered"] == 1
        assert stats["by_method"].get("existing_txn_match") == 1
        review = get_transactions_needing_review(self.cf_conn, source="gmail")
        assert len(review) == 0

    def test_existing_txn_no_match_different_date(self):
        """Existing txn with date >1 day apart should NOT match."""
        add_transactions(self.cf_conn, [{
            "date_created": "2026-04-18", "date_payed": "2026-05-01",
            "description": "Coral - stuff", "account": "Visa Pichincha",
            "amount": -25.0, "category": "Home Food", "budget": None,
            "status": "committed", "origin_id": None,
        }])
        upsert_consumo(self.consumos_conn, _make_txn("m1", "CORAL CARAPUNGO", 25.0), "Consumos/Pichincha")
        stats = register_consumos(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, rules=TEST_RULES,
        )
        assert stats["by_method"].get("existing_txn_match") is None

    def test_after_filter(self):
        upsert_consumo(self.consumos_conn, _make_txn("m1", "A", 10.0), "Consumos/Pichincha")
        stats = register_consumos(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, after="2026-05-01", rules=TEST_RULES,
        )
        assert stats["registered"] == 0


class TestEnrichWithInvoices(unittest.TestCase):
    def setUp(self):
        self.cf_conn = create_test_db()
        self.consumos_conn = create_test_consumos_db()
        self.cf_conn.execute(
            "INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?)",
            ("Visa Pichincha", "credit_card", 13, 1),
        )
        self.cf_conn.commit()

    def test_enrich_updates_description(self):
        """Transaction with newly-matched invoice gets enriched description."""
        upsert_consumo(self.consumos_conn, _make_txn("m1", "CORAL CARAPUNGO", 25.0), "Consumos/Pichincha")
        register_consumos(self.cf_conn, self.consumos_conn, None, use_llm=False, rules=TEST_RULES)
        review = get_transactions_needing_review(self.cf_conn, source="gmail")
        assert len(review) == 1
        # Simulate invoice arriving later: set matched_invoice_number on consumo
        self.consumos_conn.execute(
            "UPDATE consumos SET matched_invoice_number = ? WHERE msg_id = ?",
            ("001-001-000012345", "m1"),
        )
        self.consumos_conn.commit()
        # Force date_created to today so it's within 3-day window
        self.cf_conn.execute(
            "UPDATE transactions SET date_created = date('now') WHERE id = ?",
            (review[0]["id"],),
        )
        self.cf_conn.commit()
        stats = enrich_with_invoices(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, rules=TEST_RULES,
        )
        assert stats["enriched"] == 1
        link = get_transaction_link(self.cf_conn, review[0]["id"])
        assert link["invoice_number"] == "001-001-000012345"

    def test_enrich_skips_approved_transactions(self):
        """Approved (needs_review=0) transactions should not be enriched."""
        upsert_consumo(self.consumos_conn, _make_txn("m1", "CORAL CARAPUNGO", 25.0), "Consumos/Pichincha")
        register_consumos(self.cf_conn, self.consumos_conn, None, use_llm=False, rules=TEST_RULES)
        review = get_transactions_needing_review(self.cf_conn, source="gmail")
        # Approve it
        self.cf_conn.execute("UPDATE transactions SET needs_review = 0 WHERE id = ?", (review[0]["id"],))
        self.cf_conn.commit()
        self.consumos_conn.execute(
            "UPDATE consumos SET matched_invoice_number = ? WHERE msg_id = ?",
            ("001-001-000012345", "m1"),
        )
        self.consumos_conn.commit()
        stats = enrich_with_invoices(
            self.cf_conn, self.consumos_conn, None,
            use_llm=False, rules=TEST_RULES,
        )
        assert stats["enriched"] == 0


if __name__ == "__main__":
    unittest.main()

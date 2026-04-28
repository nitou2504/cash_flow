"""Tests for gmail_sync.ingest_consumos — the Gmail → consumos.db ingest loop."""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from cashflow.consumo_database import create_test_consumos_db
from cashflow.consumo_repository import get_ingested_msg_ids, find_unmatched
from gmail_sync.ingest_consumos import ingest_label, match_invoices
from gmail_sync.parsers import parse_pichincha, parse_cash


PICHINCHA_BODY = """Consumo con tu tarjeta

Valor
$ 15.05

Fecha
2026-04-22 14:30

Establecimiento
TITAN ORELLANA

Tarjeta usada
XXXX4477
"""

CASH_BODY = """Detalle

Cuenta de origen:     ******1057

Cuenta acreditada:     ******6634

Fecha:     24/04/2026

Nombre del beneficiario:     SANCHEZ RUEDA PEDRO JOSE

Monto:     USD 35.00

Concepto:     Mercado y limpieza
"""


def _fake_gc(messages: dict[str, tuple[str, str, str]]):
    """Build a mock GmailClient. messages = {msg_id: (subject, from, body)}."""
    gc = MagicMock()
    gc.resolve_label_id.return_value = "LABEL_ID"

    def _iter_ids(label_ids=None, query=None, max_total=None):
        return iter(messages.keys())

    gc.iter_message_ids.side_effect = _iter_ids

    def _get_msg(mid, fmt="full"):
        subj, frm, body = messages[mid]
        return {
            "id": mid,
            "internalDate": str(int(datetime(2026, 4, 22).timestamp() * 1000)),
            "payload": {
                "headers": [
                    {"name": "Subject", "value": subj},
                    {"name": "From", "value": frm},
                ],
                "mimeType": "text/plain",
                "body": {},
                "parts": [],
            },
        }

    gc.get_message.side_effect = _get_msg
    return gc


class TestIngestLabel(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_consumos_db()

    @patch("gmail_sync.ingest_consumos.extract_text")
    def test_pichincha_ingested(self, mock_extract):
        mock_extract.return_value = PICHINCHA_BODY
        gc = _fake_gc({"m1": ("Consumo", "alertas@pichincha.com", PICHINCHA_BODY)})

        stats = ingest_label(
            gc, "Consumos/Pichincha", "LBL", parse_pichincha,
            "after:2026/04/20", self.conn,
        )
        assert stats["upserted"] == 1
        assert stats["unparsed_logged"] == 0
        row = self.conn.execute("SELECT * FROM consumos WHERE msg_id = 'm1'").fetchone()
        assert row["merchant"] == "TITAN ORELLANA"
        assert row["amount"] == 15.05

    @patch("gmail_sync.ingest_consumos.extract_text")
    def test_cash_ingested(self, mock_extract):
        mock_extract.return_value = CASH_BODY
        gc = _fake_gc({"m2": ("NOTIF", "banco@pichincha.com", CASH_BODY)})

        stats = ingest_label(
            gc, "Consumos/Cash", "LBL", parse_cash,
            "after:2026/04/20", self.conn,
        )
        assert stats["upserted"] == 1
        row = self.conn.execute("SELECT * FROM consumos WHERE msg_id = 'm2'").fetchone()
        assert row["beneficiary"] == "SANCHEZ RUEDA PEDRO JOSE"
        assert row["destination_account"] == "6634"

    @patch("gmail_sync.ingest_consumos.extract_text")
    def test_unparseable_flagged(self, mock_extract):
        mock_extract.return_value = "garbage body no fields"
        gc = _fake_gc({"m3": ("subj", "from", "garbage")})

        stats = ingest_label(
            gc, "Consumos/Pichincha", "LBL", parse_pichincha,
            "after:2026/04/20", self.conn,
        )
        assert stats["unparsed_logged"] == 1
        assert "m3" in get_ingested_msg_ids(self.conn)

    @patch("gmail_sync.ingest_consumos.extract_text")
    def test_idempotent_second_run(self, mock_extract):
        mock_extract.return_value = PICHINCHA_BODY
        gc = _fake_gc({"m1": ("Consumo", "from", PICHINCHA_BODY)})

        ingest_label(gc, "Consumos/Pichincha", "LBL", parse_pichincha,
                     "after:2026/04/20", self.conn)
        stats = ingest_label(gc, "Consumos/Pichincha", "LBL", parse_pichincha,
                             "after:2026/04/20", self.conn)
        assert stats["skipped_known"] == 1
        assert stats["upserted"] == 0

    @patch("gmail_sync.ingest_consumos.extract_text")
    def test_dry_run_writes_nothing(self, mock_extract):
        mock_extract.return_value = PICHINCHA_BODY
        gc = _fake_gc({"m1": ("Consumo", "from", PICHINCHA_BODY)})

        stats = ingest_label(
            gc, "Consumos/Pichincha", "LBL", parse_pichincha,
            "after:2026/04/20", self.conn, dry_run=True,
        )
        assert stats["upserted"] == 1
        rows = self.conn.execute("SELECT * FROM consumos").fetchall()
        assert len(rows) == 0


class TestInvoiceMatching(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_consumos_db()

    def _insert_consumo(self, msg_id, amount, date_str):
        self.conn.execute("""
            INSERT INTO consumos (msg_id, bank, account, purchased_at, amount,
                                  merchant, card_last, subject, label)
            VALUES (?, 'Pichincha', 'Visa Pichincha', ?, ?, 'STORE', '1234', 'subj', 'Consumos/Pichincha')
        """, (msg_id, date_str, amount))
        self.conn.commit()

    def _insert_invoice(self, invoice_number, total, issue_date):
        self.conn.execute("""
            INSERT INTO invoices (doc_type, invoice_number, ruc, vendor,
                                  issue_date, subtotal_sin_impuesto, total, currency)
            VALUES ('factura', ?, '1234567890001', 'VENDOR', ?, ?, ?, 'USD')
        """, (invoice_number, issue_date, total - total * 0.15, total))
        self.conn.commit()

    def test_match_found(self):
        self._insert_consumo("m1", 15.05, "2026-04-22T14:30:00")
        self._insert_invoice("001-002-000000001", 15.05, "2026-04-22")

        stats = match_invoices(self.conn)
        assert stats["matched"] == 1
        row = self.conn.execute(
            "SELECT matched_invoice_number FROM consumos WHERE msg_id = 'm1'"
        ).fetchone()
        assert row["matched_invoice_number"] == "001-002-000000001"

    def test_no_match(self):
        self._insert_consumo("m1", 15.05, "2026-04-22T14:30:00")
        stats = match_invoices(self.conn)
        assert stats["no_match"] == 1

    def test_rematch_after_invoice_arrives(self):
        self._insert_consumo("m1", 15.05, "2026-04-22T14:30:00")
        stats = match_invoices(self.conn)
        assert stats["no_match"] == 1

        self._insert_invoice("001-002-000000001", 15.05, "2026-04-22")
        stats = match_invoices(self.conn)
        assert stats["matched"] == 1


if __name__ == "__main__":
    unittest.main()

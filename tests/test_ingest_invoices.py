"""Tests for gmail_sync.ingest_invoices — the Gmail → cash_flow.db ingest loop.

Uses a fake GmailClient that yields in-memory messages; no network calls.
"""
import io
import unittest
import zipfile
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from cashflow.invoice_database import create_test_invoices_db
from cashflow.invoice_repository import (
    list_invoices,
    list_unparsed,
    get_invoice_by_msg_id,
)
from gmail_sync.ingest_invoices import ingest_messages


# A minimal valid factura XML we can reuse for fake attachments
SAMPLE_FACTURA = b"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
  <infoTributaria>
    <razonSocial>TEST VENDOR S.A.</razonSocial>
    <nombreComercial>TEST</nombreComercial>
    <ruc>1234567890001</ruc>
    <claveAcceso>CLAVE</claveAcceso>
    <estab>001</estab><ptoEmi>002</ptoEmi><secuencial>{seq}</secuencial>
  </infoTributaria>
  <infoFactura>
    <fechaEmision>15/03/2026</fechaEmision>
    <totalSinImpuestos>10.00</totalSinImpuestos>
    <totalDescuento>0.00</totalDescuento>
    <propina>0.00</propina>
    <importeTotal>11.50</importeTotal>
  </infoFactura>
  <detalles>
    <detalle>
      <descripcion>ITEM</descripcion>
      <cantidad>1</cantidad>
      <precioUnitario>10</precioUnitario>
      <precioTotalSinImpuesto>10</precioTotalSinImpuesto>
    </detalle>
  </detalles>
</factura>"""


def _make_msg(msg_id: str, subject: str, from_addr: str,
              internal_date: datetime, attachments: list[dict]) -> dict:
    """Build a fake Gmail message payload with headers + attachments."""
    return {
        "id": msg_id,
        "internalDate": str(int(internal_date.timestamp() * 1000)),
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": from_addr},
            ],
            "parts": [
                {
                    "filename": a["filename"],
                    "mimeType": a.get("mime", "application/octet-stream"),
                    "body": {
                        "attachmentId": a["attachment_id"],
                        "size": len(a["data"]),
                    },
                }
                for a in attachments
            ],
        },
    }


class FakeGmail:
    """Drop-in mock for GmailClient used by ingest_messages."""
    def __init__(self, messages: list[dict], attachments_by_id: dict[str, bytes]):
        self._messages = {m["id"]: m for m in messages}
        self._attachments = attachments_by_id

    def iter_message_ids(self, label_ids=None, query=None, max_total=None):
        return iter(self._messages.keys())

    def get_message(self, msg_id: str, fmt: str = "full") -> dict:
        return self._messages[msg_id]

    def get_attachment(self, msg_id: str, attachment_id: str) -> bytes:
        return self._attachments[attachment_id]


def _when(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 10, 0, 0, tzinfo=timezone.utc)


class TestIngestBasic(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_parseable_xml_gets_upserted(self):
        xml = SAMPLE_FACTURA.replace(b"{seq}", b"000000001")
        msg = _make_msg(
            "msg1", "Factura 1", "vendor@x.com", _when(date(2026, 3, 15)),
            [{"filename": "fac1.xml", "attachment_id": "a1", "data": xml}],
        )
        gc = FakeGmail([msg], {"a1": xml})
        stats = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        self.assertEqual(stats["upserted"], 1)
        self.assertEqual(stats["unparsed_logged"], 0)
        invs = list_invoices(self.conn)
        self.assertEqual(len(invs), 1)
        self.assertEqual(invs[0]["msg_id"], "msg1")
        # Email metadata carried through from Gmail headers
        self.assertEqual(invs[0]["email_subject"], "Factura 1")
        self.assertEqual(invs[0]["email_from"], "vendor@x.com")
        # Email ↔ invoice lookup works
        row = get_invoice_by_msg_id(self.conn, "msg1")
        self.assertIsNotNone(row)

    def test_email_without_xml_is_flagged(self):
        msg = _make_msg(
            "msg2", "Factura sin XML", "vendor@x.com", _when(date(2026, 4, 1)),
            [{"filename": "invoice.pdf", "attachment_id": "p1", "data": b"%PDF-1.4"}],
        )
        gc = FakeGmail([msg], {"p1": b"%PDF-1.4"})
        stats = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        self.assertEqual(stats["upserted"], 0)
        self.assertEqual(stats["unparsed_logged"], 1)
        unparsed = list_unparsed(self.conn)
        self.assertEqual(len(unparsed), 1)
        self.assertEqual(unparsed[0]["msg_id"], "msg2")
        self.assertEqual(unparsed[0]["reason"], "no_xml")
        self.assertEqual(unparsed[0]["has_pdf"], 1)

    def test_email_with_no_attachment_is_flagged(self):
        msg = _make_msg(
            "msg3", "Factura HTML body", "vendor@x.com", _when(date(2026, 4, 2)),
            attachments=[],
        )
        gc = FakeGmail([msg], {})
        stats = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        self.assertEqual(stats["unparsed_logged"], 1)
        unparsed = list_unparsed(self.conn)
        self.assertEqual(unparsed[0]["reason"], "no_attachment")
        self.assertEqual(unparsed[0]["has_pdf"], 0)

    def test_malformed_xml_flagged_as_parse_failed(self):
        msg = _make_msg(
            "msg4", "Factura broken", "vendor@x.com", _when(date(2026, 4, 3)),
            [{"filename": "bad.xml", "attachment_id": "a4", "data": b"<not-a-factura/>"}],
        )
        gc = FakeGmail([msg], {"a4": b"<not-a-factura/>"})
        stats = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        self.assertEqual(stats["upserted"], 0)
        self.assertEqual(stats["parse_failed"], 1)
        self.assertEqual(stats["unparsed_logged"], 1)
        unparsed = list_unparsed(self.conn)
        self.assertEqual(unparsed[0]["reason"], "parse_failed")

    def test_zip_with_inner_xml_gets_parsed(self):
        xml = SAMPLE_FACTURA.replace(b"{seq}", b"000000005")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("invoice.xml", xml)
        zip_bytes = buf.getvalue()
        msg = _make_msg(
            "msg5", "Factura ZIP", "seedbilling@x", _when(date(2026, 4, 4)),
            [{"filename": "factura.zip", "attachment_id": "z1", "data": zip_bytes}],
        )
        gc = FakeGmail([msg], {"z1": zip_bytes})
        stats = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        self.assertEqual(stats["upserted"], 1)
        self.assertEqual(stats["unparsed_logged"], 0)


class TestIngestIdempotency(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_second_run_skips_known(self):
        xml = SAMPLE_FACTURA.replace(b"{seq}", b"000000100")
        msg = _make_msg(
            "mid100", "Factura", "v@x", _when(date(2026, 4, 5)),
            [{"filename": "f.xml", "attachment_id": "a100", "data": xml}],
        )
        gc = FakeGmail([msg], {"a100": xml})
        s1 = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        s2 = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        self.assertEqual(s1["upserted"], 1)
        self.assertEqual(s2["upserted"], 0)
        self.assertEqual(s2["skipped_known"], 1)
        self.assertEqual(len(list_invoices(self.conn)), 1)

    def test_second_run_skips_known_unparsed(self):
        msg = _make_msg(
            "mid200", "Factura HTML", "v@x", _when(date(2026, 4, 6)),
            attachments=[],
        )
        gc = FakeGmail([msg], {})
        ingest_messages(gc, "label", "", self.conn, progress_every=0)
        s2 = ingest_messages(gc, "label", "", self.conn, progress_every=0)
        self.assertEqual(s2["skipped_known"], 1)
        self.assertEqual(len(list_unparsed(self.conn)), 1)


class TestIngestDryRun(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_dry_run_writes_nothing(self):
        xml = SAMPLE_FACTURA.replace(b"{seq}", b"000000301")
        msg_parse = _make_msg(
            "mid_p", "OK", "v@x", _when(date(2026, 4, 7)),
            [{"filename": "x.xml", "attachment_id": "aP", "data": xml}],
        )
        msg_fail = _make_msg(
            "mid_f", "Fail", "v@x", _when(date(2026, 4, 8)),
            attachments=[],
        )
        gc = FakeGmail([msg_parse, msg_fail], {"aP": xml})
        stats = ingest_messages(gc, "label", "", self.conn, dry_run=True, progress_every=0)
        self.assertEqual(stats["upserted"], 1)
        self.assertEqual(stats["unparsed_logged"], 1)
        # Nothing committed
        self.assertEqual(list_invoices(self.conn), [])
        self.assertEqual(list_unparsed(self.conn), [])


if __name__ == "__main__":
    unittest.main()

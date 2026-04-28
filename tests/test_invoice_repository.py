"""Tests for cashflow.invoice_repository (cash_flow.db store)."""
import unittest
from datetime import date

from cashflow.invoice_database import create_test_invoices_db
from cashflow.invoice_repository import (
    upsert_invoice,
    get_invoice_by_id,
    get_invoice_by_number,
    get_invoice_by_msg_id,
    get_lines,
    get_taxes,
    find_invoices_near,
    list_invoices,
    record_unparsed,
    list_unparsed,
    mark_unparsed_resolved,
    get_ingested_msg_ids,
    get_latest_issue_date,
)
from gmail_sync.invoice import Invoice, InvoiceLine, InvoiceTax


def _make_invoice(
    *,
    number: str = "001-002-000000001",
    vendor: str = "TEST VENDOR",
    issue: date = date(2026, 3, 15),
    total: float = 11.50,
    lines: list[InvoiceLine] | None = None,
    taxes: list[InvoiceTax] | None = None,
    doc_type: str = "factura",
    motivo: str = "",
    motivo_category: str = "",
    refund_of: str = "",
) -> Invoice:
    return Invoice(
        vendor=vendor,
        issue_date=issue,
        total=total,
        lines=lines if lines is not None else [
            InvoiceLine(
                description="Item A", quantity=2.0, total=10.00,
                sku="SKU1", unit_price=5.00, line_tax=1.50, tax_rate=15.0,
            )
        ],
        doc_type=doc_type,
        invoice_number=number,
        clave_acceso="CLAVE",
        ruc="1234567890001",
        vendor_trade_name="TEST",
        subtotal_sin_impuesto=10.00,
        total_descuento=0.0,
        propina=0.0,
        motivo=motivo,
        motivo_category=motivo_category,
        refund_of=refund_of,
        taxes=taxes if taxes is not None else [
            InvoiceTax(tax_code=2, rate_code=4, rate_pct=15.0,
                       base_imponible=10.00, tax_value=1.50)
        ],
    )


class TestUpsertAndFetch(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_upsert_inserts_once(self):
        inv = _make_invoice()
        invoice_id = upsert_invoice(self.conn, inv, xml_path="x.xml")
        self.assertIsInstance(invoice_id, int)
        row = get_invoice_by_id(self.conn, invoice_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["invoice_number"], inv.invoice_number)
        self.assertEqual(row["xml_path"], "x.xml")
        self.assertAlmostEqual(row["total"], 11.50)

    def test_upsert_is_idempotent(self):
        inv = _make_invoice()
        a = upsert_invoice(self.conn, inv)
        b = upsert_invoice(self.conn, inv)
        self.assertEqual(a, b)
        cursor = self.conn.execute("SELECT COUNT(*) AS c FROM invoices")
        self.assertEqual(cursor.fetchone()["c"], 1)
        # Lines are replaced on re-upsert, still just one set
        self.assertEqual(len(get_lines(self.conn, a)), 1)

    def test_upsert_replaces_lines_and_taxes(self):
        """Re-upserting with different lines should wipe the old rows."""
        inv1 = _make_invoice(lines=[
            InvoiceLine(description="Old A", quantity=1.0, total=1.00),
            InvoiceLine(description="Old B", quantity=1.0, total=2.00),
        ])
        inv_id = upsert_invoice(self.conn, inv1)
        self.assertEqual(len(get_lines(self.conn, inv_id)), 2)

        inv2 = _make_invoice(lines=[
            InvoiceLine(description="New only", quantity=3.0, total=9.00),
        ])
        upsert_invoice(self.conn, inv2)
        lines = get_lines(self.conn, inv_id)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["description"], "New only")

    def test_get_lines_ordered(self):
        inv = _make_invoice(lines=[
            InvoiceLine(description="Third", quantity=1, total=1),
            InvoiceLine(description="First", quantity=1, total=1),
            InvoiceLine(description="Second", quantity=1, total=1),
        ])
        inv_id = upsert_invoice(self.conn, inv)
        lines = get_lines(self.conn, inv_id)
        # upsert assigns line_number from insertion order
        self.assertEqual([l["line_number"] for l in lines], [1, 2, 3])
        self.assertEqual([l["description"] for l in lines], ["Third", "First", "Second"])

    def test_get_taxes(self):
        inv_id = upsert_invoice(self.conn, _make_invoice())
        taxes = get_taxes(self.conn, inv_id)
        self.assertEqual(len(taxes), 1)
        self.assertAlmostEqual(taxes[0]["rate_pct"], 15.0)

    def test_get_invoice_by_number(self):
        inv_id = upsert_invoice(self.conn, _make_invoice(number="042-916-000000777"))
        row = get_invoice_by_number(self.conn, "042-916-000000777")
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], inv_id)
        self.assertIsNone(get_invoice_by_number(self.conn, "042-916-000000999"))

    def test_upsert_requires_invoice_number(self):
        inv = _make_invoice(number="")
        with self.assertRaises(ValueError):
            upsert_invoice(self.conn, inv)


class TestFindNear(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()
        upsert_invoice(self.conn, _make_invoice(
            number="001-001-000000001", issue=date(2026, 3, 15), total=45.00))
        upsert_invoice(self.conn, _make_invoice(
            number="001-001-000000002", issue=date(2026, 3, 16), total=45.00))
        upsert_invoice(self.conn, _make_invoice(
            number="001-001-000000003", issue=date(2026, 3, 20), total=45.00))

    def tearDown(self):
        self.conn.close()

    def test_finds_within_window(self):
        hits = find_invoices_near(self.conn, date(2026, 3, 15), 45.00, tol_days=2)
        self.assertEqual(len(hits), 2)
        # Sorted by nearest day diff — exact match first
        self.assertEqual(hits[0]["invoice_number"], "001-001-000000001")

    def test_respects_amount_tolerance(self):
        hits = find_invoices_near(self.conn, date(2026, 3, 15), 45.50, tol_amount=0.01)
        self.assertEqual(hits, [])

    def test_empty_when_all_out_of_range(self):
        hits = find_invoices_near(self.conn, date(2025, 1, 1), 45.00, tol_days=2)
        self.assertEqual(hits, [])


class TestListInvoices(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()
        upsert_invoice(self.conn, _make_invoice(
            number="N001", vendor="FAVORITA", issue=date(2026, 1, 1), total=10.0))
        upsert_invoice(self.conn, _make_invoice(
            number="N002", vendor="FAVORITA", issue=date(2026, 2, 1), total=20.0,
            doc_type="nota_credito", motivo="Cash Back Titán", motivo_category="loyalty"))
        upsert_invoice(self.conn, _make_invoice(
            number="N003", vendor="CORAL CAR", issue=date(2026, 3, 1), total=30.0))

    def tearDown(self):
        self.conn.close()

    def test_default_lists_newest_first(self):
        rows = list_invoices(self.conn)
        self.assertEqual([r["invoice_number"] for r in rows], ["N003", "N002", "N001"])

    def test_filter_by_vendor(self):
        rows = list_invoices(self.conn, vendor="FAVORITA")
        self.assertEqual({r["invoice_number"] for r in rows}, {"N001", "N002"})

    def test_filter_by_date_range(self):
        rows = list_invoices(self.conn, after=date(2026, 2, 1), before=date(2026, 2, 28))
        self.assertEqual([r["invoice_number"] for r in rows], ["N002"])

    def test_filter_by_doc_type(self):
        rows = list_invoices(self.conn, doc_type="nota_credito")
        self.assertEqual([r["invoice_number"] for r in rows], ["N002"])
        self.assertEqual(rows[0]["motivo_category"], "loyalty")


class TestUnparsedTracking(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_record_and_list(self):
        record_unparsed(self.conn, "mid1", "Factura X", "vendor@x.com",
                        "2026-04-19T10:00:00", reason="no_attachment", has_pdf=False)
        record_unparsed(self.conn, "mid2", "Factura Y", "vendor@y.com",
                        "2026-04-18T10:00:00", reason="parse_failed", has_pdf=True,
                        notes="2 XMLs, none valid")
        rows = list_unparsed(self.conn)
        self.assertEqual(len(rows), 2)
        # Ordered by received_at DESC
        self.assertEqual(rows[0]["msg_id"], "mid1")
        self.assertEqual(rows[0]["has_pdf"], 0)
        self.assertEqual(rows[1]["has_pdf"], 1)

    def test_record_is_idempotent(self):
        record_unparsed(self.conn, "m1", "A", "f@x", "2026-01-01", reason="no_attachment")
        record_unparsed(self.conn, "m1", "A-updated", "f@x", "2026-01-01", reason="no_xml")
        rows = list_unparsed(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject"], "A-updated")
        self.assertEqual(rows[0]["reason"], "no_xml")

    def test_list_filters_by_reason(self):
        record_unparsed(self.conn, "m1", "A", "f", "2026-01-01", reason="no_attachment")
        record_unparsed(self.conn, "m2", "B", "f", "2026-01-02", reason="parse_failed")
        self.assertEqual(len(list_unparsed(self.conn, reason="no_attachment")), 1)
        self.assertEqual(len(list_unparsed(self.conn, reason="parse_failed")), 1)

    def test_mark_resolved_manually(self):
        record_unparsed(self.conn, "m1", "A", "f", "2026-01-01", reason="no_attachment")
        self.assertTrue(mark_unparsed_resolved(self.conn, "m1", notes="handled manually"))
        self.assertEqual(list_unparsed(self.conn), [])
        all_rows = list_unparsed(self.conn, only_unresolved=False)
        self.assertEqual(all_rows[0]["resolved"], 1)
        self.assertEqual(all_rows[0]["notes"], "handled manually")
        # Idempotent: resolving again still OK
        self.assertTrue(mark_unparsed_resolved(self.conn, "m1"))
        # Unknown msg_id returns False
        self.assertFalse(mark_unparsed_resolved(self.conn, "does-not-exist"))

    def test_upsert_auto_resolves_previously_unparsed(self):
        """If an email was flagged unparsed and later we upsert an invoice
        carrying the same msg_id, the flag should be auto-resolved."""
        record_unparsed(self.conn, "mX", "A", "f", "2026-01-01", reason="parse_failed")
        self.assertEqual(len(list_unparsed(self.conn)), 1)
        inv = _make_invoice(number="001-002-000000010")
        inv.msg_id = "mX"
        upsert_invoice(self.conn, inv)
        self.assertEqual(list_unparsed(self.conn), [])  # cleared
        all_rows = list_unparsed(self.conn, only_unresolved=False)
        self.assertEqual(all_rows[0]["resolved"], 1)

    def test_get_ingested_msg_ids_union(self):
        """Should return msg_ids from BOTH invoices and unparsed_facturas."""
        inv = _make_invoice(number="001-002-000000001")
        inv.msg_id = "m_invoice"
        upsert_invoice(self.conn, inv)
        record_unparsed(self.conn, "m_unparsed", "A", "f", "2026-01-01",
                        reason="no_attachment")
        self.assertEqual(
            get_ingested_msg_ids(self.conn),
            {"m_invoice", "m_unparsed"},
        )


class TestGetInvoiceByMsgId(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_found(self):
        inv = _make_invoice(number="042-916-000099999")
        inv.msg_id = "msgABC"
        upsert_invoice(self.conn, inv)
        row = get_invoice_by_msg_id(self.conn, "msgABC")
        self.assertIsNotNone(row)
        self.assertEqual(row["invoice_number"], "042-916-000099999")

    def test_not_found(self):
        self.assertIsNone(get_invoice_by_msg_id(self.conn, "nope"))


class TestExtendedFieldsPersistence(unittest.TestCase):
    """New fields: merchant_name, establishment_code, store_address, forma_pago,
    deducible_alimentacion, email_subject, email_from."""

    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_all_new_fields_roundtrip(self):
        inv = _make_invoice()
        inv.merchant_name = "CORAL CARAPUNGO"
        inv.establishment_code = "042"
        inv.store_address = "CALLE EJE LONG. CACHA"
        inv.forma_pago = 19
        inv.deducible_alimentacion = 4.46
        inv.email_subject = "Factura Electrónica - 042-002-000000001"
        inv.email_from = "vendor@x.com"
        inv_id = upsert_invoice(self.conn, inv)
        row = get_invoice_by_id(self.conn, inv_id)
        self.assertEqual(row["merchant_name"], "CORAL CARAPUNGO")
        self.assertEqual(row["establishment_code"], "042")
        self.assertEqual(row["store_address"], "CALLE EJE LONG. CACHA")
        self.assertEqual(row["forma_pago"], 19)
        self.assertAlmostEqual(row["deducible_alimentacion"], 4.46)
        self.assertEqual(row["email_subject"], "Factura Electrónica - 042-002-000000001")
        self.assertEqual(row["email_from"], "vendor@x.com")

    def test_email_fields_preserved_across_upsert(self):
        """Re-upserting with empty email fields must not wipe previously-saved ones."""
        inv = _make_invoice()
        inv.email_subject = "Original subject"
        inv.email_from = "v@x.com"
        upsert_invoice(self.conn, inv)
        # Re-upsert without email metadata (e.g. repeat ingest where we don't
        # bother passing through the headers again)
        inv2 = _make_invoice()
        upsert_invoice(self.conn, inv2)
        row = get_invoice_by_number(self.conn, inv.invoice_number)
        self.assertEqual(row["email_subject"], "Original subject")
        self.assertEqual(row["email_from"], "v@x.com")


class TestGetLatestIssueDate(unittest.TestCase):
    def setUp(self):
        self.conn = create_test_invoices_db()

    def tearDown(self):
        self.conn.close()

    def test_empty_returns_none(self):
        self.assertIsNone(get_latest_issue_date(self.conn))

    def test_returns_max(self):
        upsert_invoice(self.conn, _make_invoice(
            number="A", issue=date(2026, 1, 1)))
        upsert_invoice(self.conn, _make_invoice(
            number="B", issue=date(2026, 3, 15)))
        upsert_invoice(self.conn, _make_invoice(
            number="C", issue=date(2026, 2, 1)))
        self.assertEqual(get_latest_issue_date(self.conn), date(2026, 3, 15))


if __name__ == "__main__":
    unittest.main()

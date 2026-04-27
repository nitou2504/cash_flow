"""Tests for gmail_sync.invoice — SRI e-invoice parser.

Covers three XML schema families (bare factura/notaCredito, autorizacion wrap,
SOAP envelope), motivo classification, and a corpus regression test over every
XML currently cached in extra/invoices/.
"""
import unittest
from pathlib import Path

from gmail_sync.invoice import (
    Invoice,
    InvoiceLine,
    InvoiceTax,
    classify_motivo,
    parse_sri_factura,
    _unwrap_to_root,
    _local_name,
)

CORPUS_DIR = Path(__file__).resolve().parent.parent / "extra" / "invoices"


# --- Crafted fixtures for unwrap unit tests --------------------------------

BARE_FACTURA = b"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
  <infoTributaria>
    <razonSocial>TEST VENDOR S.A.</razonSocial>
    <nombreComercial>TEST</nombreComercial>
    <ruc>1234567890001</ruc>
    <claveAcceso>ABC123</claveAcceso>
    <estab>042</estab><ptoEmi>916</ptoEmi><secuencial>000000003</secuencial>
  </infoTributaria>
  <infoFactura>
    <fechaEmision>15/03/2026</fechaEmision>
    <dirEstablecimiento>CALLE EJE LONG. CACHA XV y GIOVANNI</dirEstablecimiento>
    <totalSinImpuestos>10.00</totalSinImpuestos>
    <totalDescuento>0.00</totalDescuento>
    <propina>0.00</propina>
    <importeTotal>11.50</importeTotal>
    <moneda>DOLAR</moneda>
    <totalConImpuestos>
      <totalImpuesto>
        <codigo>2</codigo><codigoPorcentaje>4</codigoPorcentaje>
        <baseImponible>10.00</baseImponible><valor>1.50</valor>
      </totalImpuesto>
    </totalConImpuestos>
    <pagos><pago><formaPago>19</formaPago><total>11.50</total></pago></pagos>
  </infoFactura>
  <detalles>
    <detalle>
      <codigoPrincipal>SKU1</codigoPrincipal>
      <descripcion>TEST ITEM A</descripcion>
      <cantidad>2.0</cantidad>
      <precioUnitario>5.00</precioUnitario>
      <descuento>0.00</descuento>
      <precioTotalSinImpuesto>10.00</precioTotalSinImpuesto>
      <impuestos>
        <impuesto>
          <codigo>2</codigo><codigoPorcentaje>4</codigoPorcentaje>
          <tarifa>15.00</tarifa><baseImponible>10.00</baseImponible><valor>1.50</valor>
        </impuesto>
      </impuestos>
    </detalle>
  </detalles>
  <infoAdicional>
    <campoAdicional nombre="Lugar Venta">CORAL CARAPUNGO</campoAdicional>
    <campoAdicional nombre="Deducible Alimentacion">4.46</campoAdicional>
    <campoAdicional nombre="Codigo">9999999</campoAdicional>
  </infoAdicional>
</factura>"""

BARE_NOTA_CREDITO = b"""<?xml version="1.0" encoding="UTF-8"?>
<notaCredito id="comprobante" version="1.1.0">
  <infoTributaria>
    <razonSocial>CORPORACION FAVORITA C.A.</razonSocial>
    <ruc>1790016919001</ruc>
    <claveAcceso>NC123</claveAcceso>
    <estab>001</estab><ptoEmi>101</ptoEmi><secuencial>000099999</secuencial>
  </infoTributaria>
  <infoNotaCredito>
    <fechaEmision>08/08/2025</fechaEmision>
    <codDocModificado>01</codDocModificado>
    <numDocModificado>198-108-000221583</numDocModificado>
    <fechaEmisionDocSustento>08/08/2025</fechaEmisionDocSustento>
    <totalSinImpuestos>0.55</totalSinImpuestos>
    <valorModificacion>0.63</valorModificacion>
    <motivo>Descuento Plan de recompensas MaxiRecargas</motivo>
  </infoNotaCredito>
  <detalles>
    <detalle>
      <descripcion>MAXIRECARGAS TARIFA 15</descripcion>
      <cantidad>1.0</cantidad>
      <precioUnitario>0.55</precioUnitario>
      <precioTotalSinImpuesto>0.55</precioTotalSinImpuesto>
    </detalle>
  </detalles>
</notaCredito>"""

AUTORIZACION_WRAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<autorizacion>
  <estado>AUTORIZADO</estado>
  <numeroAutorizacion>AUTH999</numeroAutorizacion>
  <fechaAutorizacion>2026-03-15T10:00:00-05:00</fechaAutorizacion>
  <comprobante><![CDATA[""" + BARE_FACTURA + b"""]]></comprobante>
</autorizacion>"""

SOAP_ENVELOPE = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ws:autorizacionComprobanteResponse xmlns:ws="http://ec.gob.sri.ws.autorizacion">
      <RespuestaAutorizacionComprobante>
        <claveAccesoConsultada>XYZ</claveAccesoConsultada>
        <numeroComprobantes>1</numeroComprobantes>
        <autorizaciones>
          <autorizacion>
            <estado>AUTORIZADO</estado>
            <comprobante><![CDATA[""" + BARE_FACTURA + b"""]]></comprobante>
          </autorizacion>
        </autorizaciones>
      </RespuestaAutorizacionComprobante>
    </ws:autorizacionComprobanteResponse>
  </soap:Body>
</soap:Envelope>"""


# --- Tests -----------------------------------------------------------------

class TestUnwrap(unittest.TestCase):
    def test_bare_factura(self):
        root = _unwrap_to_root(BARE_FACTURA)
        self.assertIsNotNone(root)
        self.assertEqual(_local_name(root.tag), "factura")

    def test_bare_nota_credito(self):
        root = _unwrap_to_root(BARE_NOTA_CREDITO)
        self.assertIsNotNone(root)
        self.assertEqual(_local_name(root.tag), "notaCredito")

    def test_autorizacion_wrap(self):
        root = _unwrap_to_root(AUTORIZACION_WRAP)
        self.assertIsNotNone(root)
        self.assertEqual(_local_name(root.tag), "factura")

    def test_soap_envelope(self):
        root = _unwrap_to_root(SOAP_ENVELOPE)
        self.assertIsNotNone(root)
        self.assertEqual(_local_name(root.tag), "factura")

    def test_garbage_returns_none(self):
        self.assertIsNone(_unwrap_to_root(b"not xml at all"))


class TestParseFactura(unittest.TestCase):
    def test_fields(self):
        inv = parse_sri_factura(BARE_FACTURA)
        self.assertIsNotNone(inv)
        self.assertEqual(inv.doc_type, "factura")
        self.assertEqual(inv.vendor, "TEST")  # trade name preferred
        self.assertEqual(inv.ruc, "1234567890001")
        self.assertEqual(inv.invoice_number, "042-916-000000003")
        self.assertEqual(inv.clave_acceso, "ABC123")
        self.assertAlmostEqual(inv.total, 11.50)
        self.assertAlmostEqual(inv.subtotal_sin_impuesto, 10.00)
        self.assertEqual(len(inv.lines), 1)
        self.assertEqual(inv.lines[0].sku, "SKU1")
        self.assertEqual(inv.lines[0].description, "TEST ITEM A")
        self.assertAlmostEqual(inv.lines[0].quantity, 2.0)
        self.assertAlmostEqual(inv.lines[0].unit_price, 5.00)
        self.assertAlmostEqual(inv.lines[0].line_tax, 1.50)
        self.assertAlmostEqual(inv.lines[0].tax_rate, 15.0)
        self.assertEqual(len(inv.taxes), 1)
        self.assertEqual(inv.taxes[0].tax_code, 2)
        self.assertAlmostEqual(inv.taxes[0].rate_pct, 15.0)

    def test_autorizacion_wrap_same_fields(self):
        inv = parse_sri_factura(AUTORIZACION_WRAP)
        self.assertIsNotNone(inv)
        self.assertEqual(inv.invoice_number, "042-916-000000003")
        self.assertAlmostEqual(inv.total, 11.50)

    def test_soap_wrap_same_fields(self):
        inv = parse_sri_factura(SOAP_ENVELOPE)
        self.assertIsNotNone(inv)
        self.assertEqual(inv.invoice_number, "042-916-000000003")
        self.assertAlmostEqual(inv.total, 11.50)

    def test_merchant_and_store_fields(self):
        """New extended fields: merchant_name, establishment_code, store_address,
        forma_pago, deducible_alimentacion."""
        inv = parse_sri_factura(BARE_FACTURA)
        self.assertEqual(inv.merchant_name, "CORAL CARAPUNGO")
        self.assertEqual(inv.establishment_code, "042")
        self.assertEqual(inv.store_address, "CALLE EJE LONG. CACHA XV y GIOVANNI")
        self.assertEqual(inv.forma_pago, 19)  # tarjeta de crédito
        self.assertAlmostEqual(inv.deducible_alimentacion, 4.46)

    def test_forma_pago_zero_when_missing(self):
        """If infoFactura/pagos is absent, forma_pago stays 0."""
        xml = BARE_FACTURA.replace(
            b"<pagos><pago><formaPago>19</formaPago><total>11.50</total></pago></pagos>",
            b"",
        )
        inv = parse_sri_factura(xml)
        self.assertEqual(inv.forma_pago, 0)


class TestParseNotaCredito(unittest.TestCase):
    def test_fields(self):
        inv = parse_sri_factura(BARE_NOTA_CREDITO)
        self.assertIsNotNone(inv)
        self.assertEqual(inv.doc_type, "nota_credito")
        self.assertEqual(inv.invoice_number, "001-101-000099999")
        self.assertAlmostEqual(inv.total, 0.63)  # valorModificacion, not importeTotal
        self.assertEqual(inv.refund_of, "198-108-000221583")
        self.assertEqual(inv.motivo, "Descuento Plan de recompensas MaxiRecargas")
        self.assertEqual(inv.motivo_category, "loyalty")


class TestClassifyMotivo(unittest.TestCase):
    CASES = [
        ("Descuento Plan de recompensas MaxiRecargas", "loyalty"),
        ("Plan de recompensas Cash Back Titán", "loyalty"),
        ("DEVOLUCION", "refund"),
        ("Devolución parcial de producto", "refund"),
        ("Anulación de factura duplicada", "refund"),
        ("Ajuste administrativo", "other"),
        ("", "other"),
    ]

    def test_all_cases(self):
        for motivo, expected in self.CASES:
            with self.subTest(motivo=motivo):
                self.assertEqual(classify_motivo(motivo), expected)


class TestCorpus(unittest.TestCase):
    """Regression test: every XML in extra/invoices/ should parse successfully
    and its line subtotals should sum close to its declared invoice subtotal."""

    @classmethod
    def setUpClass(cls):
        cls.xmls = sorted(CORPUS_DIR.glob("*.xml"))
        if not cls.xmls:
            raise unittest.SkipTest(f"No XMLs in {CORPUS_DIR}")

    def test_parse_success_rate(self):
        parsed = 0
        failed: list[str] = []
        for p in self.xmls:
            inv = parse_sri_factura(p.read_bytes())
            if inv is not None:
                parsed += 1
            else:
                failed.append(p.name)
        total = len(self.xmls)
        rate = parsed / total
        self.assertGreaterEqual(
            rate, 0.95,
            f"Parse rate {parsed}/{total} ({rate:.1%}) below 95%; failed: {failed[:5]}"
        )

    def test_line_subtotal_consistency(self):
        """For facturas: sum(line.total) ≈ invoice.subtotal_sin_impuesto."""
        for p in self.xmls:
            inv = parse_sri_factura(p.read_bytes())
            if inv is None or inv.doc_type != "factura":
                continue
            with self.subTest(file=p.name):
                sum_lines = sum(ln.total for ln in inv.lines)
                diff = abs(sum_lines - inv.subtotal_sin_impuesto)
                # Allow for invoices that apply a header-level descuento;
                # reconciled value = subtotal + totalDescuento.
                alt = abs(sum_lines - (inv.subtotal_sin_impuesto + inv.total_descuento))
                self.assertTrue(
                    diff < 0.05 or alt < 0.05,
                    f"{p.name}: sum(lines)={sum_lines:.2f} vs subtotal={inv.subtotal_sin_impuesto:.2f} "
                    f"(+desc {inv.total_descuento:.2f})"
                )

    def test_doc_types_classified(self):
        """Every parsed invoice has a valid doc_type and (for NC) a motivo_category."""
        for p in self.xmls:
            inv = parse_sri_factura(p.read_bytes())
            if inv is None:
                continue
            with self.subTest(file=p.name):
                self.assertIn(inv.doc_type, ("factura", "nota_credito"))
                if inv.doc_type == "nota_credito":
                    self.assertIn(inv.motivo_category, ("refund", "loyalty", "other"))


if __name__ == "__main__":
    unittest.main()

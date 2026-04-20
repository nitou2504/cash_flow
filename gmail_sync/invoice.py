"""Ecuadorian SRI electronic invoice (XML) parser + cache-aware fetcher.

Handles three observed XML schema families:
    - Family 1 (~94%): bare <factura> or <notaCredito> root
    - Family 2 (~1%):  <autorizacion>/<comprobante> CDATA wrap
    - Family 3 (~5%):  {soap:Envelope} or {sri:RespuestaAutorizacion}
                       nesting autorizaciones/autorizacion/comprobante CDATA
Supports both facturas (codDoc=01) and notas de crédito (codDoc=04), classifying
NC motivos as refund / loyalty / other — loyalty NCs are Favorita rewards, not
real refunds.
"""
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .client import GmailClient, extract_text, header, list_attachments

CACHE_DIR = Path(__file__).resolve().parent.parent / "extra" / "invoices"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# --- Dataclasses -----------------------------------------------------------

@dataclass
class InvoiceTax:
    """Invoice-level tax summary row (totalConImpuestos/totalImpuesto)."""
    tax_code: int          # SRI codigo: 2=IVA, 3=ICE, 5=IRBPNR
    rate_code: int         # SRI codigoPorcentaje
    rate_pct: float        # percentage derived from rate_code
    base_imponible: float
    tax_value: float


@dataclass
class InvoiceLine:
    description: str
    quantity: float
    total: float                 # precioTotalSinImpuesto (post-discount, pre-tax)
    sku: str = ""                # codigoPrincipal
    sku_aux: str = ""            # codigoAuxiliar
    unit_price: float = 0.0      # precioUnitario (pre-discount)
    discount: float = 0.0
    line_tax: float = 0.0        # sum of per-line impuesto.valor
    tax_rate: float = 0.0        # dominant tarifa, e.g. 15.0


@dataclass
class Invoice:
    vendor: str
    issue_date: date | None
    total: float
    lines: list[InvoiceLine] = field(default_factory=list)
    msg_id: str = ""
    subject: str = ""
    pdf_filename: str = ""
    pdf_attachment_id: str = ""
    # Extended fields
    doc_type: str = "factura"            # 'factura' | 'nota_credito'
    invoice_number: str = ""             # estab-ptoEmi-secuencial
    clave_acceso: str = ""
    ruc: str = ""
    vendor_trade_name: str = ""
    subtotal_sin_impuesto: float = 0.0
    total_descuento: float = 0.0
    propina: float = 0.0
    currency: str = "USD"
    refund_of: str = ""                  # NC: numDocModificado
    refund_of_issue_date: date | None = None
    motivo: str = ""                     # NC: motivo (reason text)
    motivo_category: str = ""            # 'refund' | 'loyalty' | 'other'
    taxes: list[InvoiceTax] = field(default_factory=list)
    # Merchant / store identification + misc XML-derived metadata
    merchant_name: str = ""              # campoAdicional "Lugar Venta" / synonyms
    establishment_code: str = ""         # <estab> (e.g. 042 = Coral; 031/198 = Favorita stores)
    store_address: str = ""              # <dirEstablecimiento>
    forma_pago: int = 0                  # SRI code; 0 = unknown / not present
    deducible_alimentacion: float = 0.0  # campoAdicional — Ecuadorian IRS meal deduction
    # Email metadata populated at ingest time
    email_subject: str = ""
    email_from: str = ""


# --- Low-level helpers -----------------------------------------------------

def _text(el) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _to_float(s) -> float:
    if not s:
        return 0.0
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _to_int(s) -> int:
    if not s:
        return 0
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        # "18/04/2026"
        d, m, y = s.split("/")
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _parse_xml_str(xml_bytes: bytes) -> ET.Element | None:
    # Some invoices declare UTF-8 but contain Latin-1 bytes (e.g. "LIMÓN"). Fall back.
    try:
        text = xml_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = xml_bytes.decode("latin-1")
    # Strip XML declaration — ET.fromstring dislikes encoding decls on str input.
    text = re.sub(r"^\s*<\?xml[^?]*\?>", "", text).strip()
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


def _local_name(tag: str) -> str:
    # Strip XML namespace: "{http://...}RespuestaAutorizacion" → "RespuestaAutorizacion"
    return tag.split("}")[-1] if tag else ""


def _find_local(parent, name: str):
    """First direct child whose local-name equals `name`."""
    if parent is None:
        return None
    for child in parent:
        if _local_name(child.tag) == name:
            return child
    return None


def _findall_local(parent, name: str) -> list:
    """All direct children whose local-name equals `name`."""
    if parent is None:
        return []
    return [c for c in parent if _local_name(c.tag) == name]


# SRI codigoPorcentaje → rate percentage mapping
RATE_CODE_TO_PCT = {
    0: 0.0,    # 0%
    2: 12.0,   # 12% (pre-2024)
    3: 14.0,   # 14%
    4: 15.0,   # 15% (current since 2024)
    5: 5.0,    # 5%
    6: 0.0,    # no objeto de impuesto
    7: 0.0,    # exento
    8: 8.0,    # 8%
}


def _rate_code_to_pct(code: int) -> float:
    return RATE_CODE_TO_PCT.get(code, 0.0)


# SRI formaPago codes (infoFactura/pagos/pago/formaPago)
FORMA_PAGO_LABELS = {
    1:  "Sin sistema financiero",      # cash / direct
    15: "Compensación de deudas",
    16: "Tarjeta de débito",
    17: "Dinero electrónico",
    18: "Tarjeta prepago",
    19: "Tarjeta de crédito",
    20: "Otros (sistema financiero)",
    21: "Endoso de títulos",
}


def forma_pago_label(code: int) -> str:
    return FORMA_PAGO_LABELS.get(code, "")


# Free-form campoAdicional keys (normalized to lowercase) that indicate the
# point-of-sale / store name. Different vendors label it differently.
_MERCHANT_CAMPO_KEYS = {
    "lugar venta", "lugar de venta",
    "sucursal", "nombre sucursal", "nombre_sucursal",
    "punto de venta", "punto venta", "pdv",
    "tienda", "establecimiento", "local",
}

# campoAdicional keys that carry the IRS meal-deduction subtotal.
_DEDUCIBLE_CAMPO_KEYS = {
    "deducible alimentacion", "deducible alimentación",
}


def _campos_adicionales(factura_or_nc) -> dict[str, str]:
    """Return {normalized_key: raw_value} for all <campoAdicional> entries."""
    out: dict[str, str] = {}
    info_ad = _find_local(factura_or_nc, "infoAdicional")
    if info_ad is None:
        return out
    for c in _findall_local(info_ad, "campoAdicional"):
        name = (c.attrib.get("nombre") or "").strip().lower()
        if name:
            out[name] = (c.text or "").strip()
    return out


def _extract_merchant_name(campos: dict[str, str]) -> str:
    for key in _MERCHANT_CAMPO_KEYS:
        v = campos.get(key)
        if v:
            return v
    return ""


def _extract_deducible(campos: dict[str, str]) -> float:
    for key in _DEDUCIBLE_CAMPO_KEYS:
        v = campos.get(key)
        if v:
            return _to_float(v)
    return 0.0


def _extract_first_forma_pago(info_fact) -> int:
    """SRI invoice may declare multiple <pago>s; take the first."""
    pagos = _find_local(info_fact, "pagos")
    if pagos is None:
        return 0
    first = _find_local(pagos, "pago")
    if first is None:
        return 0
    return _to_int(_text(_find_local(first, "formaPago")))


# --- Unwrap: descend through SOAP/autorizacion wrappers --------------------

def _unwrap_to_root(xml_bytes: bytes) -> ET.Element | None:
    """Walk through SOAP envelopes, RespuestaAutorizacion, autorizacion and
    <comprobante> CDATA payloads until reaching a <factura> or <notaCredito>
    element. Returns that element, or None if not found."""
    root = _parse_xml_str(xml_bytes)
    if root is None:
        return None
    return _descend(root)


def _descend(el: ET.Element) -> ET.Element | None:
    """Recursively search for the first factura/notaCredito descendant,
    parsing <comprobante> text payloads as nested XML along the way."""
    name = _local_name(el.tag)
    if name in ("factura", "notaCredito"):
        return el
    # A <comprobante> element in SRI responses contains the inner document as
    # text (CDATA is transparent to ET.text). Parse that and recurse.
    if name == "comprobante" and el.text and el.text.strip():
        inner = _parse_xml_str(el.text.encode("utf-8"))
        if inner is not None:
            found = _descend(inner)
            if found is not None:
                return found
    for child in el:
        found = _descend(child)
        if found is not None:
            return found
    return None


# --- Motivo classifier for nota de crédito ---------------------------------

_MOTIVO_REFUND_RE = re.compile(r"devoluci[óo]n|anulaci[óo]n", re.IGNORECASE)
_MOTIVO_LOYALTY_RE = re.compile(
    r"plan\s+de\s+recompensas|cash\s+back|maxirecargas", re.IGNORECASE
)


def classify_motivo(motivo: str) -> str:
    """Classify a nota-de-crédito motivo string.

    Returns 'refund' (real product return / anulación), 'loyalty' (Favorita
    rewards / cash back accrual — NOT a real refund), or 'other'.
    """
    if not motivo:
        return "other"
    if _MOTIVO_REFUND_RE.search(motivo):
        return "refund"
    if _MOTIVO_LOYALTY_RE.search(motivo):
        return "loyalty"
    return "other"


# --- Shared extraction (works for both factura and notaCredito) ------------

_JUNK_TRADE_NAMES = {"", "false", "none", "null", "n/a", "na", "-", "--"}


def _clean_trade_name(raw: str) -> str:
    """Some vendors (e.g. Comquel) fill <nombreComercial> with literal 'False'
    or other sentinel placeholders. Treat those as empty."""
    if not raw:
        return ""
    return "" if raw.strip().lower() in _JUNK_TRADE_NAMES else raw


def _extract_info_tributaria(info_trib) -> dict:
    if info_trib is None:
        return {"vendor": "?", "trade_name": "", "razon_social": "",
                "ruc": "", "invoice_number": "", "clave": "", "estab": ""}
    trade = _clean_trade_name(_text(_find_local(info_trib, "nombreComercial")))
    razon = _text(_find_local(info_trib, "razonSocial"))
    estab = _text(_find_local(info_trib, "estab"))
    pto = _text(_find_local(info_trib, "ptoEmi"))
    sec = _text(_find_local(info_trib, "secuencial"))
    return {
        "vendor": trade or razon or "?",
        "trade_name": trade,
        "razon_social": razon,
        "ruc": _text(_find_local(info_trib, "ruc")),
        "invoice_number": f"{estab}-{pto}-{sec}" if (estab and pto and sec) else "",
        "clave": _text(_find_local(info_trib, "claveAcceso")),
        "estab": estab,
    }


def _extract_lines(detalles) -> list[InvoiceLine]:
    lines: list[InvoiceLine] = []
    if detalles is None:
        return lines
    for d in _findall_local(detalles, "detalle"):
        impuestos_el = _find_local(d, "impuestos")
        imps = _findall_local(impuestos_el, "impuesto")
        line_tax = sum(_to_float(_text(_find_local(i, "valor"))) for i in imps)
        tax_rates = [_to_float(_text(_find_local(i, "tarifa"))) for i in imps]
        tax_rate = max(tax_rates, default=0.0)
        lines.append(InvoiceLine(
            description=_text(_find_local(d, "descripcion")),
            quantity=_to_float(_text(_find_local(d, "cantidad"))),
            total=_to_float(_text(_find_local(d, "precioTotalSinImpuesto"))),
            sku=_text(_find_local(d, "codigoPrincipal")),
            sku_aux=_text(_find_local(d, "codigoAuxiliar")),
            unit_price=_to_float(_text(_find_local(d, "precioUnitario"))),
            discount=_to_float(_text(_find_local(d, "descuento"))),
            line_tax=line_tax,
            tax_rate=tax_rate,
        ))
    return lines


def _extract_taxes(info_parent) -> list[InvoiceTax]:
    """Extract totalConImpuestos summary from infoFactura or infoNotaCredito."""
    taxes: list[InvoiceTax] = []
    tci = _find_local(info_parent, "totalConImpuestos")
    if tci is None:
        return taxes
    for ti in _findall_local(tci, "totalImpuesto"):
        rate_code = _to_int(_text(_find_local(ti, "codigoPorcentaje")))
        taxes.append(InvoiceTax(
            tax_code=_to_int(_text(_find_local(ti, "codigo"))),
            rate_code=rate_code,
            rate_pct=_rate_code_to_pct(rate_code),
            base_imponible=_to_float(_text(_find_local(ti, "baseImponible"))),
            tax_value=_to_float(_text(_find_local(ti, "valor"))),
        ))
    return taxes


# --- Document-type parsers -------------------------------------------------

def _parse_factura(factura: ET.Element) -> Invoice | None:
    info_trib = _find_local(factura, "infoTributaria")
    info_fact = _find_local(factura, "infoFactura")
    detalles = _find_local(factura, "detalles")
    if info_fact is None:
        return None
    trib = _extract_info_tributaria(info_trib)
    campos = _campos_adicionales(factura)
    return Invoice(
        vendor=trib["vendor"],
        issue_date=_parse_date(_text(_find_local(info_fact, "fechaEmision"))),
        total=_to_float(_text(_find_local(info_fact, "importeTotal"))),
        lines=_extract_lines(detalles),
        doc_type="factura",
        invoice_number=trib["invoice_number"],
        clave_acceso=trib["clave"],
        ruc=trib["ruc"],
        vendor_trade_name=trib["trade_name"],
        subtotal_sin_impuesto=_to_float(_text(_find_local(info_fact, "totalSinImpuestos"))),
        total_descuento=_to_float(_text(_find_local(info_fact, "totalDescuento"))),
        propina=_to_float(_text(_find_local(info_fact, "propina"))),
        currency=_text(_find_local(info_fact, "moneda")) or "USD",
        taxes=_extract_taxes(info_fact),
        merchant_name=_extract_merchant_name(campos),
        establishment_code=trib["estab"],
        store_address=_text(_find_local(info_fact, "dirEstablecimiento")),
        forma_pago=_extract_first_forma_pago(info_fact),
        deducible_alimentacion=_extract_deducible(campos),
    )


def _parse_nota_credito(nc: ET.Element) -> Invoice | None:
    info_trib = _find_local(nc, "infoTributaria")
    info_nc = _find_local(nc, "infoNotaCredito")
    detalles = _find_local(nc, "detalles")
    if info_nc is None:
        return None
    trib = _extract_info_tributaria(info_trib)
    campos = _campos_adicionales(nc)
    motivo = _text(_find_local(info_nc, "motivo"))
    return Invoice(
        vendor=trib["vendor"],
        issue_date=_parse_date(_text(_find_local(info_nc, "fechaEmision"))),
        total=_to_float(_text(_find_local(info_nc, "valorModificacion"))),
        lines=_extract_lines(detalles),
        doc_type="nota_credito",
        invoice_number=trib["invoice_number"],
        clave_acceso=trib["clave"],
        ruc=trib["ruc"],
        vendor_trade_name=trib["trade_name"],
        subtotal_sin_impuesto=_to_float(_text(_find_local(info_nc, "totalSinImpuestos"))),
        currency=_text(_find_local(info_nc, "moneda")) or "USD",
        refund_of=_text(_find_local(info_nc, "numDocModificado")),
        refund_of_issue_date=_parse_date(_text(_find_local(info_nc, "fechaEmisionDocSustento"))),
        motivo=motivo,
        motivo_category=classify_motivo(motivo),
        taxes=_extract_taxes(info_nc),
        merchant_name=_extract_merchant_name(campos),
        establishment_code=trib["estab"],
        store_address=_text(_find_local(info_nc, "dirEstablecimiento")),
        # NC has no <pagos>; leave forma_pago=0
        deducible_alimentacion=_extract_deducible(campos),
    )


def parse_sri_factura(xml_bytes: bytes) -> Invoice | None:
    """Parse an SRI e-invoice XML (factura or notaCredito), handling all
    three observed schema wrappings. Returns None on unrecognized input."""
    root = _unwrap_to_root(xml_bytes)
    if root is None:
        return None
    name = _local_name(root.tag)
    if name == "factura":
        return _parse_factura(root)
    if name == "notaCredito":
        return _parse_nota_credito(root)
    return None


# --- Gmail fetch + disk cache ----------------------------------------------

def _cached_xml_path(filename: str) -> Path:
    # Basename only, avoid path traversal from email filenames.
    return CACHE_DIR / Path(filename).name


def fetch_invoices(gc: GmailClient, label_id: str, query: str) -> list[Invoice]:
    """Download+parse all XML-bearing Facturas matching the query. Disk-cached.

    Supports XMLs attached directly and XMLs nested inside ZIP attachments
    (Seed Billing pattern)."""
    invoices: list[Invoice] = []
    ids = list(gc.iter_message_ids(label_ids=[label_id], query=query))
    print(f"  Facturas: {len(ids)} messages in range")

    for mid in ids:
        msg = gc.get_message(mid)
        subject = header(msg, "Subject") or ""
        atts = list_attachments(msg)
        xml_atts = [a for a in atts if a["filename"].lower().endswith(".xml")]
        zip_atts = [a for a in atts if a["filename"].lower().endswith(".zip")]
        pdf_atts = [a for a in atts if a["filename"].lower().endswith(".pdf")]
        pdf_filename = pdf_atts[0]["filename"] if pdf_atts else ""
        pdf_att_id = pdf_atts[0]["attachment_id"] if pdf_atts else ""

        # Collect (xml_name, xml_bytes) pairs from both direct XMLs and inside ZIPs.
        xml_sources: list[tuple[str, bytes]] = []
        for att in xml_atts:
            cache_path = _cached_xml_path(att["filename"])
            if cache_path.exists():
                xml_sources.append((att["filename"], cache_path.read_bytes()))
            else:
                data = gc.get_attachment(mid, att["attachment_id"])
                cache_path.write_bytes(data)
                xml_sources.append((att["filename"], data))
        for att in zip_atts:
            zip_cache = _cached_xml_path(att["filename"])
            if zip_cache.exists():
                zip_data = zip_cache.read_bytes()
            else:
                zip_data = gc.get_attachment(mid, att["attachment_id"])
                zip_cache.write_bytes(zip_data)
            try:
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".xml"):
                            inner = zf.read(name)
                            inner_cache = _cached_xml_path(name)
                            inner_cache.write_bytes(inner)
                            xml_sources.append((name, inner))
            except zipfile.BadZipFile:
                pass

        if not xml_sources:
            invoices.append(
                Invoice(
                    vendor=(header(msg, "From") or "").split("<")[0].strip() or "?",
                    issue_date=None,
                    total=0.0,
                    lines=[],
                    msg_id=mid,
                    subject=subject,
                    pdf_filename=pdf_filename,
                    pdf_attachment_id=pdf_att_id,
                )
            )
            continue

        for _name, data in xml_sources:
            inv = parse_sri_factura(data)
            if inv:
                inv.msg_id = mid
                inv.subject = subject
                inv.pdf_filename = pdf_filename
                inv.pdf_attachment_id = pdf_att_id
                invoices.append(inv)

    return invoices


def find_matching_invoice(invoices: list[Invoice], purchase_date: date, amount: float) -> Invoice | None:
    """Find an invoice with matching total within ±1 day of the purchase date."""
    best = None
    best_day_diff = None
    for inv in invoices:
        if abs(inv.total - amount) > 0.01:
            continue
        if inv.issue_date is None:
            continue
        diff = abs((inv.issue_date - purchase_date).days)
        if diff > 2:
            continue
        if best_day_diff is None or diff < best_day_diff:
            best, best_day_diff = inv, diff
    return best

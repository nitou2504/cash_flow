"""Extract transaction facts from bank consumo notification emails."""
import re
from dataclasses import dataclass, field
from datetime import datetime

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


@dataclass
class EmailTxn:
    msg_id: str
    bank: str          # "Diners" / "Pichincha" / "Produbanco"
    account: str       # matches DB account name
    purchased_at: datetime
    amount: float      # positive
    merchant: str
    card_last: str
    subject: str
    # Cash-transfer-specific (None for CC consumos)
    beneficiary: str | None = None
    destination_account: str | None = None
    concepto: str | None = None


@dataclass
class ParseWarning:
    msg_id: str
    label: str
    subject: str
    code: str       # e.g. "foreign_currency", "partial_match", "reversal"
    detail: str


# Accumulates warnings during a parse session; caller should reset before each ingest run.
_warnings: list[ParseWarning] = []


def get_warnings() -> list[ParseWarning]:
    return list(_warnings)


def clear_warnings() -> None:
    _warnings.clear()


def _warn(msg_id: str, label: str, subject: str, code: str, detail: str) -> None:
    _warnings.append(ParseWarning(msg_id, label, subject, code, detail))


# Detect foreign currency in Produbanco emails
_FOREIGN_CURRENCY_RE = re.compile(r"Valor:\s*([A-Z]{3})\s", re.IGNORECASE)

# Detect "looks like a consumo" heuristics per bank
_SIGNATURE_PATTERNS: dict[str, list[re.Pattern]] = {
    "Consumos/Pichincha": [re.compile(r"Valor", re.I), re.compile(r"Establecimiento", re.I)],
    "Consumos/Diners": [re.compile(r"Valor", re.I), re.compile(r"Establecimiento", re.I)],
    "Consumos/Produbanco": [re.compile(r"Fecha y Hora:", re.I), re.compile(r"Establecimiento:", re.I)],
    "Consumos/Cash": [re.compile(r"Monto:", re.I), re.compile(r"Cuenta de origen:", re.I)],
}


def diagnose_parse_failure(msg_id: str, label: str, subject: str, text: str) -> str:
    """When a parser returns None, figure out why and emit warnings.
    Returns a reason string for the unparsed_consumos table."""
    # Reversals (Produbanco)
    if "Reverso" in subject or "reverso de un consumo" in text.lower():
        _warn(msg_id, label, subject, "reversal", "Reversal/refund email — skipped by design")
        return "reversal"

    # Foreign currency
    m = _FOREIGN_CURRENCY_RE.search(text)
    if m and m.group(1).upper() != "USD":
        currency = m.group(1).upper()
        _warn(msg_id, label, subject, "foreign_currency",
              f"Foreign currency {currency} — parser expects USD")
        return f"foreign_currency:{currency}"

    # Check which signature patterns matched — partial = format may have changed
    sigs = _SIGNATURE_PATTERNS.get(label, [])
    matched_sigs = [p.pattern for p in sigs if p.search(text)]
    if matched_sigs and len(matched_sigs) < len(sigs):
        missing = [p.pattern for p in sigs if not p.search(text)]
        _warn(msg_id, label, subject, "partial_match",
              f"Found {matched_sigs} but missing {missing} — possible format change")
        return "partial_match"

    if not matched_sigs:
        _warn(msg_id, label, subject, "no_match",
              "No expected fields found — email may not be a consumo or format changed entirely")
        return "unrecognized"

    _warn(msg_id, label, subject, "parse_failed",
          "All signature fields present but parser returned None — regex may need updating")
    return "parse_failed"


def _after_label(text: str, label: str) -> str | None:
    """Return the first non-empty line after a line containing `label`."""
    pattern = re.compile(rf"{re.escape(label)}:?\s*\n+\s*([^\n]+)", re.IGNORECASE)
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _parse_amount(raw: str) -> float:
    # Handles "$ 8,90", "USD 15.01", "13,99", "15.01"
    raw = raw.replace("$", "").replace("USD", "").strip()
    # Heuristic: if both . and , present, the last one is the decimal sep.
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    return float(raw)


def parse_pichincha(msg_id: str, subject: str, text: str) -> EmailTxn | None:
    valor = _after_label(text, "Valor")
    fecha = _after_label(text, "Fecha")
    establ = _after_label(text, "Establecimiento")
    tarjeta = _after_label(text, "Tarjeta usada")
    if not (valor and fecha and establ):
        return None
    dt = datetime.strptime(fecha[:16], "%Y-%m-%d %H:%M")
    return EmailTxn(
        msg_id=msg_id,
        bank="Pichincha",
        account="Visa Pichincha",
        purchased_at=dt,
        amount=_parse_amount(valor),
        merchant=establ.strip(),
        card_last=(tarjeta or "").strip(),
        subject=subject,
    )


def parse_diners(msg_id: str, subject: str, text: str) -> EmailTxn | None:
    valor = _after_label(text, "Valor")
    fecha = _after_label(text, "Fecha")
    establ = _after_label(text, "Establecimiento")
    tarjeta = _after_label(text, "Tarjeta terminada en")
    if not (valor and fecha and establ):
        return None
    dt = datetime.strptime(fecha[:16], "%Y-%m-%d %H:%M")
    return EmailTxn(
        msg_id=msg_id,
        bank="Diners",
        account="Diners",
        purchased_at=dt,
        amount=_parse_amount(valor),
        merchant=establ.strip(),
        card_last=(tarjeta or "").strip(),
        subject=subject,
    )


_PRODU_DATE_ES_RE = re.compile(
    r"Fecha y Hora:\s*(?:\n\s*)?(\d{1,2})/([A-Za-zÁÉÍÓÚáéíóú]+)/(\d{4})\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE,
)
_PRODU_DATE_MDY_RE = re.compile(
    r"Fecha y Hora:\s*(?:\n\s*)?(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})",
)
_PRODU_AMOUNT_RE = re.compile(r"Valor:\s*USD\s*([\d.,]+)", re.IGNORECASE | re.DOTALL)
_PRODU_MERCHANT_RE = re.compile(r"Establecimiento:\s*([^\n]+)", re.IGNORECASE)
_PRODU_CARD_RE = re.compile(r"Visa Produbanco\s+XXX?(\d+)", re.IGNORECASE)


def parse_produbanco(msg_id: str, subject: str, text: str) -> EmailTxn | None:
    # Skip reversals/refunds — different semantic, would double-count.
    if "Reverso" in subject or "reverso de un consumo" in text.lower():
        return None

    # Try Spanish month format first ("4/Abril/2026"), fall back to MM/DD/YYYY.
    m = _PRODU_DATE_ES_RE.search(text)
    if m:
        day, month_es, year, hh, mm = m.groups()
        month = SPANISH_MONTHS.get(month_es.lower())
        if not month:
            return None
    else:
        m = _PRODU_DATE_MDY_RE.search(text)
        if not m:
            return None
        mm_str, dd_str, year, hh, mm = m.groups()
        month, day = int(mm_str), int(dd_str)

    amount_m = _PRODU_AMOUNT_RE.search(text)
    merchant_m = _PRODU_MERCHANT_RE.search(text)
    card_m = _PRODU_CARD_RE.search(text)
    if not (amount_m and merchant_m):
        return None

    dt = datetime(int(year), int(month), int(day), int(hh), int(mm))
    return EmailTxn(
        msg_id=msg_id,
        bank="Produbanco",
        account="Visa Produbanco",
        purchased_at=dt,
        amount=_parse_amount(amount_m.group(1)),
        merchant=merchant_m.group(1).strip(),
        card_last=(card_m.group(1) if card_m else "").strip(),
        subject=subject,
    )


BANK_PARSERS = {
    "Pichincha": parse_pichincha,
    "Diners": parse_diners,
    "Produbanco": parse_produbanco,
}


# --- Cash transfer parser (Pichincha bank transfers from account 1057) ---

_CASH_DEST_RE = re.compile(r"Cuenta acreditada:\s*(?:\*{6}|X{6})(\d{4})")
_CASH_AMOUNT_RE = re.compile(r"Monto:\s*USD\s*([\d.,]+)", re.IGNORECASE)
_CASH_DATE_RE = re.compile(r"Fecha:\s*(\d{2}/\d{2}/\d{4})")
_CASH_CONCEPTO_RE = re.compile(r"Concepto:\s*([^\n\xa0]+)")
_CASH_BENEFICIARY_RE = re.compile(r"Nombre del beneficiario:\s*([^\n\xa0]+)")


def parse_cash(msg_id: str, subject: str, text: str) -> EmailTxn | None:
    amount_m = _CASH_AMOUNT_RE.search(text)
    date_m = _CASH_DATE_RE.search(text)
    if not (amount_m and date_m):
        return None
    dt = datetime.strptime(date_m.group(1), "%d/%m/%Y")
    dest_m = _CASH_DEST_RE.search(text)
    concepto_m = _CASH_CONCEPTO_RE.search(text)
    benef_m = _CASH_BENEFICIARY_RE.search(text)
    concepto = concepto_m.group(1).strip() if concepto_m else ""
    return EmailTxn(
        msg_id=msg_id,
        bank="Pichincha",
        account="Cash",
        purchased_at=dt,
        amount=_parse_amount(amount_m.group(1)),
        merchant=concepto,
        card_last="",
        subject=subject,
        beneficiary=benef_m.group(1).strip() if benef_m else None,
        destination_account=dest_m.group(1).strip() if dest_m else None,
        concepto=concepto,
    )


LABEL_TO_PARSER = {
    "Consumos/Pichincha": ("Pichincha", parse_pichincha),
    "Consumos/Diners": ("Diners", parse_diners),
    "Consumos/Produbanco": ("Produbanco", parse_produbanco),
    "Consumos/Cash": ("Cash", parse_cash),
}

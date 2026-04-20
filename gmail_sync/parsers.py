"""Extract transaction facts from bank consumo notification emails."""
import re
from dataclasses import dataclass
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


def _after_label(text: str, label: str) -> str | None:
    """Return the first non-empty line after a line containing `label`."""
    pattern = re.compile(rf"{re.escape(label)}\s*\n+\s*([^\n]+)", re.IGNORECASE)
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

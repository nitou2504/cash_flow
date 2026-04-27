"""Tests for parse_cash() — Pichincha bank transfer email parser."""
import unittest
from datetime import datetime

from gmail_sync.parsers import parse_cash


BODY_ASTERISK = """Torres Vega Ana Sofia Tu cédula termina en: ******* 7350

TRANSFERENCIA Tu transferencia se realizó con éxito.

Detalle

Cuenta de origen:     ******1057

Cuenta acreditada:     ******6634

Fecha:     24/04/2026

Nombre del beneficiario:     SANCHEZ RUEDA PEDRO JOSE

Monto:     USD 35.00

Concepto:     Mercado y limpieza

Número de documento:     35957815
"""

BODY_XXXXXX = """Torres Vega Ana Sofia

Transferencia
TORRES VEGA ANA SOFIA
Tu transferencia se realizó con éxito.
Detalle
Cuenta de origen:     XXXXXX1057
Cuenta acreditada:     XXXXXX6634
Nombre del beneficiario:     SANCHEZ RUEDA PEDRO JOSE
Monto:     USD 150.00
Fecha:     22/04/2026
Concepto:     Adelanto mayo
"""


class TestParseCash(unittest.TestCase):
    def test_asterisk_masking(self):
        txn = parse_cash("msg1", "NOTIFICACIÓN BANCO PICHINCHA", BODY_ASTERISK)
        assert txn is not None
        assert txn.bank == "Pichincha"
        assert txn.account == "Cash"
        assert txn.amount == 35.00
        assert txn.purchased_at == datetime(2026, 4, 24)
        assert txn.beneficiary == "SANCHEZ RUEDA PEDRO JOSE"
        assert txn.destination_account == "6634"
        assert txn.concepto == "Mercado y limpieza"
        assert txn.merchant == "Mercado y limpieza"

    def test_xxxxxx_masking(self):
        txn = parse_cash("msg2", "NOTIFICACIÓN BANCO PICHINCHA", BODY_XXXXXX)
        assert txn is not None
        assert txn.amount == 150.00
        assert txn.purchased_at == datetime(2026, 4, 22)
        assert txn.destination_account == "6634"
        assert txn.concepto == "Adelanto mayo"

    def test_missing_amount_returns_none(self):
        body = "Fecha:     24/04/2026\nConcepto:     test"
        assert parse_cash("msg3", "test", body) is None

    def test_missing_date_returns_none(self):
        body = "Monto:     USD 10.00\nConcepto:     test"
        assert parse_cash("msg4", "test", body) is None

    def test_card_last_empty_for_cash(self):
        txn = parse_cash("msg5", "test", BODY_ASTERISK)
        assert txn is not None
        assert txn.card_last == ""


if __name__ == "__main__":
    unittest.main()

"""SQLite schema + connection helpers for the invoices store.

Kept separate from `cash_flow.db` on purpose — parsed invoices are bulky
(line items, per-invoice tax buckets) and only needed for invoice-level
queries, not the hot transaction path. Linked later via an optional
`transaction_id` column added through `ensure_schema_upgrades`.
"""
import sqlite3
from sqlite3 import Connection

# Reuse DATE adapter/converter registered in cashflow.database
from cashflow import database as _cashflow_db  # noqa: F401  (import for side effects)


def create_invoice_connection(db_path: str) -> Connection:
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_invoice_tables(conn: Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id                    TEXT,
            doc_type                  TEXT NOT NULL,
            invoice_number            TEXT NOT NULL UNIQUE,
            clave_acceso              TEXT,
            ruc                       TEXT NOT NULL,
            vendor                    TEXT NOT NULL,
            vendor_trade_name         TEXT,
            issue_date                DATE NOT NULL,
            subtotal_sin_impuesto     REAL NOT NULL,
            total_descuento           REAL NOT NULL DEFAULT 0,
            propina                   REAL NOT NULL DEFAULT 0,
            total                     REAL NOT NULL,
            currency                  TEXT NOT NULL DEFAULT 'USD',
            refund_of_invoice_number  TEXT,
            refund_of_issue_date      DATE,
            motivo                    TEXT,
            motivo_category           TEXT,
            merchant_name             TEXT,
            establishment_code        TEXT,
            store_address             TEXT,
            forma_pago                INTEGER,
            deducible_alimentacion    REAL,
            email_subject             TEXT,
            email_from                TEXT,
            xml_path                  TEXT,
            pdf_path                  TEXT,
            ingested_at               TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_lines (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id     INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            line_number    INTEGER NOT NULL,
            sku            TEXT,
            sku_aux        TEXT,
            description    TEXT NOT NULL,
            quantity       REAL NOT NULL,
            unit_price     REAL NOT NULL,
            discount       REAL NOT NULL DEFAULT 0,
            line_subtotal  REAL NOT NULL,
            line_tax       REAL NOT NULL DEFAULT 0,
            line_total     REAL NOT NULL,
            tax_rate       REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_taxes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id      INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            tax_code        INTEGER NOT NULL,
            rate_code       INTEGER NOT NULL,
            rate_pct        REAL NOT NULL,
            base_imponible  REAL NOT NULL,
            tax_value       REAL NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date   ON invoices(issue_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices(vendor)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_ruc    ON invoices(ruc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_refof  ON invoices(refund_of_invoice_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_invoice   ON invoice_lines(invoice_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_sku       ON invoice_lines(sku)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_desc      ON invoice_lines(description)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_taxes_invoice   ON invoice_taxes(invoice_id)")

    # Emails tagged 'Facturas' that we couldn't parse (no XML, failed parse,
    # ZIP without invoice XML, etc.). Kept so periodic runs can skip them and
    # the user can handle them manually later.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unparsed_facturas (
            msg_id       TEXT PRIMARY KEY,
            subject      TEXT,
            from_addr    TEXT,
            received_at  TEXT,
            reason       TEXT NOT NULL,
            notes        TEXT,
            has_pdf      INTEGER NOT NULL DEFAULT 0,
            resolved     INTEGER NOT NULL DEFAULT 0,
            resolved_at  TEXT,
            ingested_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_unparsed_reason   ON unparsed_facturas(reason)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_unparsed_resolved ON unparsed_facturas(resolved)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_estab    ON invoices(establishment_code)")

    ensure_invoice_schema_upgrades(conn)
    conn.commit()


def ensure_invoice_schema_upgrades(conn: Connection) -> None:
    """Apply column additions for DBs created before the columns existed.
    Each ALTER is wrapped in try/except so rerunning is idempotent."""
    cursor = conn.cursor()
    upgrades = [
        "ALTER TABLE invoices ADD COLUMN merchant_name TEXT",
        "ALTER TABLE invoices ADD COLUMN establishment_code TEXT",
        "ALTER TABLE invoices ADD COLUMN store_address TEXT",
        "ALTER TABLE invoices ADD COLUMN forma_pago INTEGER",
        "ALTER TABLE invoices ADD COLUMN deducible_alimentacion REAL",
        "ALTER TABLE invoices ADD COLUMN email_subject TEXT",
        "ALTER TABLE invoices ADD COLUMN email_from TEXT",
    ]
    for sql in upgrades:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()


def initialize_invoices_database(db_path: str = "invoices.db") -> None:
    """Create `invoices.db` + tables if missing."""
    conn = create_invoice_connection(db_path)
    try:
        create_invoice_tables(conn)
    finally:
        conn.close()


def create_test_invoices_db() -> Connection:
    """In-memory SQLite with schema created, for tests."""
    conn = create_invoice_connection(":memory:")
    create_invoice_tables(conn)
    return conn


if __name__ == "__main__":
    from cashflow.config import INVOICES_DB_PATH
    initialize_invoices_database(INVOICES_DB_PATH)
    print(f"Initialized {INVOICES_DB_PATH}")

"""SQLite schema + connection helpers for the consumos store.

Separate from cash_flow.db — stores parsed CC/Cash consumo email
notifications. Linked to invoices.db via matched_invoice_number
(logical cross-DB FK).
"""
import sqlite3
from sqlite3 import Connection

from cashflow import database as _cashflow_db  # noqa: F401  (date adapters)


def create_consumo_connection(db_path: str) -> Connection:
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_consumo_tables(conn: Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consumos (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id                  TEXT NOT NULL UNIQUE,
            bank                    TEXT NOT NULL,
            account                 TEXT NOT NULL,
            purchased_at            TEXT NOT NULL,
            amount                  REAL NOT NULL,
            merchant                TEXT NOT NULL,
            card_last               TEXT,
            subject                 TEXT,
            label                   TEXT NOT NULL,
            beneficiary             TEXT,
            destination_account     TEXT,
            concepto                TEXT,
            matched_invoice_number  TEXT,
            matched_at              TEXT,
            registered_txn_id       INTEGER,
            registered_at           TEXT,
            ingested_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_purchased ON consumos(purchased_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_account   ON consumos(account)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_amount    ON consumos(amount)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_matched   ON consumos(matched_invoice_number)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unparsed_consumos (
            msg_id       TEXT PRIMARY KEY,
            label        TEXT NOT NULL,
            subject      TEXT,
            from_addr    TEXT,
            received_at  TEXT,
            reason       TEXT NOT NULL,
            notes        TEXT,
            resolved     INTEGER NOT NULL DEFAULT 0,
            resolved_at  TEXT,
            ingested_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_unparsed_consumos_reason   ON unparsed_consumos(reason)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_unparsed_consumos_resolved ON unparsed_consumos(resolved)")

    conn.commit()


def initialize_consumos_database(db_path: str = "consumos.db") -> None:
    conn = create_consumo_connection(db_path)
    try:
        create_consumo_tables(conn)
    finally:
        conn.close()


def create_test_consumos_db() -> Connection:
    conn = create_consumo_connection(":memory:")
    create_consumo_tables(conn)
    return conn


if __name__ == "__main__":
    from cashflow.config import CONSUMOS_DB_PATH
    initialize_consumos_database(CONSUMOS_DB_PATH)
    print(f"Initialized {CONSUMOS_DB_PATH}")

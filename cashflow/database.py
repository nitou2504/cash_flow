
import sqlite3
from sqlite3 import Connection
from datetime import date

def adapt_date_iso(d: date):
    """Adapt date to ISO 8601 string format."""
    return d.isoformat()

def convert_date(s: bytes):
    """Convert ISO 8601 string to date object."""
    return date.fromisoformat(s.decode('utf-8'))

# Register the adapter and converter
sqlite3.register_adapter(date, adapt_date_iso)
sqlite3.register_converter("DATE", convert_date)

def create_connection(db_path: str, check_same_thread: bool = True) -> Connection:
    """
    Establishes and returns a connection to the SQLite database file.

    check_same_thread=False is needed by the FastAPI app, where a request's
    dependency setup, handler, and teardown may run on different threadpool
    threads (each request still uses its own connection sequentially).
    """
    conn = sqlite3.connect(
        db_path, detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=check_same_thread,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_tables(conn: Connection):
    """
    Creates the 'accounts' and 'transactions' tables if they do not already exist.
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            account_type TEXT NOT NULL,
            cut_off_day INTEGER,
            payment_day INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            monthly_amount REAL NOT NULL,
            payment_account_id TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            is_budget BOOLEAN NOT NULL DEFAULT 0,
            is_income BOOLEAN NOT NULL DEFAULT 0,
            underspend_behavior TEXT NOT NULL DEFAULT 'keep',
            FOREIGN KEY (payment_account_id) REFERENCES accounts (account_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_created DATE NOT NULL,
            date_payed DATE NOT NULL,
            description TEXT NOT NULL,
            account TEXT,
            amount REAL NOT NULL,
            category TEXT,
            budget TEXT,
            status TEXT NOT NULL,
            origin_id TEXT,
            source TEXT DEFAULT NULL,
            needs_review INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (account) REFERENCES accounts (account_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_input TEXT NOT NULL,
            parsed_json TEXT NOT NULL,
            transaction_ids TEXT,
            source TEXT NOT NULL DEFAULT 'cli',
            timestamp DATE DEFAULT CURRENT_DATE
        )
    """)
    # --- Invoice tables (formerly invoices.db) ---
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_estab  ON invoices(establishment_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_invoice   ON invoice_lines(invoice_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_sku       ON invoice_lines(sku)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lines_desc      ON invoice_lines(description)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_taxes_invoice   ON invoice_taxes(invoice_id)")
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

    # --- Consumo tables (formerly consumos.db) ---
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
            link_source             TEXT,
            linked_at               TEXT,
            ingested_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_purchased ON consumos(purchased_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_account   ON consumos(account)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_amount    ON consumos(amount)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_matched   ON consumos(matched_invoice_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumos_txn       ON consumos(registered_txn_id)")
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_decisions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            consumo_id   INTEGER NOT NULL REFERENCES consumos(id),
            model        TEXT NOT NULL,
            method       TEXT NOT NULL,
            prompt       TEXT NOT NULL,
            response_raw TEXT NOT NULL,
            parsed_json  TEXT,
            category     TEXT,
            description  TEXT,
            decided_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_decisions_consumo ON llm_decisions(consumo_id)")
    ensure_schema_upgrades(conn)
    conn.commit()

def ensure_schema_upgrades(conn: Connection):
    """Apply schema migrations for columns added after initial release."""
    cursor = conn.cursor()
    upgrades = [
        "ALTER TABLE transactions ADD COLUMN source TEXT DEFAULT NULL",
        "ALTER TABLE transactions ADD COLUMN needs_review INTEGER NOT NULL DEFAULT 0",
        # Invoice table columns added post-initial
        "ALTER TABLE invoices ADD COLUMN merchant_name TEXT",
        "ALTER TABLE invoices ADD COLUMN establishment_code TEXT",
        "ALTER TABLE invoices ADD COLUMN store_address TEXT",
        "ALTER TABLE invoices ADD COLUMN forma_pago INTEGER",
        "ALTER TABLE invoices ADD COLUMN deducible_alimentacion REAL",
        "ALTER TABLE invoices ADD COLUMN email_subject TEXT",
        "ALTER TABLE invoices ADD COLUMN email_from TEXT",
        # Consumo columns for transaction linking (replaces transaction_links table)
        "ALTER TABLE consumos ADD COLUMN link_source TEXT",
        "ALTER TABLE consumos ADD COLUMN linked_at TEXT",
    ]
    for sql in upgrades:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    # Migrate transaction_links data into consumos, then drop
    _migrate_transaction_links(cursor)

    cleanup = [
        "UPDATE subscriptions SET category = 'Home Food & Supplies' WHERE category = 'Home Groceries'",
        "UPDATE subscriptions SET category = 'Personal Diet' WHERE category = 'Personal Groceries'",
        "DELETE FROM categories WHERE name IN ('Housing', 'Transportation', 'Home Groceries', 'Personal Groceries')",
        "UPDATE transactions SET category = 'Income' WHERE category = 'income'",
        "UPDATE transactions SET category = 'Others' WHERE category = 'utilities'",
        "UPDATE transactions SET category = 'Others' WHERE category = 'groceries'",
        "UPDATE transactions SET category = 'Others' WHERE category = 'education'",
        "DELETE FROM categories WHERE name IN ('Balance Adjustment', 'Payment Adjustment', 'Budget Release')",
    ]
    for sql in cleanup:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()


def _migrate_transaction_links(cursor):
    """Move transaction_links data into consumos columns, then drop the table."""
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transaction_links'")
        if not cursor.fetchone():
            return
    except sqlite3.OperationalError:
        return

    cursor.execute("""
        UPDATE consumos SET
            link_source = (
                SELECT tl.link_source FROM transaction_links tl
                WHERE tl.consumo_msg_id = consumos.msg_id
            ),
            linked_at = (
                SELECT tl.linked_at FROM transaction_links tl
                WHERE tl.consumo_msg_id = consumos.msg_id
            )
        WHERE consumos.link_source IS NULL
          AND consumos.msg_id IN (SELECT consumo_msg_id FROM transaction_links WHERE consumo_msg_id IS NOT NULL)
    """)
    cursor.execute("DROP TABLE transaction_links")

def insert_mock_data(conn: Connection):
    """
    Populates the 'accounts' table with mock data for demonstration.
    """
    cursor = conn.cursor()
    accounts = [
        ("Cash", "cash", None, None),
        ("Visa Produbanco", "credit_card", 14, 25),
        ("Amex Produbanco", "credit_card", 2, 15)
    ]
    cursor.executemany("INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?)", accounts)
    conn.commit()

def initialize_categories(conn: Connection):
    """
    Populates the 'categories' table with the predefined set of categories.
    Uses INSERT OR IGNORE to safely work with existing databases.
    """
    cursor = conn.cursor()
    categories = [
        ("Dining-Snacks", "Eating out, takeout, coffee, and social food/drinks"),
        ("Family Support", "Financial support for family members"),
        ("Health", "Medical, insurance, and fitness expenses"),
        ("Home", "Rent, mortgage, utilities, and home maintenance"),
        ("Home Food & Supplies", "Food and household items for home"),
        ("Income", "Money received from work or investments"),
        ("Loans", "Money lent to others and repayments received"),
        ("Others", "Miscellaneous or infrequent expenses"),
        ("Personal", "Discretionary spending, entertainment, hobbies, self-care"),
        ("Personal Diet", "Food for personal diet or specific needs"),
        ("Savings", "Funds for savings or investments"),
        ("Sister Education", "Education expenses for sister"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?)", categories)
    conn.commit()

def create_test_db() -> Connection:
    """
    Creates a fully initialized in-memory database for testing.

    Available mock data:

    Accounts:
        - "Cash" (cash, no cut-off/payment days)
        - "Visa Produbanco" (credit_card, cut-off=14, payment=25)
        - "Amex Produbanco" (credit_card, cut-off=2, payment=15)

    Categories:
        Housing, Home Groceries, Personal Groceries, Dining-Snacks,
        Transportation, Health, Personal, Income, Savings, Loans, Others

    Settings:
        - forecast_horizon_months = 6
    """
    conn = create_connection(":memory:")
    create_tables(conn)
    insert_mock_data(conn)
    initialize_categories(conn)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('forecast_horizon_months', '6')")
    conn.commit()
    return conn

def initialize_database(db_path: str = "cash_flow.db"):
    """
    A master function that ensures the database and its tables exist.
    It only populates essential settings, not mock data.
    """
    conn = create_connection(db_path)
    create_tables(conn)

    # Insert default settings
    cursor = conn.cursor()
    settings = [
        ("forecast_horizon_months", "6")
    ]
    cursor.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", settings)

    # Initialize predefined categories
    initialize_categories(conn)

    conn.commit()
    conn.close()

def initialize_database_with_mock_data(db_path: str = "cash_flow.db"):
    """
    A helper function for development and testing that initializes the database
    and populates it with mock accounts.
    """
    initialize_database(db_path)
    conn = create_connection(db_path)
    insert_mock_data(conn)
    conn.close()
    print("Database initialized with mock data.")

def migrate_external_dbs(main_db_path: str, invoices_db_path: str = None, consumos_db_path: str = None) -> dict:
    """Migrate data from separate invoices.db/consumos.db into the main database.

    Returns dict with row counts migrated per table.
    Old DB files are renamed to .migrated (not deleted).
    """
    import os

    base_dir = os.path.dirname(main_db_path) or "."
    if invoices_db_path is None:
        invoices_db_path = os.path.join(base_dir, "invoices.db")
    if consumos_db_path is None:
        consumos_db_path = os.path.join(base_dir, "consumos.db")

    conn = create_connection(main_db_path)
    create_tables(conn)
    stats = {}

    if os.path.exists(invoices_db_path):
        conn.execute(f"ATTACH DATABASE ? AS inv_db", (invoices_db_path,))
        for table in ("invoices", "invoice_lines", "invoice_taxes", "unparsed_facturas"):
            try:
                conn.execute(f"INSERT OR IGNORE INTO {table} SELECT * FROM inv_db.{table}")
                count = conn.execute(f"SELECT changes()").fetchone()[0]
                stats[table] = count
            except sqlite3.OperationalError:
                stats[table] = 0
        conn.commit()
        conn.execute("DETACH DATABASE inv_db")
        os.rename(invoices_db_path, invoices_db_path + ".migrated")

    if os.path.exists(consumos_db_path):
        conn.execute(f"ATTACH DATABASE ? AS con_db", (consumos_db_path,))
        # consumos: copy original columns (without link_source/linked_at which are new)
        try:
            cols = "id, msg_id, bank, account, purchased_at, amount, merchant, card_last, " \
                   "subject, label, beneficiary, destination_account, concepto, " \
                   "matched_invoice_number, matched_at, registered_txn_id, registered_at, ingested_at"
            conn.execute(f"INSERT OR IGNORE INTO consumos ({cols}) SELECT {cols} FROM con_db.consumos")
            stats["consumos"] = conn.execute("SELECT changes()").fetchone()[0]
        except sqlite3.OperationalError:
            stats["consumos"] = 0
        for table in ("unparsed_consumos", "llm_decisions"):
            try:
                conn.execute(f"INSERT OR IGNORE INTO {table} SELECT * FROM con_db.{table}")
                stats[table] = conn.execute("SELECT changes()").fetchone()[0]
            except sqlite3.OperationalError:
                stats[table] = 0
        conn.commit()
        conn.execute("DETACH DATABASE con_db")
        os.rename(consumos_db_path, consumos_db_path + ".migrated")

    conn.commit()
    conn.close()
    return stats


if __name__ == '__main__':
    initialize_database_with_mock_data()


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

def create_connection(db_path: str) -> Connection:
    """
    Establishes and returns a connection to the SQLite database file.
    """
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
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
    conn.commit()

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
        ("Housing", "Rent, mortgage, utilities, and home maintenance"),
        ("Home Groceries", "Food and household items for home"),
        ("Personal Groceries", "Food for personal diet or specific needs"),
        ("Dining-Snacks", "Eating out, takeout, coffee, and social food/drinks"),
        ("Transportation", "Costs for getting around"),
        ("Health", "Medical, insurance, and fitness expenses"),
        ("Personal", "Discretionary spending, entertainment, hobbies, self-care"),
        ("Income", "Money received from work or investments"),
        ("Savings", "Funds for savings or investments"),
        ("Loans", "Money lent to others and repayments received"),
        ("Others", "Miscellaneous or infrequent expenses"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?)", categories)
    conn.commit()

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
    print("Database initialized successfully.")

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

if __name__ == '__main__':
    initialize_database_with_mock_data()

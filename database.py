
import sqlite3
from sqlite3 import Connection

def create_connection(db_path: str) -> Connection:
    """
    Establishes and returns a connection to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
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
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_created DATE NOT NULL,
            date_payed DATE NOT NULL,
            description TEXT NOT NULL,
            account TEXT,
            amount REAL NOT NULL,
            category TEXT,
            budget_category TEXT,
            status TEXT NOT NULL,
            origin_id TEXT,
            FOREIGN KEY (account) REFERENCES accounts (account_id)
        )
    """)
    conn.commit()

def insert_initial_data(conn: Connection):
    """
    Populates the 'accounts' table with default data.
    """
    cursor = conn.cursor()
    accounts = [
        ("Cash", "cash", None, None),
        ("Visa Produbanco", "credit_card", 14, 25),
        ("Amex Produbanco", "credit_card", 2, 15)
    ]
    cursor.executemany("INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?)", accounts)
    conn.commit()

def initialize_database(db_path: str = "cash_flow.db"):
    """
    A master function that orchestrates the entire database setup process.
    """
    conn = create_connection(db_path)
    create_tables(conn)
    insert_initial_data(conn)
    conn.close()
    print("Database initialized successfully.")

if __name__ == '__main__':
    initialize_database()

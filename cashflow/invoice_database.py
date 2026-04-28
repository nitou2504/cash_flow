"""Thin compatibility shim — invoice tables now live in cash_flow.db.

All callers that import from here continue to work unchanged.
"""
from cashflow.database import create_connection as create_invoice_connection  # noqa: F401
from cashflow.database import create_tables as create_invoice_tables  # noqa: F401
from cashflow.database import create_test_db as create_test_invoices_db  # noqa: F401
from cashflow.database import initialize_database as initialize_invoices_database  # noqa: F401
from cashflow.database import ensure_schema_upgrades as ensure_invoice_schema_upgrades  # noqa: F401

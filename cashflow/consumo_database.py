"""Thin compatibility shim — consumo tables now live in cash_flow.db.

All callers that import from here continue to work unchanged.
"""
from cashflow.database import create_connection as create_consumo_connection  # noqa: F401
from cashflow.database import create_tables as create_consumo_tables  # noqa: F401
from cashflow.database import create_test_db as create_test_consumos_db  # noqa: F401
from cashflow.database import initialize_database as initialize_consumos_database  # noqa: F401

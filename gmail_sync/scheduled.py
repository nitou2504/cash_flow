"""Scheduled Gmail sync job for the Telegram bot.

Runs the full pipeline: ingest consumos → ingest invoices → match invoices
→ register consumos → enrich with late invoices.
"""
import asyncio
import logging
import os
import sqlite3
from datetime import timedelta

from telegram.ext import CallbackContext

from cashflow.config import CONSUMOS_DB_PATH, DB_PATH, INVOICES_DB_PATH, TELEGRAM_ALLOWED_USERS
from cashflow.consumo_database import (
    create_consumo_connection,
    initialize_consumos_database,
)
from cashflow.database import create_connection
from cashflow.invoice_database import create_invoice_connection, initialize_invoices_database
from gmail_sync.auth import get_credentials
from gmail_sync.client import GmailClient
from gmail_sync.ingest_consumos import (
    LABEL_TO_PARSER,
    _compute_after as consumos_compute_after,
    ingest_label,
    match_invoices,
)
from gmail_sync.ingest_invoices import (
    _compute_after as invoices_compute_after,
    ingest_messages,
)
from gmail_sync.register_consumos import (
    enrich_with_invoices,
    load_rules,
    register_consumos,
)

logger = logging.getLogger(__name__)

SYNC_AFTER = os.getenv("GMAIL_SYNC_AFTER", "2026-04-27")


def _run_sync() -> dict:
    """Run full pipeline synchronously. Returns summary dict."""
    summary = {
        "consumos_ingested": 0,
        "invoices_ingested": 0,
        "invoices_matched": 0,
        "registered": 0,
        "enriched": 0,
        "by_method": {},
        "errors": [],
    }

    gc = GmailClient()
    consumos_conn = create_consumo_connection(CONSUMOS_DB_PATH)
    invoices_conn = create_invoice_connection(INVOICES_DB_PATH)
    cf_conn = create_connection(DB_PATH)

    try:
        # 1. Ingest consumos (since last)
        after = consumos_compute_after(consumos_conn, None, True)
        query = f"after:{after}"
        for label_name, (_bank, parser_fn) in LABEL_TO_PARSER.items():
            try:
                label_id = gc.resolve_label_id(label_name)
            except KeyError:
                continue
            stats = ingest_label(gc, label_name, label_id, parser_fn, query, consumos_conn)
            summary["consumos_ingested"] += stats["upserted"]

        # 2. Ingest invoices (since last)
        inv_after = invoices_compute_after(invoices_conn, None, True)
        inv_query = f"after:{inv_after}"
        try:
            label_id = gc.resolve_label_id("Facturas")
            stats = ingest_messages(gc, label_id, inv_query, invoices_conn)
            summary["invoices_ingested"] += stats["upserted"]
        except KeyError:
            summary["errors"].append("Facturas label not found")

        # 3. Match invoices to consumos
        mstats = match_invoices(consumos_conn, invoices_conn)
        summary["invoices_matched"] = mstats["matched"]

        # 4. Register unregistered consumos
        rules = load_rules()
        rstats = register_consumos(
            cf_conn, consumos_conn, invoices_conn,
            use_llm=True, after=SYNC_AFTER, rules=rules,
        )
        summary["registered"] = rstats["registered"]
        summary["by_method"] = rstats["by_method"]

        # 5. Enrich with late invoices
        estats = enrich_with_invoices(
            cf_conn, consumos_conn, invoices_conn, rules=rules,
        )
        summary["enriched"] = estats["enriched"]

    except Exception as e:
        logger.exception("Gmail sync failed")
        summary["errors"].append(str(e))
    finally:
        consumos_conn.close()
        invoices_conn.close()
        cf_conn.close()

    return summary


def _format_summary(s: dict) -> str:
    lines = ["Gmail Sync Complete"]
    if s["consumos_ingested"] or s["invoices_ingested"]:
        lines.append(f"  Ingested: {s['consumos_ingested']} consumos, {s['invoices_ingested']} invoices")
    if s["invoices_matched"]:
        lines.append(f"  Invoices matched: {s['invoices_matched']}")
    if s["registered"]:
        methods = ", ".join(f"{c} {m}" for m, c in sorted(s["by_method"].items()))
        lines.append(f"  Registered: {s['registered']} ({methods})")
    if s["enriched"]:
        lines.append(f"  Enriched: {s['enriched']}")
    if s["errors"]:
        lines.append(f"  Errors: {'; '.join(s['errors'])}")
    if len(lines) == 1:
        lines.append("  Nothing new")
    return "\n".join(lines)


async def run_gmail_sync(context: CallbackContext) -> None:
    """Scheduled job callback for PTB JobQueue."""
    logger.info("Starting scheduled Gmail sync")
    try:
        summary = await asyncio.to_thread(_run_sync)
    except Exception as e:
        logger.exception("Gmail sync job crashed")
        summary = {"errors": [str(e)], "consumos_ingested": 0,
                    "invoices_ingested": 0, "invoices_matched": 0,
                    "registered": 0, "enriched": 0, "by_method": {}}

    msg = _format_summary(summary)
    logger.info(msg)

    if TELEGRAM_ALLOWED_USERS:
        owner_id = next(iter(TELEGRAM_ALLOWED_USERS))
        try:
            await context.bot.send_message(chat_id=owner_id, text=msg)
        except Exception:
            logger.exception("Failed to send sync notification")

"""Auto-register consumos as reviewable transactions in cash_flow.db.

Usage:
    python3 -m gmail_sync.register_consumos --dry-run --limit 20
    python3 -m gmail_sync.register_consumos --after 2026-04-27
    python3 -m gmail_sync.register_consumos --no-llm
    python3 -m gmail_sync.register_consumos --labels Consumos/Cash

Rules config: register_rules.yaml (merchant patterns, transfer destinations, LLM model).
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from textwrap import dedent
from typing import Optional

import litellm
import yaml

from cashflow.config import CONSUMOS_DB_PATH, INVOICES_DB_PATH
from cashflow.consumo_database import create_consumo_connection
from cashflow.consumo_repository import find_unregistered, mark_registered
from cashflow.database import create_connection
from cashflow.repository import (
    add_transactions,
    find_matching_forecast,
    find_similar_transactions,
    get_account_by_name,
    get_all_categories,
    link_transaction,
)
from cashflow.transactions import create_single_transaction

RULES_PATH = Path(__file__).resolve().parent.parent / "register_rules.yaml"


def load_rules(path: Path = RULES_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _extract_keywords(merchant: str) -> list[str]:
    cleaned = re.sub(r"[\\/*\d]", " ", merchant)
    cleaned = re.sub(r"\b(MR|MRS|DLOCAL|SA|CIA|LTDA|SAS)\b", "", cleaned, flags=re.I)
    words = [w for w in cleaned.split() if len(w) > 2]
    return words[:2] if words else [merchant.split()[0]] if merchant.strip() else []


def _match_rule(merchant: str, merchant_rules: dict) -> Optional[dict]:
    upper = merchant.upper()
    for pattern, rule in merchant_rules.items():
        if pattern.upper() in upper:
            return rule
    return None


def _match_transfer_rule(consumo: dict, transfer_rules: dict) -> Optional[dict]:
    if consumo.get("account") != "Cash":
        return None
    dest = consumo.get("destination_account") or ""
    rule = transfer_rules.get(dest)
    if rule:
        concepto = consumo.get("concepto") or consumo.get("merchant") or ""
        desc = rule["desc_template"].format(concepto=concepto)
        return {"category": rule["category"], "desc": desc}
    return None


def _build_category_block(categories: list[dict]) -> str:
    lines = []
    for cat in categories:
        name = cat["name"]
        desc = cat.get("description", "")
        if desc:
            lines.append(f"- **{name}**: {desc}")
        else:
            lines.append(f"- **{name}**")
    return "\n".join(lines)


def _build_llm_prompt(
    consumo: dict, items: list[dict], similar: list[dict], categories: list[dict],
) -> str:
    cat_block = _build_category_block(categories)

    parts = [dedent("""\
        Given a credit card purchase, generate a short description and select a category.
        Description style: "Merchant - 3-5 key items" (see examples below).
        Pick the category whose description best matches the items/purpose.
        Respond ONLY with JSON: {"description": "...", "category": "..."}
    """)]

    parts.append(f"## Purchase\nMerchant: {consumo['merchant']}")
    parts.append(f"Amount: ${consumo['amount']:.2f}")
    parts.append(f"Account: {consumo['account']}")

    if items:
        parts.append("\n## Invoice items:")
        for item in items[:30]:
            qty = f"{item['quantity']:g}x " if item.get("quantity", 1) != 1 else ""
            parts.append(f"- {qty}{item['description']} ${item.get('line_total', 0):.2f}")
        if len(items) > 30:
            parts.append(f"... and {len(items) - 30} more items")

    if similar:
        parts.append("\n## Similar past transactions (follow this style):")
        for s in similar[:8]:
            parts.append(f'- "{s["description"]}" → {s["category"]} (${abs(s["amount"]):.2f})')

    parts.append(f"\n## Categories (pick exactly one):\n{cat_block}")

    return "\n".join(parts)


def _parse_llm_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if "```" in text:
            text = text[:text.rindex("```")]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return {}


def _call_llm(prompt: str, model: str) -> dict:
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[
            {"role": "system", "content": "You are a concise JSON-only assistant. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        api_base="http://localhost:11434",
    )
    return _parse_llm_response(response.choices[0].message.content)


def _get_invoice_lines(invoices_conn, invoice_number: str) -> list[dict]:
    inv = invoices_conn.execute(
        "SELECT id FROM invoices WHERE invoice_number = ?",
        (invoice_number,),
    ).fetchone()
    if not inv:
        return []
    rows = invoices_conn.execute(
        "SELECT description, quantity, line_total FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number",
        (inv["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def prepare_one(
    consumo: dict,
    cf_conn,
    invoices_conn,
    *,
    use_llm: bool = True,
    rules: dict = None,
    categories: list[dict] = None,
) -> dict:
    """Prepare a transaction request for one consumo. Returns {description, category, method}."""
    if rules is None:
        rules = load_rules()
    merchant_rules = rules.get("merchant_rules", {})
    transfer_rules = rules.get("transfer_rules", {})
    llm_model = rules.get("llm_model", "llama3.2:3b")

    # 1. Cash transfer rules
    transfer = _match_transfer_rule(consumo, transfer_rules)
    if transfer:
        return {"description": transfer["desc"], "category": transfer["category"], "method": "transfer_rule"}

    # 2. Deterministic merchant rules
    rule = _match_rule(consumo["merchant"], merchant_rules)
    if rule:
        desc = rule.get("desc", consumo["merchant"])
        return {"description": desc, "category": rule["category"], "method": "merchant_rule"}

    # 3. Get context for LLM or fallback
    keywords = _extract_keywords(consumo["merchant"])
    similar = find_similar_transactions(cf_conn, keywords, limit=8) if keywords else []

    items = []
    if consumo.get("matched_invoice_number") and invoices_conn:
        items = _get_invoice_lines(invoices_conn, consumo["matched_invoice_number"])

    # 4. If no LLM, use first similar or fallback
    if not use_llm:
        if similar:
            return {
                "description": consumo["merchant"],
                "category": similar[0]["category"],
                "method": "fuzzy_match",
            }
        return {
            "description": consumo["merchant"],
            "category": "Others",
            "method": "fallback",
        }

    # 5. LLM (for groceries/ambiguous merchants — summarize items + pick category)
    if similar or items:
        cats = categories or []
        prompt = _build_llm_prompt(consumo, items, similar, cats)
        result = _call_llm(prompt, llm_model)
        desc = result.get("description", consumo["merchant"])
        cat = result.get("category", "Others")
        valid_names = {c["name"] for c in cats} if cats else set()
        if valid_names and cat not in valid_names:
            cat = similar[0]["category"] if similar else "Others"
        return {"description": desc, "category": cat, "method": "llm"}

    # 6. No context at all
    return {"description": consumo["merchant"], "category": "Others", "method": "fallback"}


def register_consumos(
    cf_conn, consumos_conn, invoices_conn,
    *,
    dry_run: bool = False,
    use_llm: bool = True,
    limit: int = 0,
    after: str = None,
    labels: list[str] = None,
    rules: dict = None,
) -> dict:
    stats = {"registered": 0, "skipped": 0, "by_method": {}}

    if rules is None:
        rules = load_rules()

    categories = get_all_categories(cf_conn)

    unregistered = find_unregistered(consumos_conn)
    if after:
        unregistered = [c for c in unregistered if c["purchased_at"][:10] >= after]
    if labels:
        unregistered = [c for c in unregistered if c.get("label") in labels]
    if limit:
        unregistered = unregistered[:limit]

    print(f"Consumos to register: {len(unregistered)}"
          + ("  [DRY RUN]" if dry_run else "")
          + ("  [NO LLM]" if not use_llm else ""))

    for consumo in unregistered:
        purchased = consumo["purchased_at"][:10]

        # Step 0: subscription match — link to existing forecast, don't duplicate
        forecast = find_matching_forecast(
            cf_conn, consumo["account"], consumo["amount"], purchased,
        )
        if forecast:
            method = "subscription_match"
            stats["by_method"][method] = stats["by_method"].get(method, 0) + 1
            if dry_run:
                print(f"  {purchased} {consumo['account']:18} ${consumo['amount']:>7.2f} "
                      f"[{method:14}] → forecast #{forecast['id']} {forecast['sub_name']}")
            else:
                link_transaction(
                    cf_conn, forecast["id"],
                    consumo_msg_id=consumo["msg_id"],
                    invoice_number=consumo.get("matched_invoice_number"),
                    source="auto_register",
                )
                mark_registered(consumos_conn, consumo["id"], forecast["id"])
            stats["registered"] += 1
            continue

        try:
            prep = prepare_one(
                consumo, cf_conn, invoices_conn,
                use_llm=use_llm, rules=rules, categories=categories,
            )
        except Exception as e:
            print(f"  ERROR {consumo['id']} {consumo['merchant'][:30]}: {e}")
            stats["skipped"] += 1
            continue

        method = prep["method"]
        stats["by_method"][method] = stats["by_method"].get(method, 0) + 1

        account = get_account_by_name(cf_conn, consumo["account"])
        if not account:
            print(f"  SKIP {consumo['id']}: unknown account {consumo['account']}")
            stats["skipped"] += 1
            continue

        txn_date = date.fromisoformat(purchased)

        if dry_run:
            print(f"  {purchased} {consumo['account']:18} ${consumo['amount']:>7.2f} "
                  f"[{method:14}] {prep['category']:20} {prep['description'][:50]}")
            stats["registered"] += 1
            continue

        txn = create_single_transaction(
            description=prep["description"],
            amount=consumo["amount"],
            category=prep["category"],
            budget=None,
            account=account,
            transaction_date=txn_date,
            source="gmail",
            needs_review=True,
        )
        inserted_ids = add_transactions(cf_conn, [txn])
        tid = inserted_ids[0]

        link_transaction(
            cf_conn, tid,
            consumo_msg_id=consumo["msg_id"],
            invoice_number=consumo.get("matched_invoice_number"),
            source="auto_register",
        )
        mark_registered(consumos_conn, consumo["id"], tid)
        stats["registered"] += 1

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-register consumos as reviewable transactions")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="Skip LLM, use rules + fuzzy match only")
    ap.add_argument("--limit", type=int, default=0, help="Max consumos to process (0=all)")
    ap.add_argument("--after", help="Only consumos after YYYY-MM-DD")
    ap.add_argument("--labels", nargs="*", help="Filter by Gmail label")
    ap.add_argument("--db", default="cash_flow.db")
    ap.add_argument("--consumos-db", default=None)
    ap.add_argument("--invoices-db", default=None)
    ap.add_argument("--rules", default=None, help="Override rules YAML path")
    args = ap.parse_args()

    rules = load_rules(Path(args.rules)) if args.rules else load_rules()

    cf_conn = create_connection(args.db)
    consumos_conn = create_consumo_connection(args.consumos_db or CONSUMOS_DB_PATH)
    invoices_conn = sqlite3.connect(args.invoices_db or INVOICES_DB_PATH)
    invoices_conn.row_factory = sqlite3.Row

    try:
        stats = register_consumos(
            cf_conn, consumos_conn, invoices_conn,
            dry_run=args.dry_run,
            use_llm=not args.no_llm,
            limit=args.limit,
            after=args.after,
            labels=args.labels,
            rules=rules,
        )
        print(f"\n=== Registration Summary ===")
        print(f"  Registered: {stats['registered']}")
        print(f"  Skipped:    {stats['skipped']}")
        if stats["by_method"]:
            print(f"  By method:")
            for m, c in sorted(stats["by_method"].items()):
                print(f"    {m}: {c}")
    finally:
        cf_conn.close()
        consumos_conn.close()
        invoices_conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

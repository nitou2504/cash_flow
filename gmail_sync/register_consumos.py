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
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from textwrap import dedent
from typing import Optional

import litellm
import yaml

from cashflow.consumo_repository import find_unregistered, mark_registered
from cashflow.database import create_connection
from cashflow.repository import (
    add_transactions,
    find_matching_forecast,
    find_matching_transaction,
    find_similar_transactions,
    get_account_by_name,
    get_all_categories,
    get_transaction_link,
    link_transaction,
)
from cashflow.transactions import create_single_transaction

_BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = _BASE_DIR / "register_rules.yaml"
RULES_EXAMPLE_PATH = _BASE_DIR / "register_rules.yaml.example"
CLASSIFICATION_HINTS_PATH = _BASE_DIR / "classification_hints.yaml"
CLASSIFICATION_HINTS_EXAMPLE_PATH = _BASE_DIR / "classification_hints.yaml.example"


def load_rules(path: Path = RULES_PATH) -> dict:
    rules_file = path if path.exists() else RULES_EXAMPLE_PATH
    with open(rules_file) as f:
        rules = yaml.safe_load(f)
    hints_file = CLASSIFICATION_HINTS_PATH if CLASSIFICATION_HINTS_PATH.exists() else CLASSIFICATION_HINTS_EXAMPLE_PATH
    if hints_file.exists():
        with open(hints_file) as f:
            shared = yaml.safe_load(f) or {}
        hints = rules.get("category_hints", [])
        hints.extend(shared.get("category_hints", []))
        hints.extend(shared.get("user_hints", []))
        rules["category_hints"] = hints
        budget_map = rules.get("category_budget_map", {})
        budget_map.update(shared.get("category_budget_map", {}))
        rules["category_budget_map"] = budget_map
    return rules


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
    hints: list[str] = None,
) -> str:
    cat_block = _build_category_block(categories)

    parts = [dedent("""\
        Given a credit card purchase, generate a short description and select a category.
        Description style: "Merchant - 3-5 key items in Spanish". ALWAYS start with merchant name, then dash, then pick the 3-5 most representative items only, NOT all items.
        Pick the category whose description best matches the items/purpose.
        Respond ONLY with JSON: {"description": "...", "category": "..."}
    """)]

    parts.append(f"## Purchase\nMerchant: {consumo['merchant']}")
    parts.append(f"Amount: ${consumo['amount']:.2f}")
    parts.append(f"Account: {consumo['account']}")

    if items:
        sorted_items = sorted(items, key=lambda x: abs(x.get("line_total", 0)), reverse=True)
        show = sorted_items[:15]
        parts.append("\n## Invoice items (sorted by cost, highest first):")
        for item in show:
            qty = f"{item['quantity']:g}x " if item.get("quantity", 1) != 1 else ""
            parts.append(f"- {qty}{item['description']} ${item.get('line_total', 0):.2f}")
        if len(sorted_items) > 15:
            parts.append(f"  ...and {len(sorted_items) - 15} more small items")

    if similar:
        parts.append("\n## Similar past transactions (follow this style):")
        for s in similar[:8]:
            parts.append(f'- "{s["description"]}" → {s["category"]} (${abs(s["amount"]):.2f})')

    parts.append(f"\n## Categories (pick exactly one):\n{cat_block}")

    if hints:
        parts.append("\n## IMPORTANT classification rules (these OVERRIDE similar transactions):")
        for hint in hints:
            parts.append(f"- {hint}")
        parts.append("Apply these rules based on the INVOICE ITEMS, not the similar transaction history.")

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


def _call_llm(prompt: str, model: str) -> tuple[dict, str]:
    """Returns (parsed_dict, raw_response_text)."""
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[
            {"role": "system", "content": "You are a concise JSON-only assistant. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        api_base=os.getenv("LLM_OLLAMA_BASE_URL", "http://localhost:11434"),
        extra_body={"think": False},
    )
    raw = response.choices[0].message.content
    return _parse_llm_response(raw), raw


def _get_invoice_lines(conn, invoice_number: str) -> list[dict]:
    inv = conn.execute(
        "SELECT id FROM invoices WHERE invoice_number = ?",
        (invoice_number,),
    ).fetchone()
    if not inv:
        return []
    rows = conn.execute(
        "SELECT description, quantity, line_total FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number",
        (inv["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def _apply_item_overrides(items: list[dict], rules: dict) -> Optional[str]:
    """Classify by invoice item keywords, dollar-weighted. Returns category or None."""
    overrides = rules.get("item_overrides", [])
    if not overrides or not items:
        return None
    totals: dict[str, float] = {}
    for item in items:
        desc_lower = item["description"].lower()
        for rule in overrides:
            if any(kw in desc_lower for kw in rule["keywords"]):
                cat = rule["category"]
                totals[cat] = totals.get(cat, 0) + abs(item.get("line_total", 0))
                break
    if not totals:
        return None
    return max(totals, key=totals.get)


def _log_decision(conn, consumo_id: int, method: str, model: str,
                   prompt: str, response_raw: str, parsed_json: dict,
                   category: str, description: str) -> None:
    conn.execute(
        """INSERT INTO llm_decisions
           (consumo_id, model, method, prompt, response_raw, parsed_json, category, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (consumo_id, model, method, prompt, response_raw,
         json.dumps(parsed_json) if parsed_json else None, category, description),
    )
    conn.commit()


def _resolve_budget(conn, category: str, rules: dict, payment_date: date) -> Optional[str]:
    budget_map = rules.get("category_budget_map", {})
    prefix = budget_map.get(category)
    if not prefix:
        return None
    row = conn.execute(
        """SELECT id FROM subscriptions
           WHERE is_budget = 1 AND id LIKE ?
             AND start_date <= ? AND (end_date IS NULL OR end_date >= ?)""",
        (prefix + "%", payment_date.isoformat(), payment_date.isoformat()),
    ).fetchone()
    return row["id"] if row else None


def prepare_one(
    consumo: dict,
    conn,
    *,
    use_llm: bool = True,
    rules: dict = None,
    categories: list[dict] = None,
) -> dict:
    """Prepare a transaction request for one consumo. Returns {description, category, method, _debug}."""
    if rules is None:
        rules = load_rules()
    merchant_rules = rules.get("merchant_rules", {})
    transfer_rules = rules.get("transfer_rules", {})
    llm_model = rules.get("llm_model", "llama3.2:3b")
    hints = rules.get("category_hints", [])

    def _result(desc, cat, method, prompt="", response_raw="", parsed_json=None, model="rules"):
        return {
            "description": desc, "category": cat, "method": method,
            "_debug": {"prompt": prompt, "response_raw": response_raw,
                       "parsed_json": parsed_json, "model": model},
        }

    # 1. Cash transfer rules
    transfer = _match_transfer_rule(consumo, transfer_rules)
    if transfer:
        return _result(transfer["desc"], transfer["category"], "transfer_rule",
                       prompt=f"Matched transfer rule: dest={consumo.get('destination_account')}",
                       response_raw=json.dumps(transfer))

    # 2. Deterministic merchant rules
    rule = _match_rule(consumo["merchant"], merchant_rules)
    if rule:
        desc = rule.get("desc", consumo["merchant"])
        matched_pattern = next((p for p in merchant_rules if p.upper() in consumo["merchant"].upper()), "?")
        return _result(desc, rule["category"], "merchant_rule",
                       prompt=f"Matched merchant rule: '{matched_pattern}'",
                       response_raw=json.dumps(rule))

    # 3. Get context for LLM or fallback
    keywords = _extract_keywords(consumo["merchant"])
    similar = find_similar_transactions(conn, keywords, limit=8) if keywords else []

    items = []
    if consumo.get("matched_invoice_number"):
        items = _get_invoice_lines(conn, consumo["matched_invoice_number"])

    # 4. If no LLM, use first similar or fallback
    if not use_llm:
        if similar:
            return _result(consumo["merchant"], similar[0]["category"], "fuzzy_match",
                           prompt=f"No LLM; matched {len(similar)} similar txns",
                           response_raw=json.dumps({"first_match": similar[0]["description"]}))
        return _result(consumo["merchant"], "Others", "fallback",
                       prompt="No LLM, no similar transactions found")

    # 5. LLM (for groceries/ambiguous merchants — summarize items + pick category)
    if similar or items:
        cats = categories or []
        prompt = _build_llm_prompt(consumo, items, similar, cats, hints=hints)
        result, raw = _call_llm(prompt, llm_model)
        desc = result.get("description", consumo["merchant"])
        cat = result.get("category", "Others")
        valid_names = {c["name"] for c in cats} if cats else set()
        if valid_names and cat not in valid_names:
            cat = similar[0]["category"] if similar else "Others"
        return _result(desc, cat, "llm", prompt=prompt, response_raw=raw,
                       parsed_json=result, model=llm_model)

    # 6. No context at all
    return _result(consumo["merchant"], "Others", "fallback",
                   prompt="No similar transactions or invoice items found")


def register_consumos(
    conn,
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

    categories = get_all_categories(conn)

    unregistered = find_unregistered(conn)
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
            conn, consumo["account"], consumo["amount"], purchased,
        )
        if forecast:
            method = "subscription_match"
            stats["by_method"][method] = stats["by_method"].get(method, 0) + 1
            if dry_run:
                print(f"  {purchased} {consumo['account']:18} ${consumo['amount']:>7.2f} "
                      f"[{method:14}] → forecast #{forecast['id']} {forecast['sub_name']}")
            else:
                link_transaction(
                    conn, forecast["id"],
                    consumo_msg_id=consumo["msg_id"],
                    invoice_number=consumo.get("matched_invoice_number"),
                    source="auto_register",
                )
                mark_registered(conn, consumo["id"], forecast["id"])
            stats["registered"] += 1
            continue

        # Step 0.5: existing transaction match — link to manually-created txn
        existing = find_matching_transaction(
            conn, consumo["account"], consumo["amount"], purchased,
        )
        if existing:
            method = "existing_txn_match"
            stats["by_method"][method] = stats["by_method"].get(method, 0) + 1
            if dry_run:
                print(f"  {purchased} {consumo['account']:18} ${consumo['amount']:>7.2f} "
                      f"[{method:14}] → txn #{existing['id']} {existing['description'][:30]}")
            else:
                link_transaction(
                    conn, existing["id"],
                    consumo_msg_id=consumo["msg_id"],
                    invoice_number=consumo.get("matched_invoice_number"),
                    source="auto_register",
                )
                mark_registered(conn, consumo["id"], existing["id"])
            stats["registered"] += 1
            continue

        try:
            prep = prepare_one(
                consumo, conn,
                use_llm=use_llm, rules=rules, categories=categories,
            )
        except Exception as e:
            print(f"  ERROR {consumo['id']} {consumo['merchant'][:30]}: {e}")
            stats["skipped"] += 1
            continue

        method = prep["method"]
        stats["by_method"][method] = stats["by_method"].get(method, 0) + 1

        # Log decision
        debug = prep.get("_debug", {})
        try:
            _log_decision(
                conn, consumo["id"], method, debug.get("model", ""),
                debug.get("prompt", ""), debug.get("response_raw", ""),
                debug.get("parsed_json"), prep["category"], prep["description"],
            )
        except Exception:
            pass

        account = get_account_by_name(conn, consumo["account"])
        if not account:
            print(f"  SKIP {consumo['id']}: unknown account {consumo['account']}")
            stats["skipped"] += 1
            continue

        txn_date = date.fromisoformat(purchased)

        # Create txn to compute date_payed, then resolve budget by payment month
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
        budget_id = _resolve_budget(conn, prep["category"], rules, txn["date_payed"])
        txn["budget"] = budget_id

        if dry_run:
            budget_str = f" → {budget_id}" if budget_id else ""
            print(f"  {purchased} {consumo['account']:18} ${consumo['amount']:>7.2f} "
                  f"[{method:14}] {prep['category']:20} {prep['description'][:50]}{budget_str}")
            stats["registered"] += 1
            continue

        inserted_ids = add_transactions(conn, [txn])
        tid = inserted_ids[0]

        link_transaction(
            conn, tid,
            consumo_msg_id=consumo["msg_id"],
            invoice_number=consumo.get("matched_invoice_number"),
            source="auto_register",
        )
        mark_registered(conn, consumo["id"], tid)
        stats["registered"] += 1

    return stats


def enrich_with_invoices(
    conn,
    *,
    use_llm: bool = True,
    rules: dict = None,
    dry_run: bool = False,
) -> dict:
    if rules is None:
        rules = load_rules()
    categories = get_all_categories(conn)
    stats = {"enriched": 0, "checked": 0}

    rows = conn.execute("""
        SELECT t.id, t.description, t.account, t.amount, t.date_created,
               c.msg_id as consumo_msg_id, c.matched_invoice_number as invoice_number
        FROM transactions t
        JOIN consumos c ON c.registered_txn_id = t.id
        WHERE t.needs_review = 1
          AND c.msg_id IS NOT NULL
          AND c.matched_invoice_number IS NOT NULL
          AND c.matched_at > c.linked_at
          AND t.date_created >= date('now', '-3 days')
    """).fetchall()

    for row in rows:
        stats["checked"] += 1
        consumo = conn.execute(
            "SELECT * FROM consumos WHERE msg_id = ?", (row["consumo_msg_id"],),
        ).fetchone()
        if not consumo or not consumo["matched_invoice_number"]:
            continue

        consumo = dict(consumo)
        prep = prepare_one(
            consumo, conn,
            use_llm=use_llm, rules=rules, categories=categories,
        )

        if dry_run:
            print(f"  ENRICH #{row['id']}: \"{row['description']}\" → \"{prep['description'][:50]}\" [{prep['category']}]")
        else:
            conn.execute(
                "UPDATE transactions SET description = ?, category = ? WHERE id = ?",
                (prep["description"], prep["category"], row["id"]),
            )
            link_transaction(
                conn, row["id"],
                consumo_msg_id=row["consumo_msg_id"],
                invoice_number=consumo["matched_invoice_number"],
                source="auto_register",
            )
            conn.commit()
        stats["enriched"] += 1

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-register consumos as reviewable transactions")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="Skip LLM, use rules + fuzzy match only")
    ap.add_argument("--limit", type=int, default=0, help="Max consumos to process (0=all)")
    ap.add_argument("--after", help="Only consumos after YYYY-MM-DD")
    ap.add_argument("--labels", nargs="*", help="Filter by Gmail label")
    ap.add_argument("--db", default="cash_flow.db")
    ap.add_argument("--rules", default=None, help="Override rules YAML path")
    args = ap.parse_args()

    rules = load_rules(Path(args.rules)) if args.rules else load_rules()
    conn = create_connection(args.db)

    try:
        stats = register_consumos(
            conn,
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
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

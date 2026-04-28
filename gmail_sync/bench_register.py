"""Benchmark LLM models for consumo → transaction description + category.

Usage:
    python3 -m gmail_sync.bench_register
    python3 -m gmail_sync.bench_register --models llama3.2:3b gemma4:e2b
    python3 -m gmail_sync.bench_register --no-invoice   # test merchant-only case
"""
import argparse
import json
import sqlite3
import sys
import time
from textwrap import dedent

import litellm


CATEGORIES = [
    "Dining-Snacks", "Family Support", "Health", "Home", "Home Food & Supplies",
    "Income", "Loans", "Others", "Personal", "Personal Diet",
    "Savings", "Sister Education",
]

MODELS = ["llama3.2:3b", "gemma3", "gemma4:e2b", "llama3.1"]


def _get_test_cases(conn, limit=5):
    """Build test cases: consumos with invoices that have existing transactions (ground truth)."""
    cases = []
    rows = conn.execute("""
        SELECT c.id, c.msg_id, c.merchant, c.amount, c.account, c.purchased_at,
               c.matched_invoice_number
        FROM consumos c
        WHERE c.matched_invoice_number IS NOT NULL AND c.registered_txn_id IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit * 3,)).fetchall()

    for r in rows:
        if len(cases) >= limit:
            break
        txn = conn.execute("""
            SELECT t.description, t.category FROM transactions t
            JOIN consumos c ON c.registered_txn_id = t.id
            WHERE c.msg_id = ?
        """, (r["msg_id"],)).fetchone()
        if not txn:
            continue

        inv = conn.execute(
            "SELECT id, vendor FROM invoices WHERE invoice_number = ?",
            (r["matched_invoice_number"],),
        ).fetchone()
        lines = []
        if inv:
            lines = conn.execute(
                "SELECT description, quantity, line_total FROM invoice_lines WHERE invoice_id = ? ORDER BY line_number",
                (inv["id"],),
            ).fetchall()

        similar = conn.execute("""
            SELECT description, category, amount
            FROM transactions
            WHERE status = 'committed' AND amount < 0
              AND description LIKE ?
            ORDER BY date_created DESC LIMIT 8
        """, (f"%{r['merchant'].split()[0]}%",)).fetchall()

        cases.append({
            "merchant": r["merchant"],
            "amount": r["amount"],
            "account": r["account"],
            "date": r["purchased_at"][:10],
            "invoice_vendor": inv["vendor"] if inv else None,
            "items": [{"desc": l["description"], "qty": l["quantity"], "total": l["line_total"]} for l in lines],
            "similar_txns": [{"desc": s["description"], "cat": s["category"], "amt": s["amount"]} for s in similar],
            "ground_truth_desc": txn["description"],
            "ground_truth_cat": txn["category"],
        })

    return cases


def _get_no_invoice_cases(conn, limit=5):
    """Consumos without invoices that have linked transactions."""
    cases = []
    rows = conn.execute("""
        SELECT c.msg_id, c.merchant, c.amount, c.account, c.purchased_at
        FROM consumos c
        WHERE c.matched_invoice_number IS NULL AND c.registered_txn_id IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit * 3,)).fetchall()

    for r in rows:
        if len(cases) >= limit:
            break
        txn = conn.execute("""
            SELECT t.description, t.category FROM transactions t
            JOIN consumos c ON c.registered_txn_id = t.id
            WHERE c.msg_id = ?
        """, (r["msg_id"],)).fetchone()
        if not txn:
            continue

        similar = conn.execute("""
            SELECT description, category, amount
            FROM transactions
            WHERE status = 'committed' AND amount < 0
              AND description LIKE ?
            ORDER BY date_created DESC LIMIT 8
        """, (f"%{r['merchant'].split()[0]}%",)).fetchall()

        cases.append({
            "merchant": r["merchant"],
            "amount": r["amount"],
            "account": r["account"],
            "date": r["purchased_at"][:10],
            "items": [],
            "similar_txns": [{"desc": s["description"], "cat": s["category"], "amt": s["amount"]} for s in similar],
            "ground_truth_desc": txn["description"],
            "ground_truth_cat": txn["category"],
        })

    return cases


def build_prompt(case: dict) -> str:
    parts = [dedent("""\
        You are a personal finance assistant. Given a credit card purchase, generate:
        1. A short description (merchant name + 3-5 key items or purpose)
        2. The most appropriate category

        Respond ONLY with JSON: {"description": "...", "category": "..."}
    """)]

    parts.append(f"\n## Purchase\nMerchant: {case['merchant']}")
    parts.append(f"Amount: ${case['amount']:.2f}")
    parts.append(f"Account: {case['account']}")
    parts.append(f"Date: {case['date']}")

    if case["items"]:
        parts.append("\n## Invoice items:")
        for item in case["items"][:30]:
            qty = f"{item['qty']:g}x " if item["qty"] != 1 else ""
            parts.append(f"- {qty}{item['desc']} ${item['total']:.2f}")
        if len(case["items"]) > 30:
            parts.append(f"... and {len(case['items']) - 30} more items")

    if case["similar_txns"]:
        parts.append("\n## Similar past transactions (for style reference):")
        for s in case["similar_txns"][:8]:
            parts.append(f'- "{s["desc"]}" → {s["cat"]} (${abs(s["amt"]):.2f})')

    cats = ", ".join(CATEGORIES)
    parts.append(f"\n## Categories (pick exactly one): {cats}")

    return "\n".join(parts)


def _parse_response(text: str) -> dict:
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
    return {"description": text[:100], "category": "PARSE_FAIL"}


def _call_ollama(model: str, prompt: str) -> str:
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[
            {"role": "system", "content": "You are a concise JSON-only assistant. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        api_base="http://localhost:11434",
    )
    return response.choices[0].message.content


def run_benchmark(cases: list, models: list, label: str = "WITH INVOICE"):
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: {label} — {len(cases)} cases × {len(models)} models")
    print(f"{'='*70}\n")

    results = {m: {"correct_cat": 0, "total": 0, "times": []} for m in models}

    for i, case in enumerate(cases):
        prompt = build_prompt(case)
        print(f"\n--- Case {i+1}: {case['merchant'][:30]} ${case['amount']:.2f} ({len(case['items'])} items) ---")
        print(f"  Ground truth: \"{case['ground_truth_desc']}\" → {case['ground_truth_cat']}")

        for model in models:
            t0 = time.time()
            try:
                response = _call_ollama(model, prompt)
                elapsed = time.time() - t0
                parsed = _parse_response(response)
                desc = parsed.get("description", "?")
                cat = parsed.get("category", "?")
                cat_ok = cat == case["ground_truth_cat"]
                results[model]["total"] += 1
                results[model]["times"].append(elapsed)
                if cat_ok:
                    results[model]["correct_cat"] += 1
                marker = "✓" if cat_ok else "✗"
                print(f"  [{model:15}] {elapsed:.1f}s {marker} cat={cat:20} desc=\"{desc[:50]}\"")
            except Exception as e:
                elapsed = time.time() - t0
                results[model]["total"] += 1
                results[model]["times"].append(elapsed)
                print(f"  [{model:15}] {elapsed:.1f}s ERROR: {e}")

    print(f"\n{'='*70}")
    print(f"  SUMMARY: {label}")
    print(f"{'='*70}")
    for model in models:
        r = results[model]
        if r["total"] == 0:
            continue
        acc = r["correct_cat"] / r["total"] * 100
        avg_t = sum(r["times"]) / len(r["times"])
        print(f"  {model:20} cat_accuracy={acc:.0f}% ({r['correct_cat']}/{r['total']})  avg={avg_t:.1f}s")


def main():
    ap = argparse.ArgumentParser(description="Benchmark LLM models for consumo registration")
    ap.add_argument("--models", nargs="*", default=None, help="Models to test")
    ap.add_argument("--cases", type=int, default=5, help="Number of test cases")
    ap.add_argument("--no-invoice", action="store_true", help="Test merchant-only case")
    ap.add_argument("--db", default="cash_flow.db")
    args = ap.parse_args()

    models = args.models or MODELS

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    try:
        if not args.no_invoice:
            cases = _get_test_cases(conn, limit=args.cases)
            if cases:
                run_benchmark(cases, models, "WITH INVOICE")
            else:
                print("No linked consumos with invoices found for benchmarking.")

        no_inv_cases = _get_no_invoice_cases(conn, limit=args.cases)
        if no_inv_cases:
            run_benchmark(no_inv_cases, models, "NO INVOICE (merchant only)")
        else:
            print("No linked consumos without invoices found for benchmarking.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

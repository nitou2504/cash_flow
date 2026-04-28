"""Benchmark gemma4:e2b — single call vs 2-4 parallel calls.

Usage:
    python3 -m gmail_sync.bench_parallel
    python3 -m gmail_sync.bench_parallel --rounds 5
    python3 -m gmail_sync.bench_parallel --model gemma4:e4b
"""
import argparse
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from textwrap import dedent

import litellm

litellm.suppress_debug_info = True
os.environ["LITELLM_LOG"] = "ERROR"

CATEGORIES = [
    "Dining-Snacks", "Family Support", "Health", "Home", "Home Food & Supplies",
    "Income", "Loans", "Others", "Personal", "Personal Diet",
    "Savings", "Sister Education",
]


def _build_prompt(merchant: str, amount: float, account: str, date: str, items: list) -> str:
    parts = [dedent("""\
        You are a personal finance assistant. Given a credit card purchase, generate:
        1. A short description (merchant name + 3-5 key items or purpose)
        2. The most appropriate category

        Respond ONLY with JSON: {"description": "...", "category": "..."}
    """)]
    parts.append(f"\n## Purchase\nMerchant: {merchant}")
    parts.append(f"Amount: ${amount:.2f}")
    parts.append(f"Account: {account}")
    parts.append(f"Date: {date}")
    if items:
        parts.append("\n## Invoice items:")
        for item in items[:15]:
            parts.append(f"- {item['desc']} ${item['total']:.2f}")
    cats = ", ".join(CATEGORIES)
    parts.append(f"\n## Categories (pick exactly one): {cats}")
    return "\n".join(parts)


def _call_llm(model: str, prompt: str) -> tuple[float, str]:
    t0 = time.time()
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
    elapsed = time.time() - t0
    raw = response.choices[0].message.content
    return elapsed, raw


def _get_test_prompts(n: int) -> list[str]:
    """Get N different prompts from cash_flow.db, or generate synthetic ones."""
    prompts = []
    try:
        db = sqlite3.connect("cash_flow.db")
        db.row_factory = sqlite3.Row

        rows = db.execute("""
            SELECT merchant, amount, account, purchased_at, matched_invoice_number
            FROM consumos WHERE registered_txn_id IS NOT NULL
            ORDER BY RANDOM() LIMIT ?
        """, (n,)).fetchall()

        for r in rows:
            items = []
            if r["matched_invoice_number"]:
                inv_row = db.execute(
                    "SELECT id FROM invoices WHERE invoice_number = ?",
                    (r["matched_invoice_number"],),
                ).fetchone()
                if inv_row:
                    items = [
                        {"desc": l["description"], "total": l["line_total"]}
                        for l in db.execute(
                            "SELECT description, line_total FROM invoice_lines WHERE invoice_id = ? LIMIT 15",
                            (inv_row["id"],),
                        ).fetchall()
                    ]
            prompts.append(_build_prompt(
                r["merchant"], r["amount"], r["account"],
                r["purchased_at"][:10], items,
            ))
        db.close()
    except Exception:
        pass

    # pad with synthetic if not enough real data
    synthetic = [
        ("SUPERMAXI", 45.23, "Visa Pichincha", "2026-04-20"),
        ("FYBECA", 12.50, "Diners", "2026-04-18"),
        ("UBER EATS", 8.99, "Visa Produbanco", "2026-04-22"),
        ("CORAL HIPERMERCADOS", 67.80, "Visa Pichincha", "2026-04-15"),
        ("MARATHON SPORTS", 35.00, "Diners", "2026-04-10"),
        ("KFC", 6.50, "Visa Produbanco", "2026-04-19"),
        ("PHARMACYS", 22.10, "Visa Pichincha", "2026-04-21"),
        ("AMAZON PRIME", 7.99, "Visa Produbanco", "2026-04-01"),
    ]
    while len(prompts) < n:
        s = synthetic[len(prompts) % len(synthetic)]
        prompts.append(_build_prompt(s[0], s[1], s[2], s[3], []))

    return prompts[:n]


def run_single(model: str, prompt: str) -> float:
    elapsed, _ = _call_llm(model, prompt)
    return elapsed


def run_parallel(model: str, prompts: list[str]) -> list[float]:
    times = []
    with ThreadPoolExecutor(max_workers=len(prompts)) as ex:
        futures = {ex.submit(_call_llm, model, p): i for i, p in enumerate(prompts)}
        for f in as_completed(futures):
            elapsed, _ = f.result()
            times.append(elapsed)
    return times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:e2b")
    ap.add_argument("--rounds", type=int, default=3, help="Rounds per concurrency level")
    args = ap.parse_args()

    model = args.model
    rounds = args.rounds
    max_parallel = 4

    # warmup
    print(f"Warming up {model}...")
    prompts = _get_test_prompts(max_parallel)
    _call_llm(model, prompts[0])
    print("Warm.\n")

    results = {}  # {concurrency: [wall_times]}

    for conc in [1, 2, 3, 4]:
        label = f"{conc} parallel" if conc > 1 else "1 (single)"
        results[conc] = []
        print(f"--- Concurrency: {label} ({rounds} rounds) ---")

        for r in range(rounds):
            batch = prompts[:conc]
            if conc == 1:
                t0 = time.time()
                elapsed = run_single(model, batch[0])
                wall = time.time() - t0
                results[conc].append(wall)
                print(f"  round {r+1}: wall={wall:.2f}s  call={elapsed:.2f}s")
            else:
                t0 = time.time()
                times = run_parallel(model, batch)
                wall = time.time() - t0
                results[conc].append(wall)
                per_call = [f"{t:.2f}s" for t in sorted(times)]
                print(f"  round {r+1}: wall={wall:.2f}s  per-call=[{', '.join(per_call)}]")

    print(f"\n{'='*55}")
    print(f"  SUMMARY — {model} — {rounds} rounds each")
    print(f"{'='*55}")
    print(f"  {'Concurrency':<14} {'Avg Wall':>10} {'Min':>8} {'Max':>8} {'Slowdown':>10}")
    print(f"  {'-'*14} {'-'*10} {'-'*8} {'-'*8} {'-'*10}")

    base_avg = sum(results[1]) / len(results[1])
    for conc in [1, 2, 3, 4]:
        times = results[conc]
        avg = sum(times) / len(times)
        mn = min(times)
        mx = max(times)
        slowdown = avg / base_avg
        label = f"{conc} parallel" if conc > 1 else "1 (single)"
        print(f"  {label:<14} {avg:>9.2f}s {mn:>7.2f}s {mx:>7.2f}s {slowdown:>9.2f}x")

    print()
    throughput_1 = 1 / base_avg
    for conc in [2, 3, 4]:
        avg = sum(results[conc]) / len(results[conc])
        throughput_n = conc / avg
        print(f"  Throughput: 1={throughput_1:.2f} req/s  {conc}={throughput_n:.2f} req/s  ({throughput_n/throughput_1:.1f}x)")


if __name__ == "__main__":
    main()

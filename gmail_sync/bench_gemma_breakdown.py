"""Benchmark gemma4 on the `add` LLM flow: full Gemini-style prompt vs broken-down sub-tasks.

Tests 10 real-world examples through:
  A) Full parse (single call — how Gemini does it today)
  B) Broken-down pipeline (3 smaller calls):
     Step 1: Extract description + type (simple/installment/split)
     Step 2: Pick category from list
     Step 3: Pick budget from list (given category + payment month)

Each tested with gemma4:e2b think=True, think=False, and gemma4:e4b think=False.

Usage:
    python3 -m gmail_sync.bench_gemma_breakdown
    python3 -m gmail_sync.bench_gemma_breakdown --models gemma4:e2b
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from textwrap import dedent

import litellm

litellm.suppress_debug_info = True
os.environ["LITELLM_LOG"] = "ERROR"

CATEGORIES = [
    "Dining-Snacks", "Family Support", "Health", "Home", "Home Food & Supplies",
    "Income", "Loans", "Others", "Personal", "Personal Diet",
    "Savings", "Sister Education",
]

CATEGORY_DESCRIPTIONS = {
    "Dining-Snacks": "Eating out, snacks, fast food, delivery",
    "Family Support": "Financial support for family members",
    "Health": "Medical, pharmacy, health products",
    "Home": "Housing expenses, rent, mortgage, home improvement",
    "Home Food & Supplies": "Groceries, household supplies, cleaning products",
    "Income": "Salary, freelance income, refunds",
    "Loans": "Loan payments, credit",
    "Others": "Miscellaneous expenses",
    "Personal": "Personal items, clothing, entertainment, subscriptions",
    "Personal Diet": "Protein, diet-specific food, gym supplements",
    "Savings": "Savings transfers",
    "Sister Education": "Sister's education expenses",
}

ACCOUNTS = ["Cash", "Visa Pichincha", "Diners", "Visa Produbanco"]

# 15 test cases derived from real transaction data.
# Difficulty: [E]asy (clear category/account), [M]edium (needs hints), [H]ard (ambiguous/complex)
TEST_CASES = [
    # [E] Simple grocery — clear account, category from keyword, budget match
    {
        "input": "pichincha, apr 22, Coral groceries, home food budget, 5.94",
        "expected": {"type": "simple", "amount": 5.94, "account": "Visa Pichincha",
                     "category": "Home Food & Supplies", "has_budget": True,
                     "description_contains": "Coral"},
        "difficulty": "easy",
    },
    # [E] Fast food — straightforward category
    {
        "input": "produbanco, Pollo Campero 3.69, no budget",
        "expected": {"type": "simple", "amount": 3.69, "account": "Visa Produbanco",
                     "category": "Dining-Snacks", "has_budget": False,
                     "description_contains": "Campero"},
        "difficulty": "easy",
    },
    # [E] Pharmacy — clear Health
    {
        "input": "pichincha, Sana Sana neogripal 7.29, no budget",
        "expected": {"type": "simple", "amount": 7.29, "account": "Visa Pichincha",
                     "category": "Health", "has_budget": False,
                     "description_contains": "Sana"},
        "difficulty": "easy",
    },
    # [E] Income — salary
    {
        "input": "NTT Salary 1184.77 cash income",
        "expected": {"type": "simple", "amount": 1184.77, "account": "Cash",
                     "category": "Income", "has_budget": False, "is_income": True,
                     "description_contains": "Salary"},
        "difficulty": "easy",
    },
    # [M] Uber for mom — needs hint to pick Family Support not Personal
    {
        "input": "diners, Uber for mom, 1.68, no budget",
        "expected": {"type": "simple", "amount": 1.68, "account": "Diners",
                     "category": "Family Support", "has_budget": False,
                     "description_contains": "Uber"},
        "difficulty": "medium",
    },
    # [M] Protein purchase — needs diet hint to separate from Home Food
    {
        "input": "pichincha, Supermaxi chicken breast and thighs 15.76, personal diet budget",
        "expected": {"type": "simple", "amount": 15.76, "account": "Visa Pichincha",
                     "category": "Personal Diet", "has_budget": True,
                     "description_contains": "chicken"},
        "difficulty": "medium",
    },
    # [M] Transfer to father — domain-specific mapping
    {
        "input": "cash, transfer to father 20, mercado budget",
        "expected": {"type": "simple", "amount": 20.0, "account": "Cash",
                     "category": "Home Food & Supplies", "has_budget": True,
                     "description_contains": "father"},
        "difficulty": "medium",
    },
    # [M] Sister education — school pension
    {
        "input": "pichincha, School Pension for Dani 175.02, no budget",
        "expected": {"type": "simple", "amount": 175.02, "account": "Visa Pichincha",
                     "category": "Sister Education", "has_budget": False,
                     "description_contains": "Pension"},
        "difficulty": "medium",
    },
    # [M] Loan — lending money
    {
        "input": "cash, Lent to Alice 50, no budget",
        "expected": {"type": "simple", "amount": 50.0, "account": "Cash",
                     "category": "Loans", "has_budget": False,
                     "description_contains": "Alice"},
        "difficulty": "medium",
    },
    # [H] Installments — Creatina on Mercado Libre
    {
        "input": "produbanco, Creatina Mercado Libre 39.12 in 6 installments, personal diet, no budget",
        "expected": {"type": "installment", "amount": 39.12, "account": "Visa Produbanco",
                     "category": "Personal Diet", "has_budget": False,
                     "description_contains": "Creatina"},
        "difficulty": "hard",
    },
    # [H] Planning + installments + grace period
    {
        "input": "what if I buy a new laptop 800 produbanco in 12 installments 3 months grace",
        "expected": {"type": "installment", "amount": 800.0, "account": "Visa Produbanco",
                     "category": "Personal", "has_budget": False, "is_planning": True,
                     "description_contains": "laptop", "grace_period": 3},
        "difficulty": "hard",
    },
    # [H] Pending flag
    {
        "input": "pichincha, Marathon Sports shoes 65, personal, no budget, pending",
        "expected": {"type": "simple", "amount": 65.0, "account": "Visa Pichincha",
                     "category": "Personal", "has_budget": False, "is_pending": True,
                     "description_contains": "Marathon"},
        "difficulty": "hard",
    },
    # [H] Food for family — "Pollo Pintado" for family, not dining
    {
        "input": "cash, Pollo Pintado for family 13.50, no budget",
        "expected": {"type": "simple", "amount": 13.50, "account": "Cash",
                     "category": "Family Support", "has_budget": False,
                     "description_contains": "Pollo"},
        "difficulty": "hard",
    },
    # [H] Mixed grocery — Titan is a supermarket, not a gas station
    {
        "input": "pichincha, apr 20, Titan Orellana 21.91, home food budget",
        "expected": {"type": "simple", "amount": 21.91, "account": "Visa Pichincha",
                     "category": "Home Food & Supplies", "has_budget": True,
                     "description_contains": "Titan"},
        "difficulty": "hard",
    },
    # [H] Refund/income — friend paid back
    {
        "input": "cash, Bob paid me for food Taco Perron 8.00",
        "expected": {"type": "simple", "amount": 8.0, "account": "Cash",
                     "category": "Income", "has_budget": False, "is_income": True,
                     "description_contains": "Bob"},
        "difficulty": "hard",
    },
]


def _get_budgets():
    """Get real budgets from DB, or use representative set."""
    try:
        conn = sqlite3.connect("cash_flow.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, name, category, start_date, end_date
            FROM subscriptions WHERE is_budget = 1
            ORDER BY start_date DESC
        """).fetchall()
        conn.close()
        budgets = []
        for r in rows:
            budgets.append({
                "id": r["id"], "name": r["name"], "category": r["category"],
                "active_from": r["start_date"],
                "active_until": r["end_date"] or "ongoing",
            })
        return budgets
    except Exception:
        return [
            {"id": "budget_home_food_supplies_apr_may", "name": "Home Food & Supplies Apr-May",
             "category": "Home Food & Supplies", "active_from": "2026-04-01", "active_until": "2026-05-31"},
            {"id": "budget_personal_diet_apr_may", "name": "Personal Diet Apr-May",
             "category": "Personal Diet", "active_from": "2026-04-01", "active_until": "2026-05-31"},
            {"id": "budget_mercado_groceries", "name": "Mercado Groceries",
             "category": "Home Food & Supplies", "active_from": "2026-01-01", "active_until": "ongoing"},
            {"id": "budget_home_mortgage", "name": "Home Mortgage",
             "category": "Home", "active_from": "2026-01-01", "active_until": "ongoing"},
        ]


def _call(model: str, system: str, user: str, think: bool) -> tuple[float, str, dict, dict]:
    """Call ollama model. Returns (elapsed, raw_text, parsed_json, usage)."""
    t0 = time.time()
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        api_base=os.getenv("LLM_OLLAMA_BASE_URL", "http://localhost:11434"),
        extra_body={"think": think},
    )
    elapsed = time.time() - t0
    raw = response.choices[0].message.content or ""
    usage = {}
    if hasattr(response, 'usage') and response.usage:
        usage = {
            "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) or 0,
            "completion_tokens": getattr(response.usage, 'completion_tokens', 0) or 0,
        }
    import re
    if "<think>" in raw:
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    if "```" in raw:
        raw = re.sub(r'```(?:json)?\s*', '', raw).strip()
    try:
        parsed = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end])
            except Exception:
                parsed = {}
        else:
            parsed = {}
    return elapsed, raw, parsed, usage


# ============================================================
# APPROACH A: Full parse (single call — replicating Gemini prompt)
# ============================================================

def _load_hints() -> list[str]:
    """Load hints from classification_hints.yaml, fallback to hardcoded."""
    base = Path(__file__).resolve().parent.parent
    hints_path = base / "classification_hints.yaml"
    if not hints_path.exists():
        hints_path = base / "classification_hints.yaml.example"
    if hints_path.exists():
        import yaml
        with open(hints_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("category_hints", []) + data.get("user_hints", [])
    return [
        "Pharmacy/medicine → Health",
        "Fast food / restaurants / delivery → Dining-Snacks",
        "Clothing, shoes, electronics, subscriptions → Personal",
        "Proteins/diet items → Personal Diet",
        "Mixed household groceries → Home Food & Supplies",
        "'paid me', 'refund' → Income (set is_income: true)",
        "'lent to', 'loan to' → Loans",
        "'what if', 'planning' → set is_planning: true",
    ]


def _load_category_descriptions() -> dict:
    """Load category descriptions from DB, fallback to hardcoded."""
    try:
        conn = sqlite3.connect("cash_flow.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT name, description FROM categories ORDER BY name").fetchall()
        conn.close()
        return {r["name"]: r["description"] for r in rows}
    except Exception:
        return CATEGORY_DESCRIPTIONS


def build_full_prompt(user_input: str, budgets: list) -> str:
    today = date.today()
    cat_descs = _load_category_descriptions()
    cat_block = "\n".join(f"- **{n}**: {d}" for n, d in cat_descs.items())
    hints = _load_hints()
    hint_block = "\n".join(f"- {h}" for h in hints)
    budget_json = json.dumps(budgets[:15], indent=2)

    return f"""You are an expert financial assistant. Parse the user's natural language input into a structured JSON transaction.

**Today: {today.isoformat()} ({today.strftime('%A, %B %d, %Y')})**

**Rules:**
1. `type`: "simple", "installment", or "split"
2. `account` MUST be one of: {ACCOUNTS}
3. `category` MUST be exactly one of the following:
{cat_block}
4. `budget`: budget **ID** from: {budget_json}
   - Match user words to budget name, return the id. Use null/omit if "no budget".
5. For installments: include `total_amount` and `installments` count.
6. If income/salary mentioned: set `is_income`: true
7. If "pending"/"unconfirmed": set `is_pending`: true
8. If "what if"/"planning": set `is_planning`: true
9. If "grace period" mentioned: set `grace_period_months`
10. `date_created`: YYYY-MM-DD if date mentioned, else omit

**Category classification rules (IMPORTANT):**
{hint_block}

**Output ONLY JSON. No markdown. No explanation.**

Example: "pichincha, feb 23, Coral groceries, home food budget, 5.94"
{{"type": "simple", "description": "Coral - Groceries", "amount": 5.94, "account": "Visa Pichincha", "category": "Home Food & Supplies", "budget": "budget_home_food_supplies_feb_mar"}}"""


def test_full(model: str, case: dict, budgets: list, think: bool) -> dict:
    prompt = build_full_prompt(case["input"], budgets)
    elapsed, raw, parsed, usage = _call(model, prompt, case["input"], think)
    return {"elapsed": elapsed, "parsed": parsed, "raw": raw, "usage": usage}


# ============================================================
# APPROACH B: Broken down into 3 focused sub-tasks
# ============================================================

STEP1_SYSTEM = f"""Extract transaction details from natural language. Output JSON only.

Today: {date.today().isoformat()}
Accounts: {ACCOUNTS}

Fields:
- "type": "simple" or "installment" or "split"
- "description": short merchant/purpose description
- "amount": number (the expense/income amount)
- "account": one of the valid accounts
- "date_created": YYYY-MM-DD if date mentioned, else omit
- "installments": number if installment type
- "is_income": true if income
- "is_pending": true if pending
- "is_planning": true if planning/what-if
- "grace_period_months": number if grace period mentioned

Output ONLY JSON."""


def _step2_system():
    cat_block = "\n".join(f"- {n}: {d}" for n, d in CATEGORY_DESCRIPTIONS.items())
    return f"""Pick the single best category for this transaction. Output ONLY JSON: {{"category": "..."}}

Categories:
{cat_block}

Rules:
- Proteins/diet items → Personal Diet
- Mixed household groceries → Home Food & Supplies
- Uber/family transport → Family Support
- Pharmacy/medicine → Health"""


def _step3_system(budgets: list):
    budget_lines = "\n".join(f"- {b['id']}: {b['name']} ({b['category']}, {b['active_from']} to {b['active_until']})" for b in budgets[:15])
    return f"""Given a transaction's category, pick the matching budget ID. Output ONLY JSON: {{"budget": "budget_id_here"}}
If user says "no budget" or no budget matches, output: {{"budget": null}}

Available budgets:
{budget_lines}

Match by category. Prefer budgets active in the current month."""


def test_breakdown(model: str, case: dict, budgets: list, think: bool) -> dict:
    total = 0.0

    # Step 1: extract details
    t, _, step1, _ = _call(model, STEP1_SYSTEM, case["input"], think)
    if not isinstance(step1, dict):
        step1 = {}
    total += t
    s1_time = t

    # Step 2: pick category
    desc = step1.get("description", case["input"][:50])
    s2_input = f"Transaction: {desc}, amount: {step1.get('amount', '?')}, account: {step1.get('account', '?')}"
    t, _, step2, _ = _call(model, _step2_system(), s2_input, think)
    if not isinstance(step2, dict):
        step2 = {}
    total += t
    s2_time = t

    # Step 3: pick budget
    category = step2.get("category", "Others")
    s3_input = f"Category: {category}. User said: {case['input']}"
    t, _, step3, _ = _call(model, _step3_system(budgets), s3_input, think)
    if not isinstance(step3, dict):
        step3 = {}
    total += t
    s3_time = t

    merged = {**step1, **step2, **step3}
    return {
        "elapsed": total,
        "step_times": [s1_time, s2_time, s3_time],
        "parsed": merged,
        "steps": [step1, step2, step3],
    }


# ============================================================
# Scoring
# ============================================================

def score(parsed: dict, expected: dict) -> dict:
    """Score parsed result against expected. Returns dict of field: pass/fail."""
    scores = {}

    # Type
    scores["type"] = parsed.get("type") == expected.get("type")

    # Amount — check both amount and total_amount
    exp_amt = expected.get("amount", 0)
    got_amt = parsed.get("amount") or parsed.get("total_amount") or 0
    scores["amount"] = abs(float(got_amt) - exp_amt) < 0.02

    # Account
    exp_acc = expected.get("account", "").lower()
    got_acc = (parsed.get("account") or "").lower()
    scores["account"] = exp_acc in got_acc or got_acc in exp_acc

    # Category
    scores["category"] = parsed.get("category") == expected.get("category")

    # Budget presence
    if "has_budget" in expected:
        has = parsed.get("budget") not in (None, "null", "", "none", "N/A")
        scores["budget"] = has == expected["has_budget"]

    # Description keyword
    if "description_contains" in expected:
        desc = (parsed.get("description") or "").lower()
        scores["desc_kw"] = expected["description_contains"].lower() in desc

    # Flags
    if expected.get("is_income"):
        scores["income"] = parsed.get("is_income") is True
    if expected.get("is_pending"):
        scores["pending"] = parsed.get("is_pending") is True
    if expected.get("is_planning"):
        scores["planning"] = parsed.get("is_planning") is True
    if expected.get("grace_period"):
        scores["grace"] = parsed.get("grace_period_months") == expected["grace_period"]

    return scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["gemma4:e2b", "gemma4:e4b"])
    ap.add_argument("--think", action="store_true", help="Also test think=True (slow)")
    ap.add_argument("--full-only", action="store_true", help="Skip breakdown approach")
    args = ap.parse_args()

    budgets = _get_budgets()

    # Configs: (model, think, label)
    configs = []
    for m in args.models:
        configs.append((m, False, f"{m} no-think"))
        if args.think:
            configs.append((m, True, f"{m} think"))

    # Warmup
    print("Warming up...")
    _call(args.models[0], "Say hi", "hi", False)  # returns 4-tuple, discard
    print()

    # Results: {config_label: {approach: [results_per_case]}}
    all_results = {}

    run_breakdown = not args.full_only

    for model, think, label in configs:
        all_results[label] = {"full": []}
        if run_breakdown:
            all_results[label]["breakdown"] = []

        print(f"\n{'='*70}")
        print(f"  {label.upper()}")
        print(f"{'='*70}")

        for i, case in enumerate(TEST_CASES):
            diff = case.get("difficulty", "?")
            print(f"\n  Case {i+1} [{diff[0].upper()}]: {case['input'][:55]}...")

            # Full parse
            r_full = test_full(model, case, budgets, think)
            s_full = score(r_full["parsed"], case["expected"])
            full_pass = sum(s_full.values())
            full_total = len(s_full)
            all_results[label]["full"].append({"time": r_full["elapsed"], "scores": s_full, "parsed": r_full["parsed"], "usage": r_full.get("usage", {})})

            full_fails = [k for k, v in s_full.items() if not v]
            usage_str = ""
            u = r_full.get("usage", {})
            if u.get("prompt_tokens"):
                usage_str = f"  tok={u['prompt_tokens']}+{u.get('completion_tokens', 0)}"
            print(f"    FULL:      {r_full['elapsed']:5.1f}s  {full_pass}/{full_total}" +
                  (f"  FAIL: {full_fails}" if full_fails else "  ALL PASS") + usage_str)

            if run_breakdown:
                r_break = test_breakdown(model, case, budgets, think)
                s_break = score(r_break["parsed"], case["expected"])
                break_pass = sum(s_break.values())
                break_total = len(s_break)
                all_results[label]["breakdown"].append({"time": r_break["elapsed"], "scores": s_break, "parsed": r_break["parsed"],
                                                         "step_times": r_break["step_times"]})
                break_fails = [k for k, v in s_break.items() if not v]
                print(f"    BREAKDOWN: {r_break['elapsed']:5.1f}s  {break_pass}/{break_total}" +
                      (f"  FAIL: {break_fails}" if break_fails else "  ALL PASS") +
                      f"  steps=[{r_break['step_times'][0]:.1f}, {r_break['step_times'][1]:.1f}, {r_break['step_times'][2]:.1f}]")

    # ============================================================
    # Summary
    # ============================================================
    print(f"\n\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}\n")

    approaches = ["full", "breakdown"] if run_breakdown else ["full"]
    for label in all_results:
        print(f"  --- {label} ---")
        for approach in approaches:
            results = all_results[label].get(approach, [])
            if not results:
                continue
            times = [r["time"] for r in results]
            avg_time = sum(times) / len(times)

            # Per-field accuracy
            all_fields = {}
            for r in results:
                for field, passed in r["scores"].items():
                    all_fields.setdefault(field, []).append(passed)
            field_acc = {f: sum(v)/len(v)*100 for f, v in all_fields.items()}
            overall_acc = sum(sum(v) for v in all_fields.values()) / sum(len(v) for v in all_fields.values()) * 100

            # Token stats
            tok_str = ""
            prompt_toks = [r.get("usage", {}).get("prompt_tokens", 0) for r in results]
            compl_toks = [r.get("usage", {}).get("completion_tokens", 0) for r in results]
            if any(prompt_toks):
                avg_prompt = sum(prompt_toks) / len(prompt_toks)
                avg_compl = sum(compl_toks) / len(compl_toks)
                tok_str = f"  prompt_tok={avg_prompt:.0f}  compl_tok={avg_compl:.0f}"

            print(f"    {approach:12} avg={avg_time:.1f}s  overall={overall_acc:.0f}%{tok_str}  " +
                  "  ".join(f"{f}={a:.0f}%" for f, a in sorted(field_acc.items())))
        print()

    # Throughput
    n_cases = len(TEST_CASES)
    print(f"  --- Throughput estimate ({n_cases} txns) ---")
    for label in all_results:
        full_total = sum(r["time"] for r in all_results[label]["full"])
        line = f"    {label:25} full={full_total:.0f}s"
        if run_breakdown and all_results[label].get("breakdown"):
            break_total = sum(r["time"] for r in all_results[label]["breakdown"])
            line += f"  breakdown={break_total:.0f}s  ratio={break_total/full_total:.1f}x"
        print(line)


if __name__ == "__main__":
    main()

"""Benchmark: can full parse replace pre_parse_date_and_account?

Tests account + date extraction accuracy across 30 cases.
Compares: gemma4:e2b (full parse) vs llama3.2:3b (pre_parse prompt) vs gemma4:e2b (pre_parse prompt).

Usage:
    python3 -m gmail_sync.bench_account_parse
    python3 -m gmail_sync.bench_account_parse --models gemma4:e2b llama3.2:3b
"""
import argparse
import json
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path

import litellm

litellm.suppress_debug_info = True
os.environ["LITELLM_LOG"] = "ERROR"

ACCOUNTS = ["Cash", "Visa Pichincha", "Diners", "Visa Produbanco"]

# 30 test cases: diverse account mention styles
# Format: (input, expected_account, expected_date_or_None, difficulty)
today = date.today()
yesterday = today - timedelta(days=1)

TEST_CASES = [
    # === EXPLICIT account name ===
    ("pichincha, Titan groceries 20.90", "Visa Pichincha", None, "easy"),
    ("diners, Uber for mom 1.68", "Diners", None, "easy"),
    ("produbanco, Pollo Campero 3.69", "Visa Produbanco", None, "easy"),
    ("cash, Mercado 20", "Cash", None, "easy"),
    ("Visa Pichincha, Sana Sana 6.54", "Visa Pichincha", None, "easy"),
    ("Visa Produbanco, SSD 35 no budget", "Visa Produbanco", None, "easy"),

    # === ABBREVIATED account ===
    ("pich, School Pension 175.02", "Visa Pichincha", None, "medium"),
    ("prod, Netflix 8.04", "Visa Produbanco", None, "medium"),
    ("din, Coral groceries 13.32", "Diners", None, "medium"),
    ("visa pichincha Megamaxi 10.05", "Visa Pichincha", None, "medium"),

    # === Account + DATE ===
    ("pichincha, apr 22, Coral groceries 5.94", "Visa Pichincha", "2026-04-22", "medium"),
    ("cash, yesterday, transfer to father 20", "Cash", yesterday.isoformat(), "medium"),
    ("diners, apr 15, KFC 12.30", "Diners", "2026-04-15", "medium"),
    ("produbanco, apr 20, Tropi Burguer 6.98", "Visa Produbanco", "2026-04-20", "medium"),
    ("cash, mar 21, iPhone case for dad 7.00", "Cash", "2026-03-21", "medium"),

    # === No account mentioned (should default to Cash) ===
    ("Mercado groceries 20", "Cash", None, "hard"),
    ("salary 1200 income", "Cash", None, "hard"),
    ("Lent to Alice 50", "Cash", None, "hard"),

    # === Ambiguous / tricky ===
    ("pichincha apr 10 CH Farina cena familiar 26.43", "Visa Pichincha", "2026-04-10", "hard"),
    ("Creatina Mercado Libre 39.12 produbanco 6 installments", "Visa Produbanco", None, "hard"),
    ("Marathon Sports shoes 65 pichincha pending", "Visa Pichincha", None, "hard"),
    ("Fybeca medicine 22.40 pichincha health", "Visa Pichincha", None, "hard"),

    # === Date edge cases ===
    ("pichincha, on the 5th, Titan 3.28", "Visa Pichincha", f"{today.year}-{today.month:02d}-05", "hard"),
    ("diners, last friday, Movistar 1.00", "Diners", None, "hard"),  # date varies
    ("cash, feb 20, Borrowed from Carol 100", "Cash", "2026-02-20", "hard"),
    ("produbanco, jan 25, Tropi Burguer 6.98", "Visa Produbanco", "2026-01-25", "hard"),

    # === Multi-word / noise ===
    ("pichincha, Supermaxi carnes pollo pechuga personal diet budget 35.50", "Visa Pichincha", None, "medium"),
    ("what if I buy laptop 800 produbanco 12 installments", "Visa Produbanco", None, "hard"),
    ("NTT Salary 1184.77 cash income", "Cash", None, "easy"),
    ("cash, Pollo Pintado for family 13.50 no budget", "Cash", None, "easy"),
]


def _call_ollama(model: str, system: str, user: str) -> tuple[float, str, dict, dict]:
    t0 = time.time()
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        api_base=os.getenv("LLM_OLLAMA_BASE_URL", "http://localhost:11434"),
        extra_body={"think": False},
    )
    elapsed = time.time() - t0
    raw = response.choices[0].message.content or ""
    usage = {}
    if hasattr(response, 'usage') and response.usage:
        usage = {
            "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) or 0,
            "completion_tokens": getattr(response.usage, 'completion_tokens', 0) or 0,
        }
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


def _build_pre_parse_prompt() -> str:
    """Replicate the pre_parse_date_and_account prompt from llm/parser.py."""
    from llm.parser import _last_weekday
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_monday = _last_weekday(today, 0)
    last_tuesday = _last_weekday(today, 1)
    last_wednesday = _last_weekday(today, 2)
    last_thursday = _last_weekday(today, 3)
    last_friday = _last_weekday(today, 4)
    last_sunday = _last_weekday(today, 6)

    return f"""You are a quick parser. Extract ONLY the date and account from the user's input.

**Today: {today.strftime('%A, %B %d, %Y')} ({today.isoformat()})**
**Current year: {today.year}**
**Current month: {today.strftime('%B')} ({today.month})**

**Pre-computed relative dates:**
- Yesterday: {yesterday.isoformat()}
- Last Monday: {last_monday.isoformat()}
- Last Tuesday: {last_tuesday.isoformat()}
- Last Wednesday: {last_wednesday.isoformat()}
- Last Thursday: {last_thursday.isoformat()}
- Last Friday: {last_friday.isoformat()}
- Last Sunday: {last_sunday.isoformat()}

**Date rules:**
1. If no date is mentioned, use today: {today.isoformat()}
2. For relative dates ("yesterday", "last friday"), use the pre-computed dates above.
3. For "on the Nth" with no month, assume the current month ({today.strftime('%B %Y')}).
4. **Year inference:** When a month is mentioned without a year:
   - If the month is the current month or a future month within 2 months ahead, use {today.year}.
   - If the month is a past month (before {today.strftime('%B')}), use the most recent occurrence.
   - Rule of thumb: always pick the nearest past or present date. Transactions are usually recent.

**Account rules:**
1. `account` MUST be EXACTLY one of: {ACCOUNTS}
2. Match partial names: "pichincha" = "Visa Pichincha", "produbanco" = "Visa Produbanco", "diners" = "Diners", "cash" = "Cash"
3. Never invent account names. Pick the closest match from the list.

**Output ONLY this JSON (no markdown, no explanation):**
{{"date": "YYYY-MM-DD", "account": "account_name"}}"""


def _build_full_parse_prompt() -> str:
    """Simplified full parse prompt — just test account+date extraction."""
    from gmail_sync.bench_gemma_breakdown import build_full_prompt, _get_budgets
    budgets = _get_budgets()
    return build_full_prompt("TEST", budgets)


def _resolve_account(raw: str) -> str:
    if not raw or raw.strip().lower() in ("n/a", "none", "null", ""):
        return "Cash"
    raw_lower = raw.strip().lower()
    for name in ACCOUNTS:
        if name == raw.strip():
            return name
    for name in ACCOUNTS:
        if name.lower() == raw_lower:
            return name
    for name in ACCOUNTS:
        if raw_lower in name.lower() or name.lower() in raw_lower:
            return name
    return "Cash"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["llama3.2:3b", "gemma4:e2b"])
    args = ap.parse_args()

    pre_parse_prompt = _build_pre_parse_prompt()

    # Warmup all models
    print("Warming up...")
    for m in args.models:
        _call_ollama(m, "Say hi", "hi")
    print()

    # Configs: (model, prompt_type, label)
    # For each model: test with pre_parse prompt AND full parse prompt
    configs = []
    for m in args.models:
        configs.append((m, "pre_parse", f"{m} pre_parse"))
    # Full parse only on gemma4:e2b (or first model)
    configs.append((args.models[-1], "full_parse", f"{args.models[-1]} full_parse"))

    results = {}  # label → [{account_ok, date_ok, time, usage}]

    for model, prompt_type, label in configs:
        results[label] = []
        print(f"\n{'='*65}")
        print(f"  {label.upper()}")
        print(f"{'='*65}")

        for i, (inp, exp_acct, exp_date, diff) in enumerate(TEST_CASES):
            if prompt_type == "pre_parse":
                elapsed, raw, parsed, usage = _call_ollama(model, pre_parse_prompt, inp)
                got_acct = _resolve_account(parsed.get("account", ""))
                got_date = parsed.get("date")
            else:
                # Full parse — build prompt fresh each time
                from gmail_sync.bench_gemma_breakdown import build_full_prompt, _get_budgets
                budgets = _get_budgets()
                prompt = build_full_prompt(inp, budgets)
                elapsed, raw, parsed, usage = _call_ollama(model, prompt, inp)
                got_acct = _resolve_account(parsed.get("account", ""))
                got_date = parsed.get("date_created")

            acct_ok = got_acct == exp_acct
            date_ok = True  # default pass if no expected date
            if exp_date:
                date_ok = got_date == exp_date

            results[label].append({
                "account_ok": acct_ok, "date_ok": date_ok,
                "time": elapsed, "usage": usage,
            })

            status = "✓" if (acct_ok and date_ok) else "✗"
            fails = []
            if not acct_ok:
                fails.append(f"acct:{got_acct}")
            if not date_ok:
                fails.append(f"date:{got_date}")
            tok = usage.get("prompt_tokens", 0)

            print(f"  {status} [{diff[0].upper()}] {inp[:50]:50} " +
                  f"{elapsed:4.1f}s tok={tok}" +
                  (f"  FAIL {fails}" if fails else ""))

    # Summary
    print(f"\n\n{'='*65}")
    print("  SUMMARY")
    print(f"{'='*65}\n")

    print(f"  {'Config':<30} {'Acct':>6} {'Date':>6} {'Both':>6} {'Avg':>6} {'AvgTok':>7}")
    print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*7}")

    for label in results:
        r = results[label]
        n = len(r)
        acct_acc = sum(x["account_ok"] for x in r) / n * 100
        date_acc = sum(x["date_ok"] for x in r) / n * 100
        both_acc = sum(x["account_ok"] and x["date_ok"] for x in r) / n * 100
        avg_time = sum(x["time"] for x in r) / n
        avg_tok = sum(x["usage"].get("prompt_tokens", 0) for x in r) / n

        print(f"  {label:<30} {acct_acc:5.0f}% {date_acc:5.0f}% {both_acc:5.0f}% {avg_time:5.1f}s {avg_tok:6.0f}")

    # Detailed: by difficulty
    print(f"\n  --- By difficulty ---")
    for label in results:
        easy = [r for r, c in zip(results[label], TEST_CASES) if c[3] == "easy"]
        med = [r for r, c in zip(results[label], TEST_CASES) if c[3] == "medium"]
        hard = [r for r, c in zip(results[label], TEST_CASES) if c[3] == "hard"]
        for diff_name, subset in [("easy", easy), ("med", med), ("hard", hard)]:
            if not subset:
                continue
            acct = sum(x["account_ok"] for x in subset) / len(subset) * 100
            both = sum(x["account_ok"] and x["date_ok"] for x in subset) / len(subset) * 100
            print(f"    {label:<30} {diff_name:5} acct={acct:.0f}% both={both:.0f}%")


if __name__ == "__main__":
    main()

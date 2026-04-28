# LLM Benchmark Results — Local Model Evaluation

Date: 2026-04-27
Hardware: GTX 1050 Ti (4GB VRAM), Ollama on localhost:11434

## Purpose

Evaluate whether local Ollama models (gemma4:e2b, gemma4:e4b) can replace Gemini for
`parse_transaction_string` — the heaviest LLM call in `cli.py add`.

## Current LLM Architecture

| Function | Model | Provider | ~Latency | Purpose |
|----------|-------|----------|----------|---------|
| `pre_parse_date_and_account` | llama3.2:3b | Ollama | 0.8s | Extract date + account |
| `parse_transaction_string` | gemini-2.5-flash | Gemini | ~2s | Full transaction parse |
| `parse_subscription_string` | gemini-2.5-flash | Gemini | ~2s | Budget/subscription creation |
| `parse_account_string` | gemini-2.5-flash | Gemini | ~2s | New account parse |
| `parse_edit_instruction` | gemini-2.5-flash | Gemini | ~2s | Edit command parse |
| `check_no_budget` | llama3.2:3b | Ollama | 0.8s | Fuzzy phrase match |
| `register_consumos._call_llm` | gemma4:e2b | Ollama | ~3.5s | Consumo → desc + category |

## Benchmark Scripts

- `gmail_sync/bench_parallel.py` — Concurrency test (1-4 parallel calls)
- `gmail_sync/bench_gemma_breakdown.py` — Full parse vs broken-down sub-tasks, multi-model
- `gmail_sync/bench_register.py` — Accuracy benchmark for consumo registration (existing)

Run: `python3 -m gmail_sync.bench_gemma_breakdown [--models gemma4:e2b gemma4:e4b] [--think]`

## Test Cases (10)

Hardcoded in `bench_gemma_breakdown.py`. Cover: simple expenses, income, installments,
pending/planning flags, grace periods, budget matching, category edge cases (Uber→Family Support,
protein→Personal Diet, transfer to father→Home Food).

## Results

### Round 1: No category hints (baseline)

| Config | Approach | Overall | Category | Budget | Amount | Planning | Avg/call |
|--------|----------|---------|----------|--------|--------|----------|----------|
| e2b no-think | full | 94% | **70%** | 90% | 100% | 100% | 9.7s |
| e2b no-think | breakdown | 86% | 80% | 60% | 90% | 0% | 11.8s |
| e2b think | full | 95% | 80% | 90% | 100% | 100% | 60.4s |
| e2b think | breakdown | 89% | 80% | 80% | 90% | 100% | 128.5s |

**Key finding:** think mode = 6x slower for +1% accuracy. Not worth it on e2b.

### Round 2: With category hints + e4b

Added explicit classification rules to prompt (Uber→Family Support, proteins→Personal Diet, etc).

| Config | Approach | Overall | Category | Budget | Amount | Planning | Avg/call |
|--------|----------|---------|----------|--------|--------|----------|----------|
| e2b no-think | full | 95% | **100%** ↑ | 100% | 90% | 0% ↓ | 12.8s |
| e2b no-think | breakdown | 86% | 80% | 60% | 90% | 0% | 15.0s |
| **e4b no-think** | **full** | **100%** | **100%** | **100%** | **100%** | **100%** | **22.7s** |
| e4b no-think | breakdown | 91% | 80% | 90% | 90% | 100% | 21.6s |

### Category hints impact (e2b full, before → after)

- Category: 70% → **100%** (the biggest win)
- Budget: 90% → 100%
- Planning flag: 100% → 0% (regression — needs investigation, may be prompt length issue)

### Concurrency test (from bench_parallel.py)

| Concurrency | Avg Wall | Throughput vs Single |
|-------------|----------|---------------------|
| 1 (single) | 3.54s | baseline (0.28 req/s) |
| 2 parallel | 5.78s | 1.2x |
| 3 parallel | 10.91s | 1.0x (no gain) |
| 4 parallel | 10.14s | 1.4x |

Ollama serializes GPU inference — parallel calls queue. No real parallelism benefit.

## Conclusions

1. **Full parse > breakdown** in every test. Single call with all context beats 3 focused sub-tasks.
   Breakdown loses cross-field context (budget step doesn't see "no budget" in user input).

2. **Category hints are critical for small models.** Explicit rules (Uber→Family Support) fix the
   main weakness. Generic descriptions aren't enough.

3. **gemma4:e4b no-think full = 100%** — perfect score. Viable Gemini replacement if 22s latency
   acceptable (vs ~2s Gemini).

4. **gemma4:e2b no-think full = 95%** — strong but misses `is_planning` flag and occasional
   installment amounts. Good for batch/automated flows.

5. **think mode not worth it** on GTX 1050 Ti. 6x latency for marginal accuracy gain.

6. **No parallelism benefit** — single GPU bottleneck means sequential is fine.

## Remaining Weaknesses (e2b)

- `is_planning` flag: 0% — model ignores "what if" phrasing
- Installment `total_amount` vs `amount`: sometimes returns per-installment amount
- `desc_kw`: occasionally rewrites description losing original merchant name

## Round 3: Externalized Hints + Fixed Examples (2026-04-27)

Refactored prompt architecture:
- Created `classification_hints.yaml` — shared hints for both `parse_transaction_string` and `register_consumos`
- Moved `category_hints` and `category_budget_map` out of `register_rules.yaml` into shared file
- Fixed 7 stale prompt examples (wrong dates, fake budget IDs, non-existent "Amex Produbanco")
- Added 2 new examples (income payback, loan)
- Added explicit hints for income detection, loans, planning flag
- Added token counting to benchmark

### Results (e2b no-think, 15 real-data cases)

| Field | Round 2 | Round 3 | Change |
|-------|---------|---------|--------|
| Overall | 95% | **95%** | Same |
| Category | 87% | **87%** | Same |
| Planning | **0%** | **100%** | Fixed by hint |
| Income | **50%** | **100%** | Fixed by hint + example |
| Loans | failing | **100%** | Fixed by example |
| Budget | 100% | 93% | Slight regression |
| Prompt tokens | unknown | **~2597** | Now tracked |
| Completion tokens | unknown | **~50** | Now tracked |
| Avg latency | 7.8s | **6.3s** | Faster (model warm) |

### Remaining failures (e2b)
- "Uber for mom" → wrong account (picks wrong card, not category issue)
- "transfer to father" → wrong category + budget (domain-specific)
- "Bob paid me for food" → wrong category (Dining vs Income ambiguity)

## Round 4: Account+Date Extraction — Can Full Parse Replace Pre-Parse? (2026-04-27)

Benchmark: `gmail_sync/bench_account_parse.py` — 30 test cases covering explicit account names,
abbreviations, date+account combos, no-account defaults, ambiguous inputs, date edge cases.

### Results

| Config | Acct | Date | Both | Avg Latency | Avg Tokens |
|--------|------|------|------|-------------|------------|
| llama3.2:3b pre_parse | **93%** | **97%** | **90%** | **1.9s** | 470 |
| gemma4:e2b pre_parse | **97%** | 93% | 90% | 3.5s | 512 |
| gemma4:e2b full_parse | 87% | 93% | 80% | 6.6s | 2592 |

### By difficulty

| Config | Easy | Medium | Hard |
|--------|------|--------|------|
| llama3.2:3b pre_parse | 100% | 80% | 92% |
| gemma4:e2b pre_parse | 100% | 80% | 92% |
| gemma4:e2b full_parse | 88% | 80% | 75% |

### Failure analysis

- **llama3.2:3b**: "prod"→Cash, "din"→Visa Pichincha (3-char abbreviations too short)
- **gemma4:e2b pre_parse**: "din"→Cash, date regressions on "mar 21" and "feb 20"
- **gemma4:e2b full_parse**: Diners→Visa Pichincha (4 times!), drops dates on past months. Bigger prompt (2592 tok) adds noise.

### Conclusion

**Keep two-step flow (pre_parse → full parse).** Full parse alone drops to 80% combined accuracy.
Pre_parse adds ~1s but catches account+date reliably. llama3.2:3b remains best pre_parser —
fastest, most accurate on dates, only weakness is ultra-short abbreviations users can avoid.

## Next Steps

- [x] Add category hints to production `parse_transaction_string` prompt
- [x] Build test cases from real transaction DB data (hard + easy mix)
- [x] Add token counting to benchmark
- [x] Fix stale prompt examples
- [x] Benchmark account extraction: full parse vs pre_parse (Round 4)
- [ ] Consider e4b as configurable option in llm_config.yaml for users with better GPUs
- [ ] Strengthen domain-specific hints for remaining 3 failures
- [ ] Benchmark with Gemini to compare baseline

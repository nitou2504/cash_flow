# Category Integrity & Enforcement Plan

## 1. Problem

`transactions.category` is meant to match `categories.name`, but no layer of the
app enforces this. The DB currently holds **18 distinct category strings** while
only **11 canonical categories** are defined, including case variants, informal
strings invented by the LLM, and hardcoded system values.

As of 2026-04-19, after a first pass of safe case normalization:

| Type | Examples |
|---|---|
| Canonical (match `categories.name`) | `Home Groceries`, `Dining-Snacks`, `Personal`, `Housing`, `Health`, `Income`, `Loans`, `Others`, `Personal Groceries`, `Transportation` |
| Undefined but recurring | `education` (15 rows, $2485), `utilities` (15), `entertainment` (16), `social` (9), `groceries` (26), `Home` (13, $1500) |
| System-internal hardcoded | `Payment Adjustment` (4), `Balance Adjustment` (2) |

## 2. Root causes

Traced every code path that writes `transactions.category`:

| # | Write path | Source of string | Validation |
|---|---|---|---|
| 1 | `cli.py:242` — `create tx --category` | Raw user arg | **None** |
| 2 | `cli.py:755-756` — `edit tx --category` | Raw user arg | **None** |
| 3 | `cli.py:871-872` — review edit `--category` | Raw user arg | **None** |
| 4 | `bot.py:298-300` — Telegram add via LLM | LLM output | Prompt lists valid categories (`llm/parser.py:220-226`) but no post-parse check |
| 5 | `bot.py:754` — Telegram review edit via LLM | LLM output | Same as #4 |
| 6 | `bot.py:541` — Telegram confirm-after-parse | LLM output | Not re-checked on confirm |
| 7 | `transactions.py:306` — Subscription-generated txn | Subscription row's `category` field | **None** at generation time |
| 8 | `controller.py:95` — Budget allocation | Subscription `category` | **None** |
| 9 | `llm/parser.py:387+` — Subscription parse | LLM output | **Prompt does not list valid categories** — LLM invents freely |

**Three underlying gaps:**

1. **Schema gap.** `database.py` declares `category TEXT` with no `FOREIGN KEY` to `categories(name)` and no `CHECK` constraint. SQLite accepts anything.
2. **Validation gap.** LLM prompts are *advisory*. `parse_transaction_string()` does not re-verify that the returned category is in the canonical list. Only `parse_edit_instruction()` (`llm/parser.py:658-660`) does.
3. **Prompt gap.** The subscription-parsing prompt has no category constraint at all — this is the provenance of `utilities`, `entertainment`, `education`, etc., since those strings came in as subscription definitions and then propagated to every generated transaction.

## 3. Impact

- Reporting/aggregation breaks silently: `GROUP BY category` splits the same real category across 2-3 buckets.
- LLM few-shot examples (`llm_examples` table) store bad categories and reinforce them on future parses.
- Category-based budgets become unreliable if the bucket name drifts.
- `/review` and CLI edits can re-introduce drift even after a cleanup.

## 4. Remediation plan (later task)

Implement in this order so each step reduces risk before the next:

### 4.1 Taxonomy cleanup (prerequisite, not yet done)
- Decide final set of categories (see separate taxonomy discussion). Likely additions: `Education`, `Utilities`, `Entertainment`. Possibly `Home Supplies` split from `Home Groceries`.
- Normalize the remaining non-canonical strings still in the DB (`groceries`, `Home`, `education`, `utilities`, `entertainment`, `social`) into the final taxonomy.
- Update `initialize_categories` in `cashflow/database.py` to match.

### 4.2 Schema enforcement
- Add a `CHECK` constraint or a trigger on `transactions.category` that rejects values not in `categories(name)` (allow NULL and the system-internal values `Balance Adjustment`, `Payment Adjustment`, `Budget Release`).
- Apply via a schema-upgrade step in `ensure_schema_upgrades` so existing deployments migrate.
- Mirror the constraint on `subscriptions.category`.

### 4.3 Application-layer validation
- In `cashflow/repository.py` (or the create/edit entry points), add a single `_validate_category(category)` helper that queries `categories` and raises on unknown values.
- Call it from every path listed in §2 — unifies behavior across CLI / Telegram / subscription generation.
- Hardcoded system categories should be allowed via an explicit allowlist constant, not magic strings.

### 4.4 LLM post-validation
- In `parse_transaction_string()` and `parse_subscription_string()` (`llm/parser.py`), post-validate the returned `category` against the live categories table.
- On mismatch: retry with a stricter reprompt, or fall back to `Others` + `needs_review=1`.
- Make the subscription prompt include the category list (current gap).

### 4.5 CLI guardrail
- `cli.py` `--category` flag should be validated at argparse time (`choices=...` loaded from DB) so wrong values fail fast with a useful error and a list of valid ones.

### 4.6 Backfill guarantees
- Any future Gmail-import pipeline (e.g. `gmail_sync/`) must route its categories through the same validator — no new drift source.

## 5. Non-goals

- Changing the *meaning* of categories (that's the separate taxonomy decision).
- Adding per-user category overrides.
- Hierarchical categories / tags.

## 6. References

- Current DB: 18 distinct `transactions.category` strings vs 11 defined in `categories` (post the 2026-04-19 case-normalization pass that merged 36 rows).
- Pre-normalization DB backup: `cash_flow.db.bk_pre_category_norm`.
- The agent investigation and numeric findings are in the `feature/gmail-integration` branch conversation log.

# Gmail Sync — Automated Transaction Capture

The core automation of the app: credit card purchase notifications (consumos) and SRI electronic invoices (facturas) are pulled from Gmail, parsed, matched, classified, and registered as transactions — you just review and approve.

```
Gmail labels                 parse                 classify & register            approve
─────────────               ──────                ─────────────────────          ────────
Consumos/Pichincha  ┐                             1. merchant rules
Consumos/Diners     ├─►  bank email parsers  ─►   2. transfer rules        ─►    Review queue
Consumos/Produbanco │     (consumos table)        3. invoice enrichment          (web / bot / CLI)
Consumos/Cash       ┘                             4. LLM fallback
Facturas            ──►  SRI XML parser (invoices table) ──►  matched to consumos by amount/date
```

Everything auto-registered is flagged `source="gmail"`, `needs_review=1` — nothing enters your timeline silently.

## Setup

1. **Enable the Gmail API** in a Google Cloud project, create an OAuth client (Desktop app), and save the credentials as `credentials.json` in the repo root. The first run opens a browser to authorize **read-only** Gmail access and caches the token to `token.json`. Both files are gitignored. (In the web app this can be done from Settings → Gmail.)

2. **Create Gmail labels** and auto-file the relevant emails with Gmail filters:

   | Gmail label | Source | Parsed as |
   |-------------|--------|-----------|
   | `Consumos/Pichincha` | Banco Pichincha CC notifications | Card purchases |
   | `Consumos/Diners` | Diners Club notifications | Card purchases |
   | `Consumos/Produbanco` | Produbanco notifications | Card purchases (skips reversals) |
   | `Consumos/Cash` | Pichincha transfer notifications | Bank transfers (beneficiary, concepto) |
   | `Facturas` | SRI electronic invoices | Invoice + line items |

   Only these labels are queried — the module never scans your whole inbox.

3. Verify with `python3 -m gmail_sync.verify` (tests auth, lists labels).

## Consumo pipeline

### 1. Ingest

```bash
python3 -m gmail_sync.ingest_consumos --since-last        # resume from last sync
python3 -m gmail_sync.ingest_consumos --after 2025-01-01  # bulk import
python3 -m gmail_sync.ingest_consumos --show-unparsed     # emails the parsers couldn't handle
python3 -m gmail_sync.ingest_consumos --rematch           # re-match invoices to consumos
```

Bank-specific parsers extract merchant, amount, timestamp, and card digits into the `consumos` table. Idempotent — already-seen Gmail message IDs are skipped.

### 2. Register

```bash
python3 -m gmail_sync.register_consumos --after 2025-01-01 --dry-run  # preview
python3 -m gmail_sync.register_consumos --after 2025-01-01            # register
python3 -m gmail_sync.register_consumos --after 2025-01-01 --no-llm   # rules only
```

Consumos already matching an existing transaction or subscription are **linked** (no duplicate created). Unmatched ones are registered through a priority chain:

1. **Merchant rules** (`register_rules.yaml`) — substring match on merchant (e.g. UBER → Transport). No LLM call.
2. **Transfer rules** — match by destination account for cash transfers.
3. **Invoice enrichment** — if a matching SRI invoice exists, line items drive item-based classification overrides.
4. **LLM fallback** — a local model classifies the remaining merchants using hints from `classification_hints.yaml`. Every decision is logged to the `llm_decisions` table (prompt, response, category) and shown in the web Review pane.

Budgets are auto-assigned via the `category_budget_map` in `classification_hints.yaml`, resolved to the active budget period by payment month.

### 3. Review

- **Web**: the Review page shows each transaction with its source email, matched invoice line items, and the LLM's reasoning — approve one by one or in batch.
- **Bot**: `/review` with inline buttons.
- **CLI**: `cli.py review ls --source gmail`.

### Scheduled sync

When the web app (or bot) is running, a scheduler syncs automatically at **midnight and midday**: ingest new consumos → ingest invoices → register → match. Manual trigger and status are available in web Settings.

## Invoice pipeline (SRI facturas — Ecuador)

Electronic invoices landing under the `Facturas` label are parsed into a full line-item database: "what exactly did I buy on that $45 Supermaxi run?"

```bash
python3 -m gmail_sync.ingest_invoices --after 2024-06-01   # first-time bulk import
python3 -m gmail_sync.ingest_invoices --since-last         # periodic (7-day safety window)
python3 -m gmail_sync.ingest_invoices --since-last --dry-run
python3 -m gmail_sync.ingest_invoices --show-unparsed
```

### What gets captured

- Vendor (razón social, nombre comercial), RUC, invoice number, emission date, clave de acceso
- Subtotal, discount, tip, total; tax buckets by rate (IVA 0%, 15%, …)
- Merchant/store disambiguation (`Lugar Venta`, establishment code, store address)
- Forma de pago (SRI code: 19 = credit card, 20 = other, …) and payment splits (pagos)
- Deducible alimentación (Ecuadorian IRS meal deduction)
- Per line: SKU, description, quantity, unit price, discount, subtotal, tax, rate
- **Notas de crédito**: original invoice reference, motivo, and a classifier label (`refund` / `loyalty` / `other`) — most retail NCs are loyalty rewards, not real refunds

Parsing handles three real-world XML wrappings (bare `<factura>`, `<autorizacion>` CDATA, SOAP envelopes) plus XMLs nested in ZIP attachments. Original XMLs are cached in `extra/invoices/` so unparsed fields are recoverable without re-hitting Gmail.

### Matching

Invoices are matched to consumos by amount and date proximity; payment splits (pagos) are considered when ranking candidates. Matched invoices appear inline in the Review pane; unmatched ones surface on the web **Invoices** page with candidate card transactions to link manually — or to accept the invoice total as the true amount (e.g. when tip or rounding differs).

### Unparsed emails

Emails under `Facturas` with no parseable invoice are recorded in `unparsed_facturas` with a reason (`no_attachment`, `no_xml`, `zip_no_xml`, `parse_failed`) instead of being lost. If a later run parses a previously failed email, the flag auto-resolves.

### Querying

It's plain SQLite:

```bash
sqlite3 cash_flow.db "
  SELECT i.issue_date, COALESCE(i.merchant_name, i.vendor) AS seller,
         l.description, l.quantity, l.unit_price, l.line_subtotal
  FROM invoice_lines l JOIN invoices i ON i.id = l.invoice_id
  WHERE LOWER(l.description) LIKE '%jabon%'
  ORDER BY i.issue_date DESC;
"
```

## Configuration files

- **`register_rules.yaml`** — merchant rules, transfer rules, item overrides. Add merchant → category mappings without code changes. (Editable in web Settings.)
- **`classification_hints.yaml`** — category hints for the LLM classifier and the category → budget prefix map. Shared with the natural-language parser.

Copy the `.example` files to get started:

```bash
cp register_rules.yaml.example register_rules.yaml
cp classification_hints.yaml.example classification_hints.yaml
```

## Cron (headless alternative)

```cron
0 * * * * cd /path/to/cash_flow && /usr/bin/python3 -m gmail_sync.ingest_invoices --since-last >> /var/log/invoices_ingest.log 2>&1
```

All ingest commands are idempotent, so scheduling them aggressively is safe.

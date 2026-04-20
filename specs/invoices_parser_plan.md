# Invoice Parser Plan

Goal: parse Ecuadorian SRI electronic invoices (already in Gmail under label `Facturas`) into a queryable store so we can:

1. **Answer "what was this transaction about?"** — given a bank-card transaction, show the line items, vendor, taxes.
2. **Track price history** — "have I seen this product cheaper before?" (deferred — Phase 5).

All work piggybacks on the existing `gmail_sync/` module (auth, Gmail client, attachment fetching, disk cache).

## Storage: separate SQLite

New database file **`invoices.db`** at repo root, independent of `cash_flow.db`. Linked only by an optional `transaction_id` on the `invoices` row.

Rationale: invoice data is bulky (per-item lines, taxes, refunds), rarely read from the hot path of the cash-flow CLI, and makes backups faster if kept separate. Joining across DBs is trivial via `ATTACH DATABASE` when needed.

### Schema

```sql
-- invoices.db
CREATE TABLE invoices (
    id                         INTEGER PRIMARY KEY,
    msg_id                     TEXT,                 -- Gmail message id
    doc_type                   TEXT NOT NULL,        -- 'factura' | 'nota_credito'
    invoice_number             TEXT UNIQUE NOT NULL, -- '042-916-000123394'
    clave_acceso               TEXT,                 -- 49-digit SRI access key (nullable)
    ruc                        TEXT NOT NULL,
    vendor                     TEXT NOT NULL,        -- razonSocial
    vendor_trade_name          TEXT,                 -- nombreComercial (friendlier)
    issue_date                 TEXT NOT NULL,        -- ISO YYYY-MM-DD
    subtotal_sin_impuesto      REAL NOT NULL,
    total_descuento            REAL NOT NULL,
    propina                    REAL NOT NULL DEFAULT 0,
    total                      REAL NOT NULL,        -- importeTotal | valorModificacion
    currency                   TEXT NOT NULL DEFAULT 'USD',
    -- Nota de crédito metadata
    refund_of_invoice_number   TEXT,                 -- numDocModificado
    refund_of_issue_date       TEXT,                 -- fechaEmisionDocSustento
    motivo                     TEXT,                 -- raw motivo text
    motivo_category            TEXT,                 -- 'loyalty' | 'refund' | 'other'
    -- Raw artifacts
    xml_path                   TEXT,                 -- relative path under extra/invoices/
    pdf_path                   TEXT,
    -- Linkage to main cash_flow DB (optional)
    transaction_id             INTEGER,
    ingested_at                TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoice_lines (
    id                         INTEGER PRIMARY KEY,
    invoice_id                 INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    line_number                INTEGER NOT NULL,     -- 1-based position
    sku                        TEXT,                 -- codigoPrincipal
    sku_aux                    TEXT,                 -- codigoAuxiliar
    description                TEXT NOT NULL,
    quantity                   REAL NOT NULL,
    unit_price                 REAL NOT NULL,        -- precioUnitario, pre-discount
    discount                   REAL NOT NULL DEFAULT 0,
    line_subtotal              REAL NOT NULL,        -- precioTotalSinImpuesto, post-discount pre-tax
    line_tax                   REAL NOT NULL,        -- sum of impuesto.valor
    line_total                 REAL NOT NULL,        -- line_subtotal + line_tax
    tax_rate                   REAL                  -- dominant tarifa, e.g. 15.0
);

CREATE TABLE invoice_taxes (
    id                         INTEGER PRIMARY KEY,
    invoice_id                 INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    tax_code                   INTEGER NOT NULL,     -- 2=IVA, 3=ICE, 5=IRBPNR
    rate_code                  INTEGER NOT NULL,     -- codigoPorcentaje
    rate_pct                   REAL NOT NULL,        -- derived: 0.0, 15.0, ...
    base_imponible             REAL NOT NULL,
    tax_value                  REAL NOT NULL
);

CREATE INDEX idx_invoices_date      ON invoices(issue_date);
CREATE INDEX idx_invoices_vendor    ON invoices(vendor);
CREATE INDEX idx_invoices_txn       ON invoices(transaction_id);
CREATE INDEX idx_invoices_ruc       ON invoices(ruc);
CREATE INDEX idx_lines_invoice      ON invoice_lines(invoice_id);
CREATE INDEX idx_lines_sku          ON invoice_lines(sku);
CREATE INDEX idx_lines_description  ON invoice_lines(description);
```

Idempotent ingest: upsert by `invoice_number` (estab-ptoEmi-secuencial is unique in SRI).

## Phases

### Phase 1 — Parser upgrade + tests
**Files:** `gmail_sync/invoice.py` (extend), `tests/test_invoice_parser.py` (new)

Extend `parse_sri_factura` to cover all three XML schema families we observed:

- **Family 1** (94.4%): bare `<factura>` or `<notaCredito>` root.
- **Family 2** (1%): `<autorizacion>` → `<comprobante>` CDATA → inner.
- **Family 3** (4.6%): `{soap:Envelope}` or `{sri:RespuestaAutorizacion}` with namespaced tags, nested `<autorizaciones>/<autorizacion>/<comprobante>` CDATA.

Add `parse_sri_nota_credito()` — same fields except total comes from `infoNotaCredito/valorModificacion`, plus `numDocModificado`, `fechaEmisionDocSustento`, `motivo`.

Classify notaCredito by `motivo`:
- Matches `/DEVOLUCION|DEVOLUCIÓN|Anulación/i` → `refund`
- Matches `/Plan de recompensas|Cash Back|MaxiRecargas/i` → `loyalty` (do not treat as refund)
- Else → `other` (logged for manual review)

Extend `Invoice` dataclass with `doc_type`, `clave_acceso`, `refund_of`, `motivo`, `motivo_category`, `invoice_taxes`, per-line `tax_rate` and `line_tax`.

Tests run against the **215 real XMLs already in `extra/invoices/`** (we audited their schemas). Assertions: parse success rate ≥ 99%, all extracted totals match XML ground truth within $0.01, all notaCredito classified without exception.

### Phase 2 — Invoice repository
**Files:** `cashflow/invoice_repository.py` (new), `cashflow/invoice_database.py` (new)

- `invoice_database.py::connect(path="invoices.db")` — returns connection, creates schema if missing.
- `invoice_repository.py` — CRUD helpers: `upsert_invoice`, `get_invoice_by_number`, `find_invoices_near(date, amount)`, `link_to_transaction(invoice_id, txn_id)`, `get_lines(invoice_id)`.

No migrations framework needed for v1 — single `CREATE IF NOT EXISTS` block.

### Phase 3 — Ingest CLI
**File:** `gmail_sync/ingest_invoices.py` (new), mirroring `enrich_missing.py` shape.

```bash
python3 -m gmail_sync.ingest_invoices --after 2025-01-01
python3 -m gmail_sync.ingest_invoices --after 2025-01-01 --link   # also link to existing transactions
```

Flow:
1. Resolve Gmail label `Facturas`.
2. Iterate messages (reuses `fetch_invoices`' caching).
3. Parse each; on success, upsert into `invoices.db`.
4. With `--link`: for each invoice, look up matching transaction using existing `find_matching_invoice` logic (±1 day, same total) and set `transaction_id`.
5. Report: parsed / skipped / errors / linked counts.

Reruns are idempotent: already-ingested `invoice_number`s get updated, not duplicated.

### Phase 4 — Transaction Q&A CLI ("what was this about?")
**File:** `cli.py` extension — new `invoice` subcommand.

```bash
cli.py invoice show <txn_id>                    # print vendor + lines
cli.py invoice show <txn_id> --summary          # LLM summary of the lines
cli.py invoice find <date> <amount>             # ad-hoc lookup
cli.py invoice by-number 042-916-000123394
```

`--summary` uses the existing LLM backend (Ollama first via `check_no_budget`-style local routing, Gemini fallback) to produce a one-line human summary: e.g. "Home groceries at Supermaxi: bread, eggs, cleaning supplies — $18.30".

### Phase 5 — Price history (deferred)
**Files:** TBD.

- Normalize `description` → `normalized_desc` (lowercase, strip packaging, dedupe "LTDA"/"CIA", unit extraction).
- Add `product_prices` view materializing (normalized_desc, min, avg, max, last_price, last_date, sample_size).
- `cli.py price "leche"` → shows every price seen for matching products across invoices + vendor of best price.
- Full product-name matching (e.g. "LECHE ENTERA 1L" ↔ "LECHE ENT 1000ML") may need an embedding model or LLM-based deduplication later. Start with exact + fuzzy substring; layer on top only if it hurts recall.

## Open decisions (for later)

- **notaCredito → transaction behavior.** Conservative v1: log but do not mutate linked transaction. Later: optionally subtract from linked transaction's amount.
- **HTML-body invoices** (~4%: Esthetic Dent, PagoPlux, Mercado Libre). Separate parser per format, or skip entirely for v1.
- **Payphone payment confirmations** (~2%): these are payment-side docs, not merchant invoices. Ignore for this pipeline.

## Milestones

- Phase 1: parser handles all 3 families + notaCredito, >99% pass on corpus.
- Phase 2: `invoice_repository` unit-tested.
- Phase 3: single `ingest_invoices` run loads all 215+ XMLs into `invoices.db`, idempotent on re-run.
- Phase 4: `cli.py invoice show <txn_id>` works for any CC transaction with a matching invoice.
- Phase 5 (later): price-history CLI.

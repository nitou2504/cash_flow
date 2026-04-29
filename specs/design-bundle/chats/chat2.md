# Invoice Details View

_Started 2026-04-28 17:02 UTC_

---

## User

I wan to edit/add a screen. IFor the transactions that have a invoice linked i would like a button and a view to see the details of that pourchase like item count, price, tax , etc

## Assistant

I'll take a look at the existing Cash Flow design to understand the visual system, then add the invoice detail view.

_[tool: list_files]_

_[tool: read_file]_

_[tool: list_files]_

_[tool: list_files]_

_[tool: list_files]_

_[tool: list_files]_

I see there's both PascalCase and lowercase versions. Let me check which are being loaded (lowercase per the html) and read them.

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

_[tool: read_file]_

I have what I need. Let me look at TxnRow and the review screen to find where invoice rendering happens, then build an invoice detail view.

_[tool: grep]_

_[tool: grep]_

_[tool: read_file]_

_[tool: snip]_

I have a clear picture. Now let me plan:

**Plan:**
1. Enrich the data: add `invoice` data (with full line items, subtotal, IVA tax, etc.) to a handful of `TXNS` that match real merchants.
2. Add an "Invoice" indicator on `TxnRow` for transactions that have a linked invoice (with a button/click target).
3. Build a new `InvoiceDetail` slide-over panel showing: vendor info, invoice number, issue date, line items (qty × price), subtotal, IVA 12%, total, payment method, etc. Styled like an SRI factura electrónica (Ecuadorian electronic invoice).
4. Wire it into the Timeline screen — clicking the "View invoice" button on a row opens the detail panel.
5. Add a new artboard in the design canvas showing the open state.

Let me start.

_[tool: update_todos]_

## Step 1: Enrich data with invoice details

_[tool: str_replace_edit]_

## Step 2: Update TxnRow with invoice indicator + button

I need a "View invoice" affordance. The row is dense; the cleanest is a small inline icon-pill that becomes a click target. I'll also pass through an `onViewInvoice` handler.

_[tool: str_replace_edit]_

Now I'll add the invoice button into the description cell. Looking at the row layout, the cleanest spot is a small inline pill in the description's secondary line.

_[tool: str_replace_edit]_

## Step 3: Build the InvoiceDetail slide-over

_[tool: write_file]_

_[tool: snip]_

## Step 4: Wire it into Timeline

_[tool: str_replace_edit]_

## Step 5: Register the new screen + add an artboard showing the invoice open

_[tool: str_replace_edit]_

_[tool: snip]_

Now add a new artboard showing the invoice drawer open. Make it taller for the larger detail view.

_[tool: str_replace_edit]_

_[tool: snip]_

_[tool: done]_

_[tool: snip]_

_[tool: fork_verifier_agent]_

Added an **Invoice** detail view linked from transactions that have a matched invoice.

**What's new:**
- `Invoice` pill on transaction rows where an invoice is linked (currently 6 txns: Supermaxi, Multicines, La Tablita, Fybeca, Mr. Books, Impaqto). Clicking it opens a slide-over.
- New `InvoiceDrawer` screen showing factura electrónica details:
  - Vendor (RUC, address) + customer block
  - Linked transaction summary
  - Line items table with qty, unit price, line total, IVA per line, SKU, discounts
  - Totals breakdown: subtotal IVA 0% / 12%, discount, IVA 12%, propina, grand total
  - Payment method + SRI authorization code
  - Footer: Open original / Download XML / Download PDF
- Closes via Esc, the X button, or backdrop click.
- New `Timeline · Invoice detail open` artboard in the canvas previewing the open state on La Tablita's $64 dinner.

Try clicking the **Invoice** pill on any committed transaction in the Timeline.

## User

Apply comment

## Assistant

## Assistant

_[tool: snip]_

_[tool: str_replace_edit]_

## User

Address these comments from my teammates:

**Diego**:
whats this for_ isnt the same as whats already on category?

## Assistant

_[tool: snip]_

_[tool: snip]_

Diego is right — the second-line meta on the row currently shows the budget category (e.g. "↳ Dining"), and the row already has a dedicated **Category** column. That's a duplication. Let me check the row to confirm what's there now and clean it up.

_[tool: read_file]_

Confirmed — `↳ {budgetName(txn.budget)}` is essentially the same info as the Category column (Dining budget → Dining category, etc). I'll drop it from the row meta and keep just `src:` and `invoice`.

_[tool: str_replace_edit]_

_[tool: snip]_

_[tool: done]_

Done — dropped the redundant `↳ Budget` meta from the row since it duplicated the Category column.


// Cash Flow — Transactions / Timeline screen
// Big chart with scrubber tied to rows, running balance column, filters.

const { useState: useStateTx, useMemo: useMemoTx, useRef: useRefTx, useEffect: useEffectTx } = React;

function Timeline({ initialInvoiceTxnId = null } = {}) {
  const [scrubIdx, setScrubIdx] = useStateTx(BALANCE_SERIES.length - 1);
  const [view, setView] = useStateTx('timeline'); // timeline | created | summary
  const [showPlanning, setShowPlanning] = useStateTx(true);
  const [accountFilter, setAccountFilter] = useStateTx('all');
  const [invoiceTxnId, setInvoiceTxnId] = useStateTx(initialInvoiceTxnId);

  const rowRefs = useRefTx({});
  const reviewCount = TXNS.filter(t => t.needs_review).length;

  // Build timeline rows, sorted by date_payed.
  const rows = useMemoTx(() => {
    const filtered = TXNS.filter(t => {
      if (!showPlanning && t.status === 'planning') return false;
      if (accountFilter !== 'all' && t.account !== accountFilter) return false;
      return true;
    });
    const sorted = [...filtered].sort((a, b) => a.date_payed.localeCompare(b.date_payed));

    // Compute running balance (skipping pending)
    let bal = 5240.50; // starting balance
    return sorted.map(t => {
      const counted = t.status !== 'pending';
      if (counted) bal += t.amount;
      return { ...t, balance: counted ? bal : null };
    });
  }, [showPlanning, accountFilter]);

  // Scrub date — used to highlight nearest row
  const scrubDate = BALANCE_SERIES[scrubIdx]?.date;
  const highlightedId = useMemoTx(() => {
    if (!scrubDate) return null;
    const matches = rows.filter(r => r.date_payed === scrubDate);
    return matches.length ? matches[matches.length - 1].id : null;
  }, [rows, scrubDate]);

  // Scroll to highlighted row when scrubbing
  useEffectTx(() => {
    if (highlightedId && rowRefs.current[highlightedId]) {
      rowRefs.current[highlightedId].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightedId]);

  // Group rows by month for headers
  const grouped = useMemoTx(() => {
    const map = new Map();
    rows.forEach(r => {
      const m = r.date_payed.slice(0, 7);
      if (!map.has(m)) map.set(m, []);
      map.get(m).push(r);
    });
    return [...map.entries()];
  }, [rows]);

  const invoiceTxn = invoiceTxnId ? rows.find(r => r.id === invoiceTxnId) || TXNS.find(t => t.id === invoiceTxnId) : null;

  return (
    <div className="cf-app" style={{ display: 'flex', height: '100%', position: 'relative' }}>
      <Sidebar active="transactions" badges={{ review: reviewCount }}/>
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Topbar title="Transactions" subtitle={`${rows.length} entries · running balance shown`}>
          <Btn kind="soft" size="sm" icon={I.filter}>Filters</Btn>
          <Btn kind="soft" size="sm" icon={I.calendar}>Apr 2026</Btn>
          <Btn kind="primary" size="sm" icon={I.plus}>Add</Btn>
        </Topbar>

        {/* Chart panel */}
        <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-elev)', padding: '14px 24px 8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 14 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  {scrubDate ? fmtDateLong(scrubDate) : 'Hover to scrub'}
                </div>
                <div className="num" style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em' }}>
                  ${BALANCE_SERIES[scrubIdx]?.balance.toFixed(2)}
                </div>
              </div>
              <div style={{ height: 32, width: 1, background: 'var(--border)' }}/>
              <Stat k="Mo. change" v="+$186.40" tone="pos"/>
              <Stat k="Forecast end of May" v="$5,612.00"/>
              <Stat k="Lowest in period" v="$3,012.10" tone="warn"/>
            </div>
            <Segmented value={view} onChange={setView} options={[
              { value: 'timeline', label: 'Timeline' },
              { value: 'created', label: 'Created' },
              { value: 'summary', label: 'Summary' },
            ]} size="sm"/>
          </div>
          <BalanceChart series={BALANCE_SERIES} height={130} scrubIndex={scrubIdx} onScrub={setScrubIdx}/>
        </div>

        {/* Filter bar */}
        <div style={{ padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
          <Segmented value={accountFilter} onChange={setAccountFilter} size="sm" options={[
            { value: 'all', label: 'All accounts' },
            ...ACCOUNTS.map(a => ({ value: a.id, label: a.name })),
          ]}/>
          <span style={{ flex: 1 }}/>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--fg-muted)' }}>
            <input type="checkbox" checked={showPlanning} onChange={e => setShowPlanning(e.target.checked)} style={{ accentColor: 'var(--accent)' }}/>
            Show planning
          </label>
          <Btn kind="ghost" size="sm" icon={I.more}>Export CSV</Btn>
        </div>

        {/* Header row */}
        <div style={{
          display: 'grid', gridTemplateColumns: '78px 1fr 130px 110px 120px 130px',
          gap: 12, padding: '8px var(--row-px)', background: 'var(--bg-sunken)',
          borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 600,
          color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase',
        }}>
          <div>Date</div>
          <div>Description</div>
          <div>Account</div>
          <div>Category</div>
          <div style={{ textAlign: 'right' }}>Amount</div>
          <div style={{ textAlign: 'right' }}>Balance</div>
        </div>

        {/* Rows */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {grouped.map(([month, items]) => {
            const lastBal = [...items].reverse().find(i => i.balance != null)?.balance;
            const totalIn = items.filter(i => i.amount > 0 && i.status === 'committed').reduce((s, i) => s + i.amount, 0);
            const totalOut = items.filter(i => i.amount < 0 && i.status === 'committed').reduce((s, i) => s + Math.abs(i.amount), 0);
            return (
              <div key={month}>
                <GroupHeader
                  label={new Date(month + '-01').toLocaleDateString('en', { month: 'long', year: 'numeric' })}
                  balance={lastBal} totalIn={totalIn} totalOut={totalOut}
                />
                {items.map(t => (
                  <div key={t.id} ref={el => rowRefs.current[t.id] = el}>
                    <TxnRow
                      txn={t}
                      balance={t.balance}
                      showBalance
                      selected={highlightedId === t.id || invoiceTxnId === t.id}
                      onViewInvoice={(tx) => setInvoiceTxnId(tx.id)}
                    />
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </main>
      {invoiceTxn && INVOICES[invoiceTxn.id] ? (
        <InvoiceDrawer txn={invoiceTxn} invoice={INVOICES[invoiceTxn.id]} onClose={() => setInvoiceTxnId(null)}/>
      ) : null}
    </div>
  );
}

function Stat({ k, v, tone = 'neutral' }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: 'var(--fg-faint)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>{k}</div>
      <div className="num" style={{ fontSize: 13.5, fontWeight: 600, color: tone === 'pos' ? 'var(--pos)' : tone === 'neg' ? 'var(--neg)' : tone === 'warn' ? 'var(--warn)' : 'var(--fg)' }}>{v}</div>
    </div>
  );
}

Object.assign(window, { Timeline });

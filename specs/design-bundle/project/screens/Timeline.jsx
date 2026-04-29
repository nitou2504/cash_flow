// Cash Flow — Timeline screen
// Big chart + scrubber that highlights the corresponding row in the txn list.

const { useState: useStateTL, useMemo: useMemoTL, useRef: useRefTL, useEffect: useEffectTL } = React;

function TimelineScreen({ density = 'balanced', includePlanning = true }) {
  const [view, setView] = useStateTL('timeline'); // timeline | created | summary
  const [scrubIdx, setScrubIdx] = useStateTL(BALANCE_SERIES.length - 1);
  const [filter, setFilter] = useStateTL('all'); // all | committed | pending | planning
  const rowRefs = useRefTL({});
  const listRef = useRefTL(null);

  const txns = useMemoTL(() => {
    const filtered = TXNS.filter(t => {
      if (!includePlanning && t.status === 'planning') return false;
      if (filter === 'all') return true;
      return t.status === filter;
    });
    return [...filtered].sort((a, b) => a.date_payed.localeCompare(b.date_payed));
  }, [filter, includePlanning]);

  // running balance map per row
  const rowsWithBalance = useMemoTL(() => {
    let bal = 5240.50 - TXNS.filter(t => t.status === 'committed').reduce((s, t) => s + t.amount, 0); // approx start
    // simpler: use BALANCE_SERIES; lookup by date
    const balByDate = {};
    BALANCE_SERIES.forEach(p => { balByDate[p.date] = p.balance; });
    let last = 5240.50;
    return txns.map(t => {
      if (t.status === 'pending') return { ...t, _bal: null };
      last = balByDate[t.date_payed] ?? last + t.amount;
      return { ...t, _bal: last };
    });
  }, [txns]);

  // group by date
  const groups = useMemoTL(() => {
    const g = {};
    rowsWithBalance.forEach(t => {
      const k = t.date_payed;
      if (!g[k]) g[k] = { date: k, items: [], in: 0, out: 0 };
      g[k].items.push(t);
      if (t.amount > 0) g[k].in += t.amount; else g[k].out += -t.amount;
    });
    return Object.values(g);
  }, [rowsWithBalance]);

  // map scrub to a date → scroll list
  const scrubDate = BALANCE_SERIES[scrubIdx]?.date;
  useEffectTL(() => {
    if (!scrubDate) return;
    const el = rowRefs.current[scrubDate];
    if (el && listRef.current) {
      const top = el.offsetTop - 80;
      listRef.current.scrollTo({ top, behavior: 'smooth' });
    }
  }, [scrubDate]);

  const cur = BALANCE_SERIES[scrubIdx];

  return (
    <div data-density={density} style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Topbar title="Transactions" subtitle={`${txns.length} entries · April 2026`}>
        <Segmented value={view} onChange={setView} options={[
          { value: 'timeline', label: 'Timeline' },
          { value: 'created', label: 'Created' },
          { value: 'summary', label: 'Summary' },
        ]} size="sm"/>
        <Btn icon={I.filter} kind="soft" size="sm">Filters</Btn>
        <Btn icon={I.plus} kind="primary" size="sm">Add</Btn>
      </Topbar>

      {/* Chart band */}
      <div style={{ borderBottom: '1px solid var(--border)', padding: '20px 28px', background: 'var(--bg-sunken)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 24, marginBottom: 10 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
              Balance on {fmtDateLong(cur?.date)}
            </div>
            <div className="num" style={{ fontSize: 30, fontWeight: 600, letterSpacing: '-0.02em' }}>${cur?.balance.toFixed(2)}</div>
          </div>
          <div style={{ flex: 1 }}/>
          <Stat label="Month start" value={`$${BALANCE_SERIES[0]?.balance.toFixed(2)}`}/>
          <Stat label="Month end (forecast)" value={`$${BALANCE_SERIES[BALANCE_SERIES.length-1]?.balance.toFixed(2)}`}/>
          <Stat label="Net change" value={`+$${(BALANCE_SERIES[BALANCE_SERIES.length-1].balance - BALANCE_SERIES[0].balance).toFixed(2)}`} pos/>
        </div>
        <BalanceChart series={BALANCE_SERIES} height={160} scrubIndex={scrubIdx} onScrub={setScrubIdx}/>
      </div>

      {/* Filter bar */}
      <div style={{ padding: '10px 28px', display: 'flex', gap: 10, alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
        <Segmented value={filter} onChange={setFilter} options={[
          { value: 'all', label: 'All' },
          { value: 'committed', label: 'Committed' },
          { value: 'pending', label: 'Pending' },
          { value: 'planning', label: 'Planning' },
        ]} size="sm"/>
        <span style={{ fontSize: 12, color: 'var(--fg-faint)' }}>·</span>
        <FilterChip label="Account" value="All"/>
        <FilterChip label="Category" value="All"/>
        <FilterChip label="Date" value="Apr 2026"/>
        <span style={{ flex: 1 }}/>
        <Btn kind="ghost" size="sm">Export CSV</Btn>
      </div>

      {/* Column headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '78px 1fr 130px 110px 120px 130px',
        gap: 12, padding: '8px var(--row-px)', fontSize: 11,
        color: 'var(--fg-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600,
        borderBottom: '1px solid var(--border)', background: 'var(--bg)',
      }}>
        <div>Pay date</div>
        <div>Description</div>
        <div>Account</div>
        <div>Category</div>
        <div style={{ textAlign: 'right' }}>Amount</div>
        <div style={{ textAlign: 'right' }}>Balance</div>
      </div>

      {/* List */}
      <div ref={listRef} style={{ flex: 1, overflow: 'auto', background: 'var(--bg)' }}>
        {groups.map(g => {
          const isScrub = g.date === scrubDate;
          const lastBal = [...g.items].reverse().find(x => x._bal != null)?._bal;
          return (
            <div key={g.date} ref={el => rowRefs.current[g.date] = el}>
              <GroupHeader label={fmtDateLong(g.date)} balance={lastBal} totalIn={g.in || null} totalOut={g.out || null}/>
              {g.items.map(t => (
                <TxnRow key={t.id} txn={t} balance={t._bal} showBalance selected={isScrub}/>
              ))}
            </div>
          );
        })}
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg-faint)', fontSize: 12 }}>End of period · {txns.length} transactions</div>
      </div>
    </div>
  );
}

function Stat({ label, value, pos }) {
  return (
    <div style={{ lineHeight: 1.2 }}>
      <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{label}</div>
      <div className="num" style={{ fontSize: 14, fontWeight: 600, color: pos ? 'var(--pos)' : 'var(--fg)' }}>{value}</div>
    </div>
  );
}

function FilterChip({ label, value }) {
  return (
    <button style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: 'var(--bg-elev)', border: '1px solid var(--border)',
      borderRadius: 7, padding: '4px 9px', fontSize: 12,
      color: 'var(--fg-muted)',
    }}>
      <span style={{ color: 'var(--fg-faint)' }}>{label}:</span>
      <span style={{ color: 'var(--fg)', fontWeight: 550 }}>{value}</span>
      {I.chevD}
    </button>
  );
}

Object.assign(window, { TimelineScreen });

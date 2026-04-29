// Cash Flow — Dashboard screen
// Layout: top KPI row + balance chart, then 2-col: budgets / recent txns / upcoming.

const { useState: useStateDash, useMemo: useMemoDash } = React;

function DashboardScreen({ density = 'balanced' }) {
  const [scrubIdx, setScrubIdx] = useStateDash(BALANCE_SERIES.length - 1);
  const [range, setRange] = useStateDash('1M');

  const cash = ACCOUNT_BALANCES.cash;
  const visa = ACCOUNT_BALANCES.cc_visa;
  const amex = ACCOUNT_BALANCES.cc_amex;
  const totalAvailable = cash.available;
  const totalDebt = -(visa.current + amex.current);
  const netWorth = cash.current + visa.current + amex.current;

  // April spending totals
  const aprSpent = TXNS.filter(t => t.status === 'committed' && t.amount < 0 && t.date_payed.startsWith('2026-04')).reduce((s, t) => s + Math.abs(t.amount), 0);
  const aprIn = TXNS.filter(t => t.status === 'committed' && t.amount > 0 && t.date_payed.startsWith('2026-04')).reduce((s, t) => s + t.amount, 0);

  // Recent committed transactions (last 6)
  const recent = TXNS.filter(t => t.status === 'committed').slice(-6).reverse();
  // Upcoming (pending + planning + forecast, next 5)
  const upcoming = TXNS.filter(t => ['pending', 'planning', 'forecast'].includes(t.status)).slice(0, 5);

  return (
    <div data-density={density} style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Topbar title="Dashboard" subtitle="April 2026 · Personal">
        <Segmented value={range} onChange={setRange} options={['1W', '1M', '3M', '1Y']} size="sm"/>
        <Btn icon={I.plus} kind="primary" size="sm">Add transaction</Btn>
      </Topbar>

      <div style={{ flex: 1, overflow: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* KPI strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
          <KPI title="Available" value={totalAvailable} delta={+182.40} pct={+4.5} icon={I.wallet}/>
          <KPI title="CC Debt" value={-totalDebt} negative delta={-94.20} pct={-9.2} icon={I.card}/>
          <KPI title="Spent in April" value={-aprSpent} delta={null} sub={`of $2,400 budget · ${Math.round(aprSpent/2400*100)}%`} progress={aprSpent/2400} icon={I.arrowDown}/>
          <KPI title="Income in April" value={aprIn} delta={null} sub="On track · 100% rec'd" pos icon={I.arrowUp}/>
        </div>

        {/* Balance chart */}
        <Card padding={0}>
          <div style={{ display: 'flex', alignItems: 'baseline', padding: '18px 20px 0', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Running balance</div>
              <div className="num" style={{ fontSize: 32, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 2 }}>
                ${BALANCE_SERIES[scrubIdx]?.balance.toFixed(2)}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--fg-muted)' }}>
                {fmtDateLong(BALANCE_SERIES[scrubIdx]?.date)} · drag to scrub
              </div>
            </div>
            <Segmented value={range} onChange={setRange} options={['1M', '3M', 'YTD', '1Y']} size="sm"/>
            <Btn kind="ghost" size="sm" icon={I.spark}>Add forecast</Btn>
          </div>
          <BalanceChart series={BALANCE_SERIES} height={220} scrubIndex={scrubIdx} onScrub={setScrubIdx}/>
        </Card>

        {/* Budgets + Recent */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Card title="Budget envelopes" subtitle="April 2026 · 6 active" action={<Btn kind="ghost" size="sm">All →</Btn>}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {BUDGETS.map(b => <BudgetRow key={b.id} b={b}/>)}
            </div>
          </Card>

          <Card title="Recent activity" subtitle="Last 6 committed" action={<Btn kind="ghost" size="sm">Timeline →</Btn>}>
            <div style={{ margin: '0 -18px' }}>
              {recent.map(t => (
                <TxnRow key={t.id} txn={t} compact showAccount={false}/>
              ))}
            </div>
          </Card>
        </div>

        {/* Upcoming + Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 14 }}>
          <Card title="Upcoming" subtitle="Pending, planning, forecast" action={<Pill tone="warn" dot>3 need review</Pill>}>
            <div style={{ margin: '0 -18px' }}>
              {upcoming.map(t => <TxnRow key={t.id} txn={t} compact/>)}
            </div>
          </Card>

          <Card title="Credit cards" subtitle="2 cards · next due Apr 22">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <CCCard name="Visa Pichincha" last4="4471" balance={visa.current} limit={visa.limit} due={visa.dueDate} min={visa.minPay} color="oklch(0.62 0.14 30)"/>
              <CCCard name="Amex Gold" last4="8810" balance={amex.current} limit={amex.limit} due={amex.dueDate} min={amex.minPay} color="oklch(0.55 0.06 250)"/>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function KPI({ title, value, delta, pct, sub, icon, progress, negative, pos }) {
  const valueColor = negative ? 'var(--neg)' : pos ? 'var(--pos)' : 'var(--fg)';
  return (
    <Card padding={16}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-muted)', marginBottom: 6 }}>
        <span style={{ width: 22, height: 22, borderRadius: 6, background: 'var(--bg-sunken)', display: 'grid', placeItems: 'center' }}>{icon}</span>
        <span style={{ fontSize: 12, fontWeight: 550 }}>{title}</span>
      </div>
      <div className="num" style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em', color: valueColor }}>
        {fmtMoney(value)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, minHeight: 18 }}>
        {delta != null ? (
          <Pill tone={delta >= 0 ? 'pos' : 'neg'} style={{ fontSize: 11 }}>
            {delta >= 0 ? '↑' : '↓'} {pct ? `${Math.abs(pct).toFixed(1)}%` : fmtMoney(Math.abs(delta))}
          </Pill>
        ) : null}
        {sub ? <span style={{ fontSize: 11.5, color: 'var(--fg-faint)' }}>{sub}</span> : null}
      </div>
      {progress != null ? (
        <div style={{ marginTop: 10 }}><ProgressBar value={progress * 100} max={100} color={progress > 1 ? 'var(--neg)' : 'var(--accent)'} over={progress > 1}/></div>
      ) : null}
    </Card>
  );
}

function BudgetRow({ b }) {
  const pct = b.spent / b.amount;
  const over = pct > 1;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 8, height: 8, borderRadius: 999, background: b.color }}/>
        <span style={{ fontSize: 13, fontWeight: 550 }}>{b.name}</span>
        <span style={{ fontSize: 11.5, color: 'var(--fg-faint)' }}>· {ACCOUNT_BY_ID[b.account].name}</span>
        <span style={{ flex: 1 }}/>
        <span className="num" style={{ fontSize: 12.5, color: over ? 'var(--neg)' : 'var(--fg-muted)' }}>
          ${b.spent.toFixed(2)} <span style={{ color: 'var(--fg-faint)' }}>/ ${b.amount.toFixed(0)}</span>
        </span>
      </div>
      <ProgressBar value={Math.min(b.spent, b.amount)} max={b.amount} color={b.color} over={over}/>
      {over ? <div style={{ fontSize: 11, color: 'var(--neg)' }}>Over by ${(b.spent - b.amount).toFixed(2)}</div> : null}
    </div>
  );
}

function CCCard({ name, last4, balance, limit, due, min, color }) {
  const used = -balance;
  const pct = used / limit;
  return (
    <div style={{
      borderRadius: 12, padding: 14, border: '1px solid var(--border)',
      background: `linear-gradient(135deg, color-mix(in oklch, ${color} 16%, var(--bg-elev)), var(--bg-elev) 70%)`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 36, height: 24, borderRadius: 4, background: color }}/>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{name}</div>
          <div className="num" style={{ fontSize: 11, color: 'var(--fg-faint)' }}>•••• {last4}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="num" style={{ fontSize: 14, fontWeight: 600 }}>${used.toFixed(2)}</div>
          <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>of ${limit.toLocaleString()}</div>
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        <ProgressBar value={used} max={limit} color={color}/>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11.5, color: 'var(--fg-muted)' }}>
        <span>Due <span className="num">{fmtDate(due)}</span></span>
        <span>Min <span className="num">${min.toFixed(2)}</span></span>
      </div>
    </div>
  );
}

Object.assign(window, { DashboardScreen });

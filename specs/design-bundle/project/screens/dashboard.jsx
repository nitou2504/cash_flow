// Cash Flow — Dashboard screen (single, polished variation)
// Hero balance + chart, KPIs, accounts, budget envelopes, recent activity, insights.

const { useState: useStateDash } = React;

function Dashboard() {
  const [scrubIdx, setScrubIdx] = useStateDash(BALANCE_SERIES.length - 1);
  const cur = BALANCE_SERIES[scrubIdx];
  const start = BALANCE_SERIES[0].balance;
  const change = cur.balance - start;

  const monthSpend = TXNS.filter(t => t.status === 'committed' && t.amount < 0 && t.date_payed.startsWith('2026-04')).reduce((s, t) => s + t.amount, 0);
  const monthIncome = TXNS.filter(t => t.status === 'committed' && t.amount > 0 && t.date_payed.startsWith('2026-04')).reduce((s, t) => s + t.amount, 0);
  const recent = [...TXNS].filter(t => t.status === 'committed').sort((a, b) => b.date_payed.localeCompare(a.date_payed)).slice(0, 5);
  const reviewCount = TXNS.filter(t => t.needs_review).length;

  return (
    <div className="cf-app" style={{ display: 'flex', height: '100%' }}>
      <Sidebar active="dashboard" badges={{ review: reviewCount }}/>
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <Topbar title="Dashboard" subtitle="Tuesday, April 28 · 3 accounts">
          <Btn kind="soft" size="sm" icon={I.calendar}>April 2026</Btn>
          <Btn kind="primary" size="sm" icon={I.plus}>Add transaction</Btn>
        </Topbar>

        <div style={{ flex: 1, padding: 24, display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 18, alignContent: 'start' }}>
          {/* LEFT */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* Hero card */}
            <div style={{
              background: 'linear-gradient(180deg, color-mix(in oklch, var(--accent) 7%, var(--bg-elev)) 0%, var(--bg-elev) 60%)',
              border: '1px solid var(--border)', borderRadius: 16, padding: '22px 22px 14px',
              boxShadow: 'var(--shadow-card)',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
                <div>
                  <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--fg-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Net balance · across accounts</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 6 }}>
                    <span className="num" style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-0.025em' }}>${cur.balance.toFixed(2)}</span>
                    <Pill tone={change >= 0 ? 'pos' : 'neg'} dot>
                      {change >= 0 ? '↑' : '↓'} {fmtMoneyCompact(Math.abs(change))}
                    </Pill>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>vs. ${start.toFixed(2)} on {fmtDateLong(BALANCE_SERIES[0].date)}</div>
                </div>
                <Segmented value="3M" onChange={() => {}} options={['1M', '3M', '6M', '1Y']} size="sm"/>
              </div>
              <BalanceChart series={BALANCE_SERIES} height={170} scrubIndex={scrubIdx} onScrub={setScrubIdx}/>
            </div>

            {/* KPIs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
              <KPI label="Income · April" value={fmtMoney(monthIncome, { alwaysSign: true })} delta="Salary cleared" tone="pos"/>
              <KPI label="Spent · April" value={fmtMoney(monthSpend)} delta="−$142 vs March" tone="neutral"/>
              <KPI label="Net · April" value={fmtMoney(monthIncome + monthSpend, { alwaysSign: monthIncome + monthSpend > 0 })} delta="On track" tone={(monthIncome + monthSpend) >= 0 ? 'pos' : 'neg'}/>
            </div>

            {/* Recent */}
            <Card title="Recent activity" subtitle="Last 5 committed" action={<Btn kind="ghost" size="sm" icon={I.chev}>View timeline</Btn>} padding={0}>
              <div>
                {recent.map((t) => <DashTxnRow key={t.id} txn={t}/>)}
              </div>
            </Card>
          </div>

          {/* RIGHT */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <Card title="Accounts" action={<Btn kind="ghost" size="sm">Manage</Btn>} padding={0}>
              <div style={{ padding: '4px 8px 10px' }}>
                {ACCOUNTS.map(a => <AccountRow key={a.id} a={a}/>)}
              </div>
            </Card>

            <Card title="Budget envelopes" subtitle="April · 6 active" action={<Btn kind="ghost" size="sm">All</Btn>} padding={0}>
              <div style={{ padding: '4px 16px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                {BUDGETS.map(b => <BudgetMini key={b.id} b={b}/>)}
              </div>
            </Card>

            <Card title="Heads up" subtitle="Things to look at">
              <Insight tone="warn" icon={I.flag}
                title="Leisure 122% over"
                body="Concert installment + Mr. Books pushed Apr's Leisure $45 over."/>
              <Insight tone="info" icon={I.sparkle}
                title={`${reviewCount} transactions need review`}
                body="From Gmail sync and family submissions."/>
              <Insight tone="pos" icon={I.check}
                title="On track for May"
                body="Forecast balance $5,612 by May 31."/>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}

function KPI({ label, value, delta, tone = 'neutral' }) {
  return (
    <div style={{
      background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 12, padding: 14,
      boxShadow: 'var(--shadow-card)',
    }}>
      <div style={{ fontSize: 11, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>{label}</div>
      <div className="num" style={{ fontSize: 22, fontWeight: 600, marginTop: 6, letterSpacing: '-0.02em', color: tone === 'pos' ? 'var(--pos)' : tone === 'neg' ? 'var(--neg)' : 'var(--fg)' }}>{value}</div>
      <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', marginTop: 2 }}>{delta}</div>
    </div>
  );
}

function AccountRow({ a }) {
  const bal = ACCOUNT_BALANCES[a.id];
  const isCC = a.type === 'credit_card';
  const utilization = isCC ? (Math.abs(bal.current) / a.limit) * 100 : null;
  return (
    <div style={{ padding: '10px 10px', display: 'flex', alignItems: 'center', gap: 12, borderRadius: 8 }}>
      <div style={{
        width: 38, height: 26, borderRadius: 5, background: a.color, color: 'white',
        display: 'grid', placeItems: 'center', fontSize: 9, fontWeight: 700, flex: 'none', letterSpacing: '0.06em',
      }}>{isCC ? 'CC' : 'CASH'}</div>
      <div style={{ flex: 1, lineHeight: 1.2, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 550 }}>
          {a.name}{a.last4 ? <span className="num" style={{ color: 'var(--fg-faint)', marginLeft: 4 }}>·{a.last4}</span> : null}
        </div>
        {isCC ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
            <div style={{ flex: 1, height: 4, background: 'var(--bg-sunken)', borderRadius: 99, overflow: 'hidden' }}>
              <div style={{ width: `${utilization}%`, height: '100%', background: utilization > 50 ? 'var(--warn)' : 'var(--pos)' }}/>
            </div>
            <span className="num" style={{ fontSize: 10.5, color: 'var(--fg-faint)' }}>{utilization.toFixed(0)}% used</span>
          </div>
        ) : (
          <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>Available cash</div>
        )}
      </div>
      <div style={{ textAlign: 'right' }}>
        <div className="num" style={{ fontSize: 14, fontWeight: 600, color: bal.current < 0 ? 'var(--neg)' : 'var(--fg)' }}>
          {isCC ? fmtMoney(bal.current) : `$${bal.current.toFixed(2)}`}
        </div>
        {isCC ? <div style={{ fontSize: 10.5, color: 'var(--fg-faint)' }}>due {fmtDate(bal.dueDate)}</div> : null}
      </div>
    </div>
  );
}

function BudgetMini({ b }) {
  const pct = (b.spent / b.amount) * 100;
  const over = b.spent > b.amount;
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <CatSwatch cat={b.category} size={18}/>
        <span style={{ fontSize: 12.5, fontWeight: 550, flex: 1 }}>{b.name}</span>
        <span className="num" style={{ fontSize: 11.5, color: over ? 'var(--neg)' : 'var(--fg-muted)' }}>
          ${b.spent.toFixed(0)} / ${b.amount}
        </span>
      </div>
      <ProgressBar value={b.spent} max={b.amount} over={over} color={b.color}/>
    </div>
  );
}

function Insight({ tone, icon, title, body }) {
  const toneBg = { warn: 'var(--warn-soft)', info: 'var(--info-soft)', pos: 'var(--pos-soft)' }[tone];
  const toneFg = { warn: 'var(--warn)', info: 'var(--info)', pos: 'var(--pos)' }[tone];
  return (
    <div style={{ display: 'flex', gap: 10, padding: '12px 0', borderTop: '1px solid var(--border)' }}>
      <div style={{ width: 28, height: 28, borderRadius: 8, background: toneBg, color: toneFg, display: 'grid', placeItems: 'center', flex: 'none' }}>{icon}</div>
      <div style={{ flex: 1, lineHeight: 1.4 }}>
        <div style={{ fontSize: 13, fontWeight: 550, marginBottom: 2 }}>{title}</div>
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{body}</div>
      </div>
    </div>
  );
}

// Compact dashboard row (skips zebra grid styling)
function DashTxnRow({ txn }) {
  const acc = ACCOUNT_BY_ID[txn.account];
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 130px 110px',
      alignItems: 'center', gap: 12, padding: '11px 18px',
      borderTop: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <CatSwatch cat={txn.category} size={26}/>
        <div style={{ minWidth: 0, lineHeight: 1.2 }}>
          <div style={{ fontSize: 13, fontWeight: 550, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{txn.desc}</div>
          <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>{fmtDate(txn.date_payed)} · {txn.category}</div>
        </div>
      </div>
      <div><AccountChip account={acc}/></div>
      <div className="num" style={{ textAlign: 'right', fontSize: 13.5, fontWeight: 600, color: txn.amount > 0 ? 'var(--pos)' : 'var(--fg)' }}>
        {fmtMoney(txn.amount, { alwaysSign: txn.amount > 0 })}
      </div>
    </div>
  );
}

Object.assign(window, { Dashboard });

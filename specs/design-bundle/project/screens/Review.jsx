// Cash Flow — Review Queue screen
// Two-pane: queue list on left, detail/decision panel on right.

const { useState: useStateRev } = React;

function ReviewScreen({ density = 'balanced' }) {
  const [selectedId, setSelectedId] = useStateRev(REVIEW_QUEUE[1].id);
  const sel = REVIEW_QUEUE.find(r => r.id === selectedId) || REVIEW_QUEUE[0];

  return (
    <div data-density={density} style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Topbar title="Review queue" subtitle={`${REVIEW_QUEUE.length} transactions need review`}>
        <Btn kind="soft" size="sm" icon={I.zap}>Sync now</Btn>
        <Btn kind="primary" size="sm" icon={I.check}>Approve all (5)</Btn>
      </Topbar>

      <div style={{ flex: 1, overflow: 'hidden', display: 'grid', gridTemplateColumns: '380px 1fr' }}>
        {/* Queue list */}
        <div style={{ borderRight: '1px solid var(--border)', overflow: 'auto' }}>
          <div style={{ padding: '10px 16px', display: 'flex', gap: 8, alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
            <Segmented value="all" options={[
              { value: 'all', label: `All ${REVIEW_QUEUE.length}` },
              { value: 'gmail', label: 'Gmail 4' },
              { value: 'mom', label: 'Family 1' },
            ]} size="sm"/>
          </div>
          {REVIEW_QUEUE.map(r => (
            <ReviewQueueItem key={r.id} r={r} selected={r.id === selectedId} onClick={() => setSelectedId(r.id)}/>
          ))}
        </div>

        {/* Detail */}
        <div style={{ overflow: 'auto', background: 'var(--bg-sunken)' }}>
          <ReviewDetail r={sel}/>
        </div>
      </div>
    </div>
  );
}

function ReviewQueueItem({ r, selected, onClick }) {
  const acc = ACCOUNT_BY_ID[r.account];
  return (
    <button onClick={onClick} style={{
      display: 'flex', flexDirection: 'column', gap: 6, padding: '14px 16px',
      width: '100%', textAlign: 'left',
      background: selected ? 'var(--bg-hover)' : 'transparent',
      border: 'none', borderBottom: '1px solid var(--border)',
      borderLeft: selected ? '3px solid var(--accent)' : '3px solid transparent',
      cursor: 'pointer', color: 'var(--fg)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <CatSwatch cat={r.suggestedCategory} size={22}/>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 550, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.desc}</div>
          <div style={{ fontSize: 11.5, color: 'var(--fg-muted)' }} className="num">{fmtDate(r.date)} · {acc.name}</div>
        </div>
        <div className="num" style={{ fontSize: 13.5, fontWeight: 600 }}>−${Math.abs(r.amount).toFixed(2)}</div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginLeft: 30, flexWrap: 'wrap' }}>
        <Pill tone="warn" dot>review</Pill>
        {r.source === 'gmail' ? <Pill tone="info">Gmail</Pill> : <Pill tone="accent">{r.source}</Pill>}
        {r.invoice ? <Pill tone="pos">Invoice ✓</Pill> : null}
        {r.llm ? <Pill tone="neutral">LLM {Math.round(r.llm.confidence * 100)}%</Pill> : null}
      </div>
    </button>
  );
}

function ReviewDetail({ r }) {
  const acc = ACCOUNT_BY_ID[r.account];
  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 880 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
        <CatSwatch cat={r.suggestedCategory} size={48}/>
        <div style={{ flex: 1, lineHeight: 1.3 }}>
          <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.015em' }}>{r.desc}</div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', color: 'var(--fg-muted)', fontSize: 12.5 }}>
            <span className="num">#{r.id}</span>
            <span>·</span>
            <span>{fmtDateLong(r.date)}</span>
            <span>·</span>
            <AccountChip account={acc}/>
          </div>
        </div>
        <div className="num" style={{ fontSize: 26, fontWeight: 600, color: 'var(--neg)' }}>−${Math.abs(r.amount).toFixed(2)}</div>
      </div>

      {/* Action bar */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <Btn kind="primary" icon={I.check}>Approve</Btn>
        <Btn kind="default" icon={I.edit}>Edit & approve</Btn>
        <Btn kind="ghost" icon={I.x}>Skip</Btn>
        <span style={{ flex: 1 }}/>
        <Btn kind="ghost" size="sm" icon={I.chevL}>Prev</Btn>
        <Btn kind="ghost" size="sm">Next {I.chev}</Btn>
        <Kbd>J</Kbd><Kbd>K</Kbd>
      </div>

      {/* Two-col grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {/* Suggested classification */}
        <Card title="Suggested classification" subtitle={r.llm ? `LLM · ${r.llm.model}` : 'Manual entry'}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <KV k="Category" v={
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <CatSwatch cat={r.suggestedCategory} size={18}/>
                <span style={{ fontWeight: 550 }}>{r.suggestedCategory}</span>
                <button style={{ background: 'transparent', border: 'none', color: 'var(--accent)', fontSize: 12, padding: 0, marginLeft: 4 }}>change</button>
              </span>
            }/>
            <KV k="Budget" v={
              r.suggestedBudget ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--cat-1)' }}/>
                  <span style={{ fontWeight: 550 }}>{budgetName(r.suggestedBudget)}</span>
                  <span style={{ color: 'var(--fg-faint)', fontSize: 11.5 }}>$83.40 left</span>
                </span>
              ) : <span style={{ color: 'var(--fg-faint)' }}>None</span>
            }/>
            <KV k="Status" v={<StatusChip status="committed"/>}/>
            <KV k="Description" v={<span>{r.desc} <button style={{ background: 'transparent', border: 'none', color: 'var(--accent)', fontSize: 12, padding: 0 }}>rename</button></span>}/>
          </div>

          {r.llm ? (
            <div style={{ marginTop: 14, padding: 12, background: 'var(--bg-sunken)', borderRadius: 10, border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ color: 'var(--accent)' }}>{I.sparkle}</span>
                <span style={{ fontSize: 12, fontWeight: 600 }}>LLM reasoning</span>
                <span style={{ flex: 1 }}/>
                <Pill tone={r.llm.confidence > 0.85 ? 'pos' : r.llm.confidence > 0.7 ? 'warn' : 'neg'}>
                  {Math.round(r.llm.confidence * 100)}% confidence
                </Pill>
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--fg-muted)', lineHeight: 1.55 }}>{r.llm.reasoning}</div>
            </div>
          ) : null}

          {r.note ? (
            <div style={{ marginTop: 14, padding: 12, background: 'var(--accent-soft)', borderRadius: 10, fontSize: 12.5, color: 'var(--accent)' }}>
              <strong>Note: </strong>{r.note}
            </div>
          ) : null}
        </Card>

        {/* Source: consumo + invoice */}
        <Card title="Source data" subtitle={r.consumo ? `Gmail · ${r.consumo.bank}` : 'No bank notification'}>
          {r.consumo ? (
            <>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Bank notification</div>
              <div style={{ background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 10, padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <KV k="Merchant" v={<span className="num" style={{ fontSize: 12.5 }}>{r.consumo.merchant}</span>}/>
                <KV k="Card" v={<span className="num">•••• {r.consumo.card}</span>}/>
                <KV k="Purchased" v={<span className="num">{r.consumo.purchasedAt}</span>}/>
                <KV k="Bank" v={r.consumo.bank}/>
              </div>
            </>
          ) : null}

          {r.invoice ? (
            <>
              <div style={{ marginTop: 14, fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                Matched invoice <Pill tone="pos" dot>SRI</Pill>
              </div>
              <div style={{ background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 10, padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <KV k="Number" v={<span className="num">{r.invoice.number}</span>}/>
                <KV k="Vendor" v={r.invoice.vendor}/>
                <KV k="Total" v={<span className="num" style={{ fontWeight: 600 }}>${r.invoice.total.toFixed(2)}</span>}/>
                <KV k="Taxes" v={<span style={{ fontSize: 12 }}>{r.invoice.taxes}</span>}/>
              </div>
            </>
          ) : (
            <div style={{ marginTop: 14, padding: 14, border: '1px dashed var(--border-strong)', borderRadius: 10, textAlign: 'center', color: 'var(--fg-faint)', fontSize: 12.5 }}>
              {I.receipt} <div style={{ marginTop: 6 }}>No matching invoice found</div>
              <button style={{ background: 'transparent', border: 'none', color: 'var(--accent)', fontSize: 12, marginTop: 4 }}>Search invoices…</button>
            </div>
          )}
        </Card>
      </div>

      {/* Recent similar */}
      <Card title="Similar past transactions" subtitle="Same merchant patterns">
        <div style={{ margin: '0 -18px' }}>
          {TXNS.filter(t => t.category === r.suggestedCategory && t.status === 'committed').slice(0, 3).map(t => (
            <TxnRow key={t.id} txn={t} compact/>
          ))}
        </div>
      </Card>
    </div>
  );
}

function KV({ k, v }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13 }}>
      <span style={{ width: 90, color: 'var(--fg-muted)', fontSize: 12 }}>{k}</span>
      <span style={{ flex: 1 }}>{v}</span>
    </div>
  );
}

Object.assign(window, { ReviewScreen });

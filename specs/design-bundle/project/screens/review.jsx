// Cash Flow — Review Queue screen
// Detail-rich card per transaction with consumo/invoice/LLM info; batch actions.

const { useState: useStateRev } = React;

function ReviewQueue() {
  const [selectedId, setSelectedId] = useStateRev(REVIEW_QUEUE[0].id);
  const [checked, setChecked] = useStateRev(new Set());
  const selected = REVIEW_QUEUE.find(r => r.id === selectedId) || REVIEW_QUEUE[0];
  const reviewCount = REVIEW_QUEUE.length;

  const toggleCheck = (id) => {
    const n = new Set(checked);
    n.has(id) ? n.delete(id) : n.add(id);
    setChecked(n);
  };

  return (
    <div className="cf-app" style={{ display: 'flex', height: '100%' }}>
      <Sidebar active="review" badges={{ review: reviewCount }}/>
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Topbar title="Review queue" subtitle={`${reviewCount} transactions awaiting approval`}>
          <Segmented value="all" onChange={()=>{}} size="sm" options={[
            { value: 'all', label: `All · ${reviewCount}` },
            { value: 'gmail', label: 'Gmail · 4' },
            { value: 'family', label: 'Family · 1' },
          ]}/>
          <Btn kind="primary" size="sm" icon={I.check}>Approve selected ({checked.size})</Btn>
        </Topbar>

        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '420px 1fr', overflow: 'hidden' }}>
          {/* List */}
          <div style={{ borderRight: '1px solid var(--border)', overflow: 'auto', background: 'var(--bg)' }}>
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-sunken)' }}>
              <input type="checkbox" style={{ accentColor: 'var(--accent)' }}
                checked={checked.size === REVIEW_QUEUE.length}
                onChange={(e) => setChecked(e.target.checked ? new Set(REVIEW_QUEUE.map(r => r.id)) : new Set())}/>
              <span style={{ fontSize: 12, color: 'var(--fg-muted)', flex: 1 }}>
                {checked.size > 0 ? `${checked.size} selected` : 'Select all'}
              </span>
              <Btn kind="ghost" size="sm" icon={I.filter}>Sort</Btn>
            </div>
            {REVIEW_QUEUE.map(r => {
              const isSel = r.id === selectedId;
              const conf = r.llm?.confidence;
              return (
                <div key={r.id} onClick={() => setSelectedId(r.id)}
                  style={{
                    padding: '14px 14px', display: 'flex', gap: 10, alignItems: 'flex-start',
                    borderBottom: '1px solid var(--border)', cursor: 'pointer',
                    background: isSel ? 'var(--accent-soft)' : 'transparent',
                    borderLeft: `3px solid ${isSel ? 'var(--accent)' : 'transparent'}`,
                  }}>
                  <input type="checkbox" checked={checked.has(r.id)} onChange={() => toggleCheck(r.id)}
                    onClick={(e) => e.stopPropagation()} style={{ accentColor: 'var(--accent)', marginTop: 4 }}/>
                  <CatSwatch cat={r.suggestedCategory} size={28}/>
                  <div style={{ flex: 1, minWidth: 0, lineHeight: 1.3 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13.5, fontWeight: 600, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.desc}</span>
                      <span className="num" style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--neg)' }}>{fmtMoney(r.amount)}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--fg-muted)', marginTop: 3 }}>
                      <span>{fmtDate(r.date)}</span>
                      <span>·</span>
                      <AccountChip account={ACCOUNT_BY_ID[r.account]}/>
                    </div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                      <Pill tone={r.source === 'gmail' ? 'info' : 'accent'} dot>
                        {r.source === 'gmail' ? 'Gmail sync' : `family · ${r.source}`}
                      </Pill>
                      {conf != null ? (
                        <Pill tone={conf >= 0.9 ? 'pos' : conf >= 0.7 ? 'warn' : 'neg'}>
                          {Math.round(conf * 100)}% confident
                        </Pill>
                      ) : null}
                      {r.invoice ? <Pill tone="neutral">+ invoice</Pill> : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Detail */}
          <div style={{ overflow: 'auto', padding: '24px 28px', background: 'var(--bg-sunken)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Reviewing</span>
              <Pill tone={selected.source === 'gmail' ? 'info' : 'accent'} dot>{selected.source === 'gmail' ? 'Gmail sync' : `family · ${selected.source}`}</Pill>
              <span style={{ flex: 1 }}/>
              <Btn kind="ghost" size="sm" icon={I.chevL}>Prev</Btn>
              <Btn kind="ghost" size="sm" icon={I.chev}>Next</Btn>
            </div>

            {/* Hero */}
            <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 14, padding: 22, boxShadow: 'var(--shadow-card)', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
                <CatSwatch cat={selected.suggestedCategory} size={48}/>
                <div style={{ flex: 1, lineHeight: 1.3 }}>
                  <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.015em' }}>{selected.desc}</div>
                  <div style={{ fontSize: 13, color: 'var(--fg-muted)', marginTop: 2 }}>{fmtDateLong(selected.date)} · {ACCOUNT_BY_ID[selected.account].name}</div>
                </div>
                <div className="num" style={{ fontSize: 28, fontWeight: 600, color: 'var(--neg)', letterSpacing: '-0.02em' }}>{fmtMoney(selected.amount)}</div>
              </div>
            </div>

            {/* Suggested fields */}
            <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 14, marginBottom: 16, overflow: 'hidden' }}>
              <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Suggested classification</span>
                <span style={{ flex: 1 }}/>
                <Btn kind="ghost" size="sm" icon={I.edit}>Edit</Btn>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)' }}>
                <DetailField label="Description" value={selected.desc}/>
                <DetailField label="Amount" value={fmtMoney(selected.amount)} mono/>
                <DetailField label="Account" value={ACCOUNT_BY_ID[selected.account].name} sub={`···${ACCOUNT_BY_ID[selected.account].last4}`}/>
                <DetailField label="Date" value={fmtDate(selected.date)} sub="payment Apr 22"/>
                <DetailField label="Category" value={selected.suggestedCategory} swatch={selected.suggestedCategory}/>
                <DetailField label="Budget" value={selected.suggestedBudget ? budgetName(selected.suggestedBudget) : '—'}
                  sub={selected.suggestedBudget ? `${BUDGETS.find(b => b.id === selected.suggestedBudget)?.spent.toFixed(0)} / ${BUDGETS.find(b => b.id === selected.suggestedBudget)?.amount}` : 'No budget'}/>
              </div>
            </div>

            {/* Source — consumo */}
            {selected.consumo ? (
              <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 14, marginBottom: 16, overflow: 'hidden' }}>
                <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: 'var(--info)' }}>{I.receipt}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>Source: bank email (consumo)</span>
                  <span style={{ flex: 1 }}/>
                  <Btn kind="ghost" size="sm">View raw email</Btn>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)' }}>
                  <DetailField label="Merchant" value={selected.consumo.merchant} mono/>
                  <DetailField label="Bank" value={selected.consumo.bank}/>
                  <DetailField label="Card" value={`···${selected.consumo.card}`} mono/>
                  <DetailField label="Purchased at" value={selected.consumo.purchasedAt} mono/>
                </div>
              </div>
            ) : null}

            {/* Invoice match */}
            {selected.invoice ? (
              <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 14, marginBottom: 16, overflow: 'hidden' }}>
                <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: 'var(--pos)' }}>{I.check}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>Matched invoice (SRI)</span>
                  <Pill tone="pos">amount + date match</Pill>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)' }}>
                  <DetailField label="Invoice number" value={selected.invoice.number} mono/>
                  <DetailField label="Vendor" value={selected.invoice.vendor}/>
                  <DetailField label="Total" value={fmtMoney(-selected.invoice.total)} mono/>
                  <DetailField label="Tax detail" value={selected.invoice.taxes}/>
                </div>
              </div>
            ) : null}

            {/* LLM reasoning */}
            {selected.llm ? (
              <div style={{
                background: 'color-mix(in oklch, var(--accent) 4%, var(--bg-elev))',
                border: '1px solid color-mix(in oklch, var(--accent) 20%, var(--border))',
                borderRadius: 14, marginBottom: 16, padding: '14px 18px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ color: 'var(--accent)' }}>{I.sparkle}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>Why this classification?</span>
                  <span style={{ flex: 1 }}/>
                  <Pill tone={selected.llm.confidence >= 0.9 ? 'pos' : 'warn'}>{Math.round(selected.llm.confidence * 100)}% confident</Pill>
                  <span className="num" style={{ fontSize: 11, color: 'var(--fg-faint)' }}>{selected.llm.model}</span>
                </div>
                <div style={{ fontSize: 13, color: 'var(--fg)', lineHeight: 1.5 }}>{selected.llm.reasoning}</div>
              </div>
            ) : selected.note ? (
              <div style={{
                background: 'var(--accent-soft)',
                border: '1px solid color-mix(in oklch, var(--accent) 20%, var(--border))',
                borderRadius: 14, marginBottom: 16, padding: '14px 18px',
                fontSize: 13, color: 'var(--fg)',
              }}>
                <strong style={{ color: 'var(--accent)' }}>From family member.</strong> {selected.note}
              </div>
            ) : null}

            {/* Decision actions */}
            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
              <Btn kind="success" icon={I.check}>Approve · ⌘↵</Btn>
              <Btn kind="default" icon={I.edit}>Edit & approve</Btn>
              <Btn kind="ghost" icon={I.chev}>Skip</Btn>
              <span style={{ flex: 1 }}/>
              <Btn kind="danger" icon={I.trash}>Reject</Btn>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function DetailField({ label, value, sub, mono, swatch }) {
  return (
    <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', borderRight: '1px solid var(--border)' }}>
      <div style={{ fontSize: 10.5, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
        {swatch ? <CatSwatch cat={swatch} size={16}/> : null}
        <span className={mono ? 'num' : ''} style={{ fontSize: 13, fontWeight: 550 }}>{value}</span>
      </div>
      {sub ? <div style={{ fontSize: 11, color: 'var(--fg-faint)', marginTop: 2 }}>{sub}</div> : null}
    </div>
  );
}

Object.assign(window, { ReviewQueue });

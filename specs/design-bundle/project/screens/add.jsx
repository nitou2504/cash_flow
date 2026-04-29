// Cash Flow — Add Transaction screen
// Slide-over panel pattern with NL parser preview, then editable form.
// Mocked behind a "current view" backdrop (timeline) so it reads as in-app.

const { useState: useStateAdd } = React;

function AddTransaction() {
  const [mode, setMode] = useStateAdd('nl'); // nl | form | installments | split
  const [parseStage, setParseStage] = useStateAdd('parsed'); // typing | parsing | parsed
  const [nlText, setNlText] = useStateAdd('Supermaxi groceries 84.20, visa, today');

  const reviewCount = TXNS.filter(t => t.needs_review).length;

  // Parsed preview
  const parsed = {
    description: 'Supermaxi groceries',
    amount: -84.20,
    account: 'cc_visa',
    category: 'Groceries',
    budget: 'b_groceries',
    date: '2026-04-28',
    status: 'committed',
    confidence: { description: 0.99, amount: 1.0, account: 0.96, category: 0.94, budget: 0.91, date: 0.99 },
  };

  return (
    <div className="cf-app" style={{ display: 'flex', height: '100%', position: 'relative' }}>
      <Sidebar active="add" badges={{ review: reviewCount }}/>
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', filter: 'blur(0)' }}>
        <Topbar title="Transactions" subtitle="Timeline · Apr 2026">
          <Btn kind="soft" size="sm" icon={I.filter}>Filters</Btn>
          <Btn kind="primary" size="sm" icon={I.plus}>Add</Btn>
        </Topbar>
        {/* Backdrop blurred preview of timeline */}
        <div style={{ flex: 1, padding: 24, opacity: 0.45, pointerEvents: 'none', filter: 'blur(2px)' }}>
          <div style={{ height: 120, background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 12 }}/>
          <div style={{ height: 12 }}/>
          {[...Array(8)].map((_, i) => (
            <div key={i} style={{ height: 44, background: 'var(--bg-elev)', borderTop: '1px solid var(--border)' }}/>
          ))}
        </div>
        {/* Scrim */}
        <div style={{ position: 'absolute', inset: 0, background: 'oklch(0.2 0.02 250 / 0.18)', backdropFilter: 'blur(2px)', pointerEvents: 'none' }}/>
      </main>

      {/* Slide-over panel */}
      <aside style={{
        position: 'absolute', top: 0, right: 0, bottom: 0,
        width: 540, background: 'var(--bg-elev)',
        borderLeft: '1px solid var(--border)', boxShadow: 'var(--shadow-pop)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>New transaction</div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Type naturally or use the form · ⌘ Enter to save</div>
          </div>
          <Btn kind="ghost" size="sm" icon={I.x}/>
        </div>

        {/* Mode tabs */}
        <div style={{ padding: '12px 22px 0' }}>
          <Segmented value={mode} onChange={setMode} size="sm" options={[
            { value: 'nl', label: '✨ Natural language' },
            { value: 'form', label: 'Form' },
            { value: 'installments', label: 'Installments' },
            { value: 'split', label: 'Split' },
          ]}/>
        </div>

        {/* NL input */}
        <div style={{ padding: '16px 22px 0' }}>
          <div style={{
            background: 'var(--bg-sunken)', border: `1.5px solid var(--accent)`,
            borderRadius: 12, padding: '14px 16px',
            display: 'flex', flexDirection: 'column', gap: 10,
            boxShadow: '0 0 0 4px var(--accent-soft)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>
              <span style={{ color: 'var(--accent)' }}>{I.sparkle}</span>
              Describe your transaction
            </div>
            <input
              value={nlText}
              onChange={e => setNlText(e.target.value)}
              style={{
                width: '100%', border: 'none', background: 'transparent',
                fontSize: 15.5, fontWeight: 500, color: 'var(--fg)', outline: 'none',
                padding: '4px 0',
              }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--fg-faint)' }}>
              <span>Try:</span>
              <ChipExample>"netflix 14.99, amex"</ChipExample>
              <ChipExample>"flight 312, visa, may 22"</ChipExample>
              <ChipExample>"alaska concert 300, 4 installments"</ChipExample>
            </div>
          </div>
        </div>

        {/* Parsed preview */}
        <div style={{ flex: 1, overflow: 'auto', padding: '18px 22px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Pill tone="info" dot>Parsed</Pill>
            <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Tap any field to override</span>
            <span style={{ flex: 1 }}/>
            <span style={{ fontSize: 11, color: 'var(--fg-faint)' }}>via gemma3:12b · 0.4s</span>
          </div>

          {/* Big amount preview */}
          <div style={{
            background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 14,
            padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14,
          }}>
            <CatSwatch cat={parsed.category} size={44}/>
            <div style={{ flex: 1, lineHeight: 1.25 }}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{parsed.description}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{fmtDateLong(parsed.date)} · {ACCOUNT_BY_ID[parsed.account].name}</div>
            </div>
            <div className="num" style={{ fontSize: 24, fontWeight: 600, color: 'var(--neg)', letterSpacing: '-0.02em' }}>
              {fmtMoney(parsed.amount)}
            </div>
          </div>

          {/* Field grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
            <Field label="Account" value={ACCOUNT_BY_ID[parsed.account].name} sub={`···${ACCOUNT_BY_ID[parsed.account].last4}`} confidence={parsed.confidence.account}/>
            <Field label="Category" value={parsed.category} confidence={parsed.confidence.category} swatch={parsed.category}/>
            <Field label="Budget" value="Groceries · Apr" sub="$167.60 / $480 left" confidence={parsed.confidence.budget}/>
            <Field label="Payment date" value={fmtDate(parsed.date)} sub="today · CC pays Apr 22" confidence={parsed.confidence.date}/>
          </div>

          {/* Notes */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
            <label style={{ fontSize: 11.5, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>Notes (optional)</label>
            <input placeholder="e.g. weekly grocery run" style={{
              padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8,
              background: 'var(--bg-elev)', color: 'var(--fg)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
            }}/>
          </div>

          {/* Status options */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 11.5, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: 6 }}>Status</label>
            <Segmented value="committed" onChange={()=>{}} size="sm" options={[
              { value: 'committed', label: 'Committed' },
              { value: 'pending', label: 'Pending' },
              { value: 'planning', label: 'Planning' },
            ]}/>
          </div>

          {/* Impact preview */}
          <div style={{
            background: 'var(--info-soft)', border: '1px solid color-mix(in oklch, var(--info) 25%, var(--border))',
            borderRadius: 10, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18,
          }}>
            <span style={{ color: 'var(--info)' }}>{I.zap}</span>
            <div style={{ flex: 1, fontSize: 12.5, color: 'var(--info)', lineHeight: 1.4 }}>
              <strong>Impact:</strong> Visa Pichincha owed becomes <span className="num">$926.60</span> · Groceries budget <span className="num">$396.60</span> remaining · Apr 22 payment <span className="num">$926.60</span>.
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div style={{ padding: '14px 22px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg)' }}>
          <Btn kind="ghost" size="md">Cancel</Btn>
          <span style={{ flex: 1 }}/>
          <Btn kind="soft" size="md">Revise</Btn>
          <Btn kind="primary" size="md" icon={I.check}>
            Save transaction <Kbd>⌘↵</Kbd>
          </Btn>
        </div>
      </aside>
    </div>
  );
}

function Field({ label, value, sub, confidence, swatch }) {
  const conf = confidence != null ? Math.round(confidence * 100) : null;
  return (
    <button style={{
      display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-start',
      padding: '10px 12px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 10,
      cursor: 'pointer', textAlign: 'left', position: 'relative',
    }}>
      <div style={{ fontSize: 10.5, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {swatch ? <CatSwatch cat={swatch} size={16}/> : null}
        <span style={{ fontSize: 13, fontWeight: 550, color: 'var(--fg)' }}>{value}</span>
      </div>
      {sub ? <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>{sub}</div> : null}
      {conf != null ? (
        <div style={{ position: 'absolute', top: 8, right: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 5, height: 5, borderRadius: 99, background: conf >= 90 ? 'var(--pos)' : conf >= 75 ? 'var(--warn)' : 'var(--neg)' }}/>
          <span className="num" style={{ fontSize: 10, color: 'var(--fg-faint)' }}>{conf}%</span>
        </div>
      ) : null}
    </button>
  );
}

function ChipExample({ children }) {
  return (
    <span style={{
      padding: '2px 8px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 999,
      fontSize: 11, color: 'var(--fg-muted)', cursor: 'pointer',
    }}>{children}</span>
  );
}

Object.assign(window, { AddTransaction });

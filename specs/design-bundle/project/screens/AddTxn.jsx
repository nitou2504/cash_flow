// Cash Flow — Add Transaction screen
// Slide-over panel from right with NL composer + structured form + preview.

const { useState: useStateAdd } = React;

function AddTxnScreen({ density = 'balanced', mode: initMode = 'natural' }) {
  const [mode, setMode] = useStateAdd(initMode); // natural | structured | installment | split | csv
  const [nlText, setNlText] = useStateAdd('Supermaxi groceries 84.20, visa pichincha, apr 22');
  const [parsing, setParsing] = useStateAdd(false);

  // Parsed/staged transaction
  const [draft, setDraft] = useStateAdd({
    desc: 'Supermaxi groceries',
    amount: 84.20,
    isIncome: false,
    account: 'cc_visa',
    category: 'Groceries',
    budget: 'b_groceries',
    date: '2026-04-22',
    status: 'committed',
  });

  // Installment
  const [installments, setInstallments] = useStateAdd(4);
  const [grace, setGrace] = useStateAdd(0);

  // Split
  const [splits, setSplits] = useStateAdd([
    { id: 1, category: 'Groceries', budget: 'b_groceries', amount: 50.00 },
    { id: 2, category: 'Health',    budget: 'b_health',    amount: 34.20 },
  ]);

  return (
    <div data-density={density} style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Topbar title="Add transaction" subtitle="Quick natural language or structured entry">
        <Btn kind="ghost" size="sm" icon={I.x}>Cancel</Btn>
      </Topbar>

      <div style={{ flex: 1, overflow: 'auto', display: 'grid', gridTemplateColumns: '1fr 360px', gap: 0 }}>
        {/* Left — composer + form */}
        <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 18, borderRight: '1px solid var(--border)' }}>
          {/* Mode tabs */}
          <Segmented value={mode} onChange={setMode} options={[
            { value: 'natural',     label: 'Natural', icon: I.sparkle },
            { value: 'structured',  label: 'Form' },
            { value: 'installment', label: 'Installment' },
            { value: 'split',       label: 'Split' },
            { value: 'csv',         label: 'CSV import' },
          ]} size="sm"/>

          {/* Natural language */}
          {mode === 'natural' ? (
            <Card padding={0}>
              <div style={{ padding: 18, borderBottom: '1px solid var(--border)' }}>
                <label style={{ fontSize: 11.5, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Describe it</label>
                <textarea
                  value={nlText}
                  onChange={(e) => setNlText(e.target.value)}
                  placeholder="e.g. Lunch at La Tablita 24.50, visa, today"
                  style={{
                    width: '100%', minHeight: 100, marginTop: 8,
                    background: 'transparent', border: 'none', resize: 'none',
                    color: 'var(--fg)', fontSize: 15, lineHeight: 1.5, fontFamily: 'inherit',
                    outline: 'none',
                  }}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
                  <Pill tone="info" dot>{parsing ? 'Parsing…' : 'Parsed'}</Pill>
                  <span style={{ fontSize: 11.5, color: 'var(--fg-faint)' }}>LLM extracted 5 fields · 96% confidence</span>
                  <span style={{ flex: 1 }}/>
                  <Btn kind="ghost" size="sm" icon={I.sparkle}>Re-parse</Btn>
                </div>
              </div>
              <div style={{ padding: 18, background: 'var(--bg-sunken)', display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ fontSize: 11.5, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Detected fields</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <Field label="Description" value={draft.desc} onChange={(v) => setDraft({ ...draft, desc: v })}/>
                  <Field label="Amount" value={`$${draft.amount.toFixed(2)}`} mono/>
                  <Field label="Account" value="Visa Pichincha · 4471"/>
                  <Field label="Date" value="Apr 22, 2026"/>
                  <Field label="Category" value="Groceries"/>
                  <Field label="Budget" value="Groceries · $480/mo"/>
                </div>
              </div>
            </Card>
          ) : null}

          {mode === 'structured' ? (
            <Card>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <Field label="Description" value={draft.desc} onChange={(v) => setDraft({ ...draft, desc: v })} editable/>
                <Field label="Amount" value={`${draft.amount.toFixed(2)}`} prefix="$" mono editable/>
                <SelectField label="Account" value="Visa Pichincha · 4471" options={ACCOUNTS.map(a => a.name)}/>
                <SelectField label="Category" value={draft.category} options={CATEGORIES}/>
                <SelectField label="Budget" value="Groceries — $480/mo" options={BUDGETS.map(b => b.name)}/>
                <Field label="Date" value="2026-04-22" mono editable/>
                <SelectField label="Status" value="Committed" options={['Committed', 'Pending', 'Planning']}/>
                <Field label="Notes (optional)" value="" placeholder="Add a note…" editable/>
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <Toggle label="Income" active={draft.isIncome}/>
                <Toggle label="Mark as pending"/>
                <Toggle label="Needs review"/>
              </div>
            </Card>
          ) : null}

          {mode === 'installment' ? (
            <Card title="Installment plan" subtitle={`${installments} payments · grace ${grace}`}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
                <Field label="Description" value="Concert — Alaska Live" editable/>
                <Field label="Total amount" value="300.00" prefix="$" mono editable/>
                <SelectField label="Account" value="Visa Pichincha · 4471" options={['Visa Pichincha · 4471']}/>
                <Field label="Purchase date" value="2026-04-22" mono editable/>
              </div>
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-end' }}>
                <NumberStepper label="# of installments" value={installments} onChange={setInstallments} min={2} max={24}/>
                <NumberStepper label="Grace months" value={grace} onChange={setGrace} min={0} max={6}/>
                <Toggle label="Skip first N"/>
              </div>
              <div style={{ marginTop: 18, fontSize: 11.5, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Generated schedule</div>
              <div style={{ marginTop: 8, border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
                {Array.from({ length: installments }).map((_, i) => {
                  const month = new Date(2026, 4 + i + grace, 22);
                  return (
                    <div key={i} style={{
                      display: 'grid', gridTemplateColumns: '40px 1fr 110px 110px',
                      padding: '8px 12px', fontSize: 13,
                      borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                      alignItems: 'center', gap: 12,
                    }}>
                      <span style={{ fontSize: 11.5, color: 'var(--fg-faint)' }} className="num">{i + 1}/{installments}</span>
                      <span>Concert — Alaska Live ({i + 1}/{installments})</span>
                      <span className="num" style={{ color: 'var(--fg-muted)' }}>{month.toLocaleDateString('en', { month: 'short', day: '2-digit', year: 'numeric' })}</span>
                      <span className="num" style={{ textAlign: 'right', fontWeight: 600 }}>${(300/installments).toFixed(2)}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          ) : null}

          {mode === 'split' ? (
            <Card title="Split across categories" subtitle={`Total $84.20 · ${splits.length} splits`}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
                <Field label="Description" value="Supermaxi run" editable/>
                <Field label="Total" value="84.20" prefix="$" mono editable/>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {splits.map((s, i) => (
                  <div key={s.id} style={{
                    display: 'grid', gridTemplateColumns: '24px 1fr 1fr 120px 28px',
                    gap: 8, alignItems: 'center', padding: '8px 10px',
                    border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg-sunken)',
                  }}>
                    <CatSwatch cat={s.category} size={20}/>
                    <SelectField inline label="Category" value={s.category} options={CATEGORIES}/>
                    <SelectField inline label="Budget" value={budgetName(s.budget)} options={BUDGETS.map(b => b.name)}/>
                    <Field inline label="Amount" value={s.amount.toFixed(2)} prefix="$" mono editable/>
                    <button style={{ background: 'transparent', border: 'none', color: 'var(--fg-faint)' }}>{I.x}</button>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
                <Btn kind="soft" size="sm" icon={I.plus}>Add split</Btn>
                <span style={{ flex: 1 }}/>
                <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Splits sum:</span>
                <span className="num" style={{ fontSize: 13, fontWeight: 600, color: 'var(--pos)' }}>$84.20 ✓</span>
              </div>
            </Card>
          ) : null}

          {mode === 'csv' ? (
            <Card title="Bulk import" subtitle="Drag a CSV or browse">
              <div style={{
                border: '2px dashed var(--border-strong)', borderRadius: 14, padding: 36,
                textAlign: 'center', color: 'var(--fg-muted)', background: 'var(--bg-sunken)',
              }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>↑</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg)', marginBottom: 4 }}>Drop CSV file here</div>
                <div style={{ fontSize: 12 }}>Required columns: description, amount, date · optional: account, category, budget</div>
                <Btn kind="default" size="sm" style={{ marginTop: 14 }}>Browse files</Btn>
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <Toggle label="Installments mode"/>
                <Toggle label="Skip header row" active/>
                <Toggle label="Auto-detect categories" active/>
              </div>
            </Card>
          ) : null}

          {/* Examples */}
          {mode === 'natural' ? (
            <Card title="Try these examples" padding={16}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  'Coffee 4.50 isveglio cash',
                  'Spotify 16.99 amex monthly',
                  'Flight Lima 312 visa, planning, may 22',
                  'Grocery run 84.20, split 50 groceries 34 health',
                ].map((s, i) => (
                  <button key={i} onClick={() => setNlText(s)} style={{
                    background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 8,
                    padding: '8px 12px', textAlign: 'left', fontSize: 13, color: 'var(--fg-muted)',
                    fontFamily: 'var(--font-mono)',
                  }}>{s}</button>
                ))}
              </div>
            </Card>
          ) : null}
        </div>

        {/* Right — preview */}
        <aside style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16, background: 'var(--bg-sunken)' }}>
          <div style={{ fontSize: 11.5, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Preview</div>

          <Card padding={16}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <CatSwatch cat={draft.category} size={32}/>
              <div style={{ flex: 1, lineHeight: 1.2 }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{draft.desc}</div>
                <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{draft.category} · {fmtDateLong(draft.date)}</div>
              </div>
              <div className="num" style={{ fontSize: 18, fontWeight: 600, color: 'var(--neg)' }}>−${draft.amount.toFixed(2)}</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12.5, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
              <Row k="Account" v={<AccountChip account={ACCOUNT_BY_ID.cc_visa}/>}/>
              <Row k="Pay date" v={<span className="num">May 22, 2026</span>} hint="based on CC cycle"/>
              <Row k="Budget" v={<span><span style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--cat-1)', display: 'inline-block', marginRight: 6 }}/>Groceries</span>}/>
              <Row k="Status" v={<StatusChip status={draft.status}/>}/>
            </div>
          </Card>

          <Card padding={14} title="Budget impact" subtitle="Groceries · April">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                <span style={{ color: 'var(--fg-muted)' }}>Before</span>
                <span className="num">$312.40 / $480.00</span>
              </div>
              <ProgressBar value={312.40} max={480} color="var(--cat-1)"/>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}>
                <span style={{ color: 'var(--fg-muted)' }}>After</span>
                <span className="num" style={{ fontWeight: 600 }}>$396.60 / $480.00</span>
              </div>
              <ProgressBar value={396.60} max={480} color="var(--cat-1)"/>
              <div style={{ fontSize: 11.5, color: 'var(--fg-muted)' }}>Remaining: <span className="num" style={{ color: 'var(--fg)' }}>$83.40</span></div>
            </div>
          </Card>

          <div style={{ flex: 1 }}/>

          <div style={{ display: 'flex', gap: 8 }}>
            <Btn kind="soft" style={{ flex: 1 }}>Save as pending</Btn>
            <Btn kind="primary" icon={I.check} style={{ flex: 1.4 }}>Confirm · ⌘↵</Btn>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, mono, prefix, placeholder, editable, inline }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: inline ? 2 : 6 }}>
      {!inline && <span style={{ fontSize: 11.5, color: 'var(--fg-muted)', fontWeight: 550 }}>{label}</span>}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '7px 10px',
        background: editable ? 'var(--bg-elev)' : 'var(--bg-sunken)',
        border: '1px solid var(--border)', borderRadius: 8,
        fontSize: 13.5, fontFamily: mono ? 'var(--font-mono)' : 'inherit',
      }}>
        {prefix ? <span style={{ color: 'var(--fg-faint)' }}>{prefix}</span> : null}
        <span style={{ flex: 1, color: value ? 'var(--fg)' : 'var(--fg-faint)' }}>{value || placeholder}</span>
      </div>
    </label>
  );
}

function SelectField({ label, value, options, inline }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: inline ? 2 : 6 }}>
      {!inline && <span style={{ fontSize: 11.5, color: 'var(--fg-muted)', fontWeight: 550 }}>{label}</span>}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '7px 10px', background: 'var(--bg-elev)',
        border: '1px solid var(--border)', borderRadius: 8,
        fontSize: 13.5,
      }}>
        <span style={{ flex: 1 }}>{value}</span>
        <span style={{ color: 'var(--fg-faint)' }}>{I.chevD}</span>
      </div>
    </label>
  );
}

function NumberStepper({ label, value, onChange, min = 0, max = 99 }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ fontSize: 11.5, color: 'var(--fg-muted)', fontWeight: 550 }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-elev)' }}>
        <button onClick={() => onChange(Math.max(min, value - 1))} style={{ width: 30, height: 32, background: 'transparent', border: 'none', color: 'var(--fg-muted)' }}>−</button>
        <span className="num" style={{ width: 36, textAlign: 'center', fontWeight: 600 }}>{value}</span>
        <button onClick={() => onChange(Math.min(max, value + 1))} style={{ width: 30, height: 32, background: 'transparent', border: 'none', color: 'var(--fg-muted)' }}>+</button>
      </div>
    </div>
  );
}

function Toggle({ label, active }) {
  const [on, setOn] = useStateAdd(active || false);
  return (
    <button onClick={() => setOn(!on)} style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '6px 12px', borderRadius: 999,
      background: on ? 'var(--accent-soft)' : 'var(--bg-elev)',
      color: on ? 'var(--accent)' : 'var(--fg-muted)',
      border: '1px solid ' + (on ? 'transparent' : 'var(--border)'),
      fontSize: 12.5, fontWeight: 550,
    }}>
      <span style={{ width: 14, height: 14, borderRadius: 4, background: on ? 'var(--accent)' : 'transparent', border: '1.5px solid currentColor', display: 'grid', placeItems: 'center' }}>
        {on ? <span style={{ color: 'white', fontSize: 10 }}>✓</span> : null}
      </span>
      {label}
    </button>
  );
}

function Row({ k, v, hint }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{ width: 80, color: 'var(--fg-muted)' }}>{k}</span>
      <span style={{ flex: 1 }}>{v}</span>
      {hint ? <span style={{ fontSize: 11, color: 'var(--fg-faint)', fontStyle: 'italic' }}>{hint}</span> : null}
    </div>
  );
}

Object.assign(window, { AddTxnScreen });

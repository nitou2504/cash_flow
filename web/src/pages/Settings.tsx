import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type {
  SyncStatus,
  RegisterRules,
  ClassificationHints,
  LLMConfig,
} from '../api/types';

const TABS = ['Sync', 'Register Rules', 'Classification', 'LLM Config'] as const;
type Tab = typeof TABS[number];

export default function Settings() {
  const [tab, setTab] = useState<Tab>('Sync');

  return (
    <div style={{ padding: 28, maxWidth: 960 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Settings</h2>
      <div style={{ display: 'flex', gap: 2, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 16px', fontSize: 13, fontWeight: tab === t ? 600 : 400,
            background: 'none', border: 'none', cursor: 'pointer',
            color: tab === t ? 'var(--accent)' : 'var(--fg-muted)',
            borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1,
          }}>{t}</button>
        ))}
      </div>
      {tab === 'Sync' && <SyncTab />}
      {tab === 'Register Rules' && <RegisterRulesTab />}
      {tab === 'Classification' && <ClassificationTab />}
      {tab === 'LLM Config' && <LLMConfigTab />}
    </div>
  );
}

// ── Shared styles ──────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  background: 'var(--bg-elev)', border: '1px solid var(--border)',
  borderRadius: 'var(--r-md)', padding: 20, marginBottom: 16,
  boxShadow: 'var(--shadow-card)',
};

const inputStyle: React.CSSProperties = {
  padding: '6px 10px', fontSize: 13, borderRadius: 'var(--r-sm)',
  border: '1px solid var(--border)', background: 'var(--bg)',
  color: 'var(--fg)', width: '100%', fontFamily: 'var(--font-sans)',
};

const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', fontSize: 13, fontWeight: 550,
  background: 'var(--accent)', color: 'var(--accent-fg)',
  border: 'none', borderRadius: 'var(--r-sm)', cursor: 'pointer',
};

const btnSecondary: React.CSSProperties = {
  padding: '6px 14px', fontSize: 12, fontWeight: 500,
  background: 'var(--bg-hover)', color: 'var(--fg-muted)',
  border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', cursor: 'pointer',
};

const btnDanger: React.CSSProperties = {
  ...btnSecondary, color: 'var(--neg)', borderColor: 'var(--neg)',
};

const labelStyle: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)',
  textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6,
};

const thStyle: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: 'var(--fg-faint)',
  textTransform: 'uppercase', letterSpacing: '0.05em',
  padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid var(--border)',
};

const tdStyle: React.CSSProperties = {
  padding: '4px 8px', borderBottom: '1px solid var(--border)',
  verticalAlign: 'middle',
};

function Toast({ msg, type }: { msg: string; type: 'ok' | 'err' }) {
  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, padding: '10px 18px',
      borderRadius: 'var(--r-sm)', fontSize: 13, fontWeight: 500,
      background: type === 'ok' ? 'var(--pos-soft)' : 'var(--neg-soft)',
      color: type === 'ok' ? 'var(--pos)' : 'var(--neg)',
      border: `1px solid ${type === 'ok' ? 'var(--pos)' : 'var(--neg)'}`,
      zIndex: 1000,
    }}>{msg}</div>
  );
}

function useToast() {
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null);
  const show = (msg: string, type: 'ok' | 'err') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };
  return { toast, show };
}

// ── Sync Tab ───────────────────────────────────────────────────

function SyncTab() {
  const { toast, show } = useToast();
  const { data: status } = useQuery<SyncStatus>({
    queryKey: ['sync-status'],
    queryFn: () => api.syncStatus(),
    refetchInterval: 30_000,
  });

  const triggerMut = useMutation({
    mutationFn: () => api.syncTrigger(),
    onSuccess: () => show('Sync complete', 'ok'),
    onError: (e: Error) => show(e.message, 'err'),
  });

  const s = status?.summary;

  return (
    <>
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={labelStyle}>Gmail Sync</div>
            {status?.last_run && (
              <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>
                Last run: {new Date(status.last_run).toLocaleString()}
              </div>
            )}
            {status?.next_run && (
              <div style={{ fontSize: 12, color: 'var(--fg-faint)', marginTop: 2 }}>
                Next: {new Date(status.next_run).toLocaleString()}
              </div>
            )}
          </div>
          <button
            onClick={() => triggerMut.mutate()}
            disabled={triggerMut.isPending || status?.running}
            style={{ ...btnPrimary, opacity: triggerMut.isPending ? 0.6 : 1 }}
          >
            {triggerMut.isPending || status?.running ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>

        {s && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
            <StatCard label="Consumos" value={s.consumos_ingested} />
            <StatCard label="Invoices" value={s.invoices_ingested} />
            <StatCard label="Matched" value={s.invoices_matched} />
            <StatCard label="Registered" value={s.registered} />
            <StatCard label="Enriched" value={s.enriched} />
          </div>
        )}
        {s && Object.keys(s.by_method).length > 0 && (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--fg-muted)' }}>
            Methods: {Object.entries(s.by_method).map(([m, c]) => `${c} ${m}`).join(', ')}
          </div>
        )}
        {s?.errors?.length ? (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--neg)' }}>
            Errors: {s.errors.join('; ')}
          </div>
        ) : null}
      </div>
      {toast && <Toast {...toast} />}
    </>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={{
      background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', padding: '10px 12px',
    }}>
      <div style={{ fontSize: 11, color: 'var(--fg-faint)', fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>{value}</div>
    </div>
  );
}

// ── Register Rules Tab ─────────────────────────────────────────

function RegisterRulesTab() {
  const { toast, show } = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<RegisterRules>({
    queryKey: ['register-rules'],
    queryFn: () => api.registerRulesGet(),
  });

  const [form, setForm] = useState<RegisterRules | null>(null);
  const current = form ?? data;

  const saveMut = useMutation({
    mutationFn: (d: RegisterRules) => api.registerRulesSave(d),
    onSuccess: () => { show('Saved', 'ok'); queryClient.invalidateQueries({ queryKey: ['register-rules'] }); setForm(null); },
    onError: (e: Error) => show(e.message, 'err'),
  });

  if (isLoading || !current) return <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>;

  const update = (patch: Partial<RegisterRules>) => setForm({ ...current, ...patch });

  return (
    <>
      <div style={cardStyle}>
        <div style={labelStyle}>LLM Model (for ambiguous merchants)</div>
        <input
          style={{ ...inputStyle, maxWidth: 300 }}
          value={current.llm_model}
          onChange={e => update({ llm_model: e.target.value })}
        />
      </div>

      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={labelStyle}>Merchant Rules</div>
          <button style={btnSecondary} onClick={() => update({
            merchant_rules: [...current.merchant_rules, { pattern: '', category: '', desc: '' }],
          })}>+ Add</button>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead><tr>
            <th style={thStyle}>Pattern</th>
            <th style={thStyle}>Category</th>
            <th style={thStyle}>Description</th>
            <th style={{ ...thStyle, width: 36 }}></th>
          </tr></thead>
          <tbody>
            {current.merchant_rules.map((r, i) => (
              <tr key={i}>
                <td style={tdStyle}><input style={inputStyle} value={r.pattern} onChange={e => {
                  const rules = [...current.merchant_rules];
                  rules[i] = { ...r, pattern: e.target.value };
                  update({ merchant_rules: rules });
                }} /></td>
                <td style={tdStyle}><input style={inputStyle} value={r.category} onChange={e => {
                  const rules = [...current.merchant_rules];
                  rules[i] = { ...r, category: e.target.value };
                  update({ merchant_rules: rules });
                }} /></td>
                <td style={tdStyle}><input style={inputStyle} value={r.desc ?? ''} onChange={e => {
                  const rules = [...current.merchant_rules];
                  rules[i] = { ...r, desc: e.target.value || null };
                  update({ merchant_rules: rules });
                }} /></td>
                <td style={tdStyle}><button style={btnDanger} onClick={() => {
                  update({ merchant_rules: current.merchant_rules.filter((_, j) => j !== i) });
                }}>x</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={labelStyle}>Transfer Destinations</div>
          <button style={btnSecondary} onClick={() => update({
            transfer_destinations: [...current.transfer_destinations, { account_suffix: '', name: '' }],
          })}>+ Add</button>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead><tr>
            <th style={thStyle}>Account (last 4)</th>
            <th style={thStyle}>Name</th>
            <th style={{ ...thStyle, width: 36 }}></th>
          </tr></thead>
          <tbody>
            {current.transfer_destinations.map((r, i) => (
              <tr key={i}>
                <td style={tdStyle}><input style={{ ...inputStyle, maxWidth: 100 }} value={r.account_suffix} onChange={e => {
                  const dests = [...current.transfer_destinations];
                  dests[i] = { ...r, account_suffix: e.target.value };
                  update({ transfer_destinations: dests });
                }} /></td>
                <td style={tdStyle}><input style={inputStyle} value={r.name} onChange={e => {
                  const dests = [...current.transfer_destinations];
                  dests[i] = { ...r, name: e.target.value };
                  update({ transfer_destinations: dests });
                }} /></td>
                <td style={tdStyle}><button style={btnDanger} onClick={() => {
                  update({ transfer_destinations: current.transfer_destinations.filter((_, j) => j !== i) });
                }}>x</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={labelStyle}>Item Overrides</div>
          <button style={btnSecondary} onClick={() => update({
            item_overrides: [...current.item_overrides, { keywords: [], category: '' }],
          })}>+ Add</button>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead><tr>
            <th style={thStyle}>Keywords (comma-separated)</th>
            <th style={thStyle}>Category</th>
            <th style={{ ...thStyle, width: 36 }}></th>
          </tr></thead>
          <tbody>
            {current.item_overrides.map((r, i) => (
              <tr key={i}>
                <td style={tdStyle}><input style={inputStyle} value={r.keywords.join(', ')} onChange={e => {
                  const overrides = [...current.item_overrides];
                  overrides[i] = { ...r, keywords: e.target.value.split(',').map(s => s.trim()).filter(Boolean) };
                  update({ item_overrides: overrides });
                }} /></td>
                <td style={tdStyle}><input style={{ ...inputStyle, maxWidth: 200 }} value={r.category} onChange={e => {
                  const overrides = [...current.item_overrides];
                  overrides[i] = { ...r, category: e.target.value };
                  update({ item_overrides: overrides });
                }} /></td>
                <td style={tdStyle}><button style={btnDanger} onClick={() => {
                  update({ item_overrides: current.item_overrides.filter((_, j) => j !== i) });
                }}>x</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button style={btnPrimary} onClick={() => saveMut.mutate(current)} disabled={saveMut.isPending}>
        {saveMut.isPending ? 'Saving...' : 'Save Rules'}
      </button>
      {toast && <Toast {...toast} />}
    </>
  );
}

// ── Classification Tab ─────────────────────────────────────────

function ClassificationTab() {
  const { toast, show } = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<ClassificationHints>({
    queryKey: ['classification-hints'],
    queryFn: () => api.classificationHintsGet(),
  });

  const [form, setForm] = useState<ClassificationHints | null>(null);
  const current = form ?? data;

  const saveMut = useMutation({
    mutationFn: (d: ClassificationHints) => api.classificationHintsSave(d),
    onSuccess: () => { show('Saved', 'ok'); queryClient.invalidateQueries({ queryKey: ['classification-hints'] }); setForm(null); },
    onError: (e: Error) => show(e.message, 'err'),
  });

  if (isLoading || !current) return <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>;

  const update = (patch: Partial<ClassificationHints>) => setForm({ ...current, ...patch });

  return (
    <>
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={labelStyle}>Category Hints</div>
          <button style={btnSecondary} onClick={() => update({
            category_hints: [...current.category_hints, ''],
          })}>+ Add</button>
        </div>
        {current.category_hints.map((h, i) => (
          <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
            <input style={{ ...inputStyle, flex: 1 }} value={h} onChange={e => {
              const hints = [...current.category_hints];
              hints[i] = e.target.value;
              update({ category_hints: hints });
            }} />
            <button style={btnDanger} onClick={() => {
              update({ category_hints: current.category_hints.filter((_, j) => j !== i) });
            }}>x</button>
          </div>
        ))}
      </div>

      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={labelStyle}>User Hints</div>
          <button style={btnSecondary} onClick={() => update({
            user_hints: [...current.user_hints, ''],
          })}>+ Add</button>
        </div>
        {current.user_hints.map((h, i) => (
          <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
            <input style={{ ...inputStyle, flex: 1 }} value={h} onChange={e => {
              const hints = [...current.user_hints];
              hints[i] = e.target.value;
              update({ user_hints: hints });
            }} />
            <button style={btnDanger} onClick={() => {
              update({ user_hints: current.user_hints.filter((_, j) => j !== i) });
            }}>x</button>
          </div>
        ))}
      </div>

      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={labelStyle}>Category → Budget Map</div>
          <button style={btnSecondary} onClick={() => update({
            category_budget_map: { ...current.category_budget_map, '': '' },
          })}>+ Add</button>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead><tr>
            <th style={thStyle}>Category</th>
            <th style={thStyle}>Budget Prefix</th>
            <th style={{ ...thStyle, width: 36 }}></th>
          </tr></thead>
          <tbody>
            {Object.entries(current.category_budget_map).map(([cat, prefix], i) => (
              <tr key={i}>
                <td style={tdStyle}><input style={inputStyle} value={cat} onChange={e => {
                  const map = { ...current.category_budget_map };
                  delete map[cat];
                  map[e.target.value] = prefix;
                  update({ category_budget_map: map });
                }} /></td>
                <td style={tdStyle}><input style={inputStyle} value={prefix} onChange={e => {
                  update({ category_budget_map: { ...current.category_budget_map, [cat]: e.target.value } });
                }} /></td>
                <td style={tdStyle}><button style={btnDanger} onClick={() => {
                  const map = { ...current.category_budget_map };
                  delete map[cat];
                  update({ category_budget_map: map });
                }}>x</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button style={btnPrimary} onClick={() => saveMut.mutate(current)} disabled={saveMut.isPending}>
        {saveMut.isPending ? 'Saving...' : 'Save Hints'}
      </button>
      {toast && <Toast {...toast} />}
    </>
  );
}

// ── LLM Config Tab ─────────────────────────────────────────────

function LLMConfigTab() {
  const { toast, show } = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<LLMConfig>({
    queryKey: ['llm-config'],
    queryFn: () => api.llmConfigGet(),
  });

  const [form, setForm] = useState<LLMConfig | null>(null);
  const current = form ?? data;

  const saveMut = useMutation({
    mutationFn: (d: LLMConfig) => api.llmConfigSave(d),
    onSuccess: () => { show('Saved', 'ok'); queryClient.invalidateQueries({ queryKey: ['llm-config'] }); setForm(null); },
    onError: (e: Error) => show(e.message, 'err'),
  });

  if (isLoading || !current) return <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Loading...</div>;

  const update = (patch: Partial<LLMConfig>) => setForm({ ...current, ...patch });

  return (
    <>
      <div style={cardStyle}>
        <div style={labelStyle}>Defaults</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 8 }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Provider</div>
            <input style={inputStyle} value={current.default_provider} onChange={e => update({ default_provider: e.target.value })} />
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Model</div>
            <input style={inputStyle} value={current.default_model} onChange={e => update({ default_model: e.target.value })} />
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Temperature</div>
            <input style={inputStyle} type="number" step="0.1" value={current.temperature} onChange={e => update({ temperature: parseFloat(e.target.value) || 0 })} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Timeout (seconds)</div>
            <input style={inputStyle} type="number" value={current.timeout_seconds} onChange={e => update({ timeout_seconds: parseInt(e.target.value) || 120 })} />
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Max Retries</div>
            <input style={inputStyle} type="number" value={current.max_retries} onChange={e => update({ max_retries: parseInt(e.target.value) || 2 })} />
          </div>
        </div>
      </div>

      <div style={cardStyle}>
        <div style={labelStyle}>Function Model Routing</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginTop: 8 }}>
          <thead><tr>
            <th style={thStyle}>Function</th>
            <th style={thStyle}>Provider</th>
            <th style={thStyle}>Model</th>
            <th style={thStyle}>Reason</th>
          </tr></thead>
          <tbody>
            {Object.entries(current.function_models).map(([fn, fm]) => (
              <tr key={fn}>
                <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12 }}>{fn}</td>
                <td style={tdStyle}><input style={{ ...inputStyle, maxWidth: 120 }} value={fm.provider} onChange={e => {
                  update({ function_models: { ...current.function_models, [fn]: { ...fm, provider: e.target.value } } });
                }} /></td>
                <td style={tdStyle}><input style={{ ...inputStyle, maxWidth: 160 }} value={fm.model} onChange={e => {
                  update({ function_models: { ...current.function_models, [fn]: { ...fm, model: e.target.value } } });
                }} /></td>
                <td style={tdStyle}><input style={inputStyle} value={fm.reason ?? ''} onChange={e => {
                  update({ function_models: { ...current.function_models, [fn]: { ...fm, reason: e.target.value || null } } });
                }} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={cardStyle}>
        <div style={labelStyle}>Providers</div>
        {Object.entries(current.providers).map(([name, prov]) => (
          <div key={name} style={{
            border: '1px solid var(--border)', borderRadius: 'var(--r-sm)',
            padding: 12, marginTop: 8,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>{name}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Type</div>
                <input style={inputStyle} value={prov.type} onChange={e => {
                  update({ providers: { ...current.providers, [name]: { ...prov, type: e.target.value } } });
                }} />
              </div>
              {prov.api_key_env !== undefined && (
                <div>
                  <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>API Key Env</div>
                  <input style={inputStyle} value={prov.api_key_env ?? ''} onChange={e => {
                    update({ providers: { ...current.providers, [name]: { ...prov, api_key_env: e.target.value || null } } });
                  }} />
                </div>
              )}
              {prov.base_url !== undefined && (
                <div>
                  <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Base URL</div>
                  <input style={inputStyle} value={prov.base_url ?? ''} onChange={e => {
                    update({ providers: { ...current.providers, [name]: { ...prov, base_url: e.target.value || null } } });
                  }} />
                </div>
              )}
              <div style={{ gridColumn: '1 / -1' }}>
                <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginBottom: 4 }}>Models (comma-separated)</div>
                <input style={inputStyle} value={prov.models.join(', ')} onChange={e => {
                  update({ providers: { ...current.providers, [name]: { ...prov, models: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } } });
                }} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <button style={btnPrimary} onClick={() => saveMut.mutate(current)} disabled={saveMut.isPending}>
        {saveMut.isPending ? 'Saving...' : 'Save LLM Config'}
      </button>
      {toast && <Toast {...toast} />}
    </>
  );
}

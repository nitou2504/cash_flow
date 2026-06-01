import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Subscription, Account, Category, SubscriptionCreate } from '../api/types';
import { fmtMoney } from '../utils/format';

// ── Shared styles (mirrors Settings.tsx conventions) ──────────────
const cardStyle: React.CSSProperties = {
  background: 'var(--bg-elev)', border: '1px solid var(--border)',
  borderRadius: 'var(--r-md)', padding: 20, marginBottom: 16, boxShadow: 'var(--shadow-card)',
};
const inputStyle: React.CSSProperties = {
  padding: '6px 10px', fontSize: 13, borderRadius: 'var(--r-sm)',
  border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--fg)',
  width: '100%', fontFamily: 'var(--font-sans)', boxSizing: 'border-box',
};
const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', fontSize: 13, fontWeight: 550, background: 'var(--accent)',
  color: 'var(--accent-fg)', border: 'none', borderRadius: 'var(--r-sm)', cursor: 'pointer',
};
const btnSecondary: React.CSSProperties = {
  padding: '6px 14px', fontSize: 12, fontWeight: 500, background: 'var(--bg-hover)',
  color: 'var(--fg-muted)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', cursor: 'pointer',
};
const btnDanger: React.CSSProperties = { ...btnSecondary, color: 'var(--neg)', borderColor: 'var(--neg)' };
const labelStyle: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: 'var(--fg-faint)', display: 'block', marginBottom: 4,
};
const thStyle: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: 'var(--fg-faint)', textTransform: 'uppercase',
  letterSpacing: '0.05em', padding: '8px 10px', textAlign: 'left', borderBottom: '1px solid var(--border)',
};
const tdStyle: React.CSSProperties = { padding: '8px 10px', borderBottom: '1px solid var(--border)', fontSize: 13 };

type FormState = {
  id?: string;
  name: string;
  category: string;
  monthly_amount: string;
  payment_account_id: string;
  start_date: string;
  end_date: string;
  is_budget: boolean;
  is_income: boolean;
  underspend_behavior: string;
};

const emptyForm = (account: string, category: string): FormState => ({
  name: '', category, monthly_amount: '', payment_account_id: account,
  start_date: '', end_date: '', is_budget: false, is_income: false, underspend_behavior: 'keep',
});

function StatusPill({ status }: { status: string | null }) {
  const active = status === 'Active';
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999,
      background: 'var(--bg-sunken)',
      color: active ? 'var(--pos)' : 'var(--fg-faint)',
    }}>{status ?? '—'}</span>
  );
}

export default function Subscriptions() {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null);
  const [editing, setEditing] = useState<FormState | null>(null);
  const [showExpired, setShowExpired] = useState(false);
  const [filter, setFilter] = useState<'all' | 'budgets' | 'subs'>('all');

  const show = (msg: string, type: 'ok' | 'err') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const { data: subs } = useQuery<Subscription[]>({ queryKey: ['subscriptions'], queryFn: api.subscriptions });
  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  const { data: categories } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: api.categories });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    queryClient.invalidateQueries({ queryKey: ['budgets'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    queryClient.invalidateQueries({ queryKey: ['timeline'] });
  };

  const createMut = useMutation({
    mutationFn: (body: SubscriptionCreate) => api.createSubscription(body),
    onSuccess: () => { show('Created', 'ok'); invalidate(); setEditing(null); },
    onError: (e: Error) => show(e.message, 'err'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof api.updateSubscription>[1] }) =>
      api.updateSubscription(id, body),
    onSuccess: () => { show('Saved', 'ok'); invalidate(); setEditing(null); },
    onError: (e: Error) => show(e.message, 'err'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteSubscription(id),
    onSuccess: () => { show('Deleted', 'ok'); invalidate(); },
    onError: (e: Error) => show(e.message, 'err'),
  });

  const startEdit = (s: Subscription) => setEditing({
    id: s.id, name: s.name, category: s.category,
    monthly_amount: String(s.monthly_amount), payment_account_id: s.payment_account_id,
    start_date: s.start_date ?? '', end_date: s.end_date ?? '',
    is_budget: s.is_budget, is_income: s.is_income, underspend_behavior: s.underspend_behavior,
  });

  const submitForm = (f: FormState) => {
    const amount = parseFloat(f.monthly_amount);
    if (!f.name || isNaN(amount)) { show('Name and amount required', 'err'); return; }
    if (f.id) {
      updateMut.mutate({
        id: f.id,
        body: {
          name: f.name, category: f.category, monthly_amount: amount,
          payment_account_id: f.payment_account_id,
          end_date: f.end_date || 'none',
          underspend_behavior: f.underspend_behavior,
        },
      });
    } else {
      createMut.mutate({
        name: f.name, category: f.category, monthly_amount: amount,
        payment_account_id: f.payment_account_id,
        start_date: f.start_date || undefined,
        end_date: f.end_date || null,
        is_budget: f.is_budget, is_income: f.is_income,
        underspend_behavior: f.underspend_behavior,
      });
    }
  };

  const visible = (subs ?? [])
    .filter(s => showExpired || s.status !== 'Expired')
    .filter(s => filter === 'all' || (filter === 'budgets' ? s.is_budget : !s.is_budget));

  const defaultAccount = accounts?.[0]?.account_id ?? 'Cash';
  const defaultCategory = categories?.[0]?.name ?? 'Others';

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: '24px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>Subscriptions &amp; Budgets</h1>
        <button onClick={() => setEditing(emptyForm(defaultAccount, defaultCategory))} style={btnPrimary}>
          + New
        </button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['all', 'budgets', 'subs'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              ...btnSecondary,
              background: filter === f ? 'var(--accent)' : 'var(--bg-hover)',
              color: filter === f ? 'var(--accent-fg)' : 'var(--fg-muted)',
            }}>{f === 'subs' ? 'Subscriptions' : f[0].toUpperCase() + f.slice(1)}</button>
          ))}
        </div>
        <label style={{ fontSize: 12, color: 'var(--fg-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={showExpired} onChange={e => setShowExpired(e.target.checked)} />
          Show expired
        </label>
      </div>

      <div style={cardStyle}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>Type</th>
              <th style={thStyle}>Amount</th>
              <th style={thStyle}>Account</th>
              <th style={thStyle}>Category</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}></th>
            </tr>
          </thead>
          <tbody>
            {visible.map(s => (
              <tr key={s.id}>
                <td style={tdStyle}>{s.name}</td>
                <td style={{ ...tdStyle, color: 'var(--fg-faint)' }}>{s.is_budget ? 'Budget' : 'Sub'}</td>
                <td style={{ ...tdStyle, fontVariantNumeric: 'tabular-nums' }}>{fmtMoney(s.monthly_amount)}/mo</td>
                <td style={{ ...tdStyle, color: 'var(--fg-muted)' }}>{s.payment_account_id}</td>
                <td style={{ ...tdStyle, color: 'var(--fg-muted)' }}>{s.category}</td>
                <td style={tdStyle}><StatusPill status={s.status} /></td>
                <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                  <button onClick={() => startEdit(s)} style={{ ...btnSecondary, marginRight: 6 }}>Edit</button>
                  <button
                    onClick={() => { if (confirm(`Delete "${s.name}"?`)) deleteMut.mutate(s.id); }}
                    style={btnDanger}
                  >Delete</button>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr><td style={{ ...tdStyle, color: 'var(--fg-faint)', textAlign: 'center' }} colSpan={7}>
                No subscriptions
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <EditModal
          form={editing}
          accounts={accounts ?? []}
          categories={categories ?? []}
          onChange={setEditing}
          onCancel={() => setEditing(null)}
          onSubmit={() => submitForm(editing)}
          pending={createMut.isPending || updateMut.isPending}
        />
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, padding: '10px 16px',
          borderRadius: 'var(--r-sm)', fontSize: 13, color: 'var(--accent-fg)',
          background: toast.type === 'ok' ? 'var(--pos)' : 'var(--neg)',
        }}>{toast.msg}</div>
      )}
    </div>
  );
}

function EditModal({ form, accounts, categories, onChange, onCancel, onSubmit, pending }: {
  form: FormState;
  accounts: Account[];
  categories: Category[];
  onChange: (f: FormState) => void;
  onCancel: () => void;
  onSubmit: () => void;
  pending: boolean;
}) {
  const set = (patch: Partial<FormState>) => onChange({ ...form, ...patch });
  const isEdit = !!form.id;

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }} onClick={onCancel}>
      <div style={{ ...cardStyle, width: 460, maxWidth: '90vw', marginBottom: 0 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 16px' }}>
          {isEdit ? 'Edit' : 'New'} {form.is_budget ? 'Budget' : 'Subscription'}
        </h2>

        <div style={{ display: 'grid', gap: 12 }}>
          <div>
            <label style={labelStyle}>Name</label>
            <input style={inputStyle} value={form.name} onChange={e => set({ name: e.target.value })} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>Amount / month</label>
              <input style={inputStyle} type="number" step="0.01" value={form.monthly_amount}
                onChange={e => set({ monthly_amount: e.target.value })} />
            </div>
            <div>
              <label style={labelStyle}>Account</label>
              <select style={inputStyle} value={form.payment_account_id} onChange={e => set({ payment_account_id: e.target.value })}>
                {accounts.map(a => <option key={a.account_id} value={a.account_id}>{a.account_id}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label style={labelStyle}>Category</label>
            <select style={inputStyle} value={form.category} onChange={e => set({ category: e.target.value })}>
              {categories.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>Start date {isEdit ? '(locked)' : '(optional)'}</label>
              <input style={inputStyle} type="date" value={form.start_date}
                disabled={isEdit} onChange={e => set({ start_date: e.target.value })} />
            </div>
            <div>
              <label style={labelStyle}>End date (optional)</label>
              <input style={inputStyle} type="date" value={form.end_date}
                onChange={e => set({ end_date: e.target.value })} />
            </div>
          </div>

          {!isEdit && (
            <div style={{ display: 'flex', gap: 16 }}>
              <label style={{ fontSize: 12, display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="checkbox" checked={form.is_budget} onChange={e => set({ is_budget: e.target.checked })} />
                Is budget (envelope)
              </label>
              <label style={{ fontSize: 12, display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="checkbox" checked={form.is_income} onChange={e => set({ is_income: e.target.checked })} />
                Is income
              </label>
            </div>
          )}

          {form.is_budget && (
            <div>
              <label style={labelStyle}>Underspend behavior</label>
              <select style={inputStyle} value={form.underspend_behavior} onChange={e => set({ underspend_behavior: e.target.value })}>
                <option value="keep">keep (leftover stays reserved)</option>
                <option value="return">return (release leftover at month end)</option>
              </select>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
          <button onClick={onCancel} style={btnSecondary}>Cancel</button>
          <button onClick={onSubmit} disabled={pending} style={{ ...btnPrimary, opacity: pending ? 0.6 : 1 }}>
            {pending ? 'Saving…' : isEdit ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}

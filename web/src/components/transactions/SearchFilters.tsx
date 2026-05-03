import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { SearchFilters as Filters, Account, Category, Subscription } from '../../api/types';

const STATUSES = ['committed', 'pending', 'planning', 'forecast'];
const STATUS_COLORS: Record<string, string> = {
  committed: 'var(--pos)',
  pending: 'var(--warn)',
  planning: 'oklch(0.65 0.15 290)',
  forecast: 'var(--fg-muted)',
};

export default function SearchFilters({ filters, onChange }: {
  filters: Filters;
  onChange: (f: Filters) => void;
}) {
  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  const { data: categories } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: api.categories });
  const { data: budgets } = useQuery<Subscription[]>({ queryKey: ['budgets'], queryFn: api.budgets });

  const activeBudgets = budgets?.filter(b => b.is_budget) ?? [];

  const set = (key: keyof Filters, val: string) => {
    onChange({ ...filters, [key]: val || undefined });
  };

  const statuses = filters.statuses ?? ['committed'];
  const toggleStatus = (s: string) => {
    const next = statuses.includes(s) ? statuses.filter(x => x !== s) : [...statuses, s];
    onChange({ ...filters, statuses: next.length ? next : ['committed'] });
  };

  const activeCount = [filters.account, filters.category, filters.budget,
    filters.from_date, filters.to_date, filters.min_amount, filters.max_amount,
    filters.date_field === 'date_created' ? 'y' : ''].filter(Boolean).length;

  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 8, padding: '10px 20px',
      borderBottom: '1px solid var(--border)', background: 'var(--bg-sunken)',
      alignItems: 'center',
    }}>
      <Select label="Account" value={filters.account} onChange={v => set('account', v)}>
        {accounts?.map(a => <option key={a.account_id} value={a.account_id}>{a.account_id}</option>)}
      </Select>

      <Select label="Category" value={filters.category} onChange={v => set('category', v)}>
        {categories?.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
      </Select>

      <div style={{ display: 'flex', gap: 3 }}>
        {STATUSES.map(s => {
          const on = statuses.includes(s);
          return (
            <button key={s} onClick={() => toggleStatus(s)} style={{
              padding: '4px 7px', borderRadius: 5, fontSize: 10.5, fontWeight: 600,
              border: `1px solid ${on ? STATUS_COLORS[s] || 'var(--accent)' : 'var(--border)'}`,
              background: on ? `color-mix(in oklch, ${STATUS_COLORS[s] || 'var(--accent)'} 12%, var(--bg))` : 'var(--bg)',
              color: on ? STATUS_COLORS[s] || 'var(--accent)' : 'var(--fg-faint)',
              cursor: 'pointer', textTransform: 'capitalize',
            }}>{s}</button>
          );
        })}
      </div>

      <Select label="Budget" value={filters.budget} onChange={v => set('budget', v)}>
        {activeBudgets.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
      </Select>

      <div style={{ height: 20, width: 1, background: 'var(--border)', margin: '0 2px' }} />

      <button
        onClick={() => set('date_field', filters.date_field === 'date_created' ? 'date_payed' : 'date_created')}
        title={filters.date_field === 'date_created' ? 'Filtering by purchase date' : 'Filtering by payment date'}
        style={{
          padding: '5px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
          border: '1px solid var(--border)', cursor: 'pointer', whiteSpace: 'nowrap',
          background: filters.date_field === 'date_created'
            ? 'color-mix(in oklch, var(--accent) 8%, var(--bg))' : 'var(--bg)',
          color: filters.date_field === 'date_created' ? 'var(--accent)' : 'var(--fg-muted)',
        }}
      >
        {filters.date_field === 'date_created' ? 'Purchased' : 'Pays'}
      </button>

      <DateInput label="From" value={filters.from_date} onChange={v => set('from_date', v)} />
      <DateInput label="To" value={filters.to_date} onChange={v => set('to_date', v)} />

      <NumberInput label="Min $" value={filters.min_amount} onChange={v => set('min_amount', v)} />
      <NumberInput label="Max $" value={filters.max_amount} onChange={v => set('max_amount', v)} />

      {activeCount > 0 && (
        <button onClick={() => onChange({})} style={{
          padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--fg-muted)', cursor: 'pointer',
        }}>
          Clear filters
        </button>
      )}
    </div>
  );
}

function Select({ label, value, onChange, children }: {
  label: string; value?: string; onChange: (v: string) => void; children: React.ReactNode;
}) {
  const active = !!value;
  return (
    <select
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      style={{
        padding: '5px 8px', borderRadius: 6, fontSize: 12, fontWeight: 550,
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
        background: active ? 'color-mix(in oklch, var(--accent) 8%, var(--bg))' : 'var(--bg)',
        color: active ? 'var(--accent)' : 'var(--fg-muted)',
        cursor: 'pointer', outline: 'none', minWidth: 0,
      }}
    >
      <option value="">{label}</option>
      {children}
    </select>
  );
}

function DateInput({ label, value, onChange }: {
  label: string; value?: string; onChange: (v: string) => void;
}) {
  const active = !!value;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 11, color: 'var(--fg-faint)', fontWeight: 600 }}>{label}</span>
      <input
        type="date"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        style={{
          padding: '4px 6px', borderRadius: 6, fontSize: 12,
          border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
          background: active ? 'color-mix(in oklch, var(--accent) 8%, var(--bg))' : 'var(--bg)',
          color: active ? 'var(--accent)' : 'var(--fg-muted)',
          outline: 'none', fontFamily: 'inherit',
        }}
      />
    </div>
  );
}

function NumberInput({ label, value, onChange }: {
  label: string; value?: string; onChange: (v: string) => void;
}) {
  const active = !!value;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 11, color: 'var(--fg-faint)', fontWeight: 600 }}>{label}</span>
      <input
        type="number"
        step="0.01"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        placeholder="0.00"
        style={{
          width: 70, padding: '4px 6px', borderRadius: 6, fontSize: 12,
          border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
          background: active ? 'color-mix(in oklch, var(--accent) 8%, var(--bg))' : 'var(--bg)',
          color: active ? 'var(--accent)' : 'var(--fg-muted)',
          outline: 'none', fontFamily: 'inherit',
        }}
      />
    </div>
  );
}

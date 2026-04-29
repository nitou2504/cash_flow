import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { TransactionCreate, Account, Category, Subscription, Transaction, BudgetSpending } from '../../api/types';
import { fmtMoney, fmtDate, fmtDateLong } from '../../utils/format';
import CatSwatch from '../primitives/CatSwatch';
import Segmented from '../primitives/Segmented';

interface Props {
  onClose: () => void;
}

export interface FormInitial {
  desc?: string; amount?: string; account?: string; category?: string;
  budget?: string; date?: string; isIncome?: boolean; status?: string;
}

export default function AddTransactionPanel({ onClose }: Props) {
  const [mode, setMode] = useState('form');
  const [formInit, setFormInit] = useState<FormInitial | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        display: 'flex', justifyContent: 'flex-end',
        background: 'color-mix(in oklch, var(--fg) 18%, transparent)',
        backdropFilter: 'blur(2px)',
      }}
      onClick={onClose}
    >
      <aside
        onClick={e => e.stopPropagation()}
        style={{
          width: 540, maxWidth: '90%', height: '100%',
          background: 'var(--bg-elev)', borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-pop)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>New transaction</div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
              {mode === 'nl' ? 'Type naturally or use the form' : 'Fill in the details'} &middot; &thinsp;&#8984; Enter to save
            </div>
          </div>
          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--fg-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div style={{ padding: '12px 22px 0' }}>
          <Segmented value={mode} onChange={setMode} size="sm" options={[
            { value: 'nl', label: '✨ Natural language' },
            { value: 'form', label: 'Form' },
            { value: 'installments', label: 'Installments' },
            { value: 'split', label: 'Split' },
          ]} />
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: '16px 22px 100px' }}>
          {mode === 'nl' && <NLMode onClose={onClose} queryClient={queryClient} onRevise={(vals) => { setFormInit(vals); setMode('form'); }} />}
          {mode === 'form' && <FormMode onClose={onClose} queryClient={queryClient} initial={formInit} />}
          {mode === 'installments' && <InstallmentMode onClose={onClose} queryClient={queryClient} />}
          {mode === 'split' && <SplitMode onClose={onClose} queryClient={queryClient} />}
        </div>
      </aside>
    </div>
  );
}

function NLMode({ onClose, queryClient, onRevise }: { onClose: () => void; queryClient: ReturnType<typeof useQueryClient>; onRevise: (vals: FormInitial) => void }) {
  const [text, setText] = useState('');
  const [parsed, setParsed] = useState<Record<string, unknown> | null>(null);
  const [parseStep, setParseStep] = useState<string | null>(null);

  const parseMut = useMutation({
    mutationFn: (input: string) => api.parseTransaction(input, (_step, label) => setParseStep(label)),
    onSuccess: (data) => { setParsed(data); setParseStep(null); },
    onError: () => setParseStep(null),
  });

  const createMut = useMutation({
    mutationFn: (body: TransactionCreate) => api.createTransaction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
    },
  });

  const handleParse = () => {
    if (text.trim()) parseMut.mutate(text);
  };

  const handleConfirm = () => {
    if (!parsed) return;
    const body: TransactionCreate = {
      description: String(parsed.description || ''),
      amount: -(Math.abs(Number(parsed.amount || 0))),
      account: String(parsed.account || ''),
      category: parsed.category ? String(parsed.category) : undefined,
      budget: parsed.budget ? String(parsed.budget) : undefined,
      date: parsed.date_created ? String(parsed.date_created) : undefined,
      is_income: !!parsed.is_income,
      status: parsed.is_pending ? 'pending' : parsed.is_planning ? 'planning' : 'committed',
      installments: parsed.installments ? Number(parsed.installments) : undefined,
      grace_period_months: parsed.grace_period_months ? Number(parsed.grace_period_months) : 0,
    };
    if (parsed.is_income) body.amount = Math.abs(body.amount);
    createMut.mutate(body);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        if (parsed) handleConfirm();
        else handleParse();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  return (
    <>
      <div style={{
        background: 'var(--bg-sunken)', border: '1.5px solid var(--accent)',
        borderRadius: 12, padding: '14px 16px',
        display: 'flex', flexDirection: 'column', gap: 10,
        boxShadow: '0 0 0 4px var(--accent-soft)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>
          <span style={{ color: 'var(--accent)' }}>&#10024;</span>
          Describe your transaction
        </div>
        <input
          value={text}
          onChange={e => { setText(e.target.value); setParsed(null); }}
          onKeyDown={e => { if (e.key === 'Enter' && !e.metaKey && !e.ctrlKey) handleParse(); }}
          placeholder='e.g. "supermaxi groceries 84.20, visa, today"'
          style={{
            width: '100%', border: 'none', background: 'transparent',
            fontSize: 15.5, fontWeight: 500, color: 'var(--fg)', outline: 'none',
            padding: '4px 0', fontFamily: 'inherit',
          }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--fg-faint)', flexWrap: 'wrap' }}>
          <span>Try:</span>
          <ChipExample>supermaxi groceries 84.20, visa, today</ChipExample>
          <ChipExample>uber 4.50 cash</ChipExample>
          <ChipExample>tv 500, produbanco, 6 installments</ChipExample>
        </div>
      </div>

      {parseMut.isPending && <ParsingAnimation step={parseStep} />}

      {parseMut.error && (
        <div style={{ marginTop: 16, padding: '12px 16px', background: 'color-mix(in oklch, var(--neg) 8%, transparent)', border: '1px solid color-mix(in oklch, var(--neg) 25%, var(--border))', borderRadius: 10, fontSize: 12.5, color: 'var(--neg)' }}>
          {parseMut.error.message || 'Failed to parse. Try rephrasing.'}
        </div>
      )}

      {parsed && (
        <div style={{ marginTop: 16 }}>
          {/* Preview card */}
          <div style={{
            background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 14,
            padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14,
          }}>
            <CatSwatch cat={parsed.category ? String(parsed.category) : null} size={44} />
            <div style={{ flex: 1, lineHeight: 1.25 }}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{String(parsed.description || '')}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                {parsed.date_created ? fmtDateLong(String(parsed.date_created)) : 'Today'} &middot; {String(parsed.account || '')}
              </div>
            </div>
            <div className="num" style={{
              fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em',
              color: parsed.is_income ? 'var(--pos)' : 'var(--fg)',
            }}>
              {fmtMoney(parsed.is_income ? Math.abs(Number(parsed.amount)) : -Math.abs(Number(parsed.amount)))}
            </div>
          </div>

          {/* Parsed fields grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
            <ParsedField label="Category" value={parsed.category ? String(parsed.category) : 'None'} />
            <ParsedField label="Budget" value={parsed.budget ? String(parsed.budget) : 'None'} />
            <ParsedField label="Type" value={String(parsed.type || 'simple')} />
            {!!parsed.installments && <ParsedField label="Installments" value={String(parsed.installments)} />}
            {!!parsed.grace_period_months && <ParsedField label="Grace period" value={`${parsed.grace_period_months} months`} />}
            {!!parsed.is_pending && <ParsedField label="Status" value="Pending" />}
          </div>

          <div style={{
            display: 'flex', gap: 8, justifyContent: 'flex-end',
            position: 'sticky', bottom: 0, margin: '0 -22px', padding: '14px 22px',
            borderTop: '1px solid var(--border)', background: 'var(--bg)',
          }}>
            {createMut.error && <span style={{ fontSize: 12, color: 'var(--neg)', flex: 1 }}>{createMut.error.message}</span>}
            <span style={{ flex: createMut.error ? 0 : 1 }} />
            <button onClick={() => onRevise({
              desc: String(parsed.description || ''),
              amount: String(Math.abs(Number(parsed.amount || 0))),
              account: String(parsed.account || ''),
              category: parsed.category ? String(parsed.category) : undefined,
              budget: parsed.budget ? String(parsed.budget) : undefined,
              date: parsed.date_created ? String(parsed.date_created) : undefined,
              isIncome: !!parsed.is_income,
              status: parsed.is_pending ? 'pending' : parsed.is_planning ? 'planning' : 'committed',
            })} style={{
              padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 550,
              background: 'transparent', border: '1px solid var(--border)', color: 'var(--fg-muted)', cursor: 'pointer',
            }}>Revise in form</button>
            <button onClick={onClose} style={{
              padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 550,
              background: 'transparent', border: '1px solid var(--border)', color: 'var(--fg-muted)', cursor: 'pointer',
            }}>Cancel</button>
            <button onClick={handleConfirm} disabled={createMut.isPending} style={{
              padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: 'var(--accent)', border: 'none', color: 'white', cursor: 'pointer',
              opacity: createMut.isPending ? 0.6 : 1,
            }}>
              {createMut.isPending ? 'Saving...' : 'Confirm'}
              {!createMut.isPending && <span style={{ marginLeft: 8, opacity: 0.7, fontSize: 11 }}>&#8984;&#8629;</span>}
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function ParsedField({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      padding: '8px 12px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 8,
    }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--fg-faint)', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 550 }}>{value}</div>
    </div>
  );
}

function ChipExample({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      padding: '2px 8px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 999,
      fontSize: 11, color: 'var(--fg-muted)', cursor: 'pointer',
    }}>{children}</span>
  );
}

function FormMode({ onClose, queryClient, initial }: { onClose: () => void; queryClient: ReturnType<typeof useQueryClient>; initial?: FormInitial | null }) {
  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  const { data: categories } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: api.categories });
  const { data: budgets } = useQuery<Subscription[]>({ queryKey: ['budgets'], queryFn: api.budgets });

  const [desc, setDesc] = useState(initial?.desc || '');
  const [amount, setAmount] = useState(initial?.amount || '');
  const [account, setAccount] = useState(initial?.account || '');
  const [category, setCategory] = useState(initial?.category || '');
  const [budget, setBudget] = useState(initial?.budget || '');
  const [date, setDate] = useState(initial?.date || new Date().toISOString().slice(0, 10));
  const [status, setStatus] = useState(initial?.status || 'committed');
  const [isIncome, setIsIncome] = useState(initial?.isIncome || false);
  const [needsReview, setNeedsReview] = useState(false);

  useEffect(() => {
    if (accounts?.length && !account) setAccount(initial?.account || accounts[0].account_id);
  }, [accounts, account, initial]);

  const filteredBudgets = useMemo(() => {
    if (!budgets) return [];
    return budgets.filter(b => b.is_budget && (!account || b.payment_account_id === account));
  }, [budgets, account]);

  const budgetMonth = date ? date.slice(0, 7) : undefined;
  const { data: budgetSpending } = useQuery<BudgetSpending[]>({
    queryKey: ['budget-spending', budgetMonth],
    queryFn: () => api.budgetSpending(budgetMonth),
    enabled: !!budget && !!budgetMonth,
  });
  const selectedBudgetInfo = budgetSpending?.find(b => b.id === budget);

  const createMut = useMutation({
    mutationFn: (body: TransactionCreate) => api.createTransaction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
    },
  });

  const handleSave = () => {
    if (!desc || !amount || !account) return;
    const amt = parseFloat(amount);
    if (isNaN(amt)) return;
    createMut.mutate({
      description: desc,
      amount: isIncome ? Math.abs(amt) : -Math.abs(amt),
      account,
      category: category || undefined,
      budget: budget || undefined,
      date: date || undefined,
      is_income: isIncome,
      status,
      needs_review: needsReview,
    });
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSave();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const parsedAmt = parseFloat(amount);
  const previewAmt = isNaN(parsedAmt) ? 0 : isIncome ? parsedAmt : -parsedAmt;

  return (
    <>
      {desc && amount && (
        <div style={{
          background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 14,
          padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14,
        }}>
          <CatSwatch cat={category || null} size={44} />
          <div style={{ flex: 1, lineHeight: 1.25 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{desc}</div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{fmtDateLong(date)} &middot; {account}</div>
          </div>
          <div className="num" style={{ fontSize: 24, fontWeight: 600, color: previewAmt > 0 ? 'var(--pos)' : 'var(--fg)', letterSpacing: '-0.02em' }}>
            {fmtMoney(previewAmt)}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        <FormField label="Description" full>
          <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="What did you buy?" style={inputStyle} />
        </FormField>
        <FormField label="Amount ($)">
          <input value={amount} onChange={e => setAmount(e.target.value)} type="number" step="0.01" placeholder="0.00" style={inputStyle} />
        </FormField>
        <FormField label="Account">
          <select value={account} onChange={e => setAccount(e.target.value)} style={inputStyle}>
            {accounts?.map(a => <option key={a.account_id} value={a.account_id}>{a.account_id}</option>)}
          </select>
        </FormField>
        <FormField label="Category">
          <select value={category} onChange={e => setCategory(e.target.value)} style={inputStyle}>
            <option value="">None</option>
            {categories?.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </FormField>
        <FormField label="Budget">
          <select value={budget} onChange={e => setBudget(e.target.value)} style={inputStyle}>
            <option value="">None</option>
            {filteredBudgets.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </FormField>
        <FormField label="Date">
          <input value={date} onChange={e => setDate(e.target.value)} type="date" style={inputStyle} />
        </FormField>
      </div>

      <div style={{ marginBottom: 14 }}>
        <FieldLabel>Status</FieldLabel>
        <Segmented value={status} onChange={setStatus} size="sm" options={[
          { value: 'committed', label: 'Committed' },
          { value: 'pending', label: 'Pending' },
          { value: 'planning', label: 'Planning' },
        ]} />
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 14 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--fg-muted)', cursor: 'pointer' }}>
          <input type="checkbox" checked={isIncome} onChange={e => setIsIncome(e.target.checked)} style={{ accentColor: 'var(--accent)' }} />
          This is income
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--fg-muted)', cursor: 'pointer' }}>
          <input type="checkbox" checked={needsReview} onChange={e => setNeedsReview(e.target.checked)} style={{ accentColor: 'var(--warn)' }} />
          Needs review
        </label>
      </div>

      {selectedBudgetInfo && (
        <div style={{
          background: 'var(--info-soft)', border: '1px solid color-mix(in oklch, var(--info) 25%, var(--border))',
          borderRadius: 10, padding: '10px 14px', marginBottom: 14, fontSize: 12.5, color: 'var(--info)',
        }}>
          <strong>{selectedBudgetInfo.name}</strong>: <span className="num">{fmtMoney(-selectedBudgetInfo.remaining)}</span> remaining of <span className="num">{fmtMoney(-selectedBudgetInfo.allocated)}</span> allocated
        </div>
      )}

      <Footer saving={createMut.isPending} error={createMut.error?.message} onCancel={onClose} onSave={handleSave} />
    </>
  );
}

function InstallmentMode({ onClose, queryClient }: { onClose: () => void; queryClient: ReturnType<typeof useQueryClient> }) {
  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  const { data: categories } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: api.categories });
  const { data: budgets } = useQuery<Subscription[]>({ queryKey: ['budgets'], queryFn: api.budgets });

  const [desc, setDesc] = useState('');
  const [totalAmount, setTotalAmount] = useState('');
  const [account, setAccount] = useState('');
  const [category, setCategory] = useState('');
  const [budget, setBudget] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [installments, setInstallments] = useState(3);
  const [gracePeriod, setGracePeriod] = useState(0);
  const [startFrom, setStartFrom] = useState(1);

  const [preview, setPreview] = useState<Transaction[] | null>(null);

  useEffect(() => {
    if (accounts?.length && !account) setAccount(accounts[0].account_id);
  }, [accounts, account]);

  const previewMut = useMutation({
    mutationFn: (body: TransactionCreate) => api.previewTransaction(body),
    onSuccess: (data) => setPreview(data),
  });

  const createMut = useMutation({
    mutationFn: (body: TransactionCreate) => api.createTransaction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
    },
  });

  const buildBody = (): TransactionCreate | null => {
    const amt = parseFloat(totalAmount);
    if (!desc || isNaN(amt) || !account) return null;
    return {
      description: desc,
      amount: -Math.abs(amt),
      account,
      category: category || undefined,
      budget: budget || undefined,
      date: date || undefined,
      installments,
      grace_period_months: gracePeriod,
      start_from_installment: startFrom,
    };
  };

  const handlePreview = () => {
    const body = buildBody();
    if (body) previewMut.mutate(body);
  };

  const handleSave = () => {
    const body = buildBody();
    if (body) createMut.mutate(body);
  };

  const perInstallment = parseFloat(totalAmount) && installments ? (parseFloat(totalAmount) / installments) : 0;

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        <FormField label="Description" full>
          <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="What did you buy?" style={inputStyle} />
        </FormField>
        <FormField label="Total amount ($)">
          <input value={totalAmount} onChange={e => setTotalAmount(e.target.value)} type="number" step="0.01" placeholder="0.00" style={inputStyle} />
        </FormField>
        <FormField label="Account">
          <select value={account} onChange={e => setAccount(e.target.value)} style={inputStyle}>
            {accounts?.map(a => <option key={a.account_id} value={a.account_id}>{a.account_id}</option>)}
          </select>
        </FormField>
        <FormField label="Purchase date">
          <input value={date} onChange={e => setDate(e.target.value)} type="date" style={inputStyle} />
        </FormField>
        <FormField label="Category">
          <select value={category} onChange={e => setCategory(e.target.value)} style={inputStyle}>
            <option value="">None</option>
            {categories?.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </FormField>
        <FormField label="Budget">
          <select value={budget} onChange={e => setBudget(e.target.value)} style={inputStyle}>
            <option value="">None</option>
            {budgets?.filter(b => b.is_budget).map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </FormField>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 14, alignItems: 'flex-end' }}>
        <FormField label="# Installments">
          <NumberStepper value={installments} onChange={setInstallments} min={2} max={48} />
        </FormField>
        <FormField label="Grace months">
          <NumberStepper value={gracePeriod} onChange={setGracePeriod} min={0} max={12} />
        </FormField>
        <FormField label="Start from #">
          <NumberStepper value={startFrom} onChange={setStartFrom} min={1} max={installments} />
        </FormField>
        <button onClick={handlePreview} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 12.5, fontWeight: 600,
          background: 'var(--bg-sunken)', border: '1px solid var(--border)',
          color: 'var(--fg-muted)', cursor: 'pointer', whiteSpace: 'nowrap', height: 36,
        }}>
          Preview schedule
        </button>
      </div>

      {perInstallment > 0 && (
        <div style={{
          background: 'var(--info-soft)', border: '1px solid color-mix(in oklch, var(--info) 25%, var(--border))',
          borderRadius: 10, padding: '10px 14px', marginBottom: 14, fontSize: 12.5, color: 'var(--info)',
        }}>
          <strong>{installments}</strong> payments of <strong className="num">{fmtMoney(-perInstallment)}</strong> each
          {gracePeriod > 0 && <span> &middot; {gracePeriod} month grace</span>}
          {startFrom > 1 && <span> &middot; starting #{startFrom}</span>}
        </div>
      )}

      {preview && preview.length > 0 && (
        <div style={{
          border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden',
          background: 'var(--bg-elev)', marginBottom: 14,
        }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '50px 1fr 90px 90px',
            gap: 8, padding: '8px 14px', fontSize: 10.5, fontWeight: 600,
            color: 'var(--fg-faint)', letterSpacing: '0.05em', textTransform: 'uppercase',
            background: 'var(--bg-sunken)', borderBottom: '1px solid var(--border)',
          }}>
            <div>#</div><div>Description</div><div style={{ textAlign: 'right' }}>Date</div><div style={{ textAlign: 'right' }}>Amount</div>
          </div>
          {preview.map((t, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '50px 1fr 90px 90px',
              gap: 8, padding: '8px 14px', fontSize: 12.5,
              borderTop: i === 0 ? 'none' : '1px solid var(--border)',
            }}>
              <div className="num" style={{ color: 'var(--fg-faint)' }}>{i + 1}/{preview.length}</div>
              <div style={{ fontWeight: 500 }}>{t.description}</div>
              <div className="num" style={{ textAlign: 'right', color: 'var(--fg-muted)' }}>{fmtDate(t.date_payed)}</div>
              <div className="num" style={{ textAlign: 'right', fontWeight: 600 }}>{fmtMoney(t.amount)}</div>
            </div>
          ))}
        </div>
      )}

      <Footer saving={createMut.isPending} error={createMut.error?.message} onCancel={onClose} onSave={handleSave} />
    </>
  );
}

function SplitMode({ onClose, queryClient }: { onClose: () => void; queryClient: ReturnType<typeof useQueryClient> }) {
  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  const { data: categories } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: api.categories });
  const { data: budgets } = useQuery<Subscription[]>({ queryKey: ['budgets'], queryFn: api.budgets });

  const [desc, setDesc] = useState('');
  const [totalAmount, setTotalAmount] = useState('');
  const [account, setAccount] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [splits, setSplits] = useState([{ amount: '', category: '', budget: '' }]);

  useEffect(() => {
    if (accounts?.length && !account) setAccount(accounts[0].account_id);
  }, [accounts, account]);

  const addSplit = () => setSplits([...splits, { amount: '', category: '', budget: '' }]);
  const removeSplit = (i: number) => setSplits(splits.filter((_, idx) => idx !== i));
  const updateSplit = (i: number, field: string, value: string) => {
    const next = [...splits];
    next[i] = { ...next[i], [field]: value };
    setSplits(next);
  };

  const splitSum = splits.reduce((s, sp) => s + (parseFloat(sp.amount) || 0), 0);
  const total = parseFloat(totalAmount) || 0;

  const createMut = useMutation({
    mutationFn: (body: TransactionCreate) => api.createTransaction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
    },
  });

  const handleSave = () => {
    if (!desc || !total || !account) return;
    createMut.mutate({
      description: desc,
      amount: -Math.abs(total),
      account,
      date: date || undefined,
      splits: splits.filter(s => parseFloat(s.amount)).map(s => ({
        amount: -Math.abs(parseFloat(s.amount)),
        category: s.category || undefined,
        budget: s.budget || undefined,
      })),
    });
  };

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        <FormField label="Description" full>
          <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="What did you buy?" style={inputStyle} />
        </FormField>
        <FormField label="Total amount ($)">
          <input value={totalAmount} onChange={e => setTotalAmount(e.target.value)} type="number" step="0.01" placeholder="0.00" style={inputStyle} />
        </FormField>
        <FormField label="Account">
          <select value={account} onChange={e => setAccount(e.target.value)} style={inputStyle}>
            {accounts?.map(a => <option key={a.account_id} value={a.account_id}>{a.account_id}</option>)}
          </select>
        </FormField>
        <FormField label="Date">
          <input value={date} onChange={e => setDate(e.target.value)} type="date" style={inputStyle} />
        </FormField>
      </div>

      <FieldLabel>Splits</FieldLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 10 }}>
        {splits.map((sp, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 12px', background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 10,
          }}>
            <CatSwatch cat={sp.category || null} size={22} />
            <select value={sp.category} onChange={e => updateSplit(i, 'category', e.target.value)} style={{ ...inputStyle, flex: 1, minWidth: 0 }}>
              <option value="">Category</option>
              {categories?.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <select value={sp.budget} onChange={e => updateSplit(i, 'budget', e.target.value)} style={{ ...inputStyle, flex: 1, minWidth: 0 }}>
              <option value="">Budget</option>
              {budgets?.filter(b => b.is_budget).map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <input
              value={sp.amount}
              onChange={e => updateSplit(i, 'amount', e.target.value)}
              type="number" step="0.01" placeholder="$"
              style={{ ...inputStyle, width: 80 }}
            />
            {splits.length > 1 && (
              <button onClick={() => removeSplit(i)} style={{
                width: 24, height: 24, borderRadius: 6,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--fg-faint)', cursor: 'pointer', display: 'grid', placeItems: 'center', flexShrink: 0,
              }}>
                &times;
              </button>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <button onClick={addSplit} style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
          background: 'var(--bg-sunken)', border: '1px solid var(--border)',
          color: 'var(--fg-muted)', cursor: 'pointer',
        }}>
          + Add split
        </button>
        <span className="num" style={{
          fontSize: 12, fontWeight: 600,
          color: total > 0 && Math.abs(splitSum - total) < 0.01 ? 'var(--pos)' : 'var(--fg-muted)',
        }}>
          {fmtMoney(-splitSum)} / {fmtMoney(-total)}
          {total > 0 && Math.abs(splitSum - total) >= 0.01 && (
            <span style={{ color: 'var(--warn)', marginLeft: 6 }}>
              ({fmtMoney(total - splitSum)} remaining)
            </span>
          )}
        </span>
      </div>

      <Footer saving={createMut.isPending} error={createMut.error?.message} onCancel={onClose} onSave={handleSave} />
    </>
  );
}

function NumberStepper({ value, onChange, min, max }: { value: number; onChange: (v: number) => void; min: number; max: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', height: 36 }}>
      <button
        onClick={() => onChange(Math.max(min, value - 1))}
        style={{ width: 32, height: '100%', background: 'var(--bg-sunken)', border: 'none', color: 'var(--fg-muted)', cursor: 'pointer', fontSize: 16 }}
      >&minus;</button>
      <span className="num" style={{ width: 40, textAlign: 'center', fontSize: 13, fontWeight: 600, background: 'var(--bg-elev)' }}>{value}</span>
      <button
        onClick={() => onChange(Math.min(max, value + 1))}
        style={{ width: 32, height: '100%', background: 'var(--bg-sunken)', border: 'none', color: 'var(--fg-muted)', cursor: 'pointer', fontSize: 16 }}
      >+</button>
    </div>
  );
}

function Footer({ saving, error, onCancel, onSave }: { saving: boolean; error?: string; onCancel: () => void; onSave: () => void }) {
  return (
    <div style={{
      position: 'sticky', bottom: 0, margin: '0 -22px', padding: '14px 22px',
      borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8,
      background: 'var(--bg)',
    }}>
      {error && <span style={{ fontSize: 12, color: 'var(--neg)', flex: 1 }}>{error}</span>}
      <span style={{ flex: error ? 0 : 1 }} />
      <button onClick={onCancel} style={{
        padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 550,
        background: 'transparent', border: '1px solid var(--border)', color: 'var(--fg-muted)', cursor: 'pointer',
      }}>Cancel</button>
      <button onClick={onSave} disabled={saving} style={{
        padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
        background: 'var(--accent)', border: 'none', color: 'white', cursor: 'pointer',
        opacity: saving ? 0.6 : 1,
      }}>
        {saving ? 'Saving...' : 'Save transaction'}
        {!saving && <span style={{ marginLeft: 8, opacity: 0.7, fontSize: 11 }}>&#8984;&#8629;</span>}
      </button>
    </div>
  );
}

function FormField({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <div style={full ? { gridColumn: '1 / -1' } : undefined}>
      <FieldLabel>{label}</FieldLabel>
      {children}
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 11.5, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase',
      fontWeight: 600, marginBottom: 6,
    }}>{children}</div>
  );
}

const PARSE_STEPS = [
  { key: 'pre_parse', label: 'Extracting date & account' },
  { key: 'parsing', label: 'Classifying transaction' },
];

function ParsingAnimation({ step }: { step: string | null }) {
  const activeIdx = step ? PARSE_STEPS.findIndex(s => s.label === step) : -1;

  return (
    <div style={{
      marginTop: 16, padding: '20px 18px',
      background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 12,
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14,
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: '50%',
        border: '3px solid var(--border)',
        borderTopColor: 'var(--accent)',
        animation: 'spin 0.8s linear infinite',
      }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '100%', maxWidth: 220 }}>
        {PARSE_STEPS.map((s, i) => (
          <div key={s.key} style={{
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 550,
            color: i < activeIdx ? 'var(--pos)' : i === activeIdx ? 'var(--fg)' : 'var(--fg-faint)',
            transition: 'color 0.3s',
          }}>
            <span style={{ fontSize: 14 }}>{i < activeIdx ? '✓' : i === activeIdx ? '›' : '·'}</span>
            {s.label}
          </div>
        ))}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8,
  background: 'var(--bg-elev)', color: 'var(--fg)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
  boxSizing: 'border-box',
};

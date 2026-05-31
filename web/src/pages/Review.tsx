import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Transaction, ReviewItem, Account, Category, Subscription, TransactionUpdate } from '../api/types';
import { fmtMoney, fmtDate, fmtDateLong } from '../utils/format';
import CatSwatch from '../components/primitives/CatSwatch';
import Segmented from '../components/primitives/Segmented';
import { InvoiceBody } from '../components/transactions/InvoiceDrawer';

export default function Review() {
  const queryClient = useQueryClient();
  const [sourceFilter, setSourceFilter] = useState('all');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState(false);
  const [showInvoice, setShowInvoice] = useState(false);

  const { data: txns, isLoading } = useQuery<Transaction[]>({
    queryKey: ['review', sourceFilter === 'all' ? undefined : sourceFilter],
    queryFn: () => api.reviewList(sourceFilter === 'all' ? undefined : sourceFilter),
    refetchOnMount: 'always',
    staleTime: 0,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['review'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    queryClient.invalidateQueries({ queryKey: ['timeline'] });
  };

  const { data: context, isFetching: ctxLoading } = useQuery<ReviewItem>({
    queryKey: ['review-context', selectedId],
    queryFn: () => api.reviewContext(selectedId!),
    enabled: !!selectedId,
    staleTime: 0,
  });

  // Prefetch so EditPanel dropdowns are instant
  useQuery({ queryKey: ['accounts'], queryFn: api.accounts });
  useQuery({ queryKey: ['categories'], queryFn: api.categories });
  const { data: budgets } = useQuery<Subscription[]>({ queryKey: ['budgets'], queryFn: api.budgets });

  const budgetNames = useMemo(() => {
    if (!budgets) return {} as Record<string, string>;
    return Object.fromEntries(budgets.filter(b => b.is_budget).map(b => [b.id, b.name]));
  }, [budgets]);

  const sources = useMemo(() => {
    if (!txns) return [];
    const s = new Set(txns.map(t => t.source).filter(Boolean));
    return Array.from(s) as string[];
  }, [txns]);

  const approveMut = useMutation({
    mutationFn: (id: number) => api.approveReview(id),
    onSuccess: () => {
      invalidateAll();
      if (selectedId && txns) {
        const idx = txns.findIndex(t => t.id === selectedId);
        const next = txns[idx + 1] || txns[idx - 1];
        setSelectedId(next?.id ?? null);
      }
      setEditing(false);
    },
  });

  const batchApproveMut = useMutation({
    mutationFn: (ids: number[]) => api.approveReviewBatch(ids),
    onSuccess: () => {
      invalidateAll();
      setChecked(new Set());
      setSelectedId(null);
      setEditing(false);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteTransaction(id),
    onSuccess: () => {
      invalidateAll();
      if (selectedId && txns) {
        const idx = txns.findIndex(t => t.id === selectedId);
        const next = txns[idx + 1] || txns[idx - 1];
        setSelectedId(next?.id ?? null);
      }
      setEditing(false);
    },
  });

  const batchDeleteMut = useMutation({
    mutationFn: (ids: number[]) => api.deleteReviewBatch(ids),
    onSuccess: () => {
      invalidateAll();
      setChecked(new Set());
      setSelectedId(null);
      setEditing(false);
    },
  });

  const toggleCheck = (id: number) => {
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!txns) return;
    if (checked.size === txns.length) setChecked(new Set());
    else setChecked(new Set(txns.map(t => t.id)));
  };

  const handleEditDone = () => {
    setEditing(false);
    invalidateAll();
    queryClient.invalidateQueries({ queryKey: ['review-context', selectedId] });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '14px 28px', borderBottom: '1px solid var(--border)',
        background: 'color-mix(in oklch, var(--bg) 92%, transparent)',
        backdropFilter: 'blur(8px)', position: 'sticky', top: 0, zIndex: 5, minHeight: 60,
      }}>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>Review Queue</span>
            {txns && txns.length > 0 && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
                background: 'var(--warn-soft)', color: 'var(--warn)',
              }}>{txns.length}</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            {txns ? `${txns.length} transactions to review` : 'Loading...'}
          </div>
        </div>

        {sources.length > 0 && (
          <Segmented value={sourceFilter} onChange={setSourceFilter} size="sm" options={[
            { value: 'all', label: 'All' },
            ...sources.map(s => ({ value: s, label: s })),
          ]} />
        )}

        {checked.size > 0 && (
          <>
            <button onClick={() => batchDeleteMut.mutate(Array.from(checked))} style={{
              padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: 'transparent', border: '1px solid var(--neg)',
              color: 'var(--neg)', cursor: 'pointer',
            }}>
              Delete {checked.size}
            </button>
            <button onClick={() => batchApproveMut.mutate(Array.from(checked))} style={{
              padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: 'var(--pos)', border: 'none', color: 'white', cursor: 'pointer',
            }}>
              Approve {checked.size}
            </button>
          </>
        )}
        {txns && txns.length > 0 && checked.size === 0 && (
          <button onClick={() => batchApproveMut.mutate(txns.map(t => t.id))} style={{
            padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: 'transparent', border: '1px solid var(--border)', color: 'var(--fg-muted)', cursor: 'pointer',
          }}>
            Approve all
          </button>
        )}
      </div>

      {/* Split view */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: transaction list */}
        <div style={{ flex: 1, overflow: 'auto', minWidth: 0 }}>
          {/* Column headers */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '36px 78px 1fr 110px 100px minmax(80px, 140px) 90px 48px',
            gap: 8, padding: '8px 20px', background: 'var(--bg-sunken)',
            borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 600,
            color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase',
          }}>
            <div style={{ display: 'grid', placeItems: 'center' }}>
              <input type="checkbox" checked={txns?.length ? checked.size === txns.length : false} onChange={toggleAll}
                style={{ cursor: 'pointer' }} />
            </div>
            <div>Date</div>
            <div>Description</div>
            <div>Account</div>
            <div>Category</div>
            <div>Budget</div>
            <div style={{ textAlign: 'right' }}>Amount</div>
            <div />
          </div>

          {isLoading && <div style={{ padding: 28, color: 'var(--fg-muted)' }}>Loading...</div>}

          {txns?.map(txn => (
            <ReviewRow
              key={txn.id}
              txn={txn}
              budgetName={txn.budget ? budgetNames[txn.budget] || txn.budget : null}
              selected={selectedId === txn.id}
              checked={checked.has(txn.id)}
              onCheck={() => toggleCheck(txn.id)}
              onClick={() => { setSelectedId(txn.id); setShowInvoice(false); setEditing(false); }}
              onApprove={() => approveMut.mutate(txn.id)}
            />
          ))}

          {txns && txns.length === 0 && !isLoading && (
            <div style={{
              padding: '80px 40px', textAlign: 'center',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: '50%',
                background: 'var(--pos-soft)', color: 'var(--pos)',
                display: 'grid', placeItems: 'center', fontSize: 28,
              }}>&#10003;</div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>All caught up</div>
              <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>No transactions need review</div>
            </div>
          )}
        </div>

        {/* Invoice pane (left of right panel) */}
        {showInvoice && context?.invoice && selectedId && (
          <div style={{
            width: 460, borderLeft: '1px solid var(--border)',
            overflow: 'auto', background: 'var(--bg-elev)',
            display: 'flex', flexDirection: 'column',
          }}>
            <header style={{
              padding: '14px 18px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg)',
              flexShrink: 0,
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7,
                background: 'var(--accent-soft)', color: 'var(--accent)',
                display: 'grid', placeItems: 'center', flexShrink: 0,
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
                  <line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/>
                </svg>
              </div>
              <div style={{ flex: 1, lineHeight: 1.2 }}>
                <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  Factura
                </div>
                <div className="num" style={{ fontSize: 13, fontWeight: 600 }}>
                  {context.invoice.invoice_number}
                </div>
              </div>
              <button onClick={() => setShowInvoice(false)} style={{
                width: 28, height: 28, borderRadius: 7,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--fg-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer',
              }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </header>
            <div style={{ flex: 1, overflow: 'auto', padding: '18px 18px 80px' }}>
              <InvoiceBody
                txn={{ ...context.transaction, is_budget_allocation: false, has_invoice: true }}
                invoice={context.invoice}
              />
            </div>
          </div>
        )}

        {/* Right panel: context or edit */}
        {selectedId && (
          <div style={{
            width: editing ? 420 : 380, borderLeft: '1px solid var(--border)',
            overflow: 'auto', background: 'var(--bg-elev)',
            display: 'flex', flexDirection: 'column',
          }}>
            {ctxLoading && <div style={{ padding: 28, color: 'var(--fg-muted)' }}>Loading context...</div>}
            {context && !editing && (
              <ContextPanel
                item={context}
                onApprove={() => approveMut.mutate(selectedId)}
                onDelete={() => deleteMut.mutate(selectedId)}
                onEdit={() => setEditing(true)}
                onViewInvoice={() => setShowInvoice(v => !v)}
                approving={approveMut.isPending}
                deleting={deleteMut.isPending}
              />
            )}
            {context && editing && (
              <EditPanel
                txn={context.transaction}
                onCancel={() => setEditing(false)}
                onSaved={handleEditDone}
                onApprove={() => approveMut.mutate(selectedId!)}
                onViewInvoice={() => setShowInvoice(v => !v)}
                hasInvoice={!!context.invoice}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Edit Panel (inline) ── */

function EditPanel({ txn, onCancel, onSaved, onApprove, onViewInvoice, hasInvoice }: {
  txn: Transaction;
  onCancel: () => void;
  onSaved: () => void;
  onApprove: () => void;
  onViewInvoice: () => void;
  hasInvoice: boolean;
}) {
  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  const { data: categories } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: api.categories });
  const { data: budgets } = useQuery<Subscription[]>({ queryKey: ['budgets'], queryFn: api.budgets });

  const [desc, setDesc] = useState(txn.description);
  const [amount, setAmount] = useState(String(Math.abs(txn.amount)));
  const [account, setAccount] = useState(txn.account);
  const [category, setCategory] = useState(txn.category || '');
  const [budget, setBudget] = useState(txn.budget || '');
  const [date, setDate] = useState(txn.date_created);
  const [approveAfterSave, setApproveAfterSave] = useState(false);
  const isIncome = txn.amount > 0;

  const filteredBudgets = useMemo(() => {
    if (!budgets) return [];
    return budgets.filter(b => b.is_budget);
  }, [budgets]);

  const updateMut = useMutation({
    mutationFn: (body: TransactionUpdate) => api.updateTransaction(txn.id, body),
    onSuccess: () => {
      if (approveAfterSave) {
        onApprove();
      } else {
        onSaved();
      }
    },
  });

  const buildUpdates = (): TransactionUpdate | null => {
    const updates: TransactionUpdate = {};
    if (desc !== txn.description) updates.description = desc;
    const newAmt = isIncome ? Math.abs(parseFloat(amount)) : -Math.abs(parseFloat(amount));
    if (newAmt !== txn.amount) updates.amount = newAmt;
    if (account !== txn.account) updates.account = account;
    if ((category || null) !== (txn.category || null)) updates.category = category || null;
    if ((budget || null) !== (txn.budget || null)) updates.budget = budget || null;
    if (date !== txn.date_created) updates.date = date;
    return Object.keys(updates).length > 0 ? updates : null;
  };

  const handleSave = () => {
    const updates = buildUpdates();
    if (!updates) { onCancel(); return; }
    setApproveAfterSave(false);
    updateMut.mutate(updates);
  };

  const handleSaveAndApprove = () => {
    const updates = buildUpdates();
    if (!updates) { onApprove(); return; }
    setApproveAfterSave(true);
    updateMut.mutate(updates);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: '18px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <CatSwatch cat={category || txn.category} size={32} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Editing #{txn.id}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{txn.description}</div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Field label="Description">
            <input value={desc} onChange={e => setDesc(e.target.value)} style={inputStyle} />
          </Field>
          <Field label="Amount ($)">
            <input value={amount} onChange={e => setAmount(e.target.value)} type="number" step="0.01" style={inputStyle} />
          </Field>
          <Field label="Account">
            <select value={account} onChange={e => setAccount(e.target.value)} style={inputStyle}>
              {accounts?.map(a => <option key={a.account_id} value={a.account_id}>{a.account_id}</option>)}
            </select>
          </Field>
          <Field label="Category">
            <select value={category} onChange={e => setCategory(e.target.value)} style={inputStyle}>
              <option value="">None</option>
              {categories?.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="Budget">
            <select value={budget} onChange={e => setBudget(e.target.value)} style={inputStyle}>
              <option value="">None</option>
              {filteredBudgets.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </Field>
          <Field label="Date">
            <input value={date} onChange={e => setDate(e.target.value)} type="date" style={inputStyle} />
          </Field>
        </div>

        {hasInvoice && (
          <button onClick={onViewInvoice} style={{
            marginTop: 14, width: '100%', padding: '8px 0', borderRadius: 8,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--fg-muted)', fontSize: 12, fontWeight: 550, cursor: 'pointer',
          }}>View invoice</button>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '14px 16px', borderTop: '1px solid var(--border)',
        display: 'flex', gap: 8, background: 'var(--bg-elev)',
      }}>
        {updateMut.error && <span style={{ fontSize: 12, color: 'var(--neg)', flex: 1 }}>{updateMut.error.message}</span>}
        <button onClick={onCancel} style={{
          padding: '8px 12px', borderRadius: 8, fontSize: 13, fontWeight: 550,
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--fg-muted)', cursor: 'pointer',
        }}>Cancel</button>
        <button onClick={handleSave} disabled={updateMut.isPending} style={{
          flex: 1, padding: '8px 0', borderRadius: 8, fontSize: 13, fontWeight: 600,
          background: 'transparent', border: '1px solid var(--accent)',
          color: 'var(--accent)', cursor: 'pointer',
          opacity: updateMut.isPending ? 0.6 : 1,
        }}>Save</button>
        <button onClick={handleSaveAndApprove} disabled={updateMut.isPending} style={{
          flex: 1, padding: '8px 0', borderRadius: 8, fontSize: 13, fontWeight: 600,
          background: 'var(--pos)', border: 'none', color: 'white', cursor: 'pointer',
          opacity: updateMut.isPending ? 0.6 : 1,
        }}>
          {updateMut.isPending && approveAfterSave ? 'Saving...' : 'Save & Approve'}
        </button>
      </div>
    </div>
  );
}

/* ── Review Row ── */

function ReviewRow({ txn, budgetName, selected, checked, onCheck, onClick, onApprove }: {
  txn: Transaction;
  budgetName: string | null;
  selected: boolean;
  checked: boolean;
  onCheck: () => void;
  onClick: () => void;
  onApprove: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '36px 78px 1fr 110px 100px minmax(80px, 140px) 90px 48px',
        gap: 8, padding: '9px 20px',
        background: selected ? 'var(--bg-hover)' : 'transparent',
        borderTop: '1px solid var(--border)',
        cursor: 'pointer', alignItems: 'center', fontSize: 13,
      }}
    >
      <div style={{ display: 'grid', placeItems: 'center' }} onClick={e => e.stopPropagation()}>
        <input type="checkbox" checked={checked} onChange={onCheck} style={{ cursor: 'pointer' }} />
      </div>

      <div className="num" style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
        {fmtDate(txn.date_created)}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <CatSwatch cat={txn.category} size={24} />
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}>
          {txn.description}
        </span>
        {txn.source && (
          <SourcePill source={txn.source} />
        )}
      </div>

      <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{txn.account}</span>
      <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{txn.category || ''}</span>

      <span style={{
        fontSize: 11, color: budgetName ? 'var(--accent)' : 'var(--fg-faint)',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        fontWeight: budgetName ? 550 : 400,
      }}>
        {budgetName || '—'}
      </span>

      <span className="num" style={{ textAlign: 'right', fontWeight: 600, color: txn.amount > 0 ? 'var(--pos)' : 'var(--fg)' }}>
        {fmtMoney(txn.amount)}
      </span>

      <div style={{ display: 'grid', placeItems: 'center' }} onClick={e => e.stopPropagation()}>
        <button onClick={onApprove} title="Approve" style={{
          width: 28, height: 28, borderRadius: 6,
          background: 'var(--pos-soft)', border: '1px solid color-mix(in oklch, var(--pos) 25%, var(--border))',
          color: 'var(--pos)', cursor: 'pointer', display: 'grid', placeItems: 'center', fontSize: 14,
        }}>&#10003;</button>
      </div>
    </div>
  );
}

/* ── Source Pill ── */

const SOURCE_COLORS: Record<string, string> = {
  gmail: 'oklch(0.65 0.18 25)',
  telegram: 'oklch(0.62 0.15 230)',
};

function SourcePill({ source }: { source: string }) {
  const color = SOURCE_COLORS[source] || 'var(--fg-muted)';
  return (
    <span style={{
      fontSize: 9.5, fontWeight: 700, letterSpacing: '0.04em',
      padding: '1px 6px', borderRadius: 4, flexShrink: 0,
      background: `color-mix(in oklch, ${color} 12%, transparent)`,
      color,
    }}>
      {source.toUpperCase()}
    </span>
  );
}

/* ── Context Panel ── */

function ContextPanel({ item, onApprove, onDelete, onEdit, onViewInvoice, approving, deleting }: {
  item: ReviewItem;
  onApprove: () => void;
  onDelete: () => void;
  onEdit: () => void;
  onViewInvoice: () => void;
  approving: boolean;
  deleting: boolean;
}) {
  const { transaction: txn, consumo, invoice, llm_decision } = item;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: '20px 18px' }}>
        {/* Transaction header */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <CatSwatch cat={txn.category} size={36} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{txn.description}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
                {fmtDateLong(txn.date_created)}
                {txn.date_created !== txn.date_payed && ` · pays ${fmtDate(txn.date_payed)}`}
              </div>
            </div>
            <div className="num" style={{ fontSize: 22, fontWeight: 600, color: txn.amount > 0 ? 'var(--pos)' : 'var(--fg)' }}>
              {fmtMoney(txn.amount)}
            </div>
          </div>
        </div>

        {/* Fields */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
          <Block label="Account" value={txn.account || '—'} />
          <Block label="Category" value={txn.category || '—'} />
          <Block label="Budget" value={txn.budget || '—'} />
          <Block label="Status" value={txn.status} />
          {txn.source && <Block label="Source" value={txn.source} />}
        </div>

        {/* Consumo card */}
        {consumo && (
          <ContextCard title="Card Transaction" icon="💳">
            <Row k="Merchant" v={consumo.merchant} />
            <Row k="Bank" v={consumo.bank} />
            <Row k="Card" v={consumo.card_last ? `···${consumo.card_last}` : '—'} />
            <Row k="Date" v={fmtDateLong(consumo.purchased_at)} />
            <Row k="Amount" v={fmtMoney(consumo.amount)} highlight={consumo.amount !== Math.abs(txn.amount)} />
            {consumo.matched_invoice_number && (
              <Row k="Invoice #" v={consumo.matched_invoice_number} />
            )}
          </ContextCard>
        )}

        {/* Invoice card */}
        {invoice && (
          <ContextCard title="Invoice" icon="🧾">
            <Row k="Vendor" v={invoice.vendor_trade_name || invoice.vendor} />
            <Row k="Invoice #" v={invoice.invoice_number} />
            <Row k="Date" v={fmtDateLong(invoice.issue_date)} />
            <Row k="Total" v={`$${invoice.total.toFixed(2)}`} />
            {invoice.forma_pago != null && <Row k="Payment method" v={String(invoice.forma_pago)} />}
            <button onClick={onViewInvoice} style={{
              marginTop: 8, width: '100%', padding: '6px 0', borderRadius: 6,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--fg-muted)', fontSize: 12, fontWeight: 550, cursor: 'pointer',
            }}>View full invoice</button>
          </ContextCard>
        )}

        {/* LLM Decision card */}
        {llm_decision && (
          <ContextCard title="AI Classification" icon="🤖">
            {!!llm_decision.category && <Row k="Category" v={String(llm_decision.category)} />}
            {!!llm_decision.budget && <Row k="Budget" v={String(llm_decision.budget)} />}
            {!!llm_decision.response && (
              <div style={{
                marginTop: 6, padding: '8px 10px', borderRadius: 6,
                background: 'var(--bg-sunken)', fontSize: 11.5, lineHeight: 1.5,
                color: 'var(--fg-muted)', fontFamily: 'monospace', whiteSpace: 'pre-wrap',
                maxHeight: 120, overflow: 'auto',
              }}>
                {String(llm_decision.response)}
              </div>
            )}
          </ContextCard>
        )}

        {/* No context */}
        {!consumo && !invoice && !llm_decision && (
          <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--fg-faint)', fontSize: 13 }}>
            No additional context available
          </div>
        )}
      </div>

      {/* Actions footer */}
      <div style={{
        padding: '14px 18px', borderTop: '1px solid var(--border)',
        display: 'flex', gap: 8, background: 'var(--bg-elev)',
      }}>
        <button onClick={onDelete} disabled={deleting} style={{
          padding: '8px 12px', borderRadius: 8, fontSize: 13, fontWeight: 550,
          background: 'transparent', border: '1px solid var(--neg)',
          color: 'var(--neg)', cursor: 'pointer',
          opacity: deleting ? 0.6 : 1,
        }}>
          {deleting ? '...' : 'Delete'}
        </button>
        <button onClick={onEdit} style={{
          flex: 1, padding: '8px 0', borderRadius: 8, fontSize: 13, fontWeight: 550,
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--fg-muted)', cursor: 'pointer',
        }}>Edit</button>
        <button onClick={onApprove} disabled={approving} style={{
          flex: 2, padding: '8px 0', borderRadius: 8, fontSize: 13, fontWeight: 600,
          background: 'var(--pos)', border: 'none', color: 'white', cursor: 'pointer',
          opacity: approving ? 0.6 : 1,
        }}>
          {approving ? 'Approving...' : 'Approve'}
        </button>
      </div>
    </div>
  );
}

/* ── Small UI helpers ── */

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--fg-faint)', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 550 }}>{value}</div>
    </div>
  );
}

function ContextCard({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div style={{
      marginBottom: 12, border: '1px solid var(--border)', borderRadius: 10,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 12px', background: 'var(--bg-sunken)',
        fontSize: 11.5, fontWeight: 600, color: 'var(--fg-muted)',
        letterSpacing: '0.03em', display: 'flex', alignItems: 'center', gap: 6,
        borderBottom: '1px solid var(--border)',
      }}>
        <span>{icon}</span> {title}
      </div>
      <div style={{ padding: '10px 12px' }}>{children}</div>
    </div>
  );
}

function Row({ k, v, highlight }: { k: string; v: string; highlight?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 12.5 }}>
      <span style={{ color: 'var(--fg-muted)' }}>{k}</span>
      <span style={{
        fontWeight: 550,
        color: highlight ? 'var(--warn)' : 'var(--fg)',
      }}>{v}</span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600, marginBottom: 5 }}>{label}</div>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8,
  background: 'var(--bg-elev)', color: 'var(--fg)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
  boxSizing: 'border-box',
};

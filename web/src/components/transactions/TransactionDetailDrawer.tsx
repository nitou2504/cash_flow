import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { TimelineTransaction, Transaction, TransactionUpdate, Account, Category, Subscription, BudgetSpending } from '../../api/types';
import { fmtMoney, fmtDate, fmtDateLong } from '../../utils/format';
import CatSwatch from '../primitives/CatSwatch';
import Segmented from '../primitives/Segmented';

interface Props {
  txn: TimelineTransaction;
  onClose: () => void;
  onViewInvoice?: () => void;
}

export default function TransactionDetailDrawer({ txn, onClose, onViewInvoice }: Props) {
  const [editing, setEditing] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const { data: group } = useQuery<Transaction[]>({
    queryKey: ['transaction-group', txn.id],
    queryFn: () => api.transactionGroup(txn.id),
    enabled: !!txn.origin_id,
  });

  const isGroup = group && group.length > 1;

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
        {/* Header */}
        <header style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 12, background: 'var(--bg)',
        }}>
          <CatSwatch cat={txn.category} size={32} />
          <div style={{ flex: 1, lineHeight: 1.2, minWidth: 0 }}>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Transaction #{txn.id}
            </div>
            <div style={{ fontSize: 14.5, fontWeight: 600, letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {txn.description}
            </div>
          </div>
          <div className="num" style={{
            fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em',
            color: txn.amount > 0 ? 'var(--pos)' : 'var(--fg)',
          }}>
            {fmtMoney(txn.amount)}
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
        </header>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '18px 20px 100px' }}>
          {editing
            ? <EditMode txn={txn} queryClient={queryClient} onClose={onClose} onCancel={() => setEditing(false)} />
            : <ViewMode txn={txn} group={group || null} isGroup={!!isGroup} onEdit={() => setEditing(true)} onClose={onClose} onViewInvoice={onViewInvoice} queryClient={queryClient} />
          }
        </div>
      </aside>
    </div>
  );
}


function ViewMode({ txn, group, isGroup, onEdit, onClose, onViewInvoice, queryClient }: {
  txn: TimelineTransaction;
  group: Transaction[] | null;
  isGroup: boolean;
  onEdit: () => void;
  onClose: () => void;
  onViewInvoice?: () => void;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteGroup, setDeleteGroup] = useState(false);

  const deleteMut = useMutation({
    mutationFn: () => api.deleteTransaction(txn.id, deleteGroup),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
    },
  });

  const clearMut = useMutation({
    mutationFn: () => api.clearTransaction(txn.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
    },
  });

  const canClear = txn.status === 'pending' || txn.status === 'planning';

  return (
    <>
      {/* Detail fields */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
        <Block label="Purchase date">
          <div style={{ fontSize: 13, fontWeight: 550 }}>{fmtDateLong(txn.date_created)}</div>
        </Block>
        <Block label="Payment date">
          <div style={{ fontSize: 13, fontWeight: 550 }}>{fmtDateLong(txn.date_payed)}</div>
        </Block>
        <Block label="Account">
          <div style={{ fontSize: 13, fontWeight: 550 }}>{txn.account}</div>
        </Block>
        <Block label="Category">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <CatSwatch cat={txn.category} size={16} />
            <span style={{ fontSize: 13, fontWeight: 550 }}>{txn.category || 'None'}</span>
          </div>
        </Block>
        <Block label="Budget">
          <div style={{ fontSize: 13, fontWeight: 550 }}>{txn.budget || 'None'}</div>
        </Block>
        <Block label="Status">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <StatusPill status={txn.status} />
            {canClear && (
              <button
                onClick={() => clearMut.mutate()}
                disabled={clearMut.isPending}
                style={{
                  padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  background: 'var(--pos-soft)', border: '1px solid color-mix(in oklch, var(--pos) 30%, var(--border))',
                  color: 'var(--pos)', cursor: 'pointer',
                }}
              >
                {clearMut.isPending ? 'Committing...' : `Commit as confirmed`}
              </button>
            )}
          </div>
        </Block>
      </div>

      {txn.source && (
        <Block label="Source">
          <div style={{ fontSize: 13, fontWeight: 550 }}>{txn.source}</div>
        </Block>
      )}

      {/* Invoice */}
      {txn.has_invoice && onViewInvoice && (
        <button
          onClick={onViewInvoice}
          style={{
            width: '100%', padding: '10px 14px', marginBottom: 16,
            background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 10,
            display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
            fontSize: 13, fontWeight: 550, color: 'var(--fg)',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
            <line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/>
          </svg>
          View linked invoice
        </button>
      )}

      {/* Installment group */}
      {isGroup && group && (
        <>
          <SectionLabel>Installment group &middot; {group.length} payments</SectionLabel>
          <div style={{
            border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden',
            background: 'var(--bg-elev)', marginBottom: 18,
          }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '50px 1fr 90px 90px',
              gap: 8, padding: '8px 14px', fontSize: 10.5, fontWeight: 600,
              color: 'var(--fg-faint)', letterSpacing: '0.05em', textTransform: 'uppercase',
              background: 'var(--bg-sunken)', borderBottom: '1px solid var(--border)',
            }}>
              <div>#</div><div>Description</div><div style={{ textAlign: 'right' }}>Date</div><div style={{ textAlign: 'right' }}>Amount</div>
            </div>
            {group.map((g, i) => (
              <div key={g.id} style={{
                display: 'grid', gridTemplateColumns: '50px 1fr 90px 90px',
                gap: 8, padding: '8px 14px', fontSize: 12.5,
                borderTop: i === 0 ? 'none' : '1px solid var(--border)',
                background: g.id === txn.id ? 'var(--bg-hover)' : 'transparent',
              }}>
                <div className="num" style={{ color: 'var(--fg-faint)' }}>{i + 1}/{group.length}</div>
                <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.description}</div>
                <div className="num" style={{ textAlign: 'right', color: 'var(--fg-muted)' }}>{fmtDate(g.date_payed)}</div>
                <div className="num" style={{ textAlign: 'right', fontWeight: 600 }}>{fmtMoney(g.amount)}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Action bar */}
      <div style={{
        position: 'sticky', bottom: 0, margin: '0 -20px', padding: '14px 20px',
        borderTop: '1px solid var(--border)', background: 'var(--bg)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        {deleteMut.error && <span style={{ fontSize: 12, color: 'var(--neg)', flex: 1 }}>{deleteMut.error.message}</span>}
        {clearMut.error && <span style={{ fontSize: 12, color: 'var(--neg)', flex: 1 }}>{clearMut.error.message}</span>}

        {confirmDelete ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
            <span style={{ fontSize: 12.5, color: 'var(--neg)', fontWeight: 550 }}>Delete?</span>
            {isGroup && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-muted)', cursor: 'pointer' }}>
                <input type="checkbox" checked={deleteGroup} onChange={e => setDeleteGroup(e.target.checked)} style={{ accentColor: 'var(--neg)' }} />
                All {group?.length} in group
              </label>
            )}
            <span style={{ flex: 1 }} />
            <button onClick={() => setConfirmDelete(false)} style={ghostBtnStyle}>Cancel</button>
            <button
              onClick={() => deleteMut.mutate()}
              disabled={deleteMut.isPending}
              style={{ ...ghostBtnStyle, color: 'var(--neg)', borderColor: 'color-mix(in oklch, var(--neg) 30%, var(--border))' }}
            >
              {deleteMut.isPending ? 'Deleting...' : 'Confirm delete'}
            </button>
          </div>
        ) : (
          <>
            <button onClick={() => setConfirmDelete(true)} style={{ ...ghostBtnStyle, color: 'var(--neg)' }}>
              Delete
            </button>
            <span style={{ flex: 1 }} />
            <button onClick={onEdit} style={{
              padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: 'var(--accent)', border: 'none', color: 'white', cursor: 'pointer',
            }}>
              Edit
            </button>
          </>
        )}
      </div>
    </>
  );
}


function EditMode({ txn, queryClient, onClose, onCancel }: {
  txn: TimelineTransaction;
  queryClient: ReturnType<typeof useQueryClient>;
  onClose: () => void;
  onCancel: () => void;
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
  const [status, setStatus] = useState(txn.status);
  const isIncome = txn.amount > 0;

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

  const updateMut = useMutation({
    mutationFn: (body: TransactionUpdate) => api.updateTransaction(txn.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      onClose();
    },
  });

  const handleSave = () => {
    const updates: TransactionUpdate = {};
    if (desc !== txn.description) updates.description = desc;
    const newAmt = isIncome ? Math.abs(parseFloat(amount)) : -Math.abs(parseFloat(amount));
    if (newAmt !== txn.amount) updates.amount = newAmt;
    if (account !== txn.account) updates.account = account;
    if ((category || null) !== (txn.category || null)) updates.category = category || null;
    if ((budget || null) !== (txn.budget || null)) updates.budget = budget || null;
    if (date !== txn.date_created) updates.date = date;
    if (status !== txn.status) updates.status = status;

    if (Object.keys(updates).length === 0) { onCancel(); return; }
    updateMut.mutate(updates);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSave();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        <FormField label="Description" full>
          <input value={desc} onChange={e => setDesc(e.target.value)} style={inputStyle} />
        </FormField>
        <FormField label="Amount ($)">
          <input value={amount} onChange={e => setAmount(e.target.value)} type="number" step="0.01" style={inputStyle} />
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

      {selectedBudgetInfo && (
        <div style={{
          background: 'var(--info-soft)', border: '1px solid color-mix(in oklch, var(--info) 25%, var(--border))',
          borderRadius: 10, padding: '10px 14px', marginBottom: 14, fontSize: 12.5, color: 'var(--info)',
        }}>
          <strong>{selectedBudgetInfo.name}</strong>: <span className="num">{fmtMoney(-selectedBudgetInfo.remaining)}</span> remaining
        </div>
      )}

      {/* Footer */}
      <div style={{
        position: 'sticky', bottom: 0, margin: '0 -20px', padding: '14px 20px',
        borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8,
        background: 'var(--bg)',
      }}>
        {updateMut.error && <span style={{ fontSize: 12, color: 'var(--neg)', flex: 1 }}>{updateMut.error.message}</span>}
        <span style={{ flex: updateMut.error ? 0 : 1 }} />
        <button onClick={onCancel} style={ghostBtnStyle}>Cancel</button>
        <button onClick={handleSave} disabled={updateMut.isPending} style={{
          padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
          background: 'var(--accent)', border: 'none', color: 'white', cursor: 'pointer',
          opacity: updateMut.isPending ? 0.6 : 1,
        }}>
          {updateMut.isPending ? 'Saving...' : 'Save changes'}
          {!updateMut.isPending && <span style={{ marginLeft: 8, opacity: 0.7, fontSize: 11 }}>&#8984;&#8629;</span>}
        </button>
      </div>
    </>
  );
}


function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 12,
      padding: '10px 12px', background: 'var(--bg-elev)',
    }}>
      <div style={{
        fontSize: 10.5, fontWeight: 600, color: 'var(--fg-faint)',
        letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6,
      }}>{label}</div>
      {children}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, color: 'var(--fg-muted)',
      letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8,
    }}>{children}</div>
  );
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    committed: { bg: 'var(--pos-soft)', color: 'var(--pos)' },
    pending: { bg: 'var(--warn-soft)', color: 'var(--warn)' },
    planning: { bg: 'color-mix(in oklch, oklch(0.58 0.16 290) 12%, transparent)', color: 'oklch(0.58 0.16 290)' },
    forecast: { bg: 'var(--bg-sunken)', color: 'var(--fg-faint)' },
  };
  const s = styles[status] || styles.committed;
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
      padding: '2px 8px', borderRadius: 5, background: s.bg, color: s.color,
    }}>
      {status}
    </span>
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

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8,
  background: 'var(--bg-elev)', color: 'var(--fg)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
  boxSizing: 'border-box',
};

const ghostBtnStyle: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 550,
  background: 'transparent', border: '1px solid var(--border)', color: 'var(--fg-muted)', cursor: 'pointer',
};

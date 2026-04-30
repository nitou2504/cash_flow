import { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { TimelineTransaction, Transaction, TransactionCreate, TransactionUpdate, Account, Category, Subscription, BudgetSpending, ReviewItem } from '../../api/types';
import { fmtMoney, fmtDate, fmtDateLong } from '../../utils/format';
import CatSwatch from '../primitives/CatSwatch';
import Segmented from '../primitives/Segmented';
import { NumberStepper } from './AddTransactionPanel';
import { InvoiceBody } from './InvoiceDrawer';

interface Props {
  txn: TimelineTransaction;
  onClose: () => void;
  initialEdit?: boolean;
  initialShowInvoice?: boolean;
}

export default function TransactionDetailDrawer({ txn, onClose, initialEdit, initialShowInvoice }: Props) {
  const [editing, setEditing] = useState(!!initialEdit);
  const [showInvoice, setShowInvoice] = useState(!!initialShowInvoice);
  const queryClient = useQueryClient();
  const [footerEl, setFooterEl] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showInvoice) setShowInvoice(false);
        else onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, showInvoice]);

  const { data: group } = useQuery<Transaction[]>({
    queryKey: ['transaction-group', txn.id],
    queryFn: () => api.transactionGroup(txn.id),
    enabled: !!txn.origin_id,
  });

  const { data: context } = useQuery<ReviewItem>({
    queryKey: ['review-context', txn.id],
    queryFn: () => api.reviewContext(txn.id),
  });

  const fullInvoice = context?.invoice || null;

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
      {/* Invoice side pane */}
      {showInvoice && (
        <aside
          onClick={e => e.stopPropagation()}
          style={{
            width: 500, maxWidth: '45vw', height: '100%',
            background: 'var(--bg-elev)', borderLeft: '1px solid var(--border)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}
        >
          <header style={{
            padding: '14px 20px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', gap: 12, background: 'var(--bg)',
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'var(--accent-soft)', color: 'var(--accent)',
              display: 'grid', placeItems: 'center', flexShrink: 0,
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
                <line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/>
              </svg>
            </div>
            <div style={{ flex: 1, lineHeight: 1.2, minWidth: 0 }}>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                Factura electr&oacute;nica
              </div>
              <div className="num" style={{ fontSize: 14.5, fontWeight: 600, letterSpacing: '-0.01em' }}>
                {fullInvoice?.invoice_number ?? context?.invoice?.invoice_number ?? '...'}
              </div>
            </div>
            <button onClick={() => setShowInvoice(false)} style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--fg-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </header>
          <div style={{ flex: 1, overflow: 'auto', padding: '18px 20px 100px' }}>
            {!fullInvoice && <div style={{ padding: 20, color: 'var(--fg-muted)' }}>Loading...</div>}
            {fullInvoice && <InvoiceBody txn={txn} invoice={fullInvoice} />}
          </div>
        </aside>
      )}

      {/* Transaction drawer */}
      <aside
        onClick={e => e.stopPropagation()}
        style={{
          width: 540, maxWidth: showInvoice ? '50vw' : '90%', height: '100%',
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
        <div style={{ flex: 1, overflow: 'auto', padding: '18px 20px 20px' }}>
          {editing
            ? <EditMode txn={txn} group={group || null} context={context || null} queryClient={queryClient} onClose={onClose} onCancel={initialEdit ? onClose : () => setEditing(false)} onViewInvoice={() => setShowInvoice(true)} footerContainer={footerEl} />
            : <ViewMode txn={txn} group={group || null} isGroup={!!isGroup} context={context || null} onEdit={() => setEditing(true)} onClose={onClose} onViewInvoice={() => setShowInvoice(true)} queryClient={queryClient} footerContainer={footerEl} />
          }
        </div>
        <div ref={setFooterEl} />
      </aside>
    </div>
  );
}


function ViewMode({ txn, group, isGroup, context, onEdit, onClose, onViewInvoice, queryClient, footerContainer }: {
  txn: TimelineTransaction;
  group: Transaction[] | null;
  isGroup: boolean;
  context: ReviewItem | null;
  onEdit: () => void;
  onClose: () => void;
  onViewInvoice: () => void;
  queryClient: ReturnType<typeof useQueryClient>;
  footerContainer?: HTMLDivElement | null;
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

  const { consumo, invoice, llm_decision } = context || {};

  return (
    <>
      {/* Detail fields */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
        <InfoBlock label="Purchase date" value={fmtDateLong(txn.date_created)} />
        <InfoBlock label="Payment date" value={fmtDateLong(txn.date_payed)} />
        <InfoBlock label="Account" value={txn.account} />
        <InfoBlock label="Category" value={txn.category || '—'} />
        <InfoBlock label="Budget" value={txn.budget || '—'} />
        <InfoBlock label="Status">
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
                {clearMut.isPending ? 'Committing...' : 'Commit'}
              </button>
            )}
          </div>
        </InfoBlock>
        {txn.source && <InfoBlock label="Source" value={txn.source} />}
      </div>

      {/* Context cards */}
      {consumo && (
        <ContextCard title="Card Transaction" icon="💳">
          <CtxRow k="Merchant" v={consumo.merchant} />
          <CtxRow k="Bank" v={consumo.bank} />
          <CtxRow k="Card" v={consumo.card_last ? `···${consumo.card_last}` : '—'} />
          <CtxRow k="Date" v={fmtDateLong(consumo.purchased_at)} />
          <CtxRow k="Amount" v={fmtMoney(consumo.amount)} highlight={consumo.amount !== Math.abs(txn.amount)} />
          {consumo.matched_invoice_number && <CtxRow k="Invoice #" v={consumo.matched_invoice_number} />}
        </ContextCard>
      )}

      {invoice && (
        <ContextCard title="Invoice" icon="🧾">
          <CtxRow k="Vendor" v={invoice.vendor_trade_name || invoice.vendor} />
          <CtxRow k="Invoice #" v={invoice.invoice_number} />
          <CtxRow k="Date" v={fmtDateLong(invoice.issue_date)} />
          <CtxRow k="Total" v={`$${invoice.total.toFixed(2)}`} />
          {invoice.forma_pago != null && <CtxRow k="Payment" v={String(invoice.forma_pago)} />}
          <button onClick={onViewInvoice} style={{
            marginTop: 8, width: '100%', padding: '6px 0', borderRadius: 6,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--fg-muted)', fontSize: 12, fontWeight: 550, cursor: 'pointer',
          }}>View full invoice</button>
        </ContextCard>
      )}

      {!invoice && txn.has_invoice && (
        <button onClick={onViewInvoice} style={{
          width: '100%', padding: '10px 14px', marginBottom: 12,
          background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 10,
          display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
          fontSize: 13, fontWeight: 550, color: 'var(--fg)',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
            <line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/>
          </svg>
          View linked invoice
        </button>
      )}

      {llm_decision && (
        <ContextCard title="AI Classification" icon="🤖">
          {!!llm_decision.category && <CtxRow k="Category" v={String(llm_decision.category)} />}
          {!!llm_decision.budget && <CtxRow k="Budget" v={String(llm_decision.budget)} />}
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

      {footerContainer && createPortal(
        <div style={{
          padding: '14px 20px',
          borderTop: '1px solid var(--border)', background: 'var(--bg-elev)',
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
        </div>,
        footerContainer,
      )}
    </>
  );
}


function EditMode({ txn, group, context, queryClient, onClose, onCancel, onViewInvoice, footerContainer }: {
  txn: TimelineTransaction;
  group: Transaction[] | null;
  context: ReviewItem | null;
  queryClient: ReturnType<typeof useQueryClient>;
  onClose: () => void;
  onCancel: () => void;
  onViewInvoice: () => void;
  footerContainer?: HTMLDivElement | null;
}) {
  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  const { data: categories } = useQuery<Category[]>({ queryKey: ['categories'], queryFn: api.categories });
  const { data: budgets } = useQuery<Subscription[]>({ queryKey: ['budgets'], queryFn: api.budgets });

  const isGrouped = group && group.length > 1;
  const origIsInstallment = isGrouped && new Set(group!.map(g => g.date_payed)).size > 1;
  const origIsSplit = isGrouped && new Set(group!.map(g => g.date_payed)).size === 1;

  const groupTotal = isGrouped ? group!.reduce((s, g) => s + Math.abs(g.amount), 0) : Math.abs(txn.amount);
  const baseDesc = isGrouped ? group![0].description.replace(/\s*\(\d+\/\d+\)(\s*-\s*.*)?$/, '') : txn.description;

  const [desc, setDesc] = useState(baseDesc);
  const [amount, setAmount] = useState(String(groupTotal));
  const [account, setAccount] = useState(txn.account);
  const [category, setCategory] = useState(txn.category || '');
  const [budget, setBudget] = useState(txn.budget || '');
  const [date, setDate] = useState(txn.date_created);
  const [status, setStatus] = useState(txn.status);
  const isIncome = txn.amount > 0;

  const [enableInstallments, setEnableInstallments] = useState(!!origIsInstallment);
  const [installments, setInstallments] = useState(origIsInstallment ? group!.length : 3);
  const [gracePeriod, setGracePeriod] = useState(0);
  const [startFrom, setStartFrom] = useState(1);

  const [enableSplit, setEnableSplit] = useState(!!origIsSplit);
  const [splits, setSplits] = useState(() => {
    if (origIsSplit && group) {
      return group.map(g => ({
        amount: String(Math.abs(g.amount)),
        category: g.category || '',
        budget: g.budget || '',
      }));
    }
    return [{ amount: '', category: '', budget: '' }];
  });

  const [showPreview, setShowPreview] = useState(false);
  const [preview, setPreview] = useState<Transaction[] | null>(null);

  const filteredBudgets = useMemo(() => {
    if (!budgets) return [];
    return budgets.filter(b => b.is_budget && (!account || b.payment_account_id === account));
  }, [budgets, account]);

  const budgetMonth = date ? date.slice(0, 7) : undefined;
  const { data: budgetSpending } = useQuery<BudgetSpending[]>({
    queryKey: ['budget-spending', budgetMonth],
    queryFn: () => api.budgetSpending(budgetMonth),
    enabled: !!budget && !!budgetMonth && !enableSplit,
  });
  const selectedBudgetInfo = budgetSpending?.find(b => b.id === budget);

  const typeChanged = enableInstallments !== !!origIsInstallment || enableSplit !== !!origIsSplit;

  const updateMut = useMutation({
    mutationFn: (body: TransactionUpdate) => api.updateTransaction(txn.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['transaction-group'] });
      onClose();
    },
  });

  const convertMut = useMutation({
    mutationFn: (body: TransactionCreate) => api.convertTransaction(txn.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['transaction-group'] });
      onClose();
    },
  });

  const previewMut = useMutation({
    mutationFn: (body: TransactionCreate) => api.previewTransaction(body),
    onSuccess: (data) => setPreview(data),
  });

  const buildConvertBody = (): TransactionCreate => {
    const amt = parseFloat(amount);
    const body: TransactionCreate = {
      description: desc,
      amount: isIncome ? Math.abs(amt) : -Math.abs(amt),
      account,
      date: date || undefined,
      is_income: isIncome,
      status,
    };

    if (enableSplit) {
      body.splits = splits.filter(s => parseFloat(s.amount)).map(s => ({
        amount: -Math.abs(parseFloat(s.amount)),
        category: s.category || undefined,
        budget: s.budget || undefined,
      }));
    } else {
      body.category = category || undefined;
      body.budget = budget || undefined;
    }

    if (enableInstallments) {
      body.installments = installments;
      body.grace_period_months = gracePeriod;
      body.start_from_installment = startFrom;
    }

    return body;
  };

  const handleSave = () => {
    if (typeChanged) {
      convertMut.mutate(buildConvertBody());
      return;
    }

    const updates: TransactionUpdate = {};
    if (desc !== baseDesc) updates.description = desc;
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
    if (!showPreview || !enableInstallments) { setPreview(null); return; }
    const body = buildConvertBody();
    if (body) previewMut.mutate(body);
  }, [showPreview, enableInstallments, desc, amount, account, date, installments, gracePeriod, startFrom, enableSplit, splits, category, budget, status]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSave();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const addSplit = () => setSplits([...splits, { amount: '', category: '', budget: '' }]);
  const removeSplit = (i: number) => setSplits(splits.filter((_, idx) => idx !== i));
  const updateSplit = (i: number, field: string, value: string) => {
    const next = [...splits];
    next[i] = { ...next[i], [field]: value };
    setSplits(next);
  };
  const splitSum = splits.reduce((s, sp) => s + (parseFloat(sp.amount) || 0), 0);
  const total = parseFloat(amount) || 0;
  const actualPayments = installments - startFrom + 1;
  const perInstallment = total && installments ? (total / installments) : 0;

  const saving = updateMut.isPending || convertMut.isPending;
  const error = updateMut.error?.message || convertMut.error?.message;

  const { consumo, invoice, llm_decision } = context || {};

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        <FormField label="Description" full>
          <input value={desc} onChange={e => setDesc(e.target.value)} style={inputStyle} />
        </FormField>
        <FormField label={enableInstallments ? 'Total amount ($)' : 'Amount ($)'}>
          <input value={amount} onChange={e => setAmount(e.target.value)} type="number" step="0.01" style={inputStyle} />
        </FormField>
        <FormField label="Account">
          <select value={account} onChange={e => setAccount(e.target.value)} style={inputStyle}>
            {accounts?.map(a => <option key={a.account_id} value={a.account_id}>{a.account_id}</option>)}
          </select>
        </FormField>
        {!enableSplit && (
          <FormField label="Category">
            <select value={category} onChange={e => setCategory(e.target.value)} style={inputStyle}>
              <option value="">None</option>
              {categories?.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
          </FormField>
        )}
        {!enableSplit && (
          <FormField label="Budget">
            <select value={budget} onChange={e => setBudget(e.target.value)} style={inputStyle}>
              <option value="">None</option>
              {filteredBudgets.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </FormField>
        )}
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

      {!enableSplit && selectedBudgetInfo && (
        <div style={{
          background: 'var(--info-soft)', border: '1px solid color-mix(in oklch, var(--info) 25%, var(--border))',
          borderRadius: 10, padding: '10px 14px', marginBottom: 14, fontSize: 12.5, color: 'var(--info)',
        }}>
          <strong>{selectedBudgetInfo.name}</strong>: <span className="num">{fmtMoney(-selectedBudgetInfo.remaining)}</span> remaining
        </div>
      )}

      {/* Installment toggle */}
      <div style={{
        border: '1px solid var(--border)', borderRadius: 12, marginBottom: 10, overflow: 'hidden',
        background: enableInstallments ? 'var(--bg-sunken)' : 'transparent',
      }}>
        <label style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          fontSize: 13, fontWeight: 550, color: 'var(--fg)', cursor: 'pointer',
        }}>
          <input type="checkbox" checked={enableInstallments} onChange={e => { setEnableInstallments(e.target.checked); if (!e.target.checked) { setShowPreview(false); setPreview(null); } }} style={{ accentColor: 'var(--accent)' }} />
          Installment purchase
        </label>
        {enableInstallments && (
          <div style={{ padding: '0 14px 14px' }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 10 }}>
              <FormField label="# Installments">
                <NumberStepper value={installments} onChange={setInstallments} min={2} max={48} />
              </FormField>
              <FormField label="Grace months">
                <NumberStepper value={gracePeriod} onChange={setGracePeriod} min={0} max={12} />
              </FormField>
              <FormField label="Start from #">
                <NumberStepper value={startFrom} onChange={setStartFrom} min={1} max={installments} />
              </FormField>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-muted)', cursor: 'pointer', whiteSpace: 'nowrap', height: 36 }}>
                <input type="checkbox" checked={showPreview} onChange={e => setShowPreview(e.target.checked)} style={{ accentColor: 'var(--accent)' }} />
                Preview
              </label>
            </div>
            {perInstallment > 0 && (
              <div style={{
                background: 'var(--info-soft)', border: '1px solid color-mix(in oklch, var(--info) 25%, var(--border))',
                borderRadius: 10, padding: '8px 12px', fontSize: 12, color: 'var(--info)',
              }}>
                <strong>{actualPayments}</strong> payments of <strong className="num">{fmtMoney(-perInstallment)}</strong> each ({startFrom}&ndash;{installments} of {installments})
                {gracePeriod > 0 && <span> &middot; {gracePeriod} month grace</span>}
                {startFrom > 1 && <span> &middot; starting #{startFrom}</span>}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Split toggle */}
      <div style={{
        border: '1px solid var(--border)', borderRadius: 12, marginBottom: 14, overflow: 'hidden',
        background: enableSplit ? 'var(--bg-sunken)' : 'transparent',
      }}>
        <label style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          fontSize: 13, fontWeight: 550, color: 'var(--fg)', cursor: 'pointer',
        }}>
          <input type="checkbox" checked={enableSplit} onChange={e => setEnableSplit(e.target.checked)} style={{ accentColor: 'var(--accent)' }} />
          Split across categories
        </label>
        {enableSplit && (
          <div style={{ padding: '0 14px 14px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 10 }}>
              {splits.map((sp, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px', background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 10,
                }}>
                  <CatSwatch cat={sp.category || null} size={22} />
                  <select value={sp.category} onChange={e => updateSplit(i, 'category', e.target.value)} style={{ ...inputStyle, flex: 1, minWidth: 0 }}>
                    <option value="">Category</option>
                    {categories?.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                  </select>
                  <select value={sp.budget} onChange={e => updateSplit(i, 'budget', e.target.value)} style={{ ...inputStyle, flex: 1, minWidth: 0 }}>
                    <option value="">Budget</option>
                    {filteredBudgets.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button onClick={addSplit} style={{
                padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                background: 'var(--bg-elev)', border: '1px solid var(--border)',
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
          </div>
        )}
      </div>

      {/* Preview table */}
      {showPreview && preview && preview.length > 0 && enableInstallments && (
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
              <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.description}</div>
              <div className="num" style={{ textAlign: 'right', color: 'var(--fg-muted)' }}>{fmtDate(t.date_payed)}</div>
              <div className="num" style={{ textAlign: 'right', fontWeight: 600 }}>{fmtMoney(t.amount)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Context cards (read-only reference while editing) */}
      {(consumo || invoice || llm_decision) && (
        <>
          <SectionLabel>Context</SectionLabel>
          {consumo && (
            <ContextCard title="Card Transaction" icon="💳">
              <CtxRow k="Merchant" v={consumo.merchant} />
              <CtxRow k="Bank" v={consumo.bank} />
              <CtxRow k="Amount" v={fmtMoney(consumo.amount)} highlight={consumo.amount !== Math.abs(txn.amount)} />
            </ContextCard>
          )}
          {invoice && (
            <ContextCard title="Invoice" icon="🧾">
              <CtxRow k="Vendor" v={invoice.vendor_trade_name || invoice.vendor} />
              <CtxRow k="Total" v={`$${invoice.total.toFixed(2)}`} />
              <button onClick={onViewInvoice} style={{
                marginTop: 6, width: '100%', padding: '5px 0', borderRadius: 6,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--fg-muted)', fontSize: 11.5, fontWeight: 550, cursor: 'pointer',
              }}>View full invoice</button>
            </ContextCard>
          )}
        </>
      )}

      {footerContainer && createPortal(
        <div>
          {typeChanged && (
            <div style={{
              background: 'var(--warn-soft)', border: '1px solid color-mix(in oklch, var(--warn) 25%, var(--border))',
              borderRadius: 10, padding: '10px 14px', marginBottom: 10, fontSize: 12.5, color: 'var(--warn)',
            }}>
              Type change detected — saving will delete the original and create new transaction(s).
            </div>
          )}
          <div style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8,
            background: 'var(--bg)',
          }}>
            {error && <span style={{ fontSize: 12, color: 'var(--neg)', flex: 1 }}>{error}</span>}
            <span style={{ flex: error ? 0 : 1 }} />
            <button onClick={onCancel} style={ghostBtnStyle}>Cancel</button>
            <button onClick={handleSave} disabled={saving} style={{
              padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: 'var(--accent)', border: 'none', color: 'white', cursor: 'pointer',
              opacity: saving ? 0.6 : 1,
            }}>
              {saving ? 'Saving...' : typeChanged ? 'Convert & save' : 'Save changes'}
              {!saving && <span style={{ marginLeft: 8, opacity: 0.7, fontSize: 11 }}>&#8984;&#8629;</span>}
            </button>
          </div>
        </div>,
        footerContainer,
      )}
    </>
  );
}


/* ── UI helpers ── */

function InfoBlock({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--fg-faint)', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 3 }}>{label}</div>
      {children || <div style={{ fontSize: 13, fontWeight: 550 }}>{value}</div>}
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

function CtxRow({ k, v, highlight }: { k: string; v: string; highlight?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 12.5 }}>
      <span style={{ color: 'var(--fg-muted)' }}>{k}</span>
      <span style={{ fontWeight: 550, color: highlight ? 'var(--warn)' : 'var(--fg)' }}>{v}</span>
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

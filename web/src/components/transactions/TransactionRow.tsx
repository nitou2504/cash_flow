import { forwardRef } from 'react';
import type { TimelineTransaction } from '../../api/types';
import { fmtMoney, fmtDate } from '../../utils/format';
import CatSwatch from '../primitives/CatSwatch';

interface Props {
  txn: TimelineTransaction;
  showBalance: boolean;
  dateMode?: 'payed' | 'created';
  selected?: boolean;
  onClick?: () => void;
  onViewInvoice?: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'PENDING',
  planning: 'PLAN',
  forecast: 'FORECAST',
};

const TransactionRow = forwardRef<HTMLDivElement, Props>(
  ({ txn, showBalance, dateMode = 'payed', selected, onClick, onViewInvoice }, ref) => {
    const { status, is_budget_allocation } = txn;

    let bg = 'transparent';
    let color = 'var(--fg)';
    let borderLeft = 'none';
    let opacity = 1;

    if (selected) bg = 'var(--bg-hover)';
    if (is_budget_allocation) {
      bg = 'color-mix(in oklch, var(--accent) 6%, transparent)';
      color = 'var(--accent)';
    } else if (status === 'pending') {
      color = 'var(--fg-faint)';
      borderLeft = '3px solid var(--warn)';
    } else if (status === 'forecast') {
      color = 'var(--fg-faint)';
      borderLeft = '3px dashed color-mix(in oklch, var(--fg-faint) 40%, transparent)';
    } else if (status === 'planning') {
      color = 'oklch(0.58 0.16 290)';
      borderLeft = '3px solid oklch(0.58 0.16 290)';
    }

    const statusTag = STATUS_LABEL[status];

    return (
      <div
        ref={ref}
        onClick={onClick}
        style={{
          display: 'grid',
          gridTemplateColumns: '78px 1fr 130px 110px 120px' + (showBalance ? ' 130px' : ''),
          gap: 12,
          padding: '9px var(--row-px)',
          background: bg,
          color,
          opacity,
          borderTop: '1px solid var(--border)',
          borderLeft,
          cursor: 'pointer',
          alignItems: 'center',
          fontSize: 13,
        }}
      >
        {/* Date */}
        <div style={{ lineHeight: 1.3 }}>
          <div className="num" style={{ fontSize: 12, color: status === 'pending' ? 'var(--fg-faint)' : 'var(--fg-muted)' }}>
            {fmtDate(dateMode === 'created' ? txn.date_created : txn.date_payed)}
          </div>
          {txn.date_created !== txn.date_payed && (
            <div className="num" style={{ fontSize: 10, color: 'var(--fg-faint)' }}>
              {dateMode === 'created' ? 'pays' : 'bought'} {fmtDate(dateMode === 'created' ? txn.date_payed : txn.date_created)}
            </div>
          )}
        </div>

        {/* Description */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <CatSwatch cat={txn.category} size={24} />
          <span style={{
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            fontWeight: 500,
          }}>
            {txn.description}
          </span>
          {statusTag && (
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
              padding: '1px 5px', borderRadius: 4, flexShrink: 0, fontStyle: 'normal',
              background: status === 'pending' ? 'var(--warn-soft)' : status === 'planning' ? 'color-mix(in oklch, oklch(0.58 0.16 290) 12%, transparent)' : 'var(--bg-sunken)',
              color: status === 'pending' ? 'var(--warn)' : status === 'planning' ? 'oklch(0.58 0.16 290)' : 'var(--fg-faint)',
            }}>
              {statusTag}
            </span>
          )}
          {is_budget_allocation && (
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
              padding: '1px 5px', borderRadius: 4, flexShrink: 0, fontStyle: 'normal',
              background: 'color-mix(in oklch, var(--accent) 12%, transparent)',
              color: 'var(--accent)',
            }}>
              ENVELOPE
            </span>
          )}
          {txn.has_invoice && (
            <button
              onClick={e => { e.stopPropagation(); onViewInvoice?.(); }}
              title="View invoice"
              style={{
                background: 'var(--bg-sunken)', border: '1px solid var(--border)',
                borderRadius: 4, padding: '1px 4px', fontSize: 10, color: 'var(--fg-muted)',
                cursor: 'pointer', flexShrink: 0,
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>
              </svg>
            </button>
          )}
          {!!txn.needs_review && !statusTag && (
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
              padding: '1px 5px', borderRadius: 4, flexShrink: 0, fontStyle: 'normal',
              background: 'var(--warn-soft)', color: 'var(--warn)',
            }}>
              REVIEW
            </span>
          )}
        </div>

        {/* Account */}
        <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{txn.account}</span>

        {/* Category */}
        <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{txn.category || ''}</span>

        {/* Amount */}
        <span
          className="num"
          title={is_budget_allocation && txn.budget_overspend ? `Over budget by $${txn.budget_overspend.toFixed(2)}` : undefined}
          style={{
            textAlign: 'right', fontWeight: 600,
            color: is_budget_allocation
              ? (txn.budget_overspend ? 'var(--neg)' : 'var(--accent)')
              : txn.amount > 0 ? 'var(--pos)' : color,
          }}
        >
          {fmtMoney(txn.amount)}
        </span>

        {/* Balance */}
        {showBalance && (
          <span className="num" style={{
            textAlign: 'right', fontSize: 12.5,             color: status === 'pending' ? 'transparent' : 'var(--fg-muted)',
          }}>
            {txn.running_balance != null ? fmtMoney(txn.running_balance) : ''}
          </span>
        )}
      </div>
    );
  }
);

TransactionRow.displayName = 'TransactionRow';
export default TransactionRow;

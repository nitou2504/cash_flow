import { useState, useMemo, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { TimelineResponse, TimelineTransaction, Account } from '../api/types';
import { fmtMoney, fmtMoneyCompact, fmtDateLong } from '../utils/format';
import BalanceChart from '../components/charts/BalanceChart';
import Segmented from '../components/primitives/Segmented';
import TransactionRow from '../components/transactions/TransactionRow';
import MonthGroupHeader from '../components/transactions/MonthGroupHeader';
import AddTransactionPanel from '../components/transactions/AddTransactionPanel';
import TransactionDetailDrawer from '../components/transactions/TransactionDetailDrawer';

export default function Transactions() {
  const [view, setView] = useState('summary');
  const [showPlanning, setShowPlanning] = useState(true);
  const [accountFilter, setAccountFilter] = useState('all');
  const [fromMonth, setFromMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });
  const [months] = useState(3);
  const [scrubIdx, setScrubIdx] = useState<number | undefined>(undefined);
  const [detailTxn, setDetailTxn] = useState<TimelineTransaction | null>(null);
  const [openWithInvoice, setOpenWithInvoice] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const rowRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });

  const sortBy = view === 'created' ? 'date_created' : 'date_payed';
  const dateMode: 'payed' | 'created' = view === 'created' ? 'created' : 'payed';
  const summary = view === 'summary';

  const { data, isLoading } = useQuery<TimelineResponse>({
    queryKey: ['timeline', fromMonth, months, sortBy, summary, showPlanning, accountFilter],
    queryFn: () => api.timeline({
      from_month: fromMonth,
      months: String(months),
      sort_by: sortBy,
      summary: summary ? 'true' : 'false',
      include_planning: showPlanning ? 'true' : 'false',
      ...(accountFilter !== 'all' ? { account: accountFilter } : {}),
    }),
  });

  const allTxns = useMemo(() => {
    if (!data) return [];
    const txns: TimelineTransaction[] = [...data.pending_from_past];
    data.months.forEach(m => txns.push(...m.transactions));
    return txns;
  }, [data]);

  const totalEntries = allTxns.length;

  const todayIdx = useMemo(() => {
    if (!data?.balance_series?.length) return 0;
    const today = new Date().toISOString().slice(0, 10);
    let idx = data.balance_series.findIndex(p => p.date > today);
    if (idx === -1) idx = data.balance_series.length - 1;
    else if (idx > 0) idx -= 1;
    return idx;
  }, [data?.balance_series]);

  const scrubPoint = data?.balance_series?.[scrubIdx ?? todayIdx];
  const scrubDate = scrubPoint?.date;

  const highlightedId = useMemo(() => {
    if (!scrubDate || !allTxns.length) return null;
    const matches = allTxns.filter(t => t.date_payed <= scrubDate);
    return matches.length ? matches[matches.length - 1].id : null;
  }, [allTxns, scrubDate]);

  useEffect(() => {
    if (scrubIdx != null && highlightedId && rowRefs.current[highlightedId]) {
      rowRefs.current[highlightedId]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightedId, scrubIdx]);

  const showBalance = view === 'timeline' || view === 'summary';

  const prevMonth = () => {
    const [y, m] = fromMonth.split('-').map(Number);
    const d = new Date(y, m - 2, 1);
    setFromMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  };
  const nextMonth = () => {
    const [y, m] = fromMonth.split('-').map(Number);
    const d = new Date(y, m, 1);
    setFromMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  };
  const monthLabel = new Date(fromMonth + '-01T00:00:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Topbar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '14px 28px', borderBottom: '1px solid var(--border)',
        background: 'color-mix(in oklch, var(--bg) 92%, transparent)',
        backdropFilter: 'blur(8px)', position: 'sticky', top: 0, zIndex: 5, minHeight: 60,
      }}>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>Transactions</div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            {totalEntries} entries &middot; {showBalance ? 'running balance shown' : view === 'created' ? 'sorted by creation date' : 'CC aggregated'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button onClick={prevMonth} style={navBtnStyle}>&lsaquo;</button>
          <span style={{ fontSize: 13, fontWeight: 600, minWidth: 90, textAlign: 'center' }}>{monthLabel}</span>
          <button onClick={nextMonth} style={navBtnStyle}>&rsaquo;</button>
        </div>
        <button onClick={() => setAddOpen(true)} style={{
          padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
          background: 'var(--accent)', border: 'none', color: 'white', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> Add
        </button>
      </div>

      {/* Chart panel */}
      <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-elev)', padding: '14px 24px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 14 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                {scrubDate ? fmtDateLong(scrubDate) : 'Hover to scrub'}
              </div>
              <div className="num" style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em' }}>
                {scrubPoint ? `$${scrubPoint.balance.toFixed(2)}` : data?.starting_balance != null ? `$${data.starting_balance.toFixed(2)}` : '...'}
              </div>
            </div>
            <div style={{ height: 32, width: 1, background: 'var(--border)' }} />
            {data?.stats && (
              <>
                <Stat k="Mo. change" v={fmtMoney(data.stats.mom_change, { alwaysSign: true })} tone={data.stats.mom_change >= 0 ? 'pos' : 'neg'} />
                <Stat k="Forecast end" v={fmtMoneyCompact(data.stats.forecast_end)} />
                <Stat k="Lowest in period" v={fmtMoneyCompact(data.stats.lowest_in_period)} tone="warn" />
              </>
            )}
          </div>
          <Segmented value={view} onChange={setView} size="sm" options={[
            { value: 'timeline', label: 'Timeline' },
            { value: 'created', label: 'Created' },
            { value: 'summary', label: 'Summary' },
          ]} />
        </div>
        <BalanceChart series={data?.balance_series ?? []} height={130} scrubIndex={scrubIdx ?? todayIdx} onScrub={setScrubIdx} />
      </div>

      {/* Filter bar */}
      <div style={{
        padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 10,
        borderBottom: '1px solid var(--border)', background: 'var(--bg)',
      }}>
        <Segmented value={accountFilter} onChange={setAccountFilter} size="sm" options={[
          { value: 'all', label: 'All accounts' },
          ...(accounts || []).map(a => ({ value: a.account_id, label: a.account_id })),
        ]} />
        <span style={{ flex: 1 }} />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--fg-muted)', cursor: 'pointer' }}>
          <input type="checkbox" checked={showPlanning} onChange={e => setShowPlanning(e.target.checked)} style={{ accentColor: 'var(--accent)' }} />
          Show planning
        </label>
      </div>

      {/* Column headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '78px 1fr 130px 110px 120px' + (showBalance ? ' 130px' : ''),
        gap: 12, padding: '8px var(--row-px)', background: 'var(--bg-sunken)',
        borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 600,
        color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase',
      }}>
        <div>Date</div>
        <div>Description</div>
        <div>Account</div>
        <div>Category</div>
        <div style={{ textAlign: 'right' }}>Amount</div>
        {showBalance && <div style={{ textAlign: 'right' }}>Balance</div>}
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {isLoading && <div style={{ padding: 28, color: 'var(--fg-muted)' }}>Loading...</div>}

        {data && data.pending_from_past.length > 0 && (
          <>
            <div style={{
              padding: '8px var(--row-px)', fontSize: 11, fontWeight: 600,
              color: 'var(--fg-faint)', letterSpacing: '0.04em', textTransform: 'uppercase',
              background: 'var(--bg-sunken)', borderBottom: '1px solid var(--border)',
            }}>
              Pending from past
            </div>
            {data.pending_from_past.map(txn => (
              <TransactionRow
                key={txn.id}
                ref={el => { rowRefs.current[txn.id] = el; }}
                txn={txn}
                showBalance={showBalance}
                dateMode={dateMode}
                selected={selectedId === txn.id || highlightedId === txn.id}
                onClick={() => { setSelectedId(txn.id); setDetailTxn(txn); }}
                onViewInvoice={() => { setDetailTxn(txn); setSelectedId(txn.id); setOpenWithInvoice(true); }}
              />
            ))}
          </>
        )}

        {data && data.starting_balance != null && showBalance && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: '78px 1fr 130px 110px 120px 130px',
            gap: 12, padding: '9px var(--row-px)',
            borderTop: '1px solid var(--border)', fontSize: 13,
            color: 'var(--fg-faint)', fontStyle: 'italic',
          }}>
            <span />
            <span>Starting balance</span>
            <span /><span /><span />
            <span className="num" style={{ textAlign: 'right', fontWeight: 600 }}>
              {fmtMoney(data.starting_balance)}
            </span>
          </div>
        )}

        {data?.months.map(mg => (
          <div key={mg.month_key}>
            <MonthGroupHeader
              label={mg.month_label}
              totalIn={mg.total_in}
              totalOut={mg.total_out}
              balance={mg.transactions.length > 0 ? mg.transactions[mg.transactions.length - 1].running_balance : null}
              momChange={mg.mom_change}
              monthSpending={mg.month_spending}
              showBalance={showBalance}
            />
            {mg.transactions.map(txn => (
              <TransactionRow
                key={txn.id}
                ref={el => { rowRefs.current[txn.id] = el; }}
                txn={txn}
                showBalance={showBalance}
                dateMode={dateMode}
                selected={selectedId === txn.id || highlightedId === txn.id}
                onClick={() => { setSelectedId(txn.id); setDetailTxn(txn); }}
                onViewInvoice={() => { setDetailTxn(txn); setSelectedId(txn.id); setOpenWithInvoice(true); }}
              />
            ))}
          </div>
        ))}

        {data && !isLoading && allTxns.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg-faint)', fontSize: 13 }}>
            No transactions in this period
          </div>
        )}
      </div>

      {detailTxn && (
        <TransactionDetailDrawer
          txn={detailTxn}
          onClose={() => { setDetailTxn(null); setSelectedId(null); setOpenWithInvoice(false); }}
          initialShowInvoice={openWithInvoice}
        />
      )}
      {addOpen && <AddTransactionPanel onClose={() => setAddOpen(false)} />}
    </div>
  );
}

function Stat({ k, v, tone = 'neutral' }: { k: string; v: string; tone?: string }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: 'var(--fg-faint)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>{k}</div>
      <div className="num" style={{
        fontSize: 13.5, fontWeight: 600,
        color: tone === 'pos' ? 'var(--pos)' : tone === 'neg' ? 'var(--neg)' : tone === 'warn' ? 'var(--warn)' : 'var(--fg)',
      }}>{v}</div>
    </div>
  );
}

const navBtnStyle: React.CSSProperties = {
  width: 28, height: 28, borderRadius: 6,
  background: 'var(--bg-sunken)', border: '1px solid var(--border)',
  color: 'var(--fg-muted)', cursor: 'pointer', fontSize: 16,
  display: 'grid', placeItems: 'center',
};

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
import SearchFilters from '../components/transactions/SearchFilters';
import { useTransactionSearch } from '../hooks/useTransactionSearch';

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
  const search = useTransactionSearch();
  const searchInputRef = useRef<HTMLInputElement>(null);

  const rowRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const { data: accounts } = useQuery<Account[]>({ queryKey: ['accounts'], queryFn: api.accounts });
  useQuery({ queryKey: ['categories'], queryFn: api.categories, staleTime: 5 * 60_000 });
  useQuery({ queryKey: ['budgets'], queryFn: api.budgets, staleTime: 5 * 60_000 });

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
        <div style={{ lineHeight: 1.2, minWidth: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>Transactions</div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
            {search.isSearchActive
              ? `${search.total} result${search.total !== 1 ? 's' : ''}`
              : `${totalEntries} entries`}
          </div>
        </div>

        {/* Search input */}
        <div style={{
          flex: 1, maxWidth: 380, position: 'relative',
          display: 'flex', alignItems: 'center',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--fg-faint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            style={{ position: 'absolute', left: 10, pointerEvents: 'none' }}>
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={searchInputRef}
            value={search.query}
            onChange={e => search.setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Escape') { search.clearAll(); searchInputRef.current?.blur(); } }}
            placeholder="Search transactions..."
            style={{
              width: '100%', padding: '7px 32px 7px 32px', borderRadius: 8,
              border: `1px solid ${search.isSearchActive ? 'var(--accent)' : 'var(--border)'}`,
              background: search.isSearchActive ? 'color-mix(in oklch, var(--accent) 5%, var(--bg))' : 'var(--bg-sunken)',
              color: 'var(--fg)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
            }}
          />
          {search.query && (
            <button onClick={() => search.setQuery('')} style={{
              position: 'absolute', right: 6, width: 20, height: 20, borderRadius: 4,
              background: 'transparent', border: 'none', color: 'var(--fg-muted)',
              cursor: 'pointer', display: 'grid', placeItems: 'center', fontSize: 13,
            }}>&times;</button>
          )}
        </div>

        {!search.isSearchActive && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <button onClick={prevMonth} style={navBtnStyle}>&lsaquo;</button>
            <span style={{ fontSize: 13, fontWeight: 600, minWidth: 90, textAlign: 'center' }}>{monthLabel}</span>
            <button onClick={nextMonth} style={navBtnStyle}>&rsaquo;</button>
          </div>
        )}
        <button onClick={() => setAddOpen(true)} style={{
          padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
          background: 'var(--accent)', border: 'none', color: 'white', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0,
        }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> Add
        </button>
      </div>

      {search.isSearchActive ? (
        <>
          {/* Search filters */}
          <SearchFilters filters={search.filters} onChange={search.setFilters} />

          {/* Column headers (no balance) */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '78px 1fr 130px 110px 120px',
            gap: 12, padding: '8px var(--row-px)', background: 'var(--bg-sunken)',
            borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 600,
            color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase',
          }}>
            <div>Date</div>
            <div>Description</div>
            <div>Account</div>
            <div>Category</div>
            <div style={{ textAlign: 'right' }}>Amount</div>
          </div>

          {/* Search results */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            {search.isLoading && <div style={{ padding: 28, color: 'var(--fg-muted)' }}>Searching...</div>}

            {search.results.map(txn => (
              <TransactionRow
                key={txn.id}
                txn={txn}
                showBalance={false}
                dateMode={search.filters.date_field === 'date_created' ? 'created' : 'payed'}
                selected={selectedId === txn.id}
                onClick={() => { setSelectedId(txn.id); setDetailTxn(txn); }}
                onViewInvoice={() => { setDetailTxn(txn); setSelectedId(txn.id); setOpenWithInvoice(true); }}
              />
            ))}

            {search.results.length === 0 && !search.isLoading && (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--fg-faint)', fontSize: 13 }}>
                No transactions match your search
              </div>
            )}

            {search.hasMore && (
              <div style={{ padding: '16px 24px', textAlign: 'center' }}>
                <button onClick={search.loadMore} disabled={search.isFetching} style={{
                  padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 550,
                  background: 'transparent', border: '1px solid var(--border)',
                  color: 'var(--fg-muted)', cursor: 'pointer',
                }}>
                  {search.isFetching ? 'Loading...' : `Load more (${search.total - search.results.length} remaining)`}
                </button>
              </div>
            )}
          </div>
        </>
      ) : (
        <>
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
        </>
      )}

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

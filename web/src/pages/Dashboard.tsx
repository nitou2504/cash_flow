import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { DashboardData, Transaction, BudgetSpending as BudgetType, CCCard } from '../api/types';
import BalanceChart from '../components/charts/BalanceChart';
import ProgressBar from '../components/charts/ProgressBar';
import Card from '../components/primitives/Card';
import Pill from '../components/primitives/Pill';

function fmtMoney(n: number, opts?: { alwaysSign?: boolean }): string {
  const sign = n < 0 ? '−' : opts?.alwaysSign && n > 0 ? '+' : '';
  const v = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${sign}$${v}`;
}

function fmtMoneyCompact(n: number): string {
  const sign = n < 0 ? '−' : '';
  const a = Math.abs(n);
  if (a >= 1000) return `${sign}$${(a / 1000).toFixed(1)}k`;
  return `${sign}$${a.toFixed(0)}`;
}

function fmtDate(d: string): string {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: '2-digit' });
}

function fmtDateLong(d: string): string {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery<DashboardData>({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
  });
  const [scrubIdx, setScrubIdx] = useState<number | undefined>(undefined);

  if (isLoading) return <div style={{ padding: 28, color: 'var(--fg-muted)' }}>Loading...</div>;
  if (error || !data) return <div style={{ padding: 28, color: 'var(--neg)' }}>Failed to load dashboard</div>;

  const now = new Date();
  const monthShort = now.toLocaleDateString('en-US', { month: 'short' });
  const dayLabel = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  const scrubPoint = data.balance_series[scrubIdx ?? data.balance_series.length - 1];
  const start = data.balance_series[0];
  const displayBalance = scrubIdx != null ? (scrubPoint?.balance ?? 0) : data.current_balance;
  const change = start ? displayBalance - start.balance : 0;
  const net = data.month_income - data.month_expenses;

  return (
    <div className="cf-app" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* ── Topbar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '14px 28px', borderBottom: '1px solid var(--border)',
        background: 'color-mix(in oklch, var(--bg) 92%, transparent)',
        backdropFilter: 'blur(8px)',
        position: 'sticky', top: 0, zIndex: 5, minHeight: 60,
      }}>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>Dashboard</div>
          <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{dayLabel} &middot; {data.accounts.length} accounts</div>
        </div>
      </div>

      {/* ── Content: 2-column layout ── */}
      <div style={{ flex: 1, padding: 24, display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 18, alignContent: 'start', overflow: 'auto' }}>
        {/* LEFT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Hero balance card */}
          <div style={{
            background: 'linear-gradient(180deg, color-mix(in oklch, var(--accent) 7%, var(--bg-elev)) 0%, var(--bg-elev) 60%)',
            border: '1px solid var(--border)', borderRadius: 16, padding: '22px 22px 14px',
            boxShadow: 'var(--shadow-card)',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--fg-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  Net balance &middot; across accounts
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 6 }}>
                  <span className="num" style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-0.025em' }}>
                    ${displayBalance.toFixed(2)}
                  </span>
                  <Pill tone={change >= 0 ? 'pos' : 'neg'} dot>
                    {change >= 0 ? '↑' : '↓'} {fmtMoneyCompact(Math.abs(change))}
                  </Pill>
                </div>
                <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 2 }}>
                  {scrubIdx != null && scrubPoint
                    ? `Scrubbing: ${fmtDateLong(scrubPoint.date)}`
                    : data.projected_balance !== data.current_balance
                      ? `Projected end of ${monthShort}: $${data.projected_balance.toFixed(2)}`
                      : start ? `vs. $${start.balance.toFixed(2)} on ${fmtDateLong(start.date)}` : ''
                  }
                </div>
              </div>
            </div>
            <BalanceChart series={data.balance_series} height={170} scrubIndex={scrubIdx} onScrub={setScrubIdx} />
          </div>

          {/* KPIs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <KpiSmall label={`Income · ${monthShort}`} value={fmtMoney(data.month_income, { alwaysSign: true })} tone="pos" />
            <KpiSmall label={`Spent · ${monthShort}`} value={fmtMoney(-data.month_expenses)} tone="neutral" />
            <KpiSmall label={`Net · ${monthShort}`} value={fmtMoney(net, { alwaysSign: net > 0 })} tone={net >= 0 ? 'pos' : 'neg'} />
          </div>

          {/* Recent activity */}
          <Card title="Recent activity" subtitle={`Last ${data.recent_transactions.length} committed`} action={<GhostLink to="/transactions">View timeline</GhostLink>} padding={0}>
            <div>
              {data.recent_transactions.map(t => <DashTxnRow key={t.id} txn={t} />)}
              {data.recent_transactions.length === 0 && <Empty>No transactions</Empty>}
            </div>
          </Card>
        </div>

        {/* RIGHT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Accounts */}
          <Card title="Accounts" padding={0}>
            <div style={{ padding: '4px 8px 10px' }}>
              {data.accounts.map(a => <AccountRow key={a.account_id} account={a} ccCards={data.cc_cards} balance={data.current_balance} />)}
            </div>
          </Card>

          {/* Budget envelopes */}
          <Card
            title="Budget envelopes"
            subtitle={`${monthShort} · ${data.budgets.length} active`}
            padding={0}
          >
            <div style={{ padding: '4px 16px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {data.budgets.map(b => <BudgetMini key={b.id} b={b} />)}
              {data.budgets.length === 0 && <Empty>No active budgets</Empty>}
            </div>
          </Card>

          {/* Heads up */}
          <Card title="Heads up" subtitle="Things to look at">
            {data.review_count > 0 && (
              <Insight
                tone="warn"
                title={`${data.review_count} transactions need review`}
                body="From Gmail sync and auto-registration."
              />
            )}
            {data.budgets.some(b => b.spent > b.allocated) && (
              <Insight
                tone="warn"
                title="Budget overspend"
                body={data.budgets.filter(b => b.spent > b.allocated).map(b => b.name).join(', ')}
              />
            )}
            <Insight
              tone={net >= 0 ? 'pos' : 'neg'}
              title={net >= 0 ? 'On track this month' : 'Over budget this month'}
              body={`Net: ${fmtMoney(net)} (income ${fmtMoney(data.month_income)} − expenses ${fmtMoney(data.month_expenses)})`}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ── KPI (compact, 3-across) ── */

function KpiSmall({ label, value, tone }: { label: string; value: string; tone: string }) {
  const color = tone === 'pos' ? 'var(--pos)' : tone === 'neg' ? 'var(--neg)' : 'var(--fg)';
  return (
    <div style={{
      background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 12, padding: 14,
      boxShadow: 'var(--shadow-card)',
    }}>
      <div style={{ fontSize: 11, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600 }}>{label}</div>
      <div className="num" style={{ fontSize: 22, fontWeight: 600, marginTop: 6, letterSpacing: '-0.02em', color }}>{value}</div>
    </div>
  );
}

/* ── Account Row ── */

const CC_COLORS: Record<string, string> = {
  'Visa Pichincha': 'oklch(0.62 0.14 30)',
  'Diners': 'oklch(0.55 0.06 250)',
  'Visa Produbanco': 'oklch(0.58 0.14 155)',
  'Cash': 'oklch(0.58 0.14 155)',
};

function AccountRow({ account, ccCards, balance }: {
  account: { account_id: string; account_type: string; cut_off_day: number | null; payment_day: number | null };
  ccCards: CCCard[];
  balance: number;
}) {
  const isCC = account.account_type === 'credit_card';
  const color = CC_COLORS[account.account_id] || 'oklch(0.6 0.1 250)';
  const cc = ccCards.find(c => c.name === account.account_id);

  if (!isCC) {
    return (
      <div style={{ padding: '10px 10px', display: 'flex', alignItems: 'center', gap: 12, borderRadius: 8 }}>
        <div style={{
          width: 38, height: 26, borderRadius: 5, background: color, color: 'white',
          display: 'grid', placeItems: 'center', fontSize: 9, fontWeight: 700, flexShrink: 0, letterSpacing: '0.06em',
        }}>CASH</div>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ fontSize: 13, fontWeight: 550 }}>{account.account_id}</div>
          <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>Available cash</div>
        </div>
        <div className="num" style={{ fontSize: 14, fontWeight: 600 }}>{fmtMoney(balance)}</div>
      </div>
    );
  }

  const current = cc?.current_cycle_owed ?? 0;
  const next = cc?.next_cycle_owed ?? 0;
  const total = cc?.total_owed ?? 0;
  const rest = total - current - next;

  return (
    <div style={{ padding: '10px 10px', borderRadius: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <div style={{
          width: 38, height: 26, borderRadius: 5, background: color, color: 'white',
          display: 'grid', placeItems: 'center', fontSize: 9, fontWeight: 700, flexShrink: 0, letterSpacing: '0.06em',
        }}>CC</div>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ fontSize: 13, fontWeight: 550 }}>{account.account_id}</div>
        </div>
        <div className="num" style={{ fontSize: 14, fontWeight: 600, color: total > 0 ? 'var(--neg)' : 'var(--fg)' }}>
          {fmtMoney(-total)}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, fontSize: 11, color: 'var(--fg-muted)', paddingLeft: 50 }}>
        {current > 0 && (
          <CyclePill label={cc?.current_cycle_date ? fmtDate(cc.current_cycle_date) : 'Current'} amount={current} imminent />
        )}
        {next > 0 && (
          <CyclePill label={cc?.next_cycle_date ? fmtDate(cc.next_cycle_date) : 'Next'} amount={next} />
        )}
        {rest > 0 && (
          <CyclePill label="Later" amount={rest} faint />
        )}
      </div>
    </div>
  );
}

function CyclePill({ label, amount, imminent, faint }: { label: string; amount: number; imminent?: boolean; faint?: boolean }) {
  return (
    <span className="num" style={{
      padding: '2px 8px', borderRadius: 6,
      background: imminent ? 'color-mix(in oklch, var(--neg) 12%, transparent)' : faint ? 'var(--bg-sunken)' : 'color-mix(in oklch, var(--warn) 10%, transparent)',
      color: imminent ? 'var(--neg)' : faint ? 'var(--fg-faint)' : 'var(--fg-muted)',
      fontSize: 10.5, fontWeight: 550, whiteSpace: 'nowrap',
    }}>
      {label} {fmtMoney(-amount)}
    </span>
  );
}

/* ── Budget Mini (matches design: CatSwatch + name + spent/allocated + progress) ── */

const CATEGORY_COLORS: Record<string, string> = {
  'Home': 'oklch(0.62 0.10 60)',
  'Home Food & Supplies': 'var(--cat-1)',
  'Personal Diet': 'var(--cat-2)',
  'Dining-Snacks': 'var(--cat-2)',
  'Personal': 'var(--cat-4)',
  'Health': 'oklch(0.62 0.10 0)',
  'Income': 'var(--pos)',
  'Family Support': 'oklch(0.62 0.10 290)',
  'Savings': 'var(--accent)',
  'Sister Education': 'oklch(0.65 0.10 200)',
  'Loans': 'oklch(0.58 0.10 25)',
  'Others': 'var(--fg-faint)',
};

function BudgetMini({ b }: { b: BudgetType }) {
  const over = b.spent > b.allocated;
  const color = CATEGORY_COLORS[b.category] || 'var(--accent)';
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <CatSwatch cat={b.category} size={18} />
        <span style={{ fontSize: 12.5, fontWeight: 550, flex: 1 }}>{b.name}</span>
        <span className="num" style={{ fontSize: 11.5, color: over ? 'var(--neg)' : 'var(--fg-muted)' }}>
          ${b.spent.toFixed(0)} / ${b.allocated.toFixed(0)}
        </span>
      </div>
      <ProgressBar value={b.spent} max={b.allocated} color={color} />
    </div>
  );
}

/* ── Dashboard Transaction Row (compact, 3-column grid) ── */

function DashTxnRow({ txn }: { txn: Transaction }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 130px 110px',
      alignItems: 'center', gap: 12, padding: '11px 18px',
      borderTop: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <CatSwatch cat={txn.category} size={26} />
        <div style={{ minWidth: 0, lineHeight: 1.2 }}>
          <div style={{ fontSize: 13, fontWeight: 550, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {txn.description}
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>
            {fmtDate(txn.date_payed)} &middot; {txn.category || 'Uncategorized'}
          </div>
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{txn.account}</div>
      <div className="num" style={{
        textAlign: 'right', fontSize: 13.5, fontWeight: 600,
        color: txn.amount > 0 ? 'var(--pos)' : 'var(--fg)',
      }}>
        {fmtMoney(txn.amount, { alwaysSign: txn.amount > 0 })}
      </div>
    </div>
  );
}

/* ── Insight row ── */

function Insight({ tone, title, body }: { tone: string; title: string; body: string }) {
  const bg = tone === 'warn' ? 'var(--warn-soft)' : tone === 'pos' ? 'var(--pos-soft)' : 'var(--info-soft)';
  const fg = tone === 'warn' ? 'var(--warn)' : tone === 'pos' ? 'var(--pos)' : 'var(--info)';
  return (
    <div style={{ display: 'flex', gap: 10, padding: '12px 0', borderTop: '1px solid var(--border)' }}>
      <div style={{ width: 28, height: 28, borderRadius: 8, background: bg, color: fg, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
        {tone === 'warn' ? '⚠' : tone === 'pos' ? '✓' : 'ℹ'}
      </div>
      <div style={{ flex: 1, lineHeight: 1.4 }}>
        <div style={{ fontSize: 13, fontWeight: 550, marginBottom: 2 }}>{title}</div>
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{body}</div>
      </div>
    </div>
  );
}

/* ── Category Swatch ── */

const CAT_COLORS: Record<string, string> = {
  'Home Food & Supplies': 'var(--cat-1)',
  'Dining-Snacks': 'var(--cat-2)',
  'Personal Diet': 'var(--cat-2)',
  'Home': 'oklch(0.62 0.10 60)',
  'Personal': 'var(--cat-4)',
  'Health': 'oklch(0.62 0.10 0)',
  'Income': 'var(--pos)',
  'Family Support': 'oklch(0.62 0.10 290)',
  'Savings': 'var(--accent)',
  'Sister Education': 'oklch(0.65 0.10 200)',
  'Loans': 'oklch(0.58 0.10 25)',
  'Others': 'var(--fg-faint)',
};

function CatSwatch({ cat, size = 22 }: { cat: string | null; size?: number }) {
  const c = cat || 'Other';
  const color = CAT_COLORS[c] || 'var(--fg-faint)';
  const letter = c.slice(0, 1).toUpperCase();
  return (
    <span style={{
      width: size, height: size, borderRadius: 6, flexShrink: 0,
      background: `color-mix(in oklch, ${color} 18%, var(--bg-elev))`,
      color, display: 'grid', placeItems: 'center',
      fontSize: size * 0.55, fontWeight: 700, letterSpacing: 0,
    }}>
      {letter}
    </span>
  );
}

/* ── Helpers ── */

function GhostLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link to={to} style={{
      fontSize: 12.5, fontWeight: 550, color: 'var(--fg-muted)',
      textDecoration: 'none', padding: '5px 10px',
    }}>
      {children} &rsaquo;
    </Link>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-faint)', textAlign: 'center' }}>{children}</div>;
}

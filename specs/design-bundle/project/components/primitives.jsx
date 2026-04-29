// Cash Flow — shared primitives & chrome
// Sidebar, topbar, cards, badges, transaction row, etc.

const { useState, useMemo, useEffect, useRef } = React;

// ─── Icons (line, 16-20px, currentColor) ────────────────────────────────────
const Icon = ({ d, size = 16, stroke = 1.7, fill = 'none' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" style={{ flex: 'none' }}>
    {d}
  </svg>
);

const I = {
  dashboard: <Icon d={<><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></>}/>,
  list: <Icon d={<><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></>}/>,
  plus: <Icon d={<><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></>}/>,
  budget: <Icon d={<><path d="M3 12a9 9 0 1 0 9-9"/><path d="M12 3v9l6 6"/></>}/>,
  card: <Icon d={<><rect x="3" y="5" width="18" height="14" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/></>}/>,
  inbox: <Icon d={<><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5 5l-3 7v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3-7z"/></>}/>,
  search: <Icon d={<><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>}/>,
  bell: <Icon d={<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></>}/>,
  chev: <Icon d={<polyline points="9 18 15 12 9 6"/>}/>,
  chevL: <Icon d={<polyline points="15 18 9 12 15 6"/>}/>,
  chevD: <Icon d={<polyline points="6 9 12 15 18 9"/>}/>,
  chevU: <Icon d={<polyline points="18 15 12 9 6 15"/>}/>,
  arrowUp: <Icon d={<><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></>}/>,
  arrowDown: <Icon d={<><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></>}/>,
  spark: <Icon d={<><polyline points="3 17 9 11 13 15 21 7"/></>}/>,
  filter: <Icon d={<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>}/>,
  more: <Icon d={<><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>}/>,
  cmd: <Icon d={<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>}/>,
  sparkle: <Icon d={<><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/><path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8z"/></>}/>,
  check: <Icon d={<polyline points="20 6 9 17 4 12"/>}/>,
  x: <Icon d={<><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>}/>,
  edit: <Icon d={<><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></>}/>,
  trash: <Icon d={<><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></>}/>,
  calendar: <Icon d={<><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>}/>,
  tag: <Icon d={<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><circle cx="7" cy="7" r="1.2" fill="currentColor"/></>}/>,
  wallet: <Icon d={<><path d="M21 12V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/><path d="M21 12h-4a2 2 0 0 0 0 4h4"/></>}/>,
  receipt: <Icon d={<path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/>}/>,
  flag: <Icon d={<><path d="M4 22V4M4 4h13l-2 4 2 4H4"/></>}/>,
  zap: <Icon d={<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>}/>,
  sun: <Icon d={<><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.07" y2="4.93"/></>}/>,
  moon: <Icon d={<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>}/>,
};

// ─── Helpers ─────────────────────────────────────────────────────────────────
const fmtMoney = (n, opts = {}) => {
  const sign = n < 0 ? '−' : opts.alwaysSign && n > 0 ? '+' : '';
  const v = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${sign}$${v}`;
};
const fmtMoneyCompact = (n) => {
  const sign = n < 0 ? '−' : '';
  const a = Math.abs(n);
  if (a >= 1000) return `${sign}$${(a / 1000).toFixed(1)}k`;
  return `${sign}$${a.toFixed(0)}`;
};
const fmtDate = (d) => {
  const date = new Date(d);
  return date.toLocaleDateString('en-US', { month: 'short', day: '2-digit' });
};
const fmtDateLong = (d) => {
  const date = new Date(d);
  return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
};

// ─── Sidebar ─────────────────────────────────────────────────────────────────
function Sidebar({ active = 'dashboard', onNav, badges = {} }) {
  const items = [
    { id: 'dashboard', label: 'Dashboard', icon: I.dashboard },
    { id: 'transactions', label: 'Transactions', icon: I.list },
    { id: 'add', label: 'Add', icon: I.plus, kbd: '⌘N' },
    { id: 'budgets', label: 'Budgets', icon: I.budget },
    { id: 'liabilities', label: 'Liabilities', icon: I.card },
    { id: 'review', label: 'Review', icon: I.inbox, badge: badges.review },
  ];
  const settings = [
    { id: 'accounts', label: 'Accounts', icon: I.wallet },
    { id: 'categories', label: 'Categories', icon: I.tag },
    { id: 'sync', label: 'Gmail Sync', icon: I.zap },
  ];
  const Item = ({ it }) => (
    <button
      onClick={() => onNav && onNav(it.id)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '7px 10px',
        background: active === it.id ? 'var(--bg-hover)' : 'transparent',
        color: active === it.id ? 'var(--fg)' : 'var(--fg-muted)',
        border: 'none', borderRadius: 8, fontSize: 13.5, fontWeight: active === it.id ? 550 : 450,
        textAlign: 'left',
      }}>
      <span style={{ color: active === it.id ? 'var(--accent)' : 'var(--fg-faint)' }}>{it.icon}</span>
      <span style={{ flex: 1 }}>{it.label}</span>
      {it.badge ? (
        <span style={{ background: 'var(--warn-soft)', color: 'var(--warn)', fontSize: 11, fontWeight: 600, padding: '1px 7px', borderRadius: 999 }}>{it.badge}</span>
      ) : null}
      {it.kbd ? <span className="num" style={{ fontSize: 11, color: 'var(--fg-faint)' }}>{it.kbd}</span> : null}
    </button>
  );
  return (
    <aside style={{
      width: 224, flex: 'none', background: 'var(--bg)', borderRight: '1px solid var(--border)',
      padding: '14px 12px', display: 'flex', flexDirection: 'column', gap: 16, height: '100%',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 8px 8px' }}>
        <Logo/>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
          <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-0.015em' }}>Cash Flow</span>
          <span style={{ fontSize: 11, color: 'var(--fg-faint)' }}>Personal</span>
        </div>
        <button style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, padding: '3px 5px', color: 'var(--fg-muted)' }}>{I.chevD}</button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {items.map((it) => <Item key={it.id} it={it}/>)}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--fg-faint)', letterSpacing: '0.07em', textTransform: 'uppercase', padding: '4px 10px 6px' }}>Manage</div>
        {settings.map((it) => <Item key={it.id} it={it}/>)}
      </div>

      <div style={{ flex: 1 }}/>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 28, height: 28, borderRadius: 999, background: 'linear-gradient(135deg, var(--accent), oklch(0.7 0.14 290))', color: 'white', fontSize: 11, fontWeight: 600, display: 'grid', placeItems: 'center' }}>AM</div>
        <div style={{ flex: 1, lineHeight: 1.15 }}>
          <div style={{ fontSize: 12.5, fontWeight: 550 }}>Andrés M.</div>
          <div style={{ fontSize: 11, color: 'var(--fg-faint)' }}>3 accounts</div>
        </div>
        <button style={{ background: 'transparent', border: 'none', color: 'var(--fg-faint)', padding: 4 }}>{I.more}</button>
      </div>
    </aside>
  );
}

function Logo() {
  return (
    <div style={{ width: 26, height: 26, borderRadius: 8, background: 'var(--accent)', display: 'grid', placeItems: 'center', flex: 'none' }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 17l6-6 4 4 8-9"/>
      </svg>
    </div>
  );
}

// ─── Topbar ─────────────────────────────────────────────────────────────────
function Topbar({ title, subtitle, children, sticky = true }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 16,
      padding: '14px 28px', borderBottom: '1px solid var(--border)',
      background: 'color-mix(in oklch, var(--bg) 92%, transparent)',
      backdropFilter: 'blur(8px)',
      position: sticky ? 'sticky' : 'static', top: 0, zIndex: 5,
      minHeight: 60,
    }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
        <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.015em' }}>{title}</div>
        {subtitle ? <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{subtitle}</div> : null}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {children}
        <SearchBox/>
        <IconBtn>{I.bell}<Dot/></IconBtn>
      </div>
    </div>
  );
}

function SearchBox() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
      background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 8,
      minWidth: 260, color: 'var(--fg-muted)',
    }}>
      <span style={{ color: 'var(--fg-faint)' }}>{I.search}</span>
      <span style={{ flex: 1, fontSize: 13 }}>Search transactions, budgets…</span>
      <Kbd>⌘K</Kbd>
    </div>
  );
}

function Kbd({ children }) {
  return (
    <span className="num" style={{
      fontSize: 11, color: 'var(--fg-muted)', padding: '1px 5px',
      background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 4,
      lineHeight: 1.4,
    }}>{children}</span>
  );
}

function Dot() {
  return <span style={{ position: 'absolute', top: 6, right: 6, width: 7, height: 7, borderRadius: 999, background: 'var(--neg)', border: '2px solid var(--bg)' }}/>;
}

function IconBtn({ children, onClick, active }) {
  return (
    <button onClick={onClick} style={{
      position: 'relative',
      width: 34, height: 34, display: 'grid', placeItems: 'center',
      background: active ? 'var(--bg-hover)' : 'transparent',
      border: '1px solid var(--border)', borderRadius: 8,
      color: 'var(--fg-muted)',
    }}>{children}</button>
  );
}

// ─── Buttons ────────────────────────────────────────────────────────────────
function Btn({ kind = 'default', size = 'md', icon, children, onClick, style, disabled }) {
  const sz = size === 'sm' ? { padding: '5px 10px', fontSize: 12.5, height: 28 } : { padding: '7px 14px', fontSize: 13.5, height: 34 };
  const kinds = {
    default: { background: 'var(--bg-elev)', color: 'var(--fg)', border: '1px solid var(--border-strong)' },
    ghost:   { background: 'transparent', color: 'var(--fg-muted)', border: '1px solid transparent' },
    soft:    { background: 'var(--bg-sunken)', color: 'var(--fg)', border: '1px solid var(--border)' },
    primary: { background: 'var(--accent)', color: 'var(--accent-fg)', border: '1px solid var(--accent)' },
    danger:  { background: 'var(--neg-soft)', color: 'var(--neg)', border: '1px solid color-mix(in oklch, var(--neg) 30%, var(--border))' },
    success: { background: 'var(--pos-soft)', color: 'var(--pos)', border: '1px solid color-mix(in oklch, var(--pos) 30%, var(--border))' },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{
      ...sz, ...kinds[kind],
      display: 'inline-flex', alignItems: 'center', gap: 6, borderRadius: 8,
      fontWeight: 550, letterSpacing: '-0.005em', whiteSpace: 'nowrap',
      opacity: disabled ? 0.5 : 1,
      ...style,
    }}>
      {icon}
      {children}
    </button>
  );
}

// ─── Card / Pill / Badge ─────────────────────────────────────────────────────
function Card({ children, style, padding = 20, title, subtitle, action }) {
  return (
    <section style={{
      background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 14,
      boxShadow: 'var(--shadow-card)', overflow: 'hidden',
      ...style,
    }}>
      {title || action ? (
        <header style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px 10px' }}>
          <div style={{ flex: 1, lineHeight: 1.25 }}>
            {title ? <div style={{ fontSize: 13.5, fontWeight: 600 }}>{title}</div> : null}
            {subtitle ? <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{subtitle}</div> : null}
          </div>
          {action}
        </header>
      ) : null}
      <div style={{ padding: title ? '0 18px 18px' : padding }}>{children}</div>
    </section>
  );
}

function Pill({ tone = 'neutral', children, style, dot }) {
  const tones = {
    neutral: { bg: 'var(--bg-sunken)', fg: 'var(--fg-muted)', border: 'var(--border)' },
    info:    { bg: 'var(--info-soft)', fg: 'var(--info)', border: 'transparent' },
    pos:     { bg: 'var(--pos-soft)', fg: 'var(--pos)', border: 'transparent' },
    neg:     { bg: 'var(--neg-soft)', fg: 'var(--neg)', border: 'transparent' },
    warn:    { bg: 'var(--warn-soft)', fg: 'var(--warn)', border: 'transparent' },
    accent:  { bg: 'var(--accent-soft)', fg: 'var(--accent)', border: 'transparent' },
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: t.bg, color: t.fg, border: `1px solid ${t.border}`,
      fontSize: 11.5, fontWeight: 550, padding: '2px 8px', borderRadius: 999,
      letterSpacing: '-0.005em', whiteSpace: 'nowrap',
      ...style,
    }}>
      {dot ? <span style={{ width: 6, height: 6, borderRadius: 999, background: 'currentColor' }}/> : null}
      {children}
    </span>
  );
}

// Category swatch
function CatSwatch({ cat, size = 18 }) {
  const COLORS = {
    Groceries: 'var(--cat-1)',
    Dining: 'var(--cat-2)',
    Transport: 'var(--cat-3)',
    Leisure: 'var(--cat-4)',
    Utilities: 'var(--cat-5)',
    Subscriptions: 'var(--cat-6)',
    Income: 'var(--pos)',
    Housing: 'oklch(0.62 0.10 60)',
    Health: 'oklch(0.62 0.10 0)',
    Other: 'var(--fg-faint)',
  };
  const ICONS = {
    Groceries: '🛒', Dining: '🍽', Transport: '🚌', Leisure: '🎬',
    Utilities: '💡', Subscriptions: '↻', Income: '↓', Housing: '🏠', Health: '✚',
  };
  // Use letter glyph instead of emoji for clean look
  const letter = (cat || 'O').slice(0, 1).toUpperCase();
  return (
    <span style={{
      width: size, height: size, borderRadius: 6,
      background: `color-mix(in oklch, ${COLORS[cat] || 'var(--fg-faint)'} 18%, var(--bg-elev))`,
      color: COLORS[cat] || 'var(--fg-faint)',
      display: 'grid', placeItems: 'center',
      fontSize: size * 0.55, fontWeight: 700, flex: 'none',
      letterSpacing: 0,
    }}>{letter}</span>
  );
}

// Segmented control
function Segmented({ value, onChange, options, size = 'md' }) {
  const sz = size === 'sm' ? { h: 26, px: 9, fs: 12 } : { h: 32, px: 12, fs: 12.5 };
  return (
    <div style={{
      display: 'inline-flex', padding: 2, gap: 2,
      background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 9,
    }}>
      {options.map((o) => {
        const active = (o.value ?? o) === value;
        return (
          <button key={o.value ?? o} onClick={() => onChange && onChange(o.value ?? o)} style={{
            height: sz.h, padding: `0 ${sz.px}px`, fontSize: sz.fs, fontWeight: active ? 600 : 500,
            color: active ? 'var(--fg)' : 'var(--fg-muted)',
            background: active ? 'var(--bg-elev)' : 'transparent',
            border: 'none', borderRadius: 7,
            boxShadow: active ? 'var(--shadow-card)' : 'none',
            display: 'inline-flex', alignItems: 'center', gap: 5,
          }}>{o.icon}{o.label ?? o}</button>
        );
      })}
    </div>
  );
}

// Status chip for transaction
function StatusChip({ status }) {
  const map = {
    committed: { tone: 'pos', label: 'Committed' },
    pending: { tone: 'neutral', label: 'Pending' },
    planning: { tone: 'accent', label: 'Planning' },
    forecast: { tone: 'info', label: 'Forecast' },
    review: { tone: 'warn', label: 'Needs review' },
  };
  const m = map[status] || map.committed;
  return <Pill tone={m.tone} dot>{m.label}</Pill>;
}

// Account chip — small mono with last4
function AccountChip({ account }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12,
      color: 'var(--fg-muted)',
    }}>
      <span style={{ width: 14, height: 10, background: account.color || 'oklch(0.6 0.1 250)', borderRadius: 2, flex: 'none' }}/>
      {account.name}
      {account.last4 ? <span className="num" style={{ color: 'var(--fg-faint)' }}>·{account.last4}</span> : null}
    </span>
  );
}

// Expose
Object.assign(window, {
  Icon, I, fmtMoney, fmtMoneyCompact, fmtDate, fmtDateLong,
  Sidebar, Topbar, SearchBox, Kbd, Dot, IconBtn,
  Btn, Card, Pill, CatSwatch, Segmented, StatusChip, AccountChip, Logo,
});

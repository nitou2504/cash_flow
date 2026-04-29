// Cash Flow — balance chart with scrubber + transaction row primitive

const { useState: useStateChart, useMemo: useMemoChart, useRef: useRefChart, useEffect: useEffectChart } = React;

// ─── Balance Chart ──────────────────────────────────────────────────────────
// Accepts series of { date, balance, txns? }
// Highlights a hovered/scrubbed point and reports it via onScrub.
function BalanceChart({ series, height = 180, onScrub, scrubIndex, accent = 'var(--accent)', hideAxis = false, mini = false }) {
  const ref = useRefChart(null);
  const [w, setW] = useStateChart(720);
  useEffectChart(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  if (!series || series.length === 0) return <div ref={ref} style={{ height }}/>;

  const pad = mini ? { l: 0, r: 0, t: 8, b: 8 } : { l: 44, r: 16, t: 18, b: 26 };
  const innerW = Math.max(40, w - pad.l - pad.r);
  const innerH = height - pad.t - pad.b;
  const min = Math.min(...series.map(s => s.balance));
  const max = Math.max(...series.map(s => s.balance));
  const span = Math.max(1, max - min);
  const x = (i) => pad.l + (i / Math.max(1, series.length - 1)) * innerW;
  const y = (v) => pad.t + (1 - (v - min) / span) * innerH;

  // Smooth path
  const linePath = series.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(p.balance).toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L ${x(series.length - 1).toFixed(1)} ${pad.t + innerH} L ${pad.l} ${pad.t + innerH} Z`;

  const idx = scrubIndex == null ? series.length - 1 : Math.max(0, Math.min(series.length - 1, scrubIndex));
  const cur = series[idx];

  // Y axis ticks (3)
  const ticks = mini ? [] : [min, min + span / 2, max];

  // Month dividers
  const monthMarks = [];
  let lastMonth = null;
  series.forEach((p, i) => {
    const m = p.date.slice(0, 7);
    if (m !== lastMonth) { monthMarks.push({ i, m, x: x(i) }); lastMonth = m; }
  });

  const handleMove = (e) => {
    if (!onScrub) return;
    const rect = ref.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const ratio = (px - pad.l) / innerW;
    const i = Math.round(ratio * (series.length - 1));
    onScrub(Math.max(0, Math.min(series.length - 1, i)));
  };

  return (
    <div ref={ref} style={{ position: 'relative', width: '100%', height, userSelect: 'none' }} onMouseMove={handleMove}>
      <svg width={w} height={height} style={{ display: 'block', overflow: 'visible' }}>
        <defs>
          <linearGradient id={`bg-${mini ? 'm' : 'l'}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.18"/>
            <stop offset="100%" stopColor={accent} stopOpacity="0"/>
          </linearGradient>
        </defs>

        {/* Grid */}
        {!hideAxis && ticks.map((t, i) => (
          <g key={i}>
            <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeDasharray="2 4"/>
            <text x={pad.l - 8} y={y(t) + 4} textAnchor="end" fontSize="10.5" fontFamily="var(--font-mono)" fill="var(--fg-faint)">${(t/1000).toFixed(1)}k</text>
          </g>
        ))}

        {/* Month dividers */}
        {!hideAxis && monthMarks.map((mm, i) => i === 0 ? null : (
          <g key={mm.m}>
            <line x1={mm.x} x2={mm.x} y1={pad.t} y2={pad.t + innerH} stroke="var(--border)" strokeDasharray="3 5"/>
          </g>
        ))}
        {!hideAxis && monthMarks.map((mm, i) => (
          <text key={mm.m + 'lab'} x={mm.x + 6} y={pad.t + innerH + 16} fontSize="10.5" fontWeight="600" fill="var(--fg-muted)" letterSpacing="0.04em">
            {new Date(mm.m + '-01').toLocaleDateString('en', { month: 'short' }).toUpperCase()}
          </text>
        ))}

        {/* Area + line */}
        <path d={areaPath} fill={`url(#bg-${mini ? 'm' : 'l'})`}/>
        <path d={linePath} fill="none" stroke={accent} strokeWidth={mini ? 1.5 : 2} strokeLinejoin="round" strokeLinecap="round"/>

        {/* Scrub line */}
        {!mini && cur ? (
          <g>
            <line x1={x(idx)} x2={x(idx)} y1={pad.t} y2={pad.t + innerH} stroke={accent} strokeWidth="1" strokeDasharray="3 3" opacity="0.5"/>
            <circle cx={x(idx)} cy={y(cur.balance)} r="5" fill="var(--bg-elev)" stroke={accent} strokeWidth="2"/>
          </g>
        ) : null}
      </svg>

      {/* Floating tooltip */}
      {!mini && cur ? (
        <div style={{
          position: 'absolute',
          left: Math.min(w - 160, Math.max(8, x(idx) - 70)),
          top: 4,
          background: 'var(--bg-elev)', border: '1px solid var(--border)',
          borderRadius: 8, padding: '6px 10px', boxShadow: 'var(--shadow-pop)',
          fontSize: 11.5, lineHeight: 1.3, pointerEvents: 'none',
          minWidth: 140,
        }}>
          <div style={{ color: 'var(--fg-muted)' }}>{fmtDateLong(cur.date)}</div>
          <div className="num" style={{ fontWeight: 600, fontSize: 13, color: 'var(--fg)' }}>${cur.balance.toFixed(2)}</div>
          {cur.txns && cur.txns.length > 0 ? (
            <div style={{ color: 'var(--fg-faint)', fontSize: 11 }}>{cur.txns.length} txn{cur.txns.length > 1 ? 's' : ''}</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// ─── Transaction Row ────────────────────────────────────────────────────────
// Used in timeline, dashboard, review screens.
function TxnRow({ txn, balance, showBalance = false, showAccount = true, compact = false, selected = false, onClick, onViewInvoice }) {
  const acc = ACCOUNT_BY_ID[txn.account];
  const isIncome = txn.amount > 0;
  const isMuted = txn.status === 'pending' || txn.status === 'forecast';
  const isPlanning = txn.status === 'planning';
  const showReview = txn.needs_review;

  return (
    <div onClick={onClick} style={{
      display: 'grid',
      gridTemplateColumns: showBalance ? '78px 1fr 130px 110px 120px 130px' : '78px 1fr 130px 130px 130px',
      alignItems: 'center',
      gap: 12,
      height: 'var(--row-h)', padding: '0 var(--row-px)',
      borderTop: '1px solid var(--border)',
      background: selected ? 'var(--bg-hover)' : 'transparent',
      color: isMuted ? 'var(--fg-muted)' : 'var(--fg)',
      fontStyle: txn.status === 'forecast' || isPlanning ? 'italic' : 'normal',
      cursor: 'pointer',
    }}>
      {/* Date */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className="num" style={{ fontSize: 12.5, color: 'var(--fg-muted)' }}>{fmtDate(txn.date_payed)}</span>
      </div>

      {/* Description + tags */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <CatSwatch cat={txn.category} size={22}/>
        <div style={{ minWidth: 0, lineHeight: 1.25 }}>
          <div style={{ fontSize: 13.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {txn.desc}
            {showReview ? <span style={{ marginLeft: 8 }}><Pill tone="warn" dot>review</Pill></span> : null}
            {isPlanning ? <span style={{ marginLeft: 8 }}><Pill tone="accent">planning</Pill></span> : null}
            {txn.origin_id?.startsWith('inst_') ? <span style={{ marginLeft: 8, color: 'var(--fg-faint)', fontSize: 11.5 }}>installment</span> : null}
          </div>
          {!compact && (txn.source || txn.has_invoice) ? (
            <div style={{ fontSize: 11.5, color: 'var(--fg-faint)', display: 'flex', gap: 8, alignItems: 'center' }}>
              {txn.source ? <span>src: {txn.source}</span> : null}
              {txn.has_invoice ? (
                <button
                  onClick={(e) => { e.stopPropagation(); onViewInvoice && onViewInvoice(txn); }}
                  title="View linked invoice"
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 3,
                    padding: '0 4px', borderRadius: 4,
                    background: 'transparent',
                    color: 'var(--fg-muted)',
                    border: 'none',
                    fontSize: 11.5, fontWeight: 500, letterSpacing: '-0.005em',
                    fontFamily: 'inherit',
                    textDecoration: 'underline',
                    textDecorationColor: 'var(--border-strong)',
                    textUnderlineOffset: 2,
                  }}>
                  invoice
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      {/* Account */}
      {showAccount ? <div><AccountChip account={acc}/></div> : <div/>}

      {/* Category */}
      <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{txn.category}</div>

      {/* Amount */}
      <div className="num" style={{
        textAlign: 'right', fontWeight: 600, fontSize: 13.5,
        color: isIncome ? 'var(--pos)' : 'var(--fg)',
      }}>
        {fmtMoney(txn.amount, { alwaysSign: isIncome })}
      </div>

      {/* Balance */}
      {showBalance ? (
        <div className="num" style={{ textAlign: 'right', fontSize: 13, color: 'var(--fg-muted)' }}>
          {balance != null ? `$${balance.toFixed(2)}` : '—'}
        </div>
      ) : null}
    </div>
  );
}

function budgetName(id) {
  const b = BUDGETS.find(x => x.id === id);
  return b ? b.name : id;
}

// ─── Group divider (Today, Yesterday, Apr 22, ...) ──────────────────────────
function GroupHeader({ label, balance, totalIn, totalOut }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '78px 1fr 130px 110px 120px 130px',
      alignItems: 'center',
      gap: 12,
      padding: '8px var(--row-px)',
      background: 'var(--bg-sunken)',
      borderTop: '1px solid var(--border)',
      fontSize: 11.5, fontWeight: 600,
      color: 'var(--fg-muted)', letterSpacing: '0.03em', textTransform: 'uppercase',
    }}>
      <div>{label}</div>
      <div/>
      <div/>
      <div/>
      <div className="num" style={{ textAlign: 'right', textTransform: 'none', color: 'var(--fg-faint)' }}>
        {totalOut != null ? <span style={{ color: 'var(--neg)' }}>{fmtMoney(-totalOut)}</span> : null}
        {totalIn ? <span style={{ marginLeft: 8, color: 'var(--pos)' }}>+${totalIn.toFixed(2)}</span> : null}
      </div>
      <div className="num" style={{ textAlign: 'right', textTransform: 'none' }}>{balance != null ? `$${balance.toFixed(2)}` : ''}</div>
    </div>
  );
}

// ─── Sparkline (small) ──────────────────────────────────────────────────────
function Sparkline({ values, w = 100, h = 26, color = 'var(--accent)' }) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / span) * h * 0.8 - 2}`).join(' ');
  return (
    <svg width={w} height={h}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}

// ─── Progress bar (budget) ──────────────────────────────────────────────────
function ProgressBar({ value, max, color = 'var(--accent)', height = 6, over }) {
  const pct = Math.min(100, (value / max) * 100);
  const overPct = over ? Math.min(100, ((value - max) / max) * 100) : 0;
  return (
    <div style={{
      width: '100%', height, background: 'var(--bg-sunken)', borderRadius: 999, overflow: 'hidden', display: 'flex',
    }}>
      <div style={{ width: `${pct}%`, background: over ? 'var(--neg)' : color, height: '100%', borderRadius: 999 }}/>
    </div>
  );
}

Object.assign(window, { BalanceChart, TxnRow, GroupHeader, Sparkline, ProgressBar, budgetName });

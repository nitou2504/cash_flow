import { useRef, useState, useEffect } from 'react';
import type { BalancePoint } from '../../api/types';

interface Props {
  series: BalancePoint[];
  height?: number;
  scrubIndex?: number;
  onScrub?: (i: number) => void;
  accent?: string;
  mini?: boolean;
}

function fmtDateLong(d: string): string {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export default function BalanceChart({ series, height = 220, scrubIndex, onScrub, accent = 'var(--accent)', mini = false }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(720);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  if (!series || series.length === 0) return <div ref={ref} style={{ height }} />;

  const pad = mini ? { l: 0, r: 0, t: 8, b: 8 } : { l: 44, r: 16, t: 18, b: 26 };
  const innerW = Math.max(40, w - pad.l - pad.r);
  const innerH = height - pad.t - pad.b;
  const min = Math.min(...series.map(s => s.balance));
  const max = Math.max(...series.map(s => s.balance));
  const span = Math.max(1, max - min);
  const x = (i: number) => pad.l + (i / Math.max(1, series.length - 1)) * innerW;
  const y = (v: number) => pad.t + (1 - (v - min) / span) * innerH;

  const linePath = series.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(p.balance).toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L ${x(series.length - 1).toFixed(1)} ${pad.t + innerH} L ${pad.l} ${pad.t + innerH} Z`;

  const idx = scrubIndex == null ? series.length - 1 : Math.max(0, Math.min(series.length - 1, scrubIndex));
  const cur = series[idx];

  const ticks = mini ? [] : [min, min + span / 2, max];

  const monthMarks: { m: string; xi: number }[] = [];
  let lastMonth = '';
  series.forEach((p, i) => {
    const m = p.date.slice(0, 7);
    if (m !== lastMonth) { monthMarks.push({ m, xi: x(i) }); lastMonth = m; }
  });

  const handleMove = (e: React.MouseEvent) => {
    if (!onScrub || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const ratio = (px - pad.l) / innerW;
    const i = Math.round(ratio * (series.length - 1));
    onScrub(Math.max(0, Math.min(series.length - 1, i)));
  };

  const gradId = mini ? 'bg-m' : 'bg-l';

  return (
    <div ref={ref} style={{ position: 'relative', width: '100%', height, userSelect: 'none' }} onMouseMove={handleMove}>
      <svg width={w} height={height} style={{ display: 'block', overflow: 'visible' }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity={0.18} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </linearGradient>
        </defs>

        {!mini && ticks.map((t, i) => (
          <g key={i}>
            <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeDasharray="2 4" />
            <text x={pad.l - 8} y={y(t) + 4} textAnchor="end" fontSize="10.5" fontFamily="var(--font-mono)" fill="var(--fg-faint)">
              ${(t / 1000).toFixed(1)}k
            </text>
          </g>
        ))}

        {!mini && monthMarks.map((mm, i) => i === 0 ? null : (
          <line key={mm.m} x1={mm.xi} x2={mm.xi} y1={pad.t} y2={pad.t + innerH} stroke="var(--border)" strokeDasharray="3 5" />
        ))}
        {!mini && monthMarks.map(mm => (
          <text key={mm.m + 'lab'} x={mm.xi + 6} y={pad.t + innerH + 16} fontSize="10.5" fontWeight="600" fill="var(--fg-muted)" letterSpacing="0.04em">
            {new Date(mm.m + '-01').toLocaleDateString('en', { month: 'short' }).toUpperCase()}
          </text>
        ))}

        <path d={areaPath} fill={`url(#${gradId})`} />
        <path d={linePath} fill="none" stroke={accent} strokeWidth={mini ? 1.5 : 2} strokeLinejoin="round" strokeLinecap="round" />

        {!mini && cur && (
          <g>
            <line x1={x(idx)} x2={x(idx)} y1={pad.t} y2={pad.t + innerH} stroke={accent} strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />
            <circle cx={x(idx)} cy={y(cur.balance)} r="5" fill="var(--bg-elev)" stroke={accent} strokeWidth="2" />
          </g>
        )}
      </svg>

      {!mini && cur && (
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
          <div className="num" style={{ fontWeight: 600, fontSize: 13, color: 'var(--fg)' }}>
            ${cur.balance.toFixed(2)}
          </div>
        </div>
      )}
    </div>
  );
}

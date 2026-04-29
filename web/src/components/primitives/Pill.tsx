import type { CSSProperties, ReactNode } from 'react';

type Tone = 'neutral' | 'info' | 'pos' | 'neg' | 'warn' | 'accent';

const TONES: Record<Tone, { bg: string; fg: string; border: string }> = {
  neutral: { bg: 'var(--bg-sunken)', fg: 'var(--fg-muted)', border: 'var(--border)' },
  info:    { bg: 'var(--info-soft)', fg: 'var(--info)', border: 'transparent' },
  pos:     { bg: 'var(--pos-soft)', fg: 'var(--pos)', border: 'transparent' },
  neg:     { bg: 'var(--neg-soft)', fg: 'var(--neg)', border: 'transparent' },
  warn:    { bg: 'var(--warn-soft)', fg: 'var(--warn)', border: 'transparent' },
  accent:  { bg: 'var(--accent-soft)', fg: 'var(--accent)', border: 'transparent' },
};

interface Props {
  tone?: Tone;
  dot?: boolean;
  children: ReactNode;
  style?: CSSProperties;
}

export default function Pill({ tone = 'neutral', dot, children, style }: Props) {
  const t = TONES[tone];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: t.bg, color: t.fg, border: `1px solid ${t.border}`,
      fontSize: 11.5, fontWeight: 550, padding: '2px 8px', borderRadius: 999,
      letterSpacing: '-0.005em', whiteSpace: 'nowrap',
      ...style,
    }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: 999, background: 'currentColor' }} />}
      {children}
    </span>
  );
}

import type { CSSProperties, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  style?: CSSProperties;
  padding?: number;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
}

export default function Card({ children, style, padding = 20, title, subtitle, action }: Props) {
  return (
    <section style={{
      background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 14,
      boxShadow: 'var(--shadow-card)', overflow: 'hidden',
      ...style,
    }}>
      {(title || action) && (
        <header style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px 10px' }}>
          <div style={{ flex: 1, lineHeight: 1.25 }}>
            {title && <div style={{ fontSize: 13.5, fontWeight: 600 }}>{title}</div>}
            {subtitle && <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{subtitle}</div>}
          </div>
          {action}
        </header>
      )}
      <div style={{ padding: title ? '0 18px 18px' : padding }}>{children}</div>
    </section>
  );
}

interface Option {
  value: string;
  label: string;
}

interface Props {
  value: string;
  onChange: (v: string) => void;
  options: Option[];
  size?: 'sm' | 'md';
}

export default function Segmented({ value, onChange, options, size = 'md' }: Props) {
  const h = size === 'sm' ? 30 : 34;
  const fs = size === 'sm' ? 12 : 13;
  return (
    <div style={{
      display: 'inline-flex', gap: 2, padding: 3,
      background: 'var(--bg-sunken)', border: '1px solid var(--border)',
      borderRadius: 10,
    }}>
      {options.map(o => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            style={{
              height: h, padding: '0 14px',
              fontSize: fs, fontWeight: active ? 600 : 500,
              color: active ? 'var(--fg)' : 'var(--fg-muted)',
              background: active ? 'var(--bg-elev)' : 'transparent',
              border: active ? '1px solid var(--border)' : '1px solid transparent',
              borderRadius: 8, cursor: 'pointer',
              boxShadow: active ? 'var(--shadow-card)' : 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

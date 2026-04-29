interface Props {
  value: number;
  max: number;
  color?: string;
  height?: number;
}

export default function ProgressBar({ value, max, color = 'var(--accent)', height = 6 }: Props) {
  const pct = Math.min(100, (value / max) * 100);
  const over = value > max;
  return (
    <div style={{
      width: '100%', height, background: 'var(--bg-sunken)', borderRadius: 999, overflow: 'hidden',
    }}>
      <div style={{
        width: `${pct}%`, background: over ? 'var(--neg)' : color,
        height: '100%', borderRadius: 999,
        transition: 'width 0.3s',
      }} />
    </div>
  );
}

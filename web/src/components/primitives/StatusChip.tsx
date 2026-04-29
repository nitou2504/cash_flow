import Pill from './Pill';

const STATUS_MAP: Record<string, { tone: 'pos' | 'neutral' | 'accent' | 'info' | 'warn'; label: string }> = {
  committed: { tone: 'pos', label: 'Committed' },
  pending:   { tone: 'neutral', label: 'Pending' },
  planning:  { tone: 'accent', label: 'Planning' },
  forecast:  { tone: 'info', label: 'Forecast' },
};

export default function StatusChip({ status }: { status: string }) {
  const m = STATUS_MAP[status] || STATUS_MAP.committed;
  return <Pill tone={m.tone} dot>{m.label}</Pill>;
}

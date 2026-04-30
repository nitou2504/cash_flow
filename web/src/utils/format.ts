export function fmtMoney(n: number, opts?: { alwaysSign?: boolean }): string {
  const sign = n < 0 ? '−' : opts?.alwaysSign && n > 0 ? '+' : '';
  const v = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${sign}$${v}`;
}

export function fmtMoneyCompact(n: number): string {
  const sign = n < 0 ? '−' : '';
  const a = Math.abs(n);
  if (a >= 1000) return `${sign}$${(a / 1000).toFixed(1)}k`;
  return `${sign}$${a.toFixed(0)}`;
}

function parseDate(d: string): Date {
  return d.includes('T') ? new Date(d) : new Date(d + 'T00:00:00');
}

export function fmtDate(d: string): string {
  return parseDate(d).toLocaleDateString('en-US', { month: 'short', day: '2-digit' });
}

export function fmtDateLong(d: string): string {
  return parseDate(d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

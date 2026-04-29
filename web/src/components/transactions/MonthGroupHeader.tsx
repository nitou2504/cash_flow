import { fmtMoney } from '../../utils/format';

interface Props {
  label: string;
  totalIn: number;
  totalOut: number;
  balance?: number | null;
  momChange?: number | null;
  monthSpending?: number | null;
  showBalance: boolean;
}

export default function MonthGroupHeader({ label, totalIn, totalOut, balance, momChange, monthSpending, showBalance }: Props) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 14,
      padding: '10px var(--row-px)',
      background: 'var(--bg-sunken)',
      borderTop: '2px solid var(--border)',
      borderBottom: '1px solid var(--border)',
    }}>
      <span style={{ fontSize: 13, fontWeight: 650, letterSpacing: '-0.01em', flex: 1 }}>
        {label}
      </span>

      {totalIn > 0 && (
        <span className="num" style={{ fontSize: 11.5, color: 'var(--pos)', fontWeight: 550 }}>
          ↑ {fmtMoney(totalIn)}
        </span>
      )}
      {totalOut > 0 && (
        <span className="num" style={{ fontSize: 11.5, color: 'var(--fg-muted)', fontWeight: 550 }}>
          ↓ {fmtMoney(totalOut)}
        </span>
      )}

      {showBalance && balance != null && (
        <span className="num" style={{ fontSize: 11.5, fontWeight: 600, minWidth: 90, textAlign: 'right' }}>
          {fmtMoney(balance)}
        </span>
      )}

      {momChange != null && momChange !== 0 && (
        <span className="num" style={{
          fontSize: 11, fontWeight: 550, padding: '1px 7px', borderRadius: 6,
          background: momChange > 0 ? 'var(--pos-soft)' : 'var(--neg-soft)',
          color: momChange > 0 ? 'var(--pos)' : 'var(--neg)',
        }}>
          {momChange > 0 ? '+' : ''}{fmtMoney(momChange)}
        </span>
      )}

      {monthSpending != null && (
        <span className="num" style={{ fontSize: 11.5, color: 'var(--neg)', fontWeight: 550 }}>
          Spent: {fmtMoney(monthSpending)}
        </span>
      )}
    </div>
  );
}

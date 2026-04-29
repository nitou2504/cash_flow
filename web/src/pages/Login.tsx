import { useState, type FormEvent } from 'react';
import { useAuth } from '../hooks/useAuth';

export default function Login() {
  const { login } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(password);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed';
      setError(msg);
      setLoading(false);
    }
  }

  return (
    <div style={{
      height: '100%', display: 'grid', placeItems: 'center',
      background: 'var(--bg)',
    }}>
      <form onSubmit={handleSubmit} style={{
        width: 360, padding: 32,
        background: 'var(--bg-elev)', border: '1px solid var(--border)',
        borderRadius: 16, boxShadow: 'var(--shadow-pop)',
        display: 'flex', flexDirection: 'column', gap: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'var(--accent)', display: 'grid', placeItems: 'center',
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 17l6-6 4 4 8-9"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 650, letterSpacing: '-0.02em' }}>Cash Flow</div>
            <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>Personal Finance</div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, fontWeight: 550, color: 'var(--fg-muted)' }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Enter password"
            autoFocus
            style={{
              padding: '10px 14px', fontSize: 14,
              background: 'var(--bg-sunken)', border: '1px solid var(--border)',
              borderRadius: 10, color: 'var(--fg)', outline: 'none',
              transition: 'border-color 0.15s',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--accent)'}
            onBlur={e => e.target.style.borderColor = 'var(--border)'}
          />
        </div>

        {error && (
          <div style={{
            padding: '8px 12px', fontSize: 13, fontWeight: 500,
            background: 'var(--neg-soft)', color: 'var(--neg)',
            borderRadius: 8, border: '1px solid color-mix(in oklch, var(--neg) 20%, var(--border))',
          }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={loading || !password} style={{
          padding: '10px 0', fontSize: 14, fontWeight: 600,
          background: 'var(--accent)', color: 'var(--accent-fg)',
          border: '1px solid var(--accent)', borderRadius: 10,
          opacity: loading || !password ? 0.6 : 1,
          letterSpacing: '-0.005em',
        }}>
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}

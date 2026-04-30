import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import Shell from './components/layout/Shell';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Review from './pages/Review';
import Settings from './pages/Settings';
import { api } from './api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: false },
  },
});

function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<'loading' | 'ok' | 'unauth'>('loading');

  useEffect(() => {
    api.me().then(() => setState('ok')).catch(() => setState('unauth'));
  }, []);

  if (state === 'loading') return null;
  if (state === 'unauth') return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<AuthGate><Shell /></AuthGate>}>
            <Route index element={<Dashboard />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="review" element={<Review />} />
            <Route path="accounts" element={<Placeholder title="Accounts" />} />
            <Route path="categories" element={<Placeholder title="Categories" />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <div style={{ padding: 28 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600 }}>{title}</h2>
      <p style={{ color: 'var(--fg-muted)', marginTop: 8 }}>Coming soon</p>
    </div>
  );
}

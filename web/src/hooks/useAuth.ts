import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

export function useAuth() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.me()
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false));
  }, []);

  const login = useCallback(async (password: string) => {
    await api.login(password);
    setAuthenticated(true);
    navigate('/');
  }, [navigate]);

  const logout = useCallback(async () => {
    await api.logout();
    setAuthenticated(false);
    navigate('/login');
  }, [navigate]);

  return { authenticated, login, logout };
}

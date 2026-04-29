const BASE = '/api';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'same-origin',
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });

  if (res.status === 401) {
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new ApiError(401, 'Unauthorized');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  return res.json();
}

export const api = {
  login: (password: string) =>
    request<{ ok: boolean }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),

  logout: () =>
    request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),

  me: () =>
    request<{ authenticated: boolean }>('/auth/me'),

  dashboard: () =>
    request<import('./types').DashboardData>('/dashboard'),

  transactions: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<import('./types').Transaction[]>(`/transactions${qs}`);
  },

  transaction: (id: number) =>
    request<import('./types').Transaction>(`/transactions/${id}`),

  transactionGroup: (id: number) =>
    request<import('./types').Transaction[]>(`/transactions/${id}/group`),

  accounts: () =>
    request<import('./types').Account[]>('/accounts'),

  categories: () =>
    request<import('./types').Category[]>('/categories'),

  budgets: () =>
    request<import('./types').Subscription[]>('/budgets'),

  budgetSpending: (month?: string) => {
    const qs = month ? `?month=${month}` : '';
    return request<import('./types').BudgetSpending[]>(`/budgets/spending${qs}`);
  },

  reviewList: (source?: string) => {
    const qs = source ? `?source=${source}` : '';
    return request<import('./types').Transaction[]>(`/review${qs}`);
  },

  reviewContext: (id: number) =>
    request<import('./types').ReviewItem>(`/review/${id}/context`),

  invoice: (id: number) =>
    request<import('./types').Invoice>(`/invoices/${id}`),

  invoiceByTransaction: (txnId: number) =>
    request<import('./types').Invoice>(`/invoices/by-transaction/${txnId}`),

  timeline: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<import('./types').TimelineResponse>(`/transactions/timeline${qs}`);
  },

  createTransaction: (body: import('./types').TransactionCreate) =>
    request<import('./types').TransactionCreateResponse>('/transactions', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  previewTransaction: (body: import('./types').TransactionCreate) =>
    request<import('./types').Transaction[]>('/transactions/preview', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

export { ApiError };

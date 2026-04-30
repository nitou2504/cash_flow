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

  approveReview: (id: number) =>
    request<{ ok: boolean }>(`/review/${id}/approve`, { method: 'POST' }),

  approveReviewBatch: (ids: number[]) =>
    request<{ approved: number }>('/review/approve-batch', {
      method: 'POST',
      body: JSON.stringify({ ids }),
    }),

  invoice: (id: number) =>
    request<import('./types').Invoice>(`/invoices/${id}`),

  invoiceByTransaction: (txnId: number) =>
    request<import('./types').Invoice>(`/invoices/by-transaction/${txnId}`),

  timeline: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<import('./types').TimelineResponse>(`/transactions/timeline${qs}`);
  },

  parseTransaction: (
    text: string,
    onStep?: (step: string, label: string) => void,
  ): Promise<Record<string, unknown>> =>
    new Promise((resolve, reject) => {
      fetch(`${BASE}/transactions/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      }).then(res => {
        if (!res.ok || !res.body) {
          res.json().then(d => reject(new ApiError(res.status, d.detail || 'Parse failed'))).catch(() => reject(new ApiError(res.status, 'Parse failed')));
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        function read(): void {
          reader.read().then(({ done, value }) => {
            if (done) { reject(new ApiError(500, 'Stream ended without result')); return; }
            buf += decoder.decode(value, { stream: true });
            const lines = buf.split('\n');
            buf = lines.pop() || '';
            let eventName = '';
            for (const line of lines) {
              if (line.startsWith('event: ')) eventName = line.slice(7);
              else if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                if (eventName === 'step') onStep?.(data.step, data.label);
                else if (eventName === 'done') { resolve(data.result); return; }
                else if (eventName === 'error') { reject(new ApiError(422, data.detail)); return; }
              }
            }
            read();
          });
        }
        read();
      }).catch(err => reject(err));
    }),

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

  updateTransaction: (id: number, body: import('./types').TransactionUpdate) =>
    request<import('./types').Transaction>(`/transactions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteTransaction: (id: number, deleteGroup = false) =>
    request<{ ok: boolean }>(`/transactions/${id}?delete_group=${deleteGroup}`, {
      method: 'DELETE',
    }),

  clearTransaction: (id: number) =>
    request<import('./types').Transaction>(`/transactions/${id}/clear`, {
      method: 'POST',
    }),

  convertTransaction: (id: number, body: import('./types').TransactionCreate) =>
    request<import('./types').TransactionCreateResponse>(`/transactions/${id}/convert`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

export { ApiError };

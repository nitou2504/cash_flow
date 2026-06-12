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

  searchTransactions: (params: Record<string, string>) => {
    const qs = '?' + new URLSearchParams(params).toString();
    return request<import('./types').SearchResponse>(`/transactions/search${qs}`);
  },

  transaction: (id: number) =>
    request<import('./types').Transaction>(`/transactions/${id}`),

  transactionGroup: (id: number) =>
    request<import('./types').Transaction[]>(`/transactions/${id}/group`),

  budgetExpenses: (id: number) =>
    request<import('./types').BudgetExpensesResponse>(`/transactions/${id}/budget-expenses`),

  accounts: () =>
    request<import('./types').Account[]>('/accounts'),

  categories: () =>
    request<import('./types').Category[]>('/categories'),

  budgets: () =>
    request<import('./types').Subscription[]>('/budgets'),

  subscriptions: () =>
    request<import('./types').Subscription[]>('/subscriptions'),

  createSubscription: (body: import('./types').SubscriptionCreate) =>
    request<import('./types').Subscription>('/subscriptions', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSubscription: (id: string, body: import('./types').SubscriptionUpdate) =>
    request<import('./types').Subscription>(`/subscriptions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteSubscription: (id: string) =>
    request<{ ok: boolean }>(`/subscriptions/${id}`, { method: 'DELETE' }),

  balancePreview: (account: string, asOfDate?: string) =>
    request<import('./types').BalancePreview>(
      `/fixes/balance-preview?account=${encodeURIComponent(account)}${asOfDate ? `&as_of_date=${asOfDate}` : ''}`,
    ),

  fixBalance: (body: { actual_balance: number; account: string; as_of_date?: string }) =>
    request<{ ok: boolean; adjustment: number }>('/fixes/balance', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  fixStatement: (body: { account: string; statement_amount: number; month?: string }) =>
    request<import('./types').StatementFixResult>('/fixes/statement', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

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

  deleteReviewBatch: (ids: number[]) =>
    request<{ deleted: number }>('/review/delete-batch', {
      method: 'POST',
      body: JSON.stringify({ ids }),
    }),

  approveReviewBatch: (ids: number[]) =>
    request<{ approved: number }>('/review/approve-batch', {
      method: 'POST',
      body: JSON.stringify({ ids }),
    }),

  invoice: (id: number) =>
    request<import('./types').Invoice>(`/invoices/${id}`),

  invoiceByTransaction: (txnId: number) =>
    request<import('./types').Invoice>(`/invoices/by-transaction/${txnId}`),

  unmatchedInvoices: (cardOnly?: boolean) =>
    request<import('./types').Invoice[]>(`/invoices/unmatched${cardOnly ? '?card_only=true' : ''}`),

  invoiceCandidates: (invoiceId: number, windowDays?: number) =>
    request<import('./types').Consumo[]>(
      `/invoices/${invoiceId}/candidates${windowDays ? `?window_days=${windowDays}` : ''}`),

  linkInvoice: (invoiceId: number, consumoId: number) =>
    request<{ ok: boolean }>(`/invoices/${invoiceId}/link`, {
      method: 'POST',
      body: JSON.stringify({ consumo_id: consumoId }),
    }),

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

  gmailStatus: () =>
    request<import('./types').GmailStatus>('/gmail/status'),

  gmailSaveCredentials: (body: { client_id: string; client_secret: string; project_id?: string }) =>
    request<{ ok: boolean }>('/gmail/credentials', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  gmailDeleteCredentials: () =>
    request<{ ok: boolean }>('/gmail/credentials', { method: 'DELETE' }),

  gmailAuthUrl: () =>
    request<{ auth_url: string }>('/gmail/auth-url'),

  gmailDisconnect: () =>
    request<{ ok: boolean }>('/gmail/disconnect', { method: 'POST' }),

  syncStatus: () =>
    request<import('./types').SyncStatus>('/sync/status'),

  syncTrigger: () =>
    request<import('./types').SyncSummary>('/sync/trigger', { method: 'POST' }),

  syncUnparsed: () =>
    request<import('./types').UnparsedResponse>('/sync/unparsed'),

  registerRulesGet: () =>
    request<import('./types').RegisterRules>('/settings/register-rules'),

  registerRulesSave: (body: import('./types').RegisterRules) =>
    request<{ ok: boolean }>('/settings/register-rules', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  classificationHintsGet: () =>
    request<import('./types').ClassificationHints>('/settings/classification-hints'),

  classificationHintsSave: (body: import('./types').ClassificationHints) =>
    request<{ ok: boolean }>('/settings/classification-hints', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  llmConfigGet: () =>
    request<import('./types').LLMConfig>('/settings/llm-config'),

  llmConfigSave: (body: import('./types').LLMConfig) =>
    request<{ ok: boolean }>('/settings/llm-config', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
};

export { ApiError };

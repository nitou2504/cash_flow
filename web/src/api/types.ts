export interface Account {
  account_id: string;
  account_type: string;
  cut_off_day: number | null;
  payment_day: number | null;
}

export interface Category {
  name: string;
  description: string | null;
}

export interface Transaction {
  id: number;
  description: string;
  amount: number;
  date_created: string;
  date_payed: string;
  category: string | null;
  account: string;
  status: string;
  budget: string | null;
  origin_id: string | null;
  source: string | null;
  needs_review: boolean;
  running_balance: number | null;
}

export interface BalancePoint {
  date: string;
  balance: number;
}

export interface BudgetSpending {
  id: string;
  name: string;
  monthly_amount: number;
  payment_account_id: string;
  category: string;
  allocated: number;
  spent: number;
  remaining: number;
  reachable_via: string[];
}

export interface BudgetExpensesResponse {
  budget_id: string;
  budget_name: string;
  month: string;
  allocated: number;
  spent: number;
  remaining: number;
  expenses: TimelineTransaction[];
  card_affects: string[];
}

export interface Subscription {
  id: string;
  name: string;
  category: string;
  monthly_amount: number;
  payment_account_id: string;
  is_budget: boolean;
  is_income: boolean;
  underspend_behavior: string;
  status: string | null;
}

export interface CCCard {
  name: string;
  account_type: string;
  current_cycle_owed: number;
  current_cycle_date: string | null;
  next_cycle_owed: number;
  next_cycle_date: string | null;
  total_owed: number;
  cut_off_day: number | null;
  payment_day: number | null;
}

export interface DashboardData {
  accounts: Account[];
  balance_series: BalancePoint[];
  budgets: BudgetSpending[];
  review_count: number;
  recent_transactions: Transaction[];
  cc_cards: CCCard[];
  current_balance: number;
  projected_balance: number;
  cc_debt: number;
  total_budget: number;
  month_income: number;
  month_expenses: number;
}

export interface InvoiceLine {
  line_number: number;
  sku: string | null;
  description: string;
  quantity: number;
  unit_price: number;
  discount: number;
  line_subtotal: number;
  line_tax: number;
  line_total: number;
  tax_rate: number | null;
}

export interface InvoiceTax {
  tax_code: number;
  rate_code: number;
  rate_pct: number;
  base_imponible: number;
  tax_value: number;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  doc_type: string;
  ruc: string;
  vendor: string;
  vendor_trade_name?: string | null;
  issue_date: string;
  subtotal_sin_impuesto: number;
  total_descuento: number;
  propina: number;
  total: number;
  currency?: string;
  forma_pago?: number | null;
  merchant_name?: string | null;
  store_address?: string | null;
  lines?: InvoiceLine[];
  taxes?: InvoiceTax[];
}

export interface Consumo {
  id: number;
  msg_id: string;
  bank: string;
  account: string;
  purchased_at: string;
  amount: number;
  merchant: string;
  card_last: string | null;
  matched_invoice_number: string | null;
  registered_txn_id: number | null;
}

export interface ReviewItem {
  transaction: Transaction;
  consumo: Consumo | null;
  invoice: Invoice | null;
  llm_decision: Record<string, unknown> | null;
}

// Timeline

export interface TimelineTransaction extends Transaction {
  is_budget_allocation: boolean;
  has_invoice: boolean;
}

export interface MonthGroup {
  month_key: string;
  month_label: string;
  transactions: TimelineTransaction[];
  mom_change: number | null;
  month_spending: number | null;
  total_in: number;
  total_out: number;
}

export interface TimelineStats {
  mom_change: number;
  forecast_end: number;
  lowest_in_period: number;
}

export interface TimelineResponse {
  pending_from_past: TimelineTransaction[];
  starting_balance: number | null;
  months: MonthGroup[];
  balance_series: BalancePoint[];
  stats: TimelineStats;
}

// Transaction creation

export interface SplitItem {
  amount: number;
  category?: string | null;
  budget?: string | null;
}

export interface TransactionCreate {
  description: string;
  amount: number;
  account: string;
  category?: string | null;
  budget?: string | null;
  date?: string | null;
  is_income?: boolean;
  status?: string;
  needs_review?: boolean;
  installments?: number | null;
  grace_period_months?: number;
  start_from_installment?: number;
  splits?: SplitItem[] | null;
}

export interface TransactionCreateResponse {
  count: number;
  ids: number[];
  transactions: Transaction[];
}

export interface TransactionUpdate {
  description?: string;
  amount?: number;
  category?: string | null;
  budget?: string | null;
  date?: string | null;
  status?: string;
  account?: string;
  needs_review?: number;
}

// Search

export interface SearchFilters {
  account?: string;
  category?: string;
  statuses?: string[];
  budget?: string;
  from_date?: string;
  to_date?: string;
  min_amount?: string;
  max_amount?: string;
  date_field?: 'date_payed' | 'date_created';
}

export interface SearchResponse {
  results: TimelineTransaction[];
  total: number;
  limit: number;
  offset: number;
}

// Gmail

export interface GmailStatus {
  has_credentials: boolean;
  connected: boolean;
  valid?: boolean;
  expired?: boolean;
  expiry?: string;
  redirect_uri?: string;
}

// Settings

export interface SyncSummary {
  consumos_ingested: number;
  invoices_ingested: number;
  invoices_matched: number;
  registered: number;
  enriched: number;
  by_method: Record<string, number>;
  errors: string[];
}

export interface SyncStatus {
  last_run: string | null;
  summary: SyncSummary | null;
  running: boolean;
  next_run: string | null;
}

export interface UnparsedItem {
  id: number;
  msg_id: string;
  label: string;
  subject: string | null;
  received_at: string | null;
  reason: string;
  from_addr: string | null;
  resolved: number;
}

export interface UnparsedResponse {
  count: number;
  items: UnparsedItem[];
}

export interface MerchantRule {
  pattern: string;
  category: string;
  desc?: string | null;
}

export interface TransferDestination {
  account_suffix: string;
  name: string;
}

export interface ItemOverride {
  keywords: string[];
  category: string;
}

export interface RegisterRules {
  llm_model: string;
  merchant_rules: MerchantRule[];
  transfer_destinations: TransferDestination[];
  item_overrides: ItemOverride[];
}

export interface ClassificationHints {
  category_hints: string[];
  user_hints: string[];
  category_budget_map: Record<string, string>;
}

export interface FunctionModel {
  provider: string;
  model: string;
  reason?: string | null;
}

export interface LLMProvider {
  type: string;
  api_key_env?: string | null;
  base_url?: string | null;
  models: string[];
}

export interface LLMConfig {
  default_provider: string;
  default_model: string;
  providers: Record<string, LLMProvider>;
  function_models: Record<string, FunctionModel>;
  timeout_seconds: number;
  max_retries: number;
  temperature: number;
}

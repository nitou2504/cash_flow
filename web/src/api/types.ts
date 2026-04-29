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
}

export interface Subscription {
  id: string;
  name: string;
  amount: number;
  account: string;
  category: string;
  is_budget: boolean;
  monthly_amount: number | null;
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
  id: number;
  invoice_id: number;
  line_number: number;
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
}

export interface InvoiceTax {
  id: number;
  invoice_id: number;
  tax_code: string;
  tax_percent: number;
  base_amount: number;
  tax_amount: number;
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
  forma_pago?: string | null;
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

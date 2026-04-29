from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, field_validator


class AccountOut(BaseModel):
    account_id: str
    account_type: str
    cut_off_day: Optional[int] = None
    payment_day: Optional[int] = None


class CategoryOut(BaseModel):
    name: str
    description: str


class TransactionOut(BaseModel):
    id: int
    date_created: str
    date_payed: str
    description: str
    account: Optional[str] = None
    amount: float
    category: Optional[str] = None
    budget: Optional[str] = None
    status: str
    origin_id: Optional[str] = None
    source: Optional[str] = None
    needs_review: int = 0
    running_balance: Optional[float] = None


class SubscriptionOut(BaseModel):
    id: str
    name: str
    category: str
    monthly_amount: float
    payment_account_id: str
    start_date: str
    end_date: Optional[str] = None
    is_budget: bool = False
    is_income: bool = False
    underspend_behavior: str = "keep"
    status: Optional[str] = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def coerce_date(cls, v: Union[str, object, None]) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class BudgetSpending(BaseModel):
    id: str
    name: str
    monthly_amount: float
    payment_account_id: str
    category: str
    allocated: float
    spent: float
    remaining: float


class BalancePoint(BaseModel):
    date: str
    balance: float


class CCCardOut(BaseModel):
    name: str
    account_type: str
    current_cycle_owed: float
    current_cycle_date: Optional[str] = None
    next_cycle_owed: float
    next_cycle_date: Optional[str] = None
    total_owed: float
    cut_off_day: Optional[int] = None
    payment_day: Optional[int] = None


class DashboardOut(BaseModel):
    accounts: list[AccountOut]
    balance_series: list[BalancePoint]
    budgets: list[BudgetSpending]
    review_count: int
    recent_transactions: list[TransactionOut]
    cc_cards: list[CCCardOut]
    current_balance: float
    projected_balance: float
    cc_debt: float
    total_budget: float
    month_income: float
    month_expenses: float


class InvoiceLineOut(BaseModel):
    line_number: int
    sku: Optional[str] = None
    description: str
    quantity: float
    unit_price: float
    discount: float = 0
    line_subtotal: float
    line_tax: float = 0
    line_total: float
    tax_rate: Optional[float] = None


class InvoiceTaxOut(BaseModel):
    tax_code: int
    rate_code: int
    rate_pct: float
    base_imponible: float
    tax_value: float


class InvoiceOut(BaseModel):
    id: int
    invoice_number: str
    doc_type: str
    ruc: str
    vendor: str
    vendor_trade_name: Optional[str] = None
    issue_date: str
    subtotal_sin_impuesto: float
    total_descuento: float = 0
    propina: float = 0
    total: float
    currency: str = "USD"
    forma_pago: Optional[int] = None
    merchant_name: Optional[str] = None
    store_address: Optional[str] = None
    lines: list[InvoiceLineOut] = []
    taxes: list[InvoiceTaxOut] = []


class ConsumoOut(BaseModel):
    id: int
    msg_id: str
    bank: str
    account: str
    purchased_at: str
    amount: float
    merchant: str
    card_last: Optional[str] = None
    matched_invoice_number: Optional[str] = None
    registered_txn_id: Optional[int] = None


class ReviewItemOut(BaseModel):
    transaction: TransactionOut
    consumo: Optional[ConsumoOut] = None
    invoice: Optional[InvoiceOut] = None
    llm_decision: Optional[dict] = None


# ── Timeline ──

class TimelineTransaction(TransactionOut):
    is_budget_allocation: bool = False
    has_invoice: bool = False


class MonthGroup(BaseModel):
    month_key: str
    month_label: str
    transactions: list[TimelineTransaction] = []
    mom_change: Optional[float] = None
    month_spending: Optional[float] = None
    total_in: float = 0
    total_out: float = 0


class TimelineStats(BaseModel):
    mom_change: float = 0
    forecast_end: float = 0
    lowest_in_period: float = 0


class TimelineResponse(BaseModel):
    pending_from_past: list[TimelineTransaction] = []
    starting_balance: Optional[float] = None
    months: list[MonthGroup] = []
    balance_series: list[BalancePoint] = []
    stats: TimelineStats = TimelineStats()


# ── Transaction creation ──

class SplitItem(BaseModel):
    amount: float
    category: Optional[str] = None
    budget: Optional[str] = None


class TransactionCreate(BaseModel):
    description: str
    amount: float
    account: str
    category: Optional[str] = None
    budget: Optional[str] = None
    date: Optional[str] = None
    is_income: bool = False
    status: str = "committed"
    installments: Optional[int] = None
    grace_period_months: int = 0
    start_from_installment: int = 1
    splits: Optional[list[SplitItem]] = None


class TransactionCreateResponse(BaseModel):
    count: int
    ids: list[int]
    transactions: list[TransactionOut]

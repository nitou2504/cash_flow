import uuid
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from dateutil.relativedelta import relativedelta


def _generate_origin_id() -> str:
    """
    Creates a unique ID for linking related transactions.
    """
    return f"{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

def _calculate_credit_card_payment_date(
    transaction_date: date, cut_off_day: int, payment_day: int
) -> date:
    """
    Calculates the correct payment date for a credit card transaction by
    determining if it's a same-month or next-month payment cycle.
    """
    # Case 1: Same-month payment cycle (e.g., cut on 14th, pay on 25th)
    if payment_day > cut_off_day:
        if transaction_date.day >= cut_off_day:
            # Purchase is on or after cut-off, so it's on next month's bill
            payment_date = transaction_date + relativedelta(months=1)
            return payment_date.replace(day=payment_day)
        else:
            # Purchase is before cut-off, so it's on this month's bill
            return transaction_date.replace(day=payment_day)
    
    # Case 2: Next-month payment cycle (e.g., cut on 30th, pay on 15th)
    else:  # payment_day <= cut_off_day
        if transaction_date.day > cut_off_day:
            # Purchase is after cut-off, bill is month+1, payment is month+2
            payment_date = transaction_date + relativedelta(months=2)
            return payment_date.replace(day=payment_day)
        else:
            # Purchase is before cut-off, bill is this month, payment is month+1
            payment_date = transaction_date + relativedelta(months=1)
            return payment_date.replace(day=payment_day)

def _create_base_transaction(
    description: str,
    amount: float,
    category: Optional[str],
    budget: Optional[str],
    transaction_date: date,
    is_pending: bool = False,
    is_planning: bool = False,
) -> Dict[str, Any]:
    """
    A private factory function to construct the common fields for any transaction.
    """
    status = "committed"
    if is_pending:
        status = "pending"
    elif is_planning:
        status = "planning"
        
    return {
        "date_created": transaction_date,
        "description": description,
        "amount": amount,
        "category": category,
        "budget": budget,
        "status": status,
        "origin_id": None,
    }

def create_single_transaction(
    description: str,
    amount: float,
    category: Optional[str],
    budget: Optional[str],
    account: Dict[str, Any],
    transaction_date: date,
    grace_period_months: int = 0,
    is_income: bool = False,
    is_pending: bool = False,
    is_planning: bool = False,
) -> Dict[str, Any]:
    """
    Creates one complete transaction, handling logic for cash and credit cards.
    """
    final_amount = abs(amount) if is_income else -abs(amount)
    transaction = _create_base_transaction(
        description, final_amount, category, budget, transaction_date, is_pending, is_planning
    )
    transaction["account"] = account.get("account_id")

    # Apply grace period if any
    effective_date = transaction_date + relativedelta(months=grace_period_months)

    if account.get("account_type") == "credit_card":
        transaction["date_payed"] = _calculate_credit_card_payment_date(
            effective_date, account["cut_off_day"], account["payment_day"]
        )
    else:
        transaction["date_payed"] = effective_date

    return transaction

def create_installment_transactions(
    description: str,
    total_amount: float,
    installments: int,
    category: Optional[str],
    budget: Optional[str],
    account: Dict[str, Any],
    transaction_date: date,
    grace_period_months: int = 0,
    start_from_installment: int = 1,
    total_installments: Optional[int] = None,
    is_income: bool = False,
    is_pending: bool = False,
    is_planning: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generates a list of transactions for a purchase made in installments.
    """
    origin_id = _generate_origin_id()
    
    # If total_installments isn't specified, it's a new plan, so the total is simply the number of installments.
    final_total_installments = total_installments if total_installments is not None else installments
    
    # The amount per installment is always based on the total plan, not the number of transactions being created.
    installment_amount = round(total_amount / final_total_installments, 2)
    final_amount = abs(installment_amount) if is_income else -abs(installment_amount)
    
    transactions = []

    for i in range(installments):
        current_installment_num = start_from_installment + i
        
        # Safety break to prevent creating more installments than the plan allows.
        if total_installments is not None and current_installment_num > total_installments:
            break
            
        installment_description = f"{description} ({current_installment_num}/{final_total_installments})"
        
        future_billing_date = transaction_date + relativedelta(months=i + grace_period_months)

        transaction = _create_base_transaction(
            description=installment_description,
            amount=final_amount,
            category=category,
            budget=budget,
            transaction_date=transaction_date, # The purchase date is the same for all
            is_pending=is_pending,
            is_planning=is_planning,
        )
        transaction["account"] = account.get("account_id")
        transaction["origin_id"] = origin_id

        if account.get("account_type") == "credit_card":
            transaction["date_payed"] = _calculate_credit_card_payment_date(
                future_billing_date, account["cut_off_day"], account["payment_day"]
            )
        else:
            transaction["date_payed"] = future_billing_date
        
        transactions.append(transaction)

    return transactions

def create_split_transactions(
    description: str,
    splits: List[Dict[str, Any]],
    account: Dict[str, Any],
    transaction_date: date,
    is_income: bool = False,
    is_pending: bool = False,
    is_planning: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generates a list of transactions for a split purchase.
    """
    origin_id = _generate_origin_id()
    transactions = []
    for split in splits:
        transaction = create_single_transaction(
            description=description,
            amount=split["amount"],
            category=split["category"],
            budget=split.get("budget"),
            account=account,
            transaction_date=transaction_date,
            is_income=is_income,
            is_pending=is_pending,
            is_planning=is_planning,
        )
        transaction["origin_id"] = origin_id
        transactions.append(transaction)
    return transactions

def create_recurrent_transactions(
    subscription: Dict[str, Any],
    account: Dict[str, Any],
    start_period: date,
    end_period: date,
    initial_amounts: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Generates a list of forecast transaction dictionaries for a given
    subscription over a specified period.
    """
    transactions = []
    current_date = start_period
    initial_amounts = initial_amounts or {}

    while current_date <= end_period:
        # Set the transaction day to the subscription's start day
        transaction_day = subscription["start_date"].day
        # handle cases where the day is invalid for the month (e.g. 31 in Feb)
        try:
            transaction_date = date(current_date.year, current_date.month, transaction_day)
        except ValueError:
            # This logic gets the last day of the month
            transaction_date = date(current_date.year, current_date.month + 1, 1) - timedelta(days=1)


        if transaction_date >= start_period and transaction_date <= end_period:
            # For budgets, check if there's a pre-calculated starting amount
            month_key = transaction_date.strftime("%Y-%m")
            amount = initial_amounts.get(month_key, subscription["monthly_amount"])

            trans = create_single_transaction(
                description=subscription["name"],
                amount=amount,
                category=subscription["category"],
                budget=None,  # Default to None
                account=account,
                transaction_date=transaction_date,
                is_income=subscription.get("is_income", False),
            )
            
            # Override fields for forecast
            trans["status"] = "forecast"
            trans["origin_id"] = subscription["id"]
            if subscription.get("is_budget"):
                trans["budget"] = subscription["id"]
            
            transactions.append(trans)

        current_date += relativedelta(months=1)
        
    return transactions

def create_budget_release_transaction(
    budget_id: str,
    budget_name: str,
    release_amount: float,
    account: Dict[str, Any],
    month_date: date,
) -> Dict[str, Any]:
    """
    Creates a positive 'Budget Release' transaction for underspent funds.
    """
    description = f"{budget_name} Budget Release {month_date.strftime('%Y-%m')}"
    return {
        "date_created": month_date,
        "date_payed": month_date,
        "description": description,
        "account": account.get("account_id"),
        "amount": abs(release_amount),  # Ensure amount is positive
        "category": "Budget Release",
        "budget": budget_id,
        "status": "committed",
        "origin_id": budget_id,
    }
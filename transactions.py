
import uuid
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

def _generate_origin_id() -> str:
    """
    Creates a unique ID for linking related transactions.
    """
    return f"{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

def _calculate_credit_card_payment_date(
    transaction_date: date, cut_off_day: int, payment_day: int
) -> date:
    """
    Calculates the correct payment date for a credit card transaction.
    """
    if transaction_date.day >= cut_off_day:
        # Payment falls into the next billing cycle
        payment_month = transaction_date.month + 1
        payment_year = transaction_date.year
        if payment_month > 12:
            payment_month = 1
            payment_year += 1
    else:
        # Payment is in the current billing cycle
        payment_month = transaction_date.month
        payment_year = transaction_date.year

    return date(payment_year, payment_month, payment_day)

def _create_base_transaction(
    description: str,
    amount: float,
    category: Optional[str],
    budget_category: Optional[str],
    transaction_date: date,
) -> Dict[str, Any]:
    """
    A private factory function to construct the common fields for any transaction.
    """
    return {
        "date_created": transaction_date,
        "description": description,
        "amount": -abs(amount),  # Ensure amount is negative for expenses
        "category": category,
        "budget_category": budget_category,
        "status": "committed",
        "origin_id": None,
    }

def create_single_transaction(
    description: str,
    amount: float,
    category: Optional[str],
    budget_category: Optional[str],
    account: Dict[str, Any],
    transaction_date: date,
) -> Dict[str, Any]:
    """
    Creates one complete transaction, handling logic for cash and credit cards.
    """
    transaction = _create_base_transaction(
        description, amount, category, budget_category, transaction_date
    )
    transaction["account"] = account.get("account_id")

    if account.get("account_type") == "credit_card":
        transaction["date_payed"] = _calculate_credit_card_payment_date(
            transaction_date, account["cut_off_day"], account["payment_day"]
        )
    else:
        transaction["date_payed"] = transaction_date

    return transaction

def create_installment_transactions(
    description: str,
    total_amount: float,
    installments: int,
    category: Optional[str],
    budget_category: Optional[str],
    account: Dict[str, Any],
    transaction_date: date,
) -> List[Dict[str, Any]]:
    """
    Generates a list of transactions for a purchase made in installments.
    """
    origin_id = _generate_origin_id()
    installment_amount = round(total_amount / installments, 2)
    
    transactions = []

    for i in range(installments):
        installment_description = f"{description} ({i + 1}/{installments})"
        
        # Calculate the transaction date for the billing of this installment
        # This is a simplified way to advance months. A more robust library might be better for edge cases.
        months_to_add = i
        future_year = transaction_date.year + (transaction_date.month + months_to_add -1) // 12
        future_month = (transaction_date.month + months_to_add -1) % 12 + 1
        
        # Create a date to properly calculate the payment date for future installments
        future_billing_date = date(future_year, future_month, transaction_date.day)

        transaction = _create_base_transaction(
            description=installment_description,
            amount=installment_amount,
            category=category,
            budget_category=budget_category,
            transaction_date=transaction_date, # The purchase date is the same for all
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
            budget_category=split["budget_category"],
            account=account,
            transaction_date=transaction_date,
        )
        transaction["origin_id"] = origin_id
        transactions.append(transaction)
    return transactions

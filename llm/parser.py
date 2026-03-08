
import os
import json
import logging
import re
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional
from sqlite3 import Connection
from cashflow import repository

# Configure logging
logger = logging.getLogger(__name__)


def _call_llm(
    system_prompt: str,
    user_input: str,
    function_name: str
) -> Optional[str]:
    """
    Unified LLM call for all parsing functions.

    This helper function provides a single point of integration with the
    LLM backend, eliminating code duplication across parsing functions.

    Args:
        system_prompt: Complete system instruction for the LLM
        user_input: User's natural language input
        function_name: Name of calling function (for routing)

    Returns:
        str: LLM response text
        None: If call fails after all retries

    Example:
        response = _call_llm(
            system_prompt="You are a parser...",
            user_input="spent 50 on groceries",
            function_name="parse_transaction_string"
        )
    """
    from llm.backend import LLMBackend

    try:
        backend = LLMBackend.get_instance()
        response_text = backend.generate(
            system_instruction=system_prompt,
            user_input=user_input,
            function_name=function_name
        )
        return _clean_llm_response(response_text)

    except Exception as e:
        logger.error(f"LLM call failed for {function_name}: {e}")
        return None


def _clean_llm_response(text: str) -> Optional[str]:
    """Strip local model artifacts: <think> tags, markdown fencing."""
    if not text:
        return text
    # Strip <think>...</think> blocks (smollm3, qwen3)
    if "<think>" in text:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # Strip markdown code fences (gemma3)
    if "```" in text:
        text = re.sub(r'```(?:json)?\s*', '', text).strip()
    return text


def resolve_account(raw: str, accounts: List[Dict[str, Any]], default: str = "Cash") -> str:
    """Match an LLM-returned account string to a real account name.

    Handles exact matches, case-insensitive matches, substring matches,
    and falls back to default for empty/invalid values like 'N/A'.
    """
    if not raw or raw.strip().lower() in ("n/a", "none", "null", ""):
        return default

    account_names = [a['account_id'] for a in accounts]
    raw_lower = raw.strip().lower()

    # Exact match
    for name in account_names:
        if name == raw.strip():
            return name

    # Case-insensitive match
    for name in account_names:
        if name.lower() == raw_lower:
            return name

    # Substring match (e.g. "pichincha" -> "Visa Pichincha")
    for name in account_names:
        if raw_lower in name.lower() or name.lower() in raw_lower:
            return name

    return default


def _last_weekday(today: date, weekday: int) -> date:
    """Find the most recent past occurrence of a weekday (0=Mon, 6=Sun)."""
    d = today
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def pre_parse_date_and_account(user_input: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Quick LLM call to extract just the date and account from user input.
    Used to calculate payment date before the main parse.
    """
    account_names = [acc['account_id'] for acc in accounts]
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Pre-compute relative dates so the model doesn't have to do date math
    last_monday = _last_weekday(today, 0)
    last_tuesday = _last_weekday(today, 1)
    last_wednesday = _last_weekday(today, 2)
    last_thursday = _last_weekday(today, 3)
    last_friday = _last_weekday(today, 4)
    last_sunday = _last_weekday(today, 6)

    system_prompt = f"""You are a quick parser. Extract ONLY the date and account from the user's input.

**Today: {today.strftime('%A, %B %d, %Y')} ({today.isoformat()})**
**Current year: {today.year}**
**Current month: {today.strftime('%B')} ({today.month})**

**Pre-computed relative dates:**
- Yesterday: {yesterday.isoformat()}
- Last Monday: {last_monday.isoformat()}
- Last Tuesday: {last_tuesday.isoformat()}
- Last Wednesday: {last_wednesday.isoformat()}
- Last Thursday: {last_thursday.isoformat()}
- Last Friday: {last_friday.isoformat()}
- Last Sunday: {last_sunday.isoformat()}

**Date rules:**
1. If no date is mentioned, use today: {today.isoformat()}
2. For relative dates ("yesterday", "last friday"), use the pre-computed dates above.
3. For "on the Nth" with no month, assume the current month ({today.strftime('%B %Y')}).
4. **Year inference:** When a month is mentioned without a year:
   - If the month is the current month or a future month within 2 months ahead, use {today.year}.
   - If the month is a past month (before {today.strftime('%B')}), use the most recent occurrence.
   - Rule of thumb: always pick the nearest past or present date. Transactions are usually recent.
   - Examples from today ({today.isoformat()}):
     - "feb 23" → {today.year}-02-23 (recent past this year)
     - "jan 15" → {today.year}-01-15 (recent past this year)
     - "dec 25" → {today.year - 1}-12-25 (last December, not next)
     - "march 1" → {today.year}-03-01 (current month)
     - "april 10" → {today.year}-04-10 (near future, same year)

**Account rules:**
1. `account` MUST be EXACTLY one of: {account_names}
2. Match partial names: "pichincha" = "Visa Pichincha", "produbanco" = "Visa Produbanco", "diners" = "Diners", "cash" = "Cash"
3. Never invent account names. Pick the closest match from the list.

**Output ONLY this JSON (no markdown, no explanation):**
{{"date": "YYYY-MM-DD", "account": "account_name"}}"""

    # Call LLM via unified backend
    response_text = _call_llm(
        system_prompt=system_prompt,
        user_input=user_input,
        function_name="pre_parse_date_and_account"
    )

    # Handle response
    if not response_text:
        # Fallback to defaults on failure
        print("Warning: LLM call failed for pre-parse. Using defaults.")
        return {"date": today.isoformat(), "account": accounts[0]['account_id'] if accounts else None}

    try:
        result = json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Failed to parse pre-parse response: {e}")
        # Fallback to defaults
        result = {"date": today.isoformat(), "account": accounts[0]['account_id'] if accounts else None}

    result['account'] = resolve_account(result.get('account', ''), accounts)
    return result


def parse_transaction_string(conn: Connection, user_input: str, accounts: List[Dict[str, Any]], budgets: List[Dict[str, Any]], payment_month: date = None) -> Dict[str, Any]:
    """Parse a natural language string into a structured JSON object for a transaction.

    Args:
        payment_month: The month when this transaction will be paid (for budget selection context)
    """
    # Prepare the list of valid account names, budgets, and categories for the prompt
    account_names = [acc['account_id'] for acc in accounts]

    # Build budget info with IDs and active periods
    budget_info = []
    for b in budgets:
        end_str = str(b['end_date']) if b.get('end_date') else "ongoing"
        budget_info.append({
            "id": b['id'],
            "name": b['name'],
            "category": b.get('category', ''),
            "active_from": str(b['start_date']),
            "active_until": end_str
        })

    # Filter budgets to those active in payment month if provided
    if payment_month:
        active_budgets = []
        for b in budget_info:
            start = date.fromisoformat(b['active_from'])
            end = date.fromisoformat(b['active_until']) if b['active_until'] != 'ongoing' else date(2099, 12, 31)
            if start <= payment_month <= end:
                active_budgets.append(b)
        budget_info = active_budgets if active_budgets else budget_info  # Fallback to all if none active

    categories = repository.get_all_categories(conn)
    category_names = [cat['name'] for cat in categories]
    category_descriptions = {cat['name']: cat.get('description', '') for cat in categories}
    category_info = ", ".join(
        f"{name} ({desc})" if desc else name
        for name, desc in category_descriptions.items()
    )

    today = date.today()
    payment_context = ""
    if payment_month:
        payment_context = f"\n**Payment Month: {payment_month.strftime('%B %Y')}** - Select budgets active during this month.\n"
    system_prompt = f"""
You are an expert financial assistant. Your task is to parse a user's natural language input into a structured JSON object for a transaction.

**Today's Date: {today.isoformat()} ({today.strftime('%A, %B %d, %Y')})**
**Current Month: {today.strftime('%B %Y')}**
{payment_context}
**Rules:**
1.  The `type` field must be one of: "simple", "installment", or "split".
2.  The `account` field MUST be one of the following valid account names: {account_names}, ensure no typos or variations.
3.  The `category` field is MANDATORY and MUST EXACTLY MATCH one of the following valid categories (descriptions in parentheses to help you choose): {category_info}. Do not invent new categories. Always select the most appropriate category from this list based on the description.
4.  **Budget Selection:** The `budget` field must be the budget **ID** (not the name). Available budgets: {json.dumps(budget_info, indent=2)}
    - Match the user's words to the budget **name** field, then return that budget's **id**.
    - Be precise: "Mercado" budget is different from "Home Groceries" budget. Only select "Mercado" if user explicitly says "mercado".
    - If user says "Home Groceries budget", look for a budget with "Home Groceries" or "Groceries" in the name (not "Mercado").
    - Prefer budgets whose active period includes the payment month.
    - If no exact match, select the closest match by name that is active in the payment month.
5.  **Installment Logic:** The `installments` field (the number of payments to create) is **mandatory** for this type.
    - If the user gives a total number (e.g., "6 installments"), set `installments` to that number.
    - If the user gives a partial plan (e.g., "starting the 3rd of 12"), you MUST calculate the remaining payments and set `installments` to that value (e.g., `12 - 3 + 1 = 10`). You must also include `start_from_installment` and `total_installments` for context.
6.  If the user mentions income, salary, current funds, or being paid, you MUST set `"is_income": true`. Otherwise, omit it or set it to false. Since the default assumption is an expense by the system.
7.  **Date Logic:** Only include `date_created` if the user provides specific date information (e.g., 'yesterday', 'last Tuesday', 'on the 5th', 'each months 15th'). If NO DATE is mentioned, omit the field.
8.  If a establishment or vendor name is mentioned, include it in the `description` field. Capitalize appropriately. E.g. "Amazon - School Supplies".
9.  **Pending Logic:** If the user mentions 'pending', 'unconfirmed', 'not yet paid', 'waiting for', or similar terms, you MUST set `"is_pending": true`.
10. **Planning Logic:** If the user mentions 'plan for', 'planning', 'what if', 'tentative', or similar forward-looking, non-committed terms, you MUST set `"is_planning": true`.
11. **Grace Period Logic:** If the user mentions a "grace period", "deferred payment", "months grace", "buy now pay later", or similar terms indicating delayed first payment, extract the number of months and set `grace_period_months`. If no grace period is mentioned, omit the field.

**Schema:**
- `type`: (string) "simple", "installment", or "split".
- `description`: (string) A brief description of the transaction.
- `date_created`: (string, optional) The creation date in "YYYY-MM-DD" format.
- `amount`: (float) For "simple" type, the total amount.
- `total_amount`: (float) For "installment" type, the total purchase amount.
- `installments`: (int) For "installment" type, the number of payments.
- `start_from_installment`: (int, optional) For existing installment plans.
- `total_installments`: (int, optional) For existing installment plans.
- `account`: (string) The account name. Must be one of {account_names}.
- `category`: (string, REQUIRED) The category of the transaction. Must be one of {category_names}.
- `budget`: (string, optional) The budget **ID** (not name) this expense is linked to.
- `is_income`: (boolean, optional) Set to true for income.
- `is_pending`: (boolean, optional) Set to true for pending transactions.
- `is_planning`: (boolean, optional) Set to true for planning/what-if scenarios.
- `grace_period_months`: (int, optional) Number of months to defer the first payment. Only include if a grace period is mentioned.
- `splits`: (array of objects, for "split" type only)
    - `amount`: (float) Amount for this part of the split.
    - `category`: (string, REQUIRED) Category for this part. Must be one of {category_names}.
    - `budget`: (string, optional) Budget for this part.

**Final Constraints:**
- Do NOT add any fields that are not in the schemas described above.
- Do NOT enclose the JSON in markdown backticks.
- Output ONLY the JSON object.

**Examples:**


User: "Mercado groceries 20 cash last friday"
{{
  "type": "simple",
  "description": "Mercado groceries",
  "amount": 20,
  "account": "Cash",
  "category": "Home Groceries",
  "budget": "budget_mercado",
  "date_created": "2025-11-07"
}}

User: "lunch at cafe 15.75 cash Food budget"
{{
  "type": "simple",
  "description": "Lunch at cafe",
  "amount": 15.75,
  "account": "Cash",
  "category": "Dining-Snacks",
  "budget": "budget_food"
}}

User: "bought a 600 bike last month on the 29th in 3 installments on visa"
{{
  "type": "installment",
  "description": "Bike",
  "total_amount": 600,
  "installments": 3,
  "account": "Visa Produbanco",
  "category": "Personal",
  "date_created": "2025-09-29"
}}

User: "Grocery store amex produbanco 80 for groceries on the food budget and 15 for household supplies on the home budget"
{{
  "type": "split",
  "description": "Grocery Store",
  "account": "Amex Produbanco",
  "splits": [
    {{ "amount": 80, "category": "Home Groceries", "budget": "budget_food" }},
    {{ "amount": 15, "category": "Home Groceries", "budget": "budget_home" }}
  ]
}}

User: "My friend owes me $25 for dinner, mark it as pending"
{{
  "type": "simple",
  "description": "Friend owes for dinner",
  "amount": 25,
  "account": "Cash",
  "is_income": true,
  "is_pending": true
}}

User: "what if I buy a new TV for 800 next month on my Visa Produbanco"
{{
  "type": "simple",
  "description": "New TV",
  "amount": 800,
  "account": "Visa Produbanco",
  "category": "Personal",
  "is_planning": true,
  "date_created": "2025-11-23"
}}

User: "Bought a TV for 500 on Visa Pichincha with 3 months grace period"
{{
  "type": "simple",
  "description": "TV",
  "amount": 500,
  "account": "Visa Pichincha",
  "category": "Personal",
  "grace_period_months": 3
}}
"""

    # Call LLM via unified backend
    response_text = _call_llm(
        system_prompt=system_prompt,
        user_input=user_input,
        function_name="parse_transaction_string"
    )

    # Handle response
    if not response_text:
        print("Error: LLM call failed for transaction parsing.")
        print("This might be due to safety filters, rate limits, or API issues.")
        print("Please try rephrasing your input or try again later.")
        return None

    try:
        result = json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error: Failed to decode JSON from LLM response: {e}")
        print(f"Raw response: {response_text}")
        return None

    result['account'] = resolve_account(result.get('account', ''), accounts)
    return result


def parse_subscription_string(conn: Connection, user_input: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse a natural language string into a structured JSON object for a subscription or budget."""
    # Prepare the list of valid account names
    account_names = [acc['account_id'] for acc in accounts]

    today = date.today()
    system_prompt = f"""
You are an expert financial assistant. Your task is to parse a user's natural language input into a structured JSON object for creating a recurring subscription or budget.

**Today's Date: {today.isoformat()} ({today.strftime('%A, %B %d, %Y')})**
**Current Month: {today.strftime('%B %Y')}**

**Rules:**
1.  You MUST generate a readable `id` from the name, prefixed with `sub_` or `budget_` (e.g., "Netflix" -> "sub_netflix", "Food Budget" -> "budget_food").
2.  **`payment_account_id` is a mandatory field.** It must be one of: {account_names}
3.  If the user's request mentions creating a "budget", you MUST set `"is_budget": true` and the `start_date` should be the 1st day of the relevant month if no other date is provided.
4.  If the user mentions recurring income or salary, you MUST set `"is_income": true`.
5.  **Date Logic:** Only include `start_date` if the user provides date information (e.g., "next month", "starting September", "on the 5th"). If no date is mentioned, omit the field.
6.  **Limited-Time Budgets:** If the user specifies a time limit (e.g., "only for December", "just this month", "until January", "for the next 3 months"), you MUST calculate and set `end_date`. Use today's date as reference for calculations.
    - "December only" -> start_date: 2025-12-01, end_date: 2025-12-31
    - "this month only" -> start_date: first of current month, end_date: last of current month
    - "next 3 months" -> end_date: last day of the month 3 months from now
    - If NO time limit is mentioned -> omit `end_date` (permanent/ongoing budget)

**Schema:**
- `id`: (string) A unique, readable ID you generate (e.g., "sub_spotify").
- `name`: (string) The name of the subscription (e.g., "Spotify Premium").
- `category`: (string) The category of the subscription.
- `monthly_amount`: (float) The recurring monthly amount.
- `payment_account_id`: (string) The account name. Must be one of {account_names}.
- `start_date`: (string, optional) The start date in "YYYY-MM-DD" format.
- `end_date`: (string, optional) The end date in "YYYY-MM-DD" format for limited-time budgets/subscriptions.
- `is_budget`: (boolean, optional) Set to true if it's a budget.
- `is_income`: (boolean, optional) Set to true for income.

**Final Constraints:**
- Do NOT add any fields that are not in the schema described above.
- Do NOT enclose the JSON in markdown backticks.
- Output ONLY the JSON object, nothing else.

**Examples:**

User: "add my netflix subscription for 15.99 on my visa produbanco"
{{
  "id": "sub_netflix",
  "name": "Netflix Subscription",
  "category": "Personal",
  "monthly_amount": 15.99,
  "payment_account_id": "Visa Produbanco"
}}

User: "create a 400 food budget on my cash account starting next month"
{{
  "id": "budget_food",
  "name": "Food Budget",
  "category": "Home Groceries",
  "monthly_amount": 400,
  "payment_account_id": "Cash",
  "start_date": "2025-12-01",
  "is_budget": true
}}

User: "I get a recurring monthly income of 1200 into my Cash account"
{{
  "id": "sub_recurrent_income",
  "name": "Recurrent Income",
  "category": "Income",
  "monthly_amount": 1200.0,
  "payment_account_id": "Cash",
  "is_income": true
}}

User: "Create a Christmas shopping budget of 500 for December only on my Visa Produbanco"
{{
  "id": "budget_christmas_shopping_dec",
  "name": "Christmas Shopping",
  "category": "Personal",
  "monthly_amount": 500,
  "payment_account_id": "Visa Produbanco",
  "start_date": "2025-12-01",
  "end_date": "2025-12-31",
  "is_budget": true
}}
"""

    # Call LLM via unified backend
    response_text = _call_llm(
        system_prompt=system_prompt,
        user_input=user_input,
        function_name="parse_subscription_string"
    )

    # Handle response
    if not response_text:
        print("Error: LLM call failed for subscription/budget parsing.")
        return None

    try:
        result = json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error: Failed to decode JSON from LLM response: {e}")
        print(f"Raw response: {response_text}")
        return None

    result['payment_account_id'] = resolve_account(result.get('payment_account_id', ''), accounts)
    return result


def parse_edit_instruction(
    conn: Connection,
    existing_transaction: Dict[str, Any],
    edit_instruction: str,
    accounts: List[Dict[str, Any]],
    budgets: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Parse a natural language edit instruction into a dict of changed fields.

    Returns only the fields that should change. Returns {} if no changes,
    None on LLM failure.
    """
    account_names = [acc['account_id'] for acc in accounts]

    budget_info = []
    for b in budgets:
        end_str = str(b['end_date']) if b.get('end_date') else "ongoing"
        budget_info.append({
            "id": b['id'],
            "name": b['name'],
            "active_from": str(b['start_date']),
            "active_until": end_str
        })

    categories = repository.get_all_categories(conn)
    category_names = [cat['name'] for cat in categories]
    category_descriptions = {cat['name']: cat.get('description', '') for cat in categories}
    category_info = ", ".join(
        f"{name} ({desc})" if desc else name
        for name, desc in category_descriptions.items()
    )

    today = date.today()
    yesterday = today - timedelta(days=1)
    last_monday = _last_weekday(today, 0)
    last_tuesday = _last_weekday(today, 1)
    last_wednesday = _last_weekday(today, 2)
    last_thursday = _last_weekday(today, 3)
    last_friday = _last_weekday(today, 4)
    last_sunday = _last_weekday(today, 6)

    # Build current transaction summary for the prompt
    tx = existing_transaction
    tx_summary = (
        f"ID: {tx['id']}\n"
        f"Description: {tx['description']}\n"
        f"Amount: {tx['amount']}\n"
        f"Date: {tx['date_created']}\n"
        f"Account: {tx['account']}\n"
        f"Category: {tx.get('category', 'N/A')}\n"
        f"Budget: {tx.get('budget', 'none')}\n"
        f"Status: {tx['status']}"
    )

    system_prompt = f"""You are a financial transaction editor. Given the current state of a transaction and the user's edit instruction, return ONLY the fields that should change as a JSON object.

**Current transaction:**
{tx_summary}

**Today: {today.strftime('%A, %B %d, %Y')} ({today.isoformat()})**

**Pre-computed relative dates:**
- Yesterday: {yesterday.isoformat()}
- Last Monday: {last_monday.isoformat()}
- Last Tuesday: {last_tuesday.isoformat()}
- Last Wednesday: {last_wednesday.isoformat()}
- Last Thursday: {last_thursday.isoformat()}
- Last Friday: {last_friday.isoformat()}
- Last Sunday: {last_sunday.isoformat()}

**Valid accounts:** {account_names}
**Valid categories (with descriptions):** {category_info}
**Available budgets:** {json.dumps(budget_info, indent=2)}

**Rules:**
1. Return ONLY the fields that change. Do NOT include unchanged fields.
2. Return empty {{}} if the instruction doesn't imply any changes.
3. **Amount sign:** Preserve the current sign convention. If the current amount is negative (expense), keep the new amount negative. If positive (income), keep positive. Only flip the sign if the user explicitly says "make it income" or "make it an expense".
4. **Budget:** Return the budget **ID** (not the name). Match the user's words to the budget name, then return the ID. Use "none" to remove a budget.
5. **Date:** Use ISO format (YYYY-MM-DD) for the `date_created` field.
6. **Account:** Must be exactly one of the valid account names.
7. **Category:** Must exactly match one of the valid categories.
8. **Status:** Must be one of: committed, pending, planning, forecast.

**Editable fields:** description, amount, date_created, account, category, budget, status

**Output ONLY JSON (no markdown, no explanation).**

**Examples:**

User: "change amount to 45.50"
(current amount is -30.00)
{{"amount": -45.50}}

User: "change description to Amazon Books"
{{"description": "Amazon Books"}}

User: "change date to march 5"
{{"date_created": "2026-03-05"}}

User: "move to personal groceries budget"
{{"budget": "budget_groceries_mar_apr"}}

User: "change category to Dining-Snacks and amount to 12"
(current amount is -8.50)
{{"category": "Dining-Snacks", "amount": -12.00}}

User: "mark as pending"
{{"status": "pending"}}"""

    response_text = _call_llm(
        system_prompt=system_prompt,
        user_input=edit_instruction,
        function_name="parse_edit_instruction"
    )

    if not response_text:
        logger.error("LLM call failed for edit instruction parsing.")
        return None

    try:
        result = json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to decode JSON from edit LLM response: {e}")
        logger.error(f"Raw response: {response_text}")
        return None

    # Post-process: resolve account name if present
    if 'account' in result:
        result['account'] = resolve_account(result['account'], accounts, default=tx['account'])

    # Validate category if present
    if 'category' in result and result['category'] not in category_names:
        logger.warning(f"LLM returned invalid category '{result['category']}', dropping field")
        del result['category']

    return result


def parse_account_string(user_input: str) -> Dict[str, Any]:
    """Parse a natural language string into a structured JSON object for creating a new account."""
    system_prompt = f"""
You are an expert financial assistant. Your task is to parse a user's natural language input into a single, structured JSON object to create a new financial account.

**Constraints and Rules:**
1.  The JSON output MUST adhere to the schema provided below.
2.  The `account_type` must be either "cash" or "credit_card".
3.  If the user mentions a "credit card", you MUST extract the `cut_off_day` and `payment_day`. If they are not provided, you can omit them.
4.  The `account_id` should be a descriptive name for the account.
5.  Do NOT add any fields that are not in the schema.
6.  Do NOT enclose the JSON in markdown backticks.

**JSON Schema:**
- `account_id`: (string) The name of the account (e.g., "My Bank Savings").
- `account_type`: (string) "cash" or "credit_card".
- `cut_off_day`: (int, optional) For credit cards, the billing cycle cut-off day.
- `payment_day`: (int, optional) For credit cards, the bill payment day.

**Examples:**

User: "add a new cash account called Wallet"
{{
  "account_id": "Wallet",
  "account_type": "cash"
}}

User: "create a credit card account for my new Visa, the cut off is on the 15th and payment is on the 30th"
{{
  "account_id": "New Visa",
  "account_type": "credit_card",
  "cut_off_day": 15,
  "payment_day": 30
}}

User: "new credit card called Amex Gold"
{{
  "account_id": "Amex Gold",
  "account_type": "credit_card"
}}
"""

    # Call LLM via unified backend
    response_text = _call_llm(
        system_prompt=system_prompt,
        user_input=user_input,
        function_name="parse_account_string"
    )

    # Handle response
    if not response_text:
        print("Error: LLM call failed for account parsing.")
        return None

    try:
        return json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error: Failed to decode JSON from LLM response: {e}")
        print(f"Raw response: {response_text}")
        return None


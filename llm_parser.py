
import os
import sys
import json
from datetime import date
from dateutil.relativedelta import relativedelta
from contextlib import contextmanager

import google.generativeai as genai
from typing import List, Dict, Any
from sqlite3 import Connection
import repository

@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr output at the file descriptor level."""
    # Save original stderr file descriptor
    stderr_fd = sys.stderr.fileno()
    original_stderr_fd = os.dup(stderr_fd)

    try:
        # Redirect stderr to /dev/null
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, stderr_fd)
        os.close(devnull_fd)
        yield
    finally:
        # Restore original stderr
        os.dup2(original_stderr_fd, stderr_fd)
        os.close(original_stderr_fd)


def pre_parse_date_and_account(user_input: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Quick LLM call to extract just the date and account from user input.
    Used to calculate payment date before the main parse.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    account_names = [acc['account_id'] for acc in accounts]
    today = date.today()

    system_prompt = f"""
You are a quick parser. Extract ONLY the date and account from the user's input.

**Today's Date: {today.isoformat()}**

**Rules:**
1. `account` MUST be one of: {account_names}
2. `date` should be in "YYYY-MM-DD" format. If no date mentioned, use today's date.
3. Parse relative dates: "yesterday" = {(today - relativedelta(days=1)).isoformat()}, "last friday", etc.

**Output ONLY this JSON (no markdown):**
{{"date": "YYYY-MM-DD", "account": "account_name"}}

**Examples:**
User: "yesterday pichincha 50 groceries"
{{"date": "{(today - relativedelta(days=1)).isoformat()}", "account": "Visa Pichincha"}}

User: "cash 20 lunch"
{{"date": "{today.isoformat()}", "account": "Cash"}}
"""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )

    with suppress_stderr():
        response = model.generate_content(contents=user_input)

    try:
        # Check if response has valid content
        if not response.candidates or not response.candidates[0].content.parts:
            print(f"Warning: Empty LLM response. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'No candidates'}")
            return {"date": today.isoformat(), "account": accounts[0]['account_id'] if accounts else None}

        return json.loads(response.text)
    except (json.JSONDecodeError, IndexError, AttributeError, ValueError) as e:
        print(f"Warning: Failed to parse pre-parse response: {e}")
        # Fallback to defaults
        return {"date": today.isoformat(), "account": accounts[0]['account_id'] if accounts else None}


def parse_transaction_string(conn: Connection, user_input: str, accounts: List[Dict[str, Any]], budgets: List[Dict[str, Any]], payment_month: date = None) -> Dict[str, Any]:
    """
    Uses the Gemini API to parse a natural language string into a structured
    JSON object for a transaction.

    Args:
        payment_month: The month when this transaction will be paid (for budget selection context)
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

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
3.  The `category` field is MANDATORY and MUST EXACTLY MATCH one of the following valid categories: {category_names}. Do not invent new categories. Always select the most appropriate category from this list.
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
"""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )

    with suppress_stderr():
        response = model.generate_content(contents=user_input)

    try:
        # Check if response has valid content
        if not response.candidates or not response.candidates[0].content.parts:
            print(f"Error: Empty LLM response (finish_reason: {response.candidates[0].finish_reason if response.candidates else 'No candidates'})")
            print("This might be due to safety filters, rate limits, or API issues.")
            print("Please try rephrasing your input or try again later.")
            return None

        return json.loads(response.text)
    except (json.JSONDecodeError, IndexError, AttributeError, ValueError) as e:
        print(f"Error: Failed to decode JSON from LLM response: {e}")
        try:
            if response.candidates and response.candidates[0].content.parts:
                print(f"Raw response: {response.text}")
        except:
            print("Could not access response text")
        return None


def parse_subscription_string(conn: Connection, user_input: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Uses the Gemini API to parse a natural language string into a structured
    JSON object for a subscription or budget.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

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

    with suppress_stderr():
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt
        )
        response = model.generate_content(contents=user_input)

    try:
        # Check if response has valid content
        if not response.candidates or not response.candidates[0].content.parts:
            print(f"Error: Empty LLM response (finish_reason: {response.candidates[0].finish_reason if response.candidates else 'No candidates'})")
            return None

        return json.loads(response.text)
    except (json.JSONDecodeError, IndexError, AttributeError, ValueError) as e:
        print(f"Error: Failed to decode JSON from LLM response: {e}")
        try:
            if response.candidates and response.candidates[0].content.parts:
                print(f"Raw response: {response.text}")
        except:
            print("Could not access response text")
        return None


def parse_account_string(user_input: str) -> Dict[str, Any]:
    """
    Uses the Gemini API to parse a natural language string into a structured
    JSON object for creating a new account.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

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

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )

    with suppress_stderr():
        response = model.generate_content(contents=user_input)

    try:
        # Check if response has valid content
        if not response.candidates or not response.candidates[0].content.parts:
            print(f"Error: Empty LLM response (finish_reason: {response.candidates[0].finish_reason if response.candidates else 'No candidates'})")
            return None

        return json.loads(response.text)
    except (json.JSONDecodeError, IndexError, AttributeError, ValueError) as e:
        print(f"Error: Failed to decode JSON from LLM response: {e}")
        try:
            if response.candidates and response.candidates[0].content.parts:
                print(f"Raw response: {response.text}")
        except:
            print("Could not access response text")
        return None


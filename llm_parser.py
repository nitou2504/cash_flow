
import os
import json
from datetime import date
from dateutil.relativedelta import relativedelta
import google.generativeai as genai
from typing import List, Dict, Any

def parse_transaction_string(user_input: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Uses the Gemini API to parse a natural language string into a structured
    JSON object for a transaction.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    # Prepare the list of valid account names for the prompt
    account_names = [acc['account_id'] for acc in accounts]

    today = date.today()
    system_prompt = f"""
You are an expert financial assistant. Your task is to parse a user's natural language input into a single, structured JSON object.
You must first determine if the user is logging a one-time transaction or creating a recurring subscription/budget.

**Today's Date is: {today.isoformat()}**

**Primary Directive:**
Your output MUST be a single JSON object with a root-level `request_type` field, which must be either "transaction" or "subscription".

---
### **IF `request_type` IS `transaction`:**

**Rules:**
1.  The `type` field must be one of: "simple", "installment", or "split".
2.  The `account` field MUST be one of the following valid account names: {account_names}.
3.  For `installment` transactions, if the user mentions a partial payment (e.g., "3rd of 6"), you MUST populate `start_from_installment` and `total_installments`. If they only say "6 installments", then `installments` is 6, and the other two fields should be omitted.
4.  If the user mentions income, salary, or being paid, you MUST set `"is_income": true`. Otherwise, omit it or set it to false.

**Schema:**
- `type`: (string) "simple", "installment", or "split".
- `description`: (string) A brief description of the transaction.
- `amount`: (float) For "simple" type, the total amount.
- `total_amount`: (float) For "installment" type, the total purchase amount.
- `installments`: (int) For "installment" type, the number of payments.
- `start_from_installment`: (int, optional) For existing installment plans.
- `total_installments`: (int, optional) For existing installment plans.
- `account`: (string) The account name. Must be one of {account_names}.
- `category`: (string, optional) The category of the expense.
- `budget`: (string, optional) The budget this expense is linked to.
- `is_income`: (boolean, optional) Set to true for income.
- `splits`: (array of objects, for "split" type only)
    - `amount`: (float) Amount for this part of the split.
    - `category`: (string) Category for this part.
    - `budget`: (string, optional) Budget for this part.

---
### **IF `request_type` IS `subscription`:**

**Rules:**
1.  You MUST generate a readable `id` from the name, prefixed with `sub_` or `budget_` (e.g., "Netflix" -> "sub_netflix", "Food Budget" -> "budget_food").
2.  **`payment_account_id` is a mandatory field.** It must be one of the provided account names.
3.  If the user's request mentions creating a "budget", you MUST set `"is_budget": true` and the `start_date` should be the 1st day of the relevant month.
4.  If the user mentions recurring income or salary, you MUST set `"is_income": true`.
5.  **Date Logic:** Only include `start_date` if the user provides date information (e.g., "next month", "starting September", "on the 5th"). If no date is mentioned, omit the field.

**Schema:**
- `details`: (object)
    - `id`: (string) A unique, readable ID you generate (e.g., "sub_spotify").
    - `name`: (string) The name of the subscription (e.g., "Spotify Premium").
    - `category`: (string) The category of the subscription.
    - `monthly_amount`: (float) The recurring monthly amount.
    - `payment_account_id`: (string) The account name. Must be one of {account_names}.
    - `start_date`: (string, optional) The start date in "YYYY-MM-DD" format.
    - `is_budget`: (boolean, optional) Set to true if it's a budget.
    - `is_income`: (boolean, optional) Set to true for income.

---
**Final Constraints (Apply to ALL):**
- Do NOT add any fields that are not in the schemas described above.
- Do NOT enclose the JSON in markdown backticks.

---
**Examples:**

User: "lunch at cafe 15.75 cash food budget"
{{
  "request_type": "transaction",
  "type": "simple",
  "description": "Lunch at cafe",
  "amount": 15.75,
  "account": "Cash",
  "category": "dining",
  "budget": "food"
}}

User: "1200 for a new laptop in 6 installments on my visa"
{{
  "request_type": "transaction",
  "type": "installment",
  "description": "New Laptop",
  "total_amount": 1200.00,
  "installments": 6,
  "account": "Visa Produbanco",
  "category": "electronics"
}}

User: "Grocery store amex produbanco 80 for groceries on the food budget and 15 for household supplies on the home budget"
{{
  "request_type": "transaction",
  "type": "split",
  "description": "Grocery Store",
  "account": "Amex Produbanco",
  "splits": [
    {{ "amount": 80, "category": "groceries", "budget": "food" }},
    {{ "amount": 15, "category": "household", "budget": "home" }}
  ]
}}

User: "add my netflix subscription for 15.99 on my visa produbanco"
{{
  "request_type": "subscription",
  "details": {{
    "id": "sub_netflix",
    "name": "Netflix Subscription",
    "category": "entertainment",
    "monthly_amount": 15.99,
    "payment_account_id": "Visa Produbanco"
  }}
}}

User: "create a 400 food budget on my cash account starting next month"
{{
  "request_type": "subscription",
  "details": {{
    "id": "budget_food",
    "name": "Food Budget",
    "category": "Food",
    "monthly_amount": 400,
    "payment_account_id": "Cash",
    "start_date": "2025-11-01",
    "is_budget": true
  }}
}}

User: "Set up my internet bill for 60 on Amex Produbanco, it's paid on the 3rd of each month"
{{
  "request_type": "subscription",
  "details": {{
    "id": "sub_internet",
    "name": "Internet Bill",
    "category": "utilities",
    "monthly_amount": 60,
    "payment_account_id": "Amex Produbanco",
    "start_date": "2025-11-03"
  }}
}}

User: "I get a recurring monthly income of 1200 into my Cash account"
{{
  "request_type": "subscription",
  "details": {{
    "id": "sub_recurrent_income",
    "name": "Recurrent Income",
    "category": "income",
    "monthly_amount": 1200.0,
    "payment_account_id": "Cash",
    "is_income": true
  }}
}}
"""

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )
    
    response = model.generate_content(contents=user_input)
    
    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, IndexError) as e:
        print(f"Error: Failed to decode JSON from LLM response.")
        print(f"Raw response: {response.text}")
        return None


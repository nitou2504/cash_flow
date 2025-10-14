
import os
import json
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

    system_prompt = f"""
You are an expert financial assistant responsible for parsing natural language into a structured JSON format.
Your task is to convert a user's input string into a single JSON object representing a financial transaction.

**Constraints and Rules:**
1.  The JSON output MUST adhere to the schema provided below.
2.  The `type` field must be one of: "simple", "installment", or "split".
3.  The `account` field MUST be one of the following valid account names: {account_names}.
4.  For `installment` transactions, if the user mentions a partial payment (e.g., "3rd of 6"), you MUST populate `start_from_installment` and `total_installments`. If they only say "6 installments", then `installments` is 6, and the other two fields should be omitted.
5.  If the user mentions income, salary, or being paid, you MUST set `"is_income": true`. Otherwise, omit it or set it to false.
6.  Do NOT add any fields that are not in the schema.
7.  Do NOT enclose the JSON in markdown backticks.

**JSON Schema:**
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

**Examples:**

User: "lunch at cafe 15.75 cash food budget"
{{
  "type": "simple",
  "description": "Lunch at cafe",
  "amount": 15.75,
  "account": "Cash",
  "category": "dining",
  "budget": "food"
}}

User: "1200 for a new laptop in 6 installments on my visa"
{{
  "type": "installment",
  "description": "New Laptop",
  "total_amount": 1200.00,
  "installments": 6,
  "account": "Visa Produbanco",
  "category": "electronics"
}}

User: "received my monthly salary of 3000 into my cash account"
{{
  "type": "simple",
  "description": "Monthly Salary",
  "amount": 3000,
  "account": "Cash",
  "category": "income",
  "is_income": true
}}

User: "Grocery store amex produbanco 80 for groceries on the food budget and 15 for household supplies on the home budget"
{{
  "type": "split",
  "description": "Grocery Store",
  "account": "Amex Produbanco",
  "splits": [
    {{ "amount": 80, "category": "groceries", "budget": "food" }},
    {{ "amount": 15, "category": "household", "budget": "home" }}
  ]
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


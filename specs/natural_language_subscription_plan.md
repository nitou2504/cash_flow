# 🧩 Unified `add` Command for Transactions and Subscriptions

## Overview

The goal is to make the LLM intelligent enough to act as a **router** that distinguishes between logging a single transaction and creating a recurring subscription or budget.
Based on user intent, the LLM will output a **JSON object** with the appropriate structure.

---

## 1. Evolve the LLM Prompt and JSON Schema (`llm_parser.py`)

This is the most critical step — the LLM prompt and schema will be redesigned to support multiple request types.

### ✳️ Key Additions

* **Introduce `request_type`:**
  The LLM will determine the user’s intent and include a root-level key called `request_type`, which can be either:

  * `"transaction"`
  * `"subscription"`

* **Conditional JSON Structure:**

  * If `request_type` is `"transaction"`, follow the existing schema for **simple**, **installment**, or **split** transactions.
  * If `request_type` is `"subscription"`, include a new `details` object matching the fields needed to create a subscription:

    ```json
    {
      "id": "string",
      "name": "string",
      "monthly_amount": "number",
      "is_budget": "boolean"
    }
    ```

* **Enhanced Prompt Examples:**

  * *Transaction:* “Add a $50 grocery expense.”
  * *Subscription:* “Add my Netflix subscription.”
  * *Budget:* “Create a $400 food budget every month.”

---

## 2. Create a Subscription Controller (`main.py`)

To maintain a clean architecture, the CLI should **not** directly interact with the repository.
A new controller function will handle subscription-related logic.

### 🧠 New Function

```python
process_subscription_request(conn, subscription_data)
```

### 🧩 Responsibilities

1. **Persist the subscription definition**
   Call `repository.add_subscription()` to store the new subscription details.
2. **Generate initial forecasts**
   Immediately call `generate_forecasts()` to create the corresponding transaction records, ensuring the **cash flow forecast** updates instantly.

---

## 3. Update the CLI Handler (`cli.py`)

The existing `handle_add` function will be upgraded to interpret the smarter LLM output.

### ⚙️ Logic Flow

1. **Inspect `request_type`:**
   After receiving the JSON from `llm_parser`, check the value of the `request_type` field.
2. **Conditional Routing:**

   * If `"transaction"`, call:

     ```python
     controller.process_transaction_request(conn, data)
     ```
   * If `"subscription"`, call:

     ```python
     controller.process_subscription_request(conn, data["details"])
     ```

---

## ✅ Outcome

This design ensures:

* **A single, unified `add` command** for all financial events.
* **Clean separation of concerns** between parsing, control, and persistence layers.
* **Immediate forecast updates** for new subscriptions or budgets.

# LLM Configuration

The app works fully without LLMs (web UI, interactive CLI mode, explicit `create` commands). An LLM enables:

- natural language input — `cli.py add "Spent 50 on groceries"` and the Telegram bot
- natural language edits — `cli.py edit 42 "change amount to 30"`
- merchant classification in the [Gmail auto-registration pipeline](gmail-sync.md)

It uses [LiteLLM](https://github.com/BerriAI/litellm), so any provider works (Gemini, Ollama, OpenAI, Anthropic, …).

## Quick start (Gemini only)

1. Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. `echo "GEMINI_API_KEY=your_key" >> .env`
3. `python3 cli.py add "Spent 50 on groceries today"`

No `llm_config.yaml` needed — Gemini is used for everything by default.

**Multiple API keys**: add numbered keys (`GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, …) to work around free-tier rate limits. A random key is picked per request and rotated on rate-limit errors.

## Hybrid setup: local + cloud

Route simple tasks to a free local model and complex ones to Gemini. Based on benchmarking 25 real test cases:

| Function | Recommended model | Accuracy | Speed | Why |
|----------|-------------------|----------|-------|-----|
| Pre-parse (date/account) | Ollama `llama3.2:3b` | 96% | 0.8s | Simple extraction, free |
| Transaction parsing | Gemini `2.5-flash` | — | ~1.2s | Complex JSON, needs accuracy |
| Subscription parsing | Gemini `2.5-flash` | — | ~1.2s | Budget creation needs accuracy |
| Account parsing | Gemini `2.5-flash` | — | ~1.2s | Local models emit code instead of JSON |
| Edit instruction parsing | Gemini `2.5-flash` | — | ~1.2s | Context understanding |
| No-budget phrase detection | Ollama `llama3.2:3b` | 100% | ~0.5s | Binary classification, free |

```bash
ollama pull llama3.2:3b
ollama serve                              # port 11434
cp llm_config.yaml.example llm_config.yaml   # pre-configured with the routing above
```

## Configuration reference (`llm_config.yaml`)

```yaml
function_models:
  pre_parse_date_and_account:
    provider: "ollama"
    model: "llama3.2:3b"
  parse_transaction_string:
    provider: "gemini"
    model: "gemini-2.5-flash"
  parse_subscription_string:
    provider: "gemini"
    model: "gemini-2.5-flash"
  parse_account_string:
    provider: "gemini"
    model: "gemini-2.5-flash"
  parse_edit_instruction:
    provider: "gemini"
    model: "gemini-2.5-flash"
  check_no_budget:
    provider: "ollama"
    model: "llama3.2:3b"

providers:
  gemini:
    type: "litellm"
    api_key_env: "GEMINI_API_KEY"
  ollama:
    type: "litellm"
    base_url: "http://localhost:11434"

fallback_chain:
  - provider: "gemini"
    model: "gemini-2.5-flash"

timeout_seconds: 30
max_retries: 2
temperature: 0.0
```

Any LiteLLM-compatible provider can be added:

```yaml
providers:
  openai:
    type: "litellm"
    api_key_env: "OPENAI_API_KEY"
  anthropic:
    type: "litellm"
    api_key_env: "ANTHROPIC_API_KEY"
```

## Environment variable overrides

Lower priority than `llm_config.yaml`; useful for Docker:

```bash
LLM_DEFAULT_PROVIDER=gemini
LLM_DEFAULT_MODEL=gemini-2.5-flash
LLM_OLLAMA_BASE_URL=http://localhost:11434

# Per-function (provider/model)
LLM_PRE_PARSE_MODEL=ollama/llama3.2:3b
LLM_TRANSACTION_PARSE_MODEL=gemini/gemini-2.5-flash
LLM_EDIT_PARSE_MODEL=gemini/gemini-2.5-flash
LLM_NO_BUDGET_MODEL=ollama/llama3.2:3b
```

## Notes

- Two-step add: a cheap pre-parse extracts date + account first, then the full parse runs with budgets filtered by payment month.
- `_clean_llm_response()` strips `<think>` tags and markdown fencing from local model output.
- Category descriptions are fed into prompts to improve auto-classification — write good ones.
- Benchmark notes: `gemma3:4b` 92% (adds fencing), `smollm3` 88% (adds `<think>`), thinking models (qwen3, deepseek-r1) burn all tokens and are unusable for this.

See `llm_config.yaml.example` for full documentation with benchmark results and troubleshooting tips.

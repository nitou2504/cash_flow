import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user, get_db

router = APIRouter(tags=["settings"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent

CONFIG_KEYS = {
    "register_rules": {
        "yaml_path": BASE_DIR / "register_rules.yaml",
        "description": "Merchant rules, transfer rules, item overrides, LLM model for auto-registration",
    },
    "classification_hints": {
        "yaml_path": BASE_DIR / "classification_hints.yaml",
        "description": "Category hints, user hints, and category→budget mapping for LLM prompts",
    },
    "llm_config": {
        "yaml_path": BASE_DIR / "llm_config.yaml",
        "description": "LLM provider configuration and per-function model routing",
    },
}


def _get_config(conn: sqlite3.Connection, key: str) -> dict:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (f"config:{key}",)).fetchone()
    if row:
        return json.loads(row[0])
    return None


def _set_config(conn: sqlite3.Connection, key: str, data: dict):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (f"config:{key}", json.dumps(data, ensure_ascii=False)),
    )
    conn.commit()


def seed_configs(conn: sqlite3.Connection):
    """Seed DB from YAML files if config keys don't exist yet."""
    for key, info in CONFIG_KEYS.items():
        existing = conn.execute("SELECT 1 FROM settings WHERE key = ?", (f"config:{key}",)).fetchone()
        if existing:
            continue
        path = info["yaml_path"]
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            _set_config(conn, key, data)


# ── Sync status / trigger ──────────────────────────────────────────


@router.get("/api/sync/status", dependencies=[Depends(get_current_user)])
async def sync_status():
    from sync.scheduler import get_last_sync
    return get_last_sync()


@router.post("/api/sync/trigger", dependencies=[Depends(get_current_user)])
async def sync_trigger():
    from sync.scheduler import trigger_sync
    try:
        summary = await trigger_sync()
    except RuntimeError:
        raise HTTPException(409, "Sync already running")
    return summary


@router.get("/api/sync/unparsed", dependencies=[Depends(get_current_user)])
def sync_unparsed(conn=Depends(get_db)):
    """Emails the parsers could not handle (format changes, foreign currency, etc.)."""
    from cashflow.consumo_repository import list_unparsed
    rows = list_unparsed(conn)
    return {"count": len(rows), "items": rows}


# ── Register Rules ──────────────────────────────────────────────────


class MerchantRule(BaseModel):
    pattern: str
    category: str
    desc: str | None = None


class TransferDestination(BaseModel):
    account_suffix: str
    name: str


class ItemOverride(BaseModel):
    keywords: list[str]
    category: str


class RegisterRulesIn(BaseModel):
    llm_model: str
    merchant_rules: list[MerchantRule]
    transfer_destinations: list[TransferDestination]
    item_overrides: list[ItemOverride]


def _register_rules_to_json(raw: dict) -> dict:
    merchants = []
    for pattern, cfg in (raw.get("merchant_rules") or {}).items():
        merchants.append({"pattern": pattern, "category": cfg["category"], "desc": cfg.get("desc")})
    destinations = []
    for suffix, name in (raw.get("transfer_destinations") or {}).items():
        destinations.append({"account_suffix": suffix, "name": name})
    return {
        "llm_model": raw.get("llm_model", ""),
        "merchant_rules": merchants,
        "transfer_destinations": destinations,
        "item_overrides": raw.get("item_overrides") or [],
    }


def _register_rules_from_json(data: RegisterRulesIn) -> dict:
    merchant_dict: dict[str, Any] = {}
    for r in data.merchant_rules:
        entry: dict[str, str] = {"category": r.category}
        if r.desc:
            entry["desc"] = r.desc
        merchant_dict[r.pattern] = entry
    dest_dict: dict[str, str] = {}
    for r in data.transfer_destinations:
        dest_dict[r.account_suffix] = r.name
    return {
        "llm_model": data.llm_model,
        "merchant_rules": merchant_dict,
        "transfer_destinations": dest_dict,
        "item_overrides": [{"keywords": o.keywords, "category": o.category} for o in data.item_overrides],
    }


@router.get("/api/settings/register-rules", dependencies=[Depends(get_current_user)])
def get_register_rules(conn=Depends(get_db)):
    raw = _get_config(conn, "register_rules") or {}
    return _register_rules_to_json(raw)


@router.put("/api/settings/register-rules", dependencies=[Depends(get_current_user)])
def put_register_rules(body: RegisterRulesIn, conn=Depends(get_db)):
    _set_config(conn, "register_rules", _register_rules_from_json(body))
    return {"ok": True}


# ── Classification Hints ────────────────────────────────────────────


class ClassificationHintsIn(BaseModel):
    category_hints: list[str]
    user_hints: list[str]
    category_budget_map: dict[str, str]


@router.get("/api/settings/classification-hints", dependencies=[Depends(get_current_user)])
def get_classification_hints(conn=Depends(get_db)):
    raw = _get_config(conn, "classification_hints") or {}
    return {
        "category_hints": raw.get("category_hints") or [],
        "user_hints": raw.get("user_hints") or [],
        "category_budget_map": raw.get("category_budget_map") or {},
    }


@router.put("/api/settings/classification-hints", dependencies=[Depends(get_current_user)])
def put_classification_hints(body: ClassificationHintsIn, conn=Depends(get_db)):
    _set_config(conn, "classification_hints", {
        "category_hints": body.category_hints,
        "user_hints": body.user_hints,
        "category_budget_map": body.category_budget_map,
    })
    return {"ok": True}


# ── LLM Config ──────────────────────────────────────────────────────


class FunctionModelIn(BaseModel):
    provider: str
    model: str
    reason: str | None = None


class LLMProviderIn(BaseModel):
    type: str
    api_key_env: str | None = None
    base_url: str | None = None
    models: list[str]


class LLMConfigIn(BaseModel):
    default_provider: str
    default_model: str
    providers: dict[str, LLMProviderIn]
    function_models: dict[str, FunctionModelIn]
    timeout_seconds: int
    max_retries: int
    temperature: float


@router.get("/api/settings/llm-config", dependencies=[Depends(get_current_user)])
def get_llm_config(conn=Depends(get_db)):
    raw = _get_config(conn, "llm_config") or {}
    return {
        "default_provider": raw.get("default_provider", ""),
        "default_model": raw.get("default_model", ""),
        "providers": raw.get("providers") or {},
        "function_models": raw.get("function_models") or {},
        "timeout_seconds": raw.get("timeout_seconds", 120),
        "max_retries": raw.get("max_retries", 2),
        "temperature": raw.get("temperature", 0.0),
    }


@router.put("/api/settings/llm-config", dependencies=[Depends(get_current_user)])
def put_llm_config(body: LLMConfigIn, conn=Depends(get_db)):
    providers = {}
    for name, p in body.providers.items():
        entry: dict[str, Any] = {"type": p.type}
        if p.api_key_env:
            entry["api_key_env"] = p.api_key_env
        if p.base_url:
            entry["base_url"] = p.base_url
        entry["models"] = p.models
        providers[name] = entry

    fn_models = {}
    for name, fm in body.function_models.items():
        entry = {"provider": fm.provider, "model": fm.model}
        if fm.reason:
            entry["reason"] = fm.reason
        fn_models[name] = entry

    _set_config(conn, "llm_config", {
        "default_provider": body.default_provider,
        "default_model": body.default_model,
        "providers": providers,
        "function_models": fn_models,
        "timeout_seconds": body.timeout_seconds,
        "max_retries": body.max_retries,
        "temperature": body.temperature,
    })
    from llm.backend import LLMBackend
    LLMBackend._instance = None
    return {"ok": True}

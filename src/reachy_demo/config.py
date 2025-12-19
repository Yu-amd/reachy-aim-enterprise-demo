from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _env(key: str, default: str | None = None) -> str | None:
    v = os.getenv(key)
    if v is None or v == "":
        return default
    return v

def _env_int(key: str, default: int) -> int:
    v = _env(key)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default

def _env_bool(key: str, default: bool) -> bool:
    v = _env(key)
    if v is None:
        return default
    return v.lower() in ("true", "1", "yes", "on")

def _env_float(key: str, default: float) -> float:
    v = _env(key)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default

@dataclass(frozen=True)
class Settings:
    # AIM (OpenAI-compatible)
    aim_base_url: str
    aim_chat_path: str = "/v1/chat/completions"
    aim_model: str = "llm-prod"
    aim_api_key: str | None = None
    aim_timeout_ms: int = 30000  # 30 seconds - local LLMs need more time
    aim_max_retries: int = 1
    aim_max_tokens: int = 200  # Increased to allow for thinking tokens (100) + response (100)

    # Reachy Mini daemon
    reachy_daemon_url: str = "http://127.0.0.1:8001"  # Default 8001 to avoid AIM port conflicts
    robot_mode: str = "sim"  # sim|hardware

    # SLO + metrics
    e2e_slo_ms: int = 2500
    metrics_host: str = "127.0.0.1"
    metrics_port: int = 9100

def load_settings() -> Settings:
    base = _env("AIM_BASE_URL")
    if not base:
        raise RuntimeError("AIM_BASE_URL is required. Set it in .env or environment.")
    return Settings(
        aim_base_url=base.rstrip("/"),
        aim_chat_path=_env("AIM_CHAT_PATH", "/v1/chat/completions") or "/v1/chat/completions",
        aim_model=_env("AIM_MODEL", "llm-prod") or "llm-prod",
        aim_api_key=_env("AIM_API_KEY", None),
        aim_timeout_ms=_env_int("AIM_TIMEOUT_MS", 30000),  # 30 seconds default
        aim_max_retries=_env_int("AIM_MAX_RETRIES", 1),
        aim_max_tokens=_env_int("AIM_MAX_TOKENS", 200),  # Default: 200 (100 for thinking + 100 for response)
        reachy_daemon_url=_env("REACHY_DAEMON_URL", "http://127.0.0.1:8001") or "http://127.0.0.1:8001",
        robot_mode=_env("ROBOT_MODE", "sim") or "sim",
        e2e_slo_ms=_env_int("E2E_SLO_MS", 2500),
        metrics_host=_env("EDGE_METRICS_HOST", "127.0.0.1") or "127.0.0.1",
        metrics_port=_env_int("EDGE_METRICS_PORT", 9100),
    )

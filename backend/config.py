from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = APP_DIR.parent

load_dotenv(REPO_DIR / ".env")
load_dotenv(APP_DIR / ".env")


def _normalize_bright_data_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if parsed.path.endswith("/sse"):
        return urlunparse(parsed._replace(path=parsed.path[: -len("/sse")] + "/mcp"))
    return urlunparse(parsed)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_url: str
    openrouter_api_key: str
    openrouter_base_url: str
    default_models: tuple[str, ...]
    openrouter_timeout_seconds: float
    bright_data_api_key: str
    bright_data_mcp_url: str
    bright_data_mcp_pro_mode: bool
    bright_data_mcp_groups: str
    bright_data_mcp_tools: str
    bright_data_timeout_seconds: float
    bright_data_retries: int
    search_engine: str
    search_max_results: int
    search_max_total_results: int
    frontend_origins: tuple[str, ...]
    data_path: Path
    storage_dir: Path
    supabase_url: str
    supabase_service_key: str

    @property
    def bright_data_mcp_url_with_token(self) -> str:
        parsed = urlparse(self.bright_data_mcp_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if "token" not in query and self.bright_data_api_key:
            query["token"] = self.bright_data_api_key
        if self.bright_data_mcp_tools and "tools" not in query:
            query["tools"] = self.bright_data_mcp_tools
        elif self.bright_data_mcp_groups and "groups" not in query:
            query["groups"] = self.bright_data_mcp_groups
        elif self.bright_data_mcp_pro_mode and "pro" not in query:
            query["pro"] = "1"
        return urlunparse(parsed._replace(query=urlencode(query, safe=",")))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_models = tuple(
        item.strip()
        for item in os.getenv(
            "AGENT_ARENA_MODELS",
            "anthropic/claude-sonnet-4.6,openai/gpt-4o,google/gemini-2.5-pro,perplexity/sonar-pro-search,perplexity/sonar-deep-research,x-ai/grok-4.3,openai/gpt-4o-mini,openai/gpt-oss-120b,deepseek/deepseek-v4-flash,nvidia/nemotron-3-super-120b-a12b,google/gemini-3.1-flash-lite,anthropic/claude-opus-4.7",
        ).split(",")
        if item.strip()
    )
    origins = [
        "http://localhost:8787",
        "http://127.0.0.1:8787",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    origins.extend(
        origin.strip()
        for origin in os.getenv("AGENT_ARENA_FRONTEND_ORIGINS", "").split(",")
        if origin.strip()
    )
    return Settings(
        app_name=os.getenv("AGENT_ARENA_APP_NAME", "Agent Royale"),
        app_url=os.getenv("AGENT_ARENA_APP_URL", "http://localhost:8787"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        default_models=default_models,
        openrouter_timeout_seconds=float(
            os.getenv("OPENROUTER_REQUEST_TIMEOUT_SECONDS", "30")
        ),
        bright_data_api_key=os.getenv("BRIGHT_DATA_API_KEY", ""),
        bright_data_mcp_url=_normalize_bright_data_url(
            os.getenv("BRIGHT_DATA_MCP_URL", "https://mcp.brightdata.com/mcp")
        ),
        bright_data_mcp_pro_mode=_env_bool("BRIGHT_DATA_MCP_PRO_MODE", False),
        bright_data_mcp_groups=os.getenv("BRIGHT_DATA_MCP_GROUPS", "").strip(),
        bright_data_mcp_tools=os.getenv("BRIGHT_DATA_MCP_TOOLS", "").strip(),
        bright_data_timeout_seconds=float(
            os.getenv("BRIGHT_DATA_REQUEST_TIMEOUT_SECONDS", "25")
        ),
        bright_data_retries=int(os.getenv("BRIGHT_DATA_MAX_RETRIES", "1")),
        search_engine=os.getenv("AGENT_ARENA_SEARCH_ENGINE", "native"),
        search_max_results=int(os.getenv("AGENT_ARENA_SEARCH_MAX_RESULTS", "5")),
        search_max_total_results=int(os.getenv("AGENT_ARENA_SEARCH_MAX_TOTAL_RESULTS", "10")),
        frontend_origins=tuple(dict.fromkeys(origins)),
        data_path=Path(os.getenv("AGENT_ARENA_TASKS_PATH", APP_DIR / "data" / "tasks.csv")),
        storage_dir=Path(os.getenv("AGENT_ARENA_STORAGE_DIR", APP_DIR / "storage")),
        supabase_url=os.getenv("SUPABASE_URL", "").rstrip("/"),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        or os.getenv("SUPABASE_SECRET_KEY", ""),
    )

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    debug: bool
    api_prefix: str
    openai_api_key: str
    openai_base_url: str
    default_chat_model: str
    use_openai_dialog: bool
    openai_dialog_model: str
    openai_dialog_reasoning_effort: str
    openai_dialog_timeout_seconds: float
    use_openai_planner: bool
    planner_api_key: str
    planner_base_url: str
    planner_model: str
    planner_timeout_seconds: float
    use_openai_slide_planner: bool
    slide_planner_api_key: str
    slide_planner_base_url: str
    slide_planner_model: str
    slide_planner_timeout_seconds: float
    embeddings_backend: str
    embeddings_model: str
    local_embedding_dim: int
    transcribe_model: str
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_default_top_k: int
    web_search_enabled: bool
    web_search_provider: str
    web_search_default_top_k: int
    web_search_timeout_seconds: float
    project_root: Path
    data_dir: Path
    raw_data_dir: Path
    parsed_data_dir: Path
    knowledge_base_dir: Path
    vector_store_dir: Path
    exports_dir: Path
    workspaces_dir: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = PROJECT_ROOT / "data"
    return Settings(
        app_name=os.getenv("APP_NAME", "Teaching Agent"),
        app_env=os.getenv("APP_ENV", "development"),
        debug=_get_bool("APP_DEBUG", default=True),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
        default_chat_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        use_openai_dialog=_get_bool("USE_OPENAI_DIALOG", default=False),
        openai_dialog_model=os.getenv("OPENAI_DIALOG_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.4")),
        openai_dialog_reasoning_effort=os.getenv("OPENAI_DIALOG_REASONING_EFFORT", "medium").strip().lower(),
        openai_dialog_timeout_seconds=float(os.getenv("OPENAI_DIALOG_TIMEOUT_SECONDS", "30")),
        use_openai_planner=_get_bool("USE_OPENAI_PLANNER", default=False),
        planner_api_key=os.getenv("PLANNER_API_KEY", "").strip(),
        planner_base_url=os.getenv("PLANNER_BASE_URL", "").strip(),
        planner_model=os.getenv("PLANNER_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.4")).strip(),
        planner_timeout_seconds=float(os.getenv("PLANNER_TIMEOUT_SECONDS", "45")),
        use_openai_slide_planner=_get_bool("USE_OPENAI_SLIDE_PLANNER", default=False),
        slide_planner_api_key=os.getenv("SLIDE_PLANNER_API_KEY", "").strip(),
        slide_planner_base_url=os.getenv("SLIDE_PLANNER_BASE_URL", "").strip(),
        slide_planner_model=os.getenv("SLIDE_PLANNER_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.4")).strip(),
        slide_planner_timeout_seconds=float(os.getenv("SLIDE_PLANNER_TIMEOUT_SECONDS", "60")),
        embeddings_backend=os.getenv("EMBEDDINGS_BACKEND", "local"),
        embeddings_model=os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small"),
        local_embedding_dim=int(os.getenv("LOCAL_EMBEDDING_DIM", "256")),
        transcribe_model=os.getenv("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
        rag_chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "400")),
        rag_chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "80")),
        rag_default_top_k=int(os.getenv("RAG_DEFAULT_TOP_K", "5")),
        web_search_enabled=_get_bool("WEB_SEARCH_ENABLED", default=False),
        web_search_provider=os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo").strip().lower(),
        web_search_default_top_k=int(os.getenv("WEB_SEARCH_DEFAULT_TOP_K", "3")),
        web_search_timeout_seconds=float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "8")),
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        raw_data_dir=data_dir / "raw",
        parsed_data_dir=data_dir / "parsed",
        knowledge_base_dir=data_dir / "kb",
        vector_store_dir=PROJECT_ROOT / "vector_store",
        exports_dir=PROJECT_ROOT / "exports",
        workspaces_dir=data_dir / "workspaces",
    )

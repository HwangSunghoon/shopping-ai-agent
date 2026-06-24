import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)


class Settings:
    chatku_api_key: str = os.getenv("CHATKU_API_KEY", "")
    chatku_base_url: str = os.getenv("CHATKU_BASE_URL", "")
    chatku_model: str = os.getenv("CHATKU_MODEL", "gpt-5.4")
    chatku_model_planner: str = os.getenv("CHATKU_MODEL_PLANNER", "")
    chatku_model_extractor: str = os.getenv("CHATKU_MODEL_EXTRACTOR", "")
    chatku_model_followup: str = os.getenv("CHATKU_MODEL_FOLLOWUP", "")
    chatku_model_summary: str = os.getenv("CHATKU_MODEL_SUMMARY", "")

    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./shopping_agent.db")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    planner_cache_ttl_seconds: int = int(os.getenv("PLANNER_CACHE_TTL_SECONDS", "1800"))
    naver_cache_ttl_seconds: int = int(os.getenv("NAVER_CACHE_TTL_SECONDS", "600"))
    planner_llm_threshold: int = int(os.getenv("PLANNER_LLM_THRESHOLD", "3"))
    llm_cache_ttl_seconds: int = int(os.getenv("LLM_CACHE_TTL_SECONDS", "900"))
    naver_timeout_seconds: float = float(os.getenv("NAVER_TIMEOUT_SECONDS", "12"))
    naver_max_retries: int = int(os.getenv("NAVER_MAX_RETRIES", "2"))
    chatku_timeout_seconds: float = float(os.getenv("CHATKU_TIMEOUT_SECONDS", "12"))
    chatku_max_retries: int = int(os.getenv("CHATKU_MAX_RETRIES", "1"))
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    db_pool_recycle_seconds: int = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    rate_limit_max_requests: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "120"))
    home_cache_ttl_seconds: int = int(os.getenv("HOME_CACHE_TTL_SECONDS", "300"))

    def model_for_task(self, task: str) -> str:
        if task == "planner" and self.chatku_model_planner:
            return self.chatku_model_planner
        if task == "extractor" and self.chatku_model_extractor:
            return self.chatku_model_extractor
        if task == "followup" and self.chatku_model_followup:
            return self.chatku_model_followup
        if task == "summary" and self.chatku_model_summary:
            return self.chatku_model_summary
        return self.chatku_model


@lru_cache
def get_settings() -> Settings:
    return Settings()

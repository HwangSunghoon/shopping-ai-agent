import json
import logging
import sqlite3
import time
import traceback
from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.schemas import (
    AgentFeedbackRequest,
    AgentFinalSelectRequest,
    AgentRefineRequest,
    AgentSearchRequest,
    AgentSearchResponse,
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    HistoryItem,
    RecommendRequest,
    RecommendResponse,
    SearchDetailResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.agent_service import run_agent_refine, run_agent_search, save_agent_feedback, save_final_selection
from app.services.chat_service import answer_chat
from app.services.preference_service import apply_feedback_to_preferences, load_user_preferences, record_user_event
from app.services.recommendation_service import recommend_products
from app.services.search_service import execute_search, get_search_detail, list_history

settings = get_settings()
logger = logging.getLogger("shopping_agent")
logging.basicConfig(level=logging.INFO, format="%(message)s")
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()


def ensure_sqlite_search_session_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    sqlite_path = settings.database_url.replace("sqlite:///", "", 1)
    connection = sqlite3.connect(sqlite_path)
    try:
        cursor = connection.execute("PRAGMA table_info(search_sessions)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        columns_to_add = [
            ("user_id", "TEXT"),
            ("intent_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("search_terms_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("assistant_mode", "TEXT NOT NULL DEFAULT 'llm'"),
            ("llm_failed", "BOOLEAN NOT NULL DEFAULT 0"),
        ]

        for column_name, column_ddl in columns_to_add:
            if column_name not in existing_columns:
                connection.execute(f"ALTER TABLE search_sessions ADD COLUMN {column_name} {column_ddl}")

        if {"conditions_json", "search_queries_json"}.issubset(existing_columns):
            connection.execute(
                "UPDATE search_sessions SET intent_json = COALESCE(NULLIF(intent_json, '{}'), conditions_json)"
            )
            connection.execute(
                "UPDATE search_sessions SET search_terms_json = COALESCE(NULLIF(search_terms_json, '[]'), search_queries_json)"
            )
        connection.commit()
    finally:
        connection.close()


Base.metadata.create_all(bind=engine)
ensure_sqlite_search_session_columns()

app = FastAPI(title="Shopping AI Agent MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id

    if request.method != "OPTIONS" and request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        with _RATE_LIMIT_LOCK:
            bucket = _RATE_LIMIT_BUCKETS[client_ip]
            while bucket and now - bucket[0] > settings.rate_limit_window_seconds:
                bucket.popleft()
            if len(bucket) >= settings.rate_limit_max_requests:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."},
                )
                response.headers["X-Request-ID"] = request_id
                return response
            bucket.append(now)

    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            json.dumps(
                {
                    "event": "request_error",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": request.url.query,
                    "latency_ms": latency_ms,
                },
                ensure_ascii=False,
            )
        )
        raise

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "request_complete",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
            ensure_ascii=False,
        )
    )
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": settings.chatku_model,
        "models": {
            "planner": settings.model_for_task("planner"),
            "extractor": settings.model_for_task("extractor"),
            "followup": settings.model_for_task("followup"),
            "summary": settings.model_for_task("summary"),
        },
        "llm_ready": bool(settings.chatku_api_key),
        "naver_ready": bool(settings.naver_client_id and settings.naver_client_secret),
    }


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest, db: Session = Depends(get_db)):
    try:
        payload = await execute_search(db, request.query, user_id=request.user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return payload


@app.get("/api/search/{search_id}", response_model=SearchDetailResponse)
def search_detail(search_id: int, db: Session = Depends(get_db)):
    payload = get_search_detail(db, search_id)
    if not payload:
        raise HTTPException(status_code=404, detail="검색 기록을 찾을 수 없습니다.")
    return payload


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        payload = answer_chat(
            db,
            request.search_id,
            request.message,
            selected_product_link=request.selected_product_link,
            selected_product_title=request.selected_product_title,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return payload


@app.get("/api/history", response_model=list[HistoryItem])
def history(db: Session = Depends(get_db)):
    return list_history(db)


@app.post("/api/feedback")
def feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    try:
        event = record_user_event(
            db,
            request.user_id,
            request.event_type,
            query=request.query,
            product=request.product,
            reason=request.reason,
        )
        updated_preferences = apply_feedback_to_preferences(
            db,
            request.user_id,
            request.event_type,
            product=request.product,
            query=request.query,
            reason=request.reason,
        )
        current_preferences = load_user_preferences(db, request.user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "ok",
        "event_id": event.id,
        "updated_preference_count": len(updated_preferences),
        "preferences": current_preferences,
    }


@app.post("/api/recommend", response_model=RecommendResponse)
async def recommend(request: RecommendRequest, db: Session = Depends(get_db)):
    try:
        payload = await recommend_products(db, request.user_id, request.query, limit=request.limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return payload


@app.post("/api/agent/search", response_model=AgentSearchResponse)
async def agent_search(request: AgentSearchRequest, db: Session = Depends(get_db)):
    try:
        payload = await run_agent_search(
            db,
            user_id=request.user_id,
            query=request.query,
            conversation_id=request.conversation_id,
            filters=request.filters,
            page=request.page,
            display=request.display,
            track_event=request.track_event,
            search_term_limit=request.search_term_limit,
            conversation_context=request.conversation_context,
        )
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "agent_search_failed",
                    "query": request.query,
                    "page": request.page,
                    "display": request.display,
                    "track_event": request.track_event,
                    "conversation_id": request.conversation_id,
                },
                ensure_ascii=False,
            )
        )
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return payload


@app.post("/api/agent/refine", response_model=AgentSearchResponse)
async def agent_refine(request: AgentRefineRequest, db: Session = Depends(get_db)):
    try:
        payload = await run_agent_refine(
            db,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            message=request.message,
            current_product_ids=request.current_product_ids,
            current_top3_ids=request.current_top3_ids,
            current_products=request.current_products,
            current_top3_products=request.current_top3_products,
            filters=request.filters,
            page=request.page,
            display=request.display,
            conversation_context=request.conversation_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return payload


@app.post("/api/agent/feedback")
def agent_feedback(request: AgentFeedbackRequest, db: Session = Depends(get_db)):
    try:
        return save_agent_feedback(
            db,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            product_id=request.product_id,
            event_type=request.event_type,
            metadata=request.metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/agent/final-select")
def agent_final_select(request: AgentFinalSelectRequest, db: Session = Depends(get_db)):
    try:
        return save_final_selection(
            db,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            product_id=request.product_id,
            product=request.product,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

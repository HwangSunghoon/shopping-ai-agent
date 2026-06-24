import asyncio
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import ChatTurn, SearchSession
from app.schemas import ChatMessage
from app.services.fallback_service import build_search_summary_fallback, is_similar_title, normalize_title_key
from app.services.naver_api import search_naver_shopping
from app.services.query_planner import build_query_plan
from app.services.ranking import rank_products


def _serialize_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for product in products:
        item = dict(product)
        if item.get("lprice") is not None:
            item["lprice"] = int(item["lprice"])
        serialized.append(item)
    return serialized


def _dedupe_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    seen_titles: list[str] = []

    for product in products:
        link = (product.get("link") or "").strip()
        title = product.get("title") or ""
        title_key = normalize_title_key(title)

        if link and link in seen_links:
            continue

        similar = any(is_similar_title(title_key, seen_title) for seen_title in seen_titles)
        if similar:
            continue

        if link:
            seen_links.add(link)
        if title_key:
            seen_titles.append(title_key)
        deduped.append(product)

    return deduped


async def _search_all_terms(search_terms: list[str]) -> tuple[list[tuple[str, list[dict[str, Any]]]], list[str]]:
    tasks = [search_naver_shopping(term, display=24) for term in search_terms]
    if not tasks:
        return [], []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    batches: list[tuple[str, list[dict[str, Any]]]] = []
    failed_terms: list[str] = []
    for term, result in zip(search_terms, results):
        if isinstance(result, Exception):
            failed_terms.append(term)
            continue
        batches.append((term, result))
    return batches, failed_terms


def _history_payload(turns: list[ChatTurn]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for turn in sorted(turns, key=lambda item: item.created_at):
        if getattr(turn, "user_message", None):
            history.append(
                {
                    "role": "user",
                    "message": turn.user_message,
                    "created_at": turn.created_at.isoformat(),
                }
            )
        if getattr(turn, "assistant_message", None):
            history.append(
                {
                    "role": "assistant",
                    "message": turn.assistant_message,
                    "created_at": turn.created_at.isoformat(),
                }
            )
    return history


def _load_json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


async def execute_search(db: Session, user_query: str, user_id: str | None = None) -> dict[str, Any]:
    plan = build_query_plan(user_query)
    intent = plan["intent"]
    search_terms = plan["search_terms"]

    successful_batches, failed_terms = await _search_all_terms(search_terms)

    raw_results: list[dict[str, Any]] = []
    for term, batch in successful_batches:
        for product in batch:
            item = dict(product)
            item["search_term"] = term
            raw_results.append(item)

    deduped_products = _dedupe_products(raw_results)
    ranked_products, recommendations = rank_products(deduped_products, intent, top_k=3)
    final_candidates = ranked_products[:50]
    recommendations = recommendations[:3]

    fallback_active = bool(plan["fallback_used"] or failed_terms)
    fallback_reason = plan["fallback_reason"]
    if failed_terms and not fallback_reason:
        fallback_reason = "네이버 쇼핑 검색 일부가 실패해 성공한 결과만 사용했습니다."

    assistant_message = build_search_summary_fallback(user_query, intent, recommendations, fallback_active=fallback_active or plan["fallback_used"])
    summary_mode = "fallback"

    session = SearchSession(
        user_id=user_id,
        query=user_query,
        conditions_json=json.dumps(intent, ensure_ascii=False),
        search_queries_json=json.dumps(search_terms, ensure_ascii=False),
        intent_json=json.dumps(intent, ensure_ascii=False),
        search_terms_json=json.dumps(search_terms, ensure_ascii=False),
        raw_products_json=json.dumps(_serialize_products(raw_results), ensure_ascii=False),
        candidate_products_json=json.dumps(_serialize_products(final_candidates), ensure_ascii=False),
        recommended_products_json=json.dumps(_serialize_products(recommendations), ensure_ascii=False),
        assistant_message=assistant_message,
        summary=assistant_message,
        assistant_mode=summary_mode,
        clarification_questions_json=json.dumps(plan["clarification_questions"], ensure_ascii=False),
        fallback_active=fallback_active,
        fallback_reason=fallback_reason,
        llm_failed=plan["llm_failed"],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "search_id": session.id,
        "query": user_query,
        "intent": intent,
        "search_terms": search_terms,
        "raw_result_count": len(raw_results),
        "candidate_count": len(final_candidates),
        "products": _serialize_products(final_candidates),
        "recommendations": _serialize_products(recommendations),
        "assistant_message": assistant_message,
        "summary_mode": summary_mode,
        "fallback_active": fallback_active,
        "fallback_reason": fallback_reason,
        "needs_clarification": False,
        "clarification_questions": plan["clarification_questions"],
    }


def get_search_detail(db: Session, search_id: int) -> dict[str, Any] | None:
    session = db.get(SearchSession, search_id)
    if not session:
        return None

    chat_history = _history_payload(session.chat_turns)

    return {
        "search_id": session.id,
        "query": session.query,
        "intent": json.loads(session.intent_json or "{}"),
        "search_terms": _load_json_list(session.search_terms_json),
        "raw_result_count": len(_load_json_list(session.raw_products_json)),
        "candidate_count": len(_load_json_list(session.candidate_products_json)),
        "products": _load_json_list(session.candidate_products_json),
        "recommendations": _load_json_list(session.recommended_products_json),
        "assistant_message": session.assistant_message,
        "summary_mode": session.assistant_mode,
        "fallback_active": session.fallback_active,
        "fallback_reason": session.fallback_reason,
        "needs_clarification": False,
        "clarification_questions": _load_json_list(session.clarification_questions_json),
        "chat_history": chat_history,
    }


def list_history(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    sessions = db.query(SearchSession).order_by(SearchSession.created_at.desc()).limit(limit).all()
    return [
        {
            "id": session.id,
            "query": session.query,
            "assistant_message": session.assistant_message,
            "fallback_active": session.fallback_active,
            "created_at": session.created_at.isoformat(),
            "search_terms": _load_json_list(session.search_terms_json),
        }
        for session in sessions
    ]


def append_chat_turn(db: Session, search_id: int, role: str, message: str, fallback_used: bool = False) -> ChatTurn:
    turn = ChatTurn(
        search_session_id=search_id,
        user_message=message if role == "user" else "",
        assistant_message=message if role == "assistant" else "",
        fallback_active=fallback_used,
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return turn


def build_chat_history(turns: list[ChatTurn]) -> list[ChatMessage]:
    return _history_payload(turns)

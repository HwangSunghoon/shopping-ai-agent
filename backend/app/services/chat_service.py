from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import SearchSession
from app.services.fallback_service import build_followup_answer_fallback
from app.services.llm_service import answer_followup
from app.services.search_service import append_chat_turn, build_chat_history, get_search_detail


def _compact_product(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": product.get("title"),
        "price": product.get("lprice"),
        "mall_name": product.get("mall_name"),
        "category": product.get("category"),
        "score": product.get("score"),
        "reason": product.get("reason"),
        "caution": product.get("caution"),
        "link": product.get("link"),
    }


def _compact_chat_history(chat_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recent_turns = chat_history[-2:]
    return [
        {
            "role": turn.get("role"),
            "message": turn.get("message"),
        }
        for turn in recent_turns
    ]


def _session_context(search_detail: dict[str, Any]) -> dict[str, Any]:
    recommendations = [_compact_product(product) for product in (search_detail.get("recommendations") or [])[:3]]
    products = [_compact_product(product) for product in (search_detail.get("products") or [])[:5]]
    return {
        "query": search_detail.get("query"),
        "intent": search_detail.get("intent", {}),
        "search_terms": (search_detail.get("search_terms") or [])[:3],
        "recommendations": recommendations,
        "products": products,
        "assistant_message": search_detail.get("assistant_message", ""),
    }


def _find_selected_product(search_detail: dict[str, Any], selected_product_link: str | None, selected_product_title: str | None) -> dict[str, Any] | None:
    products = (search_detail.get("products") or []) + (search_detail.get("recommendations") or [])
    if selected_product_link:
        for product in products:
            if product.get("link") == selected_product_link:
                return product

    if selected_product_title:
        normalized_title = selected_product_title.strip().lower()
        for product in products:
            title = (product.get("title") or "").strip().lower()
            if title and normalized_title and normalized_title in title:
                return product

    return None


def answer_chat(db: Session, search_id: int, user_message: str, selected_product_link: str | None = None, selected_product_title: str | None = None) -> dict[str, Any]:
    session = db.get(SearchSession, search_id)
    if not session:
        raise HTTPException(status_code=404, detail="검색 기록을 찾을 수 없습니다.")

    search_detail = get_search_detail(db, search_id)
    if not search_detail:
        raise HTTPException(status_code=404, detail="검색 기록을 찾을 수 없습니다.")

    chat_history_payload = search_detail.get("chat_history", [])
    compact_chat_history = _compact_chat_history(chat_history_payload)
    selected_product = _find_selected_product(search_detail, selected_product_link, selected_product_title)
    compact_selected_product = _compact_product(selected_product) if selected_product else None
    fallback_used = False

    try:
        assistant_message = answer_followup(user_message, _session_context(search_detail), compact_chat_history, compact_selected_product)
        summary_mode = "llm"
    except Exception:
        assistant_message = build_followup_answer_fallback(user_message, _session_context(search_detail), compact_chat_history, compact_selected_product)
        summary_mode = "fallback"
        fallback_used = True

    append_chat_turn(db, search_id, "user", user_message, fallback_used=False)
    append_chat_turn(db, search_id, "assistant", assistant_message, fallback_used=fallback_used)

    updated_session = db.get(SearchSession, search_id)
    if not updated_session:
        raise HTTPException(status_code=404, detail="검색 기록을 찾을 수 없습니다.")

    return {
        "search_id": search_id,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "fallback_active": fallback_used,
        "summary_mode": summary_mode,
        "selected_product_link": selected_product_link,
        "selected_product_title": selected_product_title,
        "chat_history": build_chat_history(updated_session.chat_turns),
    }

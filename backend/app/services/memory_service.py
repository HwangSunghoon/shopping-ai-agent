import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import UserEvent, UserMemory, UserPreference
from app.services.embedding_service import keyword_similarity

POSITIVE_MEMORY_EVENTS = {"click", "like", "save", "purchase_intent", "final_select"}
NEGATIVE_MEMORY_EVENTS = {"dislike", "remove", "not_relevant", "too_expensive", "low_quality", "review_too_low"}
PROFILE_REFRESH_EVENT = "profile_refresh"


def _dedupe_values(values: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, "", []):
            continue
        try:
            key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            key = str(value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _load_metadata(row: UserMemory) -> dict[str, Any]:
    if not row.metadata_json:
        return {}
    try:
        parsed = json.loads(row.metadata_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _memory_strength(event_type: str) -> float:
    if event_type == PROFILE_REFRESH_EVENT:
        return 0.92
    if event_type == "final_select":
        return 1.0
    if event_type in {"purchase_intent", "like", "save"}:
        return 0.85
    if event_type in {"too_expensive", "not_relevant", "dislike"}:
        return 0.8
    if event_type in {"search", "refine_query"}:
        return 0.55
    return 0.5


def _memory_documents(
    event_type: str,
    query: str | None,
    product: dict[str, Any],
    query_preferences: dict[str, Any],
    reason: str | None,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    brand = product.get("brand")
    category = product.get("category")
    mall_name = product.get("mall_name")
    title = product.get("title")
    price = product.get("price")
    features = query_preferences.get("liked_features") or []
    dislikes = query_preferences.get("disliked_features") or []

    if query:
        lines = [f"사용자 검색: {query}"]
        if query_preferences.get("category"):
            lines.append(f"카테고리 선호: {query_preferences['category']}")
        if query_preferences.get("price_min") is not None or query_preferences.get("price_max") is not None:
            lines.append(
                f"가격 조건: {query_preferences.get('price_min') or 0}~{query_preferences.get('price_max') or '제한 없음'}"
            )
        if features:
            lines.append(f"선호 특징: {', '.join(features)}")
        if dislikes:
            lines.append(f"비선호 특징: {', '.join(dislikes)}")
        documents.append(
            {
                "memory_type": "query_preference",
                "content": " / ".join(lines),
                "metadata": {
                    "query": query,
                    "query_preferences": query_preferences,
                },
            }
        )

    if title:
        sentiment = "긍정 평가" if event_type in POSITIVE_MEMORY_EVENTS else "부정 평가"
        lines = [f"사용자 {sentiment}: {title}"]
        if brand:
            lines.append(f"브랜드: {brand}")
        if category:
            lines.append(f"카테고리: {category}")
        if price is not None:
            lines.append(f"가격: {price}")
        if mall_name:
            lines.append(f"쇼핑몰: {mall_name}")
        if reason:
            lines.append(f"이유: {reason}")
        documents.append(
            {
                "memory_type": "product_feedback",
                "content": " / ".join(lines),
                "metadata": {
                    "product": product,
                    "query_preferences": query_preferences,
                    "reason": reason,
                },
            }
        )

    return documents


def store_interaction_memories(
    db: Session,
    *,
    user_id: str,
    event_type: str,
    query: str | None,
    product: dict[str, Any],
    query_preferences: dict[str, Any],
    reason: str | None,
) -> list[UserMemory]:
    memories: list[UserMemory] = []
    documents = _memory_documents(event_type, query, product, query_preferences, reason)
    strength = _memory_strength(event_type)

    for document in documents:
        memory = UserMemory(
            user_id=user_id,
            memory_type=document["memory_type"],
            source_event_type=event_type,
            content=document["content"],
            strength=strength,
            metadata_json=json.dumps(document["metadata"], ensure_ascii=False),
        )
        db.add(memory)
        memories.append(memory)

    if memories:
        db.commit()
        for memory in memories:
            db.refresh(memory)
    return memories


def _upsert_summary_memory(
    db: Session,
    *,
    user_id: str,
    memory_type: str,
    content: str,
    metadata: dict[str, Any],
    strength: float = 0.92,
) -> UserMemory:
    row = (
        db.query(UserMemory)
        .filter(
            UserMemory.user_id == user_id,
            UserMemory.memory_type == memory_type,
            UserMemory.source_event_type == PROFILE_REFRESH_EVENT,
        )
        .first()
    )

    if not row:
        row = UserMemory(
            user_id=user_id,
            memory_type=memory_type,
            source_event_type=PROFILE_REFRESH_EVENT,
            content=content,
            strength=strength,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
        db.add(row)
    else:
        row.content = content
        row.strength = strength
        row.metadata_json = json.dumps(metadata, ensure_ascii=False)
    return row


def _top_preference_values(
    rows: list[UserPreference],
    preference_type: str,
    limit: int = 3,
) -> list[str]:
    filtered = [row for row in rows if row.preference_type == preference_type]
    filtered.sort(key=lambda row: (row.confidence, row.positive_count, -row.negative_count), reverse=True)
    return [row.value for row in filtered[:limit] if row.value]


def refresh_user_profile_memories(db: Session, user_id: str) -> list[UserMemory]:
    preference_rows = db.query(UserPreference).filter(UserPreference.user_id == user_id).all()
    event_rows = (
        db.query(UserEvent)
        .filter(UserEvent.user_id == user_id)
        .order_by(UserEvent.created_at.desc())
        .limit(30)
        .all()
    )

    if not preference_rows and not event_rows:
        return []

    liked_features = _top_preference_values(preference_rows, "feature_like", limit=5)
    disliked_features = _top_preference_values(preference_rows, "feature_dislike", limit=5)
    liked_categories = _top_preference_values(preference_rows, "category_like", limit=4)
    liked_brands = _top_preference_values(preference_rows, "brand_like", limit=4)
    disliked_brands = _top_preference_values(preference_rows, "brand_dislike", limit=4)
    mall_likes = _top_preference_values(preference_rows, "mall_like", limit=3)
    mall_dislikes = _top_preference_values(preference_rows, "mall_dislike", limit=3)

    price_min_values = [int(row.value) for row in preference_rows if row.preference_type == "price_range" and row.key == "price_min" and row.value.isdigit()]
    price_max_values = [int(row.value) for row in preference_rows if row.preference_type == "price_range" and row.key == "price_max" and row.value.isdigit()]
    price_min = max(price_min_values) if price_min_values else None
    price_max = min(price_max_values) if price_max_values else None

    positive_events = [row for row in event_rows if row.event_type in POSITIVE_MEMORY_EVENTS]
    negative_events = [row for row in event_rows if row.event_type in NEGATIVE_MEMORY_EVENTS]
    frequent_queries = [row.query for row in event_rows if row.query][:5]

    summary_rows: list[UserMemory] = []

    if price_min is not None or price_max is not None:
        summary_rows.append(
            _upsert_summary_memory(
                db,
                user_id=user_id,
                memory_type="profile_summary_price",
                content=f"사용자 장기 가격 성향: {price_min or 0}원 이상, {price_max or '제한 없음'}원 이하를 선호함.",
                metadata={"price_min": price_min, "price_max": price_max},
            )
        )

    if liked_features or disliked_features:
        summary_rows.append(
            _upsert_summary_memory(
                db,
                user_id=user_id,
                memory_type="profile_summary_feature",
                content=(
                    f"사용자 장기 특징 성향: 선호 특징은 {', '.join(liked_features) or '없음'} / "
                    f"비선호 특징은 {', '.join(disliked_features) or '없음'}."
                ),
                metadata={"liked_features": liked_features, "disliked_features": disliked_features},
            )
        )

    if liked_categories or liked_brands or disliked_brands:
        summary_rows.append(
            _upsert_summary_memory(
                db,
                user_id=user_id,
                memory_type="profile_summary_category_brand",
                content=(
                    f"사용자 장기 카테고리/브랜드 성향: 선호 카테고리 {', '.join(liked_categories) or '없음'} / "
                    f"선호 브랜드 {', '.join(liked_brands) or '없음'} / "
                    f"비선호 브랜드 {', '.join(disliked_brands) or '없음'}."
                ),
                metadata={
                    "liked_categories": liked_categories,
                    "liked_brands": liked_brands,
                    "disliked_brands": disliked_brands,
                },
            )
        )

    if mall_likes or mall_dislikes or positive_events or negative_events or frequent_queries:
        summary_rows.append(
            _upsert_summary_memory(
                db,
                user_id=user_id,
                memory_type="profile_summary_behavior",
                content=(
                    f"사용자 장기 행동 성향: 최근 자주 찾은 검색은 {', '.join(frequent_queries[:3]) or '없음'} / "
                    f"선호 쇼핑몰 {', '.join(mall_likes) or '없음'} / "
                    f"비선호 쇼핑몰 {', '.join(mall_dislikes) or '없음'} / "
                    f"긍정 이벤트 {len(positive_events)}건 / 부정 이벤트 {len(negative_events)}건."
                ),
                metadata={
                    "frequent_queries": frequent_queries,
                    "mall_likes": mall_likes,
                    "mall_dislikes": mall_dislikes,
                    "positive_event_count": len(positive_events),
                    "negative_event_count": len(negative_events),
                },
            )
        )

    if summary_rows:
        db.commit()
        for row in summary_rows:
            db.refresh(row)
    return summary_rows


def retrieve_user_memories(db: Session, user_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id, UserMemory.source_event_type != PROFILE_REFRESH_EVENT)
        .order_by(UserMemory.updated_at.desc())
        .limit(80)
        .all()
    )
    scored: list[dict[str, Any]] = []
    for row in rows:
        similarity = keyword_similarity(query, row.content)
        recency_bonus = 0.08 if row.source_event_type in {"final_select", "like", "too_expensive"} else 0.03
        score = similarity * 0.75 + row.strength * 0.2 + recency_bonus
        scored.append(
            {
                "id": row.id,
                "memory_type": row.memory_type,
                "source_event_type": row.source_event_type,
                "content": row.content,
                "strength": row.strength,
                "score": round(score, 4),
                "metadata": _load_metadata(row),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def retrieve_profile_memories(db: Session, user_id: str, query: str, limit: int = 3) -> list[dict[str, Any]]:
    rows = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id, UserMemory.source_event_type == PROFILE_REFRESH_EVENT)
        .order_by(UserMemory.updated_at.desc())
        .all()
    )
    scored: list[dict[str, Any]] = []
    for row in rows:
        similarity = keyword_similarity(query, row.content)
        score = similarity * 0.7 + row.strength * 0.3
        scored.append(
            {
                "id": row.id,
                "memory_type": row.memory_type,
                "source_event_type": row.source_event_type,
                "content": row.content,
                "strength": row.strength,
                "score": round(score, 4),
                "metadata": _load_metadata(row),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def retrieve_memory_context(db: Session, user_id: str, query: str, raw_limit: int = 5, summary_limit: int = 3) -> dict[str, list[dict[str, Any]]]:
    raw_memories = retrieve_user_memories(db, user_id, query, limit=raw_limit)
    summary_memories = retrieve_profile_memories(db, user_id, query, limit=summary_limit)
    combined = sorted([*summary_memories, *raw_memories], key=lambda item: item["score"], reverse=True)
    return {
        "raw_memories": raw_memories,
        "summary_memories": summary_memories,
        "combined_memories": combined[: raw_limit + summary_limit],
    }


def build_preferences_from_memories(memories: list[dict[str, Any]]) -> dict[str, Any]:
    preferences: dict[str, Any] = {
        "price_min": 0,
        "price_max": None,
        "liked_brands": [],
        "disliked_brands": [],
        "liked_categories": [],
        "disliked_categories": [],
        "liked_features": [],
        "disliked_features": [],
        "mall_likes": [],
        "mall_dislikes": [],
        "memory_hints": [],
    }

    for memory in memories:
        metadata = memory.get("metadata", {})
        query_preferences = metadata.get("query_preferences", {})
        product = metadata.get("product", {})
        source_event_type = memory.get("source_event_type")
        preferences["memory_hints"].append(memory.get("content", ""))

        if source_event_type == PROFILE_REFRESH_EVENT:
            for key in ["price_min", "price_max"]:
                if metadata.get(key) is not None:
                    if key == "price_min":
                        preferences["price_min"] = max(preferences.get("price_min") or 0, int(metadata[key]))
                    else:
                        current_max = preferences.get("price_max")
                        incoming_max = int(metadata[key])
                        preferences["price_max"] = incoming_max if current_max is None else min(current_max, incoming_max)
            for key in ["liked_features", "disliked_features", "liked_categories", "liked_brands", "disliked_brands", "mall_likes", "mall_dislikes"]:
                for value in metadata.get(key, []) or []:
                    preferences[key].append(value)
            continue

        if query_preferences.get("price_min") is not None:
            preferences["price_min"] = max(preferences.get("price_min") or 0, int(query_preferences["price_min"]))
        if query_preferences.get("price_max") is not None:
            current_max = preferences.get("price_max")
            incoming_max = int(query_preferences["price_max"])
            preferences["price_max"] = incoming_max if current_max is None else min(current_max, incoming_max)

        for feature in query_preferences.get("liked_features", []) or []:
            preferences["liked_features"].append(feature)
        for feature in query_preferences.get("disliked_features", []) or []:
            preferences["disliked_features"].append(feature)
        if query_preferences.get("category"):
            preferences["liked_categories"].append(query_preferences["category"])

        brand = product.get("brand")
        category = product.get("category")
        mall_name = product.get("mall_name")
        price = product.get("price")

        if source_event_type in POSITIVE_MEMORY_EVENTS:
            if brand:
                preferences["liked_brands"].append(brand)
            if category:
                preferences["liked_categories"].append(category)
            if mall_name:
                preferences["mall_likes"].append(mall_name)
        if source_event_type in NEGATIVE_MEMORY_EVENTS:
            if brand:
                preferences["disliked_brands"].append(brand)
            if category:
                preferences["disliked_categories"].append(category)
            if mall_name:
                preferences["mall_dislikes"].append(mall_name)
            if source_event_type == "too_expensive" and price is not None:
                adjusted_max = max(0, int(price) - 10000)
                current_max = preferences.get("price_max")
                preferences["price_max"] = adjusted_max if current_max is None else min(current_max, adjusted_max)

    for key in ["liked_brands", "disliked_brands", "liked_categories", "disliked_categories", "liked_features", "disliked_features", "mall_likes", "mall_dislikes", "memory_hints"]:
        preferences[key] = _dedupe_values(preferences[key])
    return preferences


def merge_memory_preferences(base_preferences: dict[str, Any], memory_preferences: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_preferences)
    merged["price_min"] = max(base_preferences.get("price_min") or 0, memory_preferences.get("price_min") or 0)

    base_max = base_preferences.get("price_max")
    memory_max = memory_preferences.get("price_max")
    if base_max is None:
        merged["price_max"] = memory_max
    elif memory_max is None:
        merged["price_max"] = base_max
    else:
        merged["price_max"] = min(base_max, memory_max)

    for key in [
        "liked_brands",
        "disliked_brands",
        "liked_categories",
        "disliked_categories",
        "liked_features",
        "disliked_features",
        "mall_likes",
        "mall_dislikes",
        "memory_hints",
    ]:
        merged[key] = _dedupe_values([*(memory_preferences.get(key) or []), *(base_preferences.get(key) or [])])

    return merged

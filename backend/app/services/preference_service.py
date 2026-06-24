import json
import re
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import UserEvent, UserPreference
from app.services.memory_service import refresh_user_profile_memories, store_interaction_memories

settings = get_settings()

PREFERENCE_KEYWORDS = [
    "저소음",
    "조용",
    "가성비",
    "무선",
    "대용량",
    "소형",
    "디자인",
    "원룸",
    "세척",
    "리뷰 많은",
    "빠른배송",
]

NEGATIVE_HINTS = {
    "비싼": "high_price",
    "소음 큰": "noisy",
    "중국산": "china",
    "대형": "large",
}

POSITIVE_EVENTS = {"click", "like", "save", "purchase_intent"}
NEGATIVE_EVENTS = {"dislike", "remove", "not_relevant"}

BRAND_INCLUDE_PATTERNS = [
    r"([A-Za-z가-힣0-9]+)\s*(?:브랜드)?\s*(?:만|위주|선호|좋아|좋고|추천)",
    r"(?:브랜드는|브랜드로는)\s*([A-Za-z가-힣0-9]+)",
]

BRAND_EXCLUDE_PATTERNS = [
    r"([A-Za-z가-힣0-9]+)\s*(?:브랜드)?\s*(?:제외|말고|빼고|싫어|비선호)",
]


def _create_client() -> OpenAI:
    if not settings.chatku_api_key or not settings.chatku_base_url:
        raise RuntimeError("ChatKU Gateway 설정이 없습니다.")
    return OpenAI(
        api_key=settings.chatku_api_key,
        base_url=settings.chatku_base_url,
        timeout=15.0,
        max_retries=1,
    )


def _extractor_model() -> str:
    return settings.model_for_task("extractor")


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("JSON 파싱 실패")


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _extract_price_bounds_rule(query: str) -> tuple[int | None, int | None]:
    price_min: int | None = None
    price_max: int | None = None

    if match := re.search(r"(\d+(?:\.\d+)?)\s*만원대", query):
        base = int(float(match.group(1)) * 10000)
        price_min = max(0, base - 30000)
        price_max = base + 20000

    if match := re.search(r"(\d+(?:\.\d+)?)\s*만원\s*(?:이하|미만|이내|까지)", query):
        price_max = int(float(match.group(1)) * 10000)

    if match := re.search(r"(\d+(?:\.\d+)?)\s*만원\s*(?:이상|부터)", query):
        price_min = int(float(match.group(1)) * 10000)

    return price_min, price_max


def _extract_category(query: str) -> str | None:
    category_keywords = ["가습기", "제습기", "공기청정기", "선풍기", "청소기", "책상", "모니터", "생활가전"]
    for keyword in category_keywords:
        if keyword in query:
            return keyword
    return None


def _extract_usage_context(query: str) -> str | None:
    if "원룸" in query or "자취" in query:
        return "원룸"
    if "사무실" in query:
        return "사무실"
    if "거실" in query:
        return "거실"
    return None


def _extract_brand_from_product(product: dict[str, Any] | None) -> str | None:
    if not product:
        return None
    for key in ("brand", "product_brand"):
        if product.get(key):
            return str(product[key]).strip()

    title = str(product.get("title") or product.get("product_title") or "").strip()
    if not title:
        return None

    first_token = re.split(r"[\s/]", title)[0].strip()
    if len(first_token) >= 2:
        return first_token
    return None


def _extract_features_from_text(*values: str | None) -> list[str]:
    source = " ".join(_normalize_text(value) for value in values)
    features = [keyword for keyword in PREFERENCE_KEYWORDS if keyword in source]
    for hint in NEGATIVE_HINTS:
        if hint in source and hint not in features:
            features.append(hint)
    return list(dict.fromkeys(features))


def _extract_brand_preferences(query: str) -> tuple[list[str], list[str]]:
    preferred: list[str] = []
    excluded: list[str] = []

    for pattern in BRAND_INCLUDE_PATTERNS:
        preferred.extend(re.findall(pattern, query))
    for pattern in BRAND_EXCLUDE_PATTERNS:
        excluded.extend(re.findall(pattern, query))

    normalize = lambda items: list(dict.fromkeys([item.strip() for item in items if item and len(item.strip()) >= 2]))
    return normalize(preferred), normalize(excluded)


def _product_payload(product: dict[str, Any] | None) -> dict[str, Any]:
    if not product:
        return {}

    return {
        "product_id": product.get("product_id") or product.get("link") or product.get("id"),
        "title": product.get("product_title") or product.get("title"),
        "price": product.get("product_price") or product.get("lprice") or product.get("price"),
        "category": product.get("product_category") or product.get("category"),
        "brand": _extract_brand_from_product(product),
        "mall_name": product.get("mallName") or product.get("mall_name"),
    }


def load_user_preferences(db: Session, user_id: str) -> dict[str, Any]:
    rows = db.query(UserPreference).filter(UserPreference.user_id == user_id).all()

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
    }

    for row in rows:
        if row.preference_type == "price_range":
            if row.key == "price_min":
                preferences["price_min"] = int(row.value)
            elif row.key == "price_max":
                preferences["price_max"] = int(row.value)
        elif row.preference_type == "brand_like":
            preferences["liked_brands"].append(row.value)
        elif row.preference_type == "brand_dislike":
            preferences["disliked_brands"].append(row.value)
        elif row.preference_type == "category_like":
            preferences["liked_categories"].append(row.value)
        elif row.preference_type == "category_dislike":
            preferences["disliked_categories"].append(row.value)
        elif row.preference_type == "feature_like":
            preferences["liked_features"].append(row.value)
        elif row.preference_type == "feature_dislike":
            preferences["disliked_features"].append(row.value)
        elif row.preference_type == "mall_like":
            preferences["mall_likes"].append(row.value)
        elif row.preference_type == "mall_dislike":
            preferences["mall_dislikes"].append(row.value)

    return preferences


def extract_preferences_from_query(query: str) -> dict[str, Any]:
    price_min, price_max = _extract_price_bounds_rule(query)
    liked_features = _extract_features_from_text(query)
    disliked_features = [label for hint, label in NEGATIVE_HINTS.items() if hint in query]
    category = _extract_category(query)
    usage_context = _extract_usage_context(query)
    preferred_brands, excluded_brands = _extract_brand_preferences(query)

    rule_result = {
        "category": category,
        "price_min": price_min,
        "price_max": price_max,
        "liked_features": liked_features,
        "disliked_features": disliked_features,
        "preferred_brands": preferred_brands,
        "excluded_brands": excluded_brands,
        "usage_context": usage_context,
    }

    # Common shopping prompts are cheap to parse with rules. Only use LLM when rules found almost nothing.
    signal_count = sum(
        [
            int(rule_result["category"] is not None),
            int(rule_result["price_min"] is not None or rule_result["price_max"] is not None),
            int(bool(rule_result["liked_features"])),
            int(bool(rule_result["disliked_features"])),
            int(rule_result["usage_context"] is not None),
        ]
    )
    if signal_count >= 2:
        return rule_result

    try:
        client = _create_client()
        prompt = (
            "사용자 쇼핑 문장에서 선호 조건을 JSON만으로 추출해라.\n"
            '{"category":null,"price_min":null,"price_max":null,"liked_features":[],"disliked_features":[],"preferred_brands":[],"excluded_brands":[],"usage_context":null}\n'
            f"문장:{query}"
        )
        response = client.chat.completions.create(
            model=_extractor_model(),
            temperature=0,
            max_tokens=160,
            messages=[
                {"role": "system", "content": "너는 쇼핑 선호 추출기다. JSON만 출력한다."},
                {"role": "user", "content": prompt},
            ],
        )
        parsed = _extract_json_object(response.choices[0].message.content or "")
    except Exception:
        parsed = {}

    result = {
        "category": parsed.get("category") or category,
        "price_min": parsed.get("price_min") if parsed.get("price_min") is not None else price_min,
        "price_max": parsed.get("price_max") if parsed.get("price_max") is not None else price_max,
        "liked_features": parsed.get("liked_features") or liked_features,
        "disliked_features": parsed.get("disliked_features") or disliked_features,
        "preferred_brands": parsed.get("preferred_brands") or preferred_brands,
        "excluded_brands": parsed.get("excluded_brands") or excluded_brands,
        "usage_context": parsed.get("usage_context") or usage_context,
    }
    return result


def _upsert_preference(
    db: Session,
    user_id: str,
    preference_type: str,
    key: str,
    value: str,
    source: str,
    positive_signal: bool,
) -> UserPreference:
    record = (
        db.query(UserPreference)
        .filter(
            UserPreference.user_id == user_id,
            UserPreference.preference_type == preference_type,
            UserPreference.key == key,
            UserPreference.value == value,
        )
        .first()
    )

    if not record:
        record = UserPreference(
            user_id=user_id,
            preference_type=preference_type,
            key=key,
            value=value,
            source=source,
            confidence=0.5,
            positive_count=0,
            negative_count=0,
        )
        db.add(record)

    if positive_signal:
        record.positive_count += 1
    else:
        record.negative_count += 1

    record.source = source
    record.confidence = max(0.1, min(1.0, 0.5 + record.positive_count * 0.1 - record.negative_count * 0.08))
    return record


def update_user_preferences(db: Session, user_id: str, parsed_preferences: dict[str, Any], source: str = "chat") -> list[UserPreference]:
    updates: list[UserPreference] = []

    if parsed_preferences.get("price_min") is not None:
        updates.append(
            _upsert_preference(db, user_id, "price_range", "price_min", str(parsed_preferences["price_min"]), source, True)
        )
    if parsed_preferences.get("price_max") is not None:
        updates.append(
            _upsert_preference(db, user_id, "price_range", "price_max", str(parsed_preferences["price_max"]), source, True)
        )
    if parsed_preferences.get("category"):
        updates.append(
            _upsert_preference(db, user_id, "category_like", "category", str(parsed_preferences["category"]), source, True)
        )
    for brand in parsed_preferences.get("preferred_brands", []):
        updates.append(_upsert_preference(db, user_id, "brand_like", "brand", str(brand), source, True))
    for brand in parsed_preferences.get("excluded_brands", []):
        updates.append(_upsert_preference(db, user_id, "brand_dislike", "brand", str(brand), source, False))
    for feature in parsed_preferences.get("liked_features", []):
        updates.append(_upsert_preference(db, user_id, "feature_like", "feature", str(feature), source, True))
    for feature in parsed_preferences.get("disliked_features", []):
        updates.append(_upsert_preference(db, user_id, "feature_dislike", "feature", str(feature), source, False))

    db.commit()
    refresh_user_profile_memories(db, user_id)
    return updates


def record_user_event(
    db: Session,
    user_id: str,
    event_type: str,
    query: str | None = None,
    product: dict[str, Any] | None = None,
    reason: str | None = None,
) -> UserEvent:
    payload = _product_payload(product)
    parsed_preferences = extract_preferences_from_query(query) if query else {}
    event = UserEvent(
        user_id=user_id,
        event_type=event_type,
        query=query,
        product_id=str(payload.get("product_id")) if payload.get("product_id") else None,
        product_title=payload.get("title"),
        product_price=int(payload["price"]) if payload.get("price") is not None else None,
        product_category=payload.get("category"),
        product_brand=payload.get("brand"),
        metadata_json=json.dumps(
            {
                "reason": reason,
                "product": payload,
            },
            ensure_ascii=False,
        ),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    store_interaction_memories(
        db,
        user_id=user_id,
        event_type=event_type,
        query=query,
        product=payload,
        query_preferences=parsed_preferences,
        reason=reason,
    )
    refresh_user_profile_memories(db, user_id)
    return event


def apply_feedback_to_preferences(
    db: Session,
    user_id: str,
    event_type: str,
    product: dict[str, Any] | None = None,
    query: str | None = None,
    reason: str | None = None,
) -> list[UserPreference]:
    payload = _product_payload(product)
    source = event_type
    updated: list[UserPreference] = []

    if event_type == "too_expensive" and payload.get("price") is not None:
        adjusted_max = max(0, int(payload["price"]) - 10000)
        updated.append(_upsert_preference(db, user_id, "price_range", "price_max", str(adjusted_max), source, True))

    if event_type in {"low_quality", "review_too_low"}:
        updated.append(_upsert_preference(db, user_id, "feature_like", "feature", "리뷰 많은", source, True))
        updated.append(_upsert_preference(db, user_id, "feature_like", "feature", "평점 좋은", source, True))

    brand = payload.get("brand")
    category = payload.get("category")
    mall_name = payload.get("mall_name")
    features = _extract_features_from_text(payload.get("title"), payload.get("category"), reason)

    if event_type in POSITIVE_EVENTS:
        if brand:
            updated.append(_upsert_preference(db, user_id, "brand_like", "brand", brand, source, True))
        if category:
            updated.append(_upsert_preference(db, user_id, "category_like", "category", category, source, True))
        if mall_name:
            updated.append(_upsert_preference(db, user_id, "mall_like", "mall", mall_name, source, True))
        for feature in features:
            updated.append(_upsert_preference(db, user_id, "feature_like", "feature", feature, source, True))

    if event_type in NEGATIVE_EVENTS:
        if brand:
            updated.append(_upsert_preference(db, user_id, "brand_dislike", "brand", brand, source, False))
        if category:
            updated.append(_upsert_preference(db, user_id, "category_dislike", "category", category, source, False))
        if mall_name:
            updated.append(_upsert_preference(db, user_id, "mall_dislike", "mall", mall_name, source, False))
        for feature in features:
            updated.append(_upsert_preference(db, user_id, "feature_dislike", "feature", feature, source, False))

    db.commit()
    refresh_user_profile_memories(db, user_id)
    return updated

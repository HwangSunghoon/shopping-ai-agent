from typing import Any

from app.services.embedding_service import build_product_document, build_rag_query, keyword_similarity


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _price_score(price: int | None, preferences: dict[str, Any]) -> float:
    if price is None:
        return 0.5

    price_min = preferences.get("price_min")
    price_max = preferences.get("price_max")
    if price_min is None and price_max is None:
        return 0.6

    if price_min is not None and price_max is not None and price_min <= price <= price_max:
        return 1.0
    if price_max is not None:
        if price <= price_max * 1.1:
            return 0.6
        if price <= price_max * 1.3:
            return 0.2
        return 0.0
    if price_min is not None:
        if price >= price_min:
            return 0.9
        if price >= price_min * 0.85:
            return 0.5
        return 0.2
    return 0.6


def _review_score(product: dict[str, Any]) -> float:
    review_count = product.get("review_count")
    rating = product.get("rating")
    if review_count is None and rating is None:
        return 0.5

    review_component = 0.5 if review_count is None else _clamp(review_count / 5000)
    rating_component = 0.5 if rating is None else _clamp((rating - 3.5) / 1.5)
    return _clamp(review_component * 0.55 + rating_component * 0.45)


def _preference_score(product: dict[str, Any], preferences: dict[str, Any]) -> float:
    score = 0.4
    title = (product.get("title") or "").lower()
    category = (product.get("category") or "").lower()
    brand = (product.get("brand") or "").lower()
    mall_name = (product.get("mall_name") or "").lower()
    shipping_badges = [str(item).lower() for item in (product.get("shipping_badges") or [])]
    product_doc = build_product_document(product).lower()

    liked_brands = [item.lower() for item in (preferences.get("liked_brands", []) or preferences.get("preferred_brands", []))]
    disliked_brands = [item.lower() for item in preferences.get("disliked_brands", [])]
    liked_categories_source = preferences.get("liked_categories", []) or ([preferences.get("category")] if preferences.get("category") else [])
    liked_categories = [item.lower() for item in liked_categories_source]
    disliked_categories = [item.lower() for item in preferences.get("disliked_categories", [])]
    liked_features = [item.lower() for item in preferences.get("liked_features", [])]
    disliked_features = [item.lower() for item in preferences.get("disliked_features", [])]
    mall_likes = [item.lower() for item in preferences.get("mall_likes", [])]
    mall_dislikes = [item.lower() for item in preferences.get("mall_dislikes", [])]
    usage_context = [item.lower() for item in preferences.get("usage_context", [])]
    required_shipping = [item.lower() for item in preferences.get("required_shipping", [])]
    min_review_count = preferences.get("min_review_count")

    if brand and any(item in brand for item in liked_brands):
        score += 0.25
    if brand and any(item in brand for item in disliked_brands):
        score -= 0.35
    if any(item in category for item in liked_categories):
        score += 0.2
    if any(item in category for item in disliked_categories):
        score -= 0.25
    if any(item in title or item in category for item in liked_features):
        score += 0.2
    if any(item in title or item in category for item in disliked_features):
        score -= 0.3
    if mall_name and any(item in mall_name for item in mall_likes):
        score += 0.1
    if mall_name and any(item in mall_name for item in mall_dislikes):
        score -= 0.15
    if usage_context and any(item in product_doc for item in usage_context):
        score += 0.12
    if required_shipping and any(item in shipping_badges for item in required_shipping):
        score += 0.08
    if min_review_count is not None and int(product.get("review_count") or 0) >= int(min_review_count):
        score += 0.06

    return _clamp(score)


def _memory_alignment_score(
    product: dict[str, Any],
    memory_context: dict[str, Any] | None,
) -> float:
    if not memory_context:
        return 0.45

    product_doc = build_product_document(product)
    product_title = (product.get("title") or "").lower()
    product_category = (product.get("category") or "").lower()
    product_brand = (product.get("brand") or "").lower()
    product_mall = (product.get("mall_name") or "").lower()

    combined_memories = memory_context.get("combined_memories", [])
    if not combined_memories:
        return 0.45

    scored_matches: list[float] = []
    for memory in combined_memories:
        content_similarity = keyword_similarity(memory.get("content", ""), product_doc)
        strength = float(memory.get("strength") or 0.5)
        source_event_type = memory.get("source_event_type")
        metadata = memory.get("metadata", {})
        match_score = content_similarity * 0.65 + strength * 0.2

        memory_product = metadata.get("product", {})
        memory_brand = str(memory_product.get("brand") or "").lower()
        memory_category = str(memory_product.get("category") or "").lower()
        memory_mall = str(memory_product.get("mall_name") or "").lower()
        liked_features = [str(item).lower() for item in (metadata.get("liked_features") or metadata.get("query_preferences", {}).get("liked_features", []) or [])]
        disliked_features = [str(item).lower() for item in (metadata.get("disliked_features") or metadata.get("query_preferences", {}).get("disliked_features", []) or [])]

        if memory_brand and product_brand and memory_brand in product_brand:
            match_score += 0.18
        if memory_category and product_category and memory_category in product_category:
            match_score += 0.14
        if memory_mall and product_mall and memory_mall in product_mall:
            match_score += 0.08
        if liked_features and any(feature in product_doc.lower() for feature in liked_features):
            match_score += 0.12
        if disliked_features and any(feature in product_doc.lower() for feature in disliked_features):
            match_score -= 0.18

        if source_event_type in {"like", "save", "purchase_intent", "final_select"}:
            match_score += 0.08
        if source_event_type in {"too_expensive", "not_relevant", "dislike"}:
            match_score -= 0.1

        scored_matches.append(_clamp(match_score))

    if not scored_matches:
        return 0.45

    scored_matches.sort(reverse=True)
    top_scores = scored_matches[:3]
    return _clamp(sum(top_scores) / len(top_scores))


def rerank_products(
    products: list[dict[str, Any]],
    query: str,
    merged_preferences: dict[str, Any],
    session_preferences: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rag_query = build_rag_query(query, merged_preferences)
    session_preference_source = session_preferences or merged_preferences

    scored_products: list[dict[str, Any]] = []
    for product in products:
        product_doc = build_product_document(product)
        semantic_score = keyword_similarity(rag_query, product_doc)
        price_score = _price_score(product.get("lprice"), merged_preferences)
        review_score = _review_score(product)
        preference_score = _preference_score(product, session_preference_source)
        memory_score = _memory_alignment_score(product, memory_context)
        product["_component_scores"] = {
            "semantic_score": round(semantic_score, 4),
            "price_score": round(price_score, 4),
            "review_score": round(review_score, 4),
            "preference_score": round(preference_score, 4),
            "memory_score": round(memory_score, 4),
        }
        scored_products.append(product)

    selected: list[dict[str, Any]] = []
    remaining = list(scored_products)
    while remaining and len(selected) < limit:
        best_product: dict[str, Any] | None = None
        best_score = -1.0
        for product in remaining:
            same_brand = sum(
                1 for picked in selected if picked.get("brand") and picked.get("brand") == product.get("brand")
            )
            same_mall = sum(
                1 for picked in selected if picked.get("mall_name") and picked.get("mall_name") == product.get("mall_name")
            )
            diversity_score = _clamp(1.0 - same_brand * 0.18 - same_mall * 0.12)
            final_score = (
                0.22 * product["_component_scores"]["semantic_score"]
                + 0.15 * product["_component_scores"]["price_score"]
                + 0.10 * product["_component_scores"]["review_score"]
                + 0.23 * product["_component_scores"]["preference_score"]
                + 0.20 * product["_component_scores"]["memory_score"]
                + 0.10 * diversity_score
            )
            product["_component_scores"]["diversity_score"] = round(diversity_score, 4)
            product["final_score"] = round(final_score, 4)

            if final_score > best_score:
                best_score = final_score
                best_product = product

        if best_product is None:
            break
        selected.append(best_product)
        remaining = [item for item in remaining if item.get("link") != best_product.get("link")]

    return selected

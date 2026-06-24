import re
from typing import Any


def build_product_document(product: dict[str, Any]) -> str:
    fields = [
        f"상품명: {product.get('title', '')}",
        f"카테고리: {product.get('category', '')}",
        f"가격: {product.get('lprice', '')}원" if product.get("lprice") is not None else "가격: 정보 없음",
        f"브랜드: {product.get('brand', '')}",
        f"쇼핑몰: {product.get('mall_name', '')}",
        f"특징: {', '.join(product.get('features', []))}" if product.get("features") else "특징: 정보 없음",
        f"리뷰 수: {product.get('review_count', '')}" if product.get("review_count") is not None else "리뷰 수: 정보 없음",
        f"평점: {product.get('rating', '')}" if product.get("rating") is not None else "평점: 정보 없음",
    ]
    return "\n".join(fields)


def build_rag_query(query: str, merged_preferences: dict[str, Any]) -> str:
    lines = [f"사용자 질문: {query}", "사용자 선호:"]
    if merged_preferences.get("price_min") or merged_preferences.get("price_max"):
        lines.append(
            f"- 가격대: {merged_preferences.get('price_min') or 0} ~ {merged_preferences.get('price_max') or '제한 없음'}"
        )
    if merged_preferences.get("liked_features"):
        lines.append(f"- 선호 특징: {', '.join(merged_preferences['liked_features'])}")
    if merged_preferences.get("disliked_features"):
        lines.append(f"- 싫어하는 조건: {', '.join(merged_preferences['disliked_features'])}")
    if merged_preferences.get("liked_categories"):
        lines.append(f"- 선호 카테고리: {', '.join(merged_preferences['liked_categories'])}")
    if merged_preferences.get("liked_brands"):
        lines.append(f"- 선호 브랜드: {', '.join(merged_preferences['liked_brands'])}")
    if merged_preferences.get("memory_hints"):
        lines.append(f"- 과거 기억: {' | '.join(merged_preferences['memory_hints'][:3])}")
    return "\n".join(lines)


def _tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[\s,./|+\-()\[\]{}:]+", text.lower()) if len(token) >= 2]


def keyword_similarity(query_text: str, product_text: str) -> float:
    query_tokens = set(_tokenize(query_text))
    product_tokens = set(_tokenize(product_text))
    if not query_tokens or not product_tokens:
        return 0.0

    overlap = len(query_tokens & product_tokens)
    union = len(query_tokens | product_tokens)
    if union == 0:
        return 0.0
    return min(1.0, overlap / union * 1.8)

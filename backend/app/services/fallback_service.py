import re
from difflib import SequenceMatcher
from typing import Any


STOPWORDS = {
    "추천해줘",
    "추천",
    "찾아줘",
    "찾아",
    "비교해줘",
    "비교",
    "알려줘",
    "사줘",
    "구해줘",
    "원해",
    "해주세요",
    "좀",
    "제일",
    "가장",
    "무슨",
    "어떤",
    "하나",
    "걸로",
    "걸",
    "용",
    "위한",
    "입문",
    "처음",
    "구입",
    "구매",
}

FEATURE_KEYWORDS = [
    "조용",
    "저소음",
    "가성비",
    "무선",
    "유선",
    "경량",
    "가벼운",
    "튼튼",
    "방수",
    "접이식",
    "휴대용",
    "컴팩트",
    "고급",
    "저진동",
    "배터리",
]

COMPARISON_KEYWORDS = ["가성비", "안전", "무난", "조용", "입문", "선물", "최적"]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _extract_price_bounds(text: str) -> tuple[int | None, int | None]:
    max_price: int | None = None
    min_price: int | None = None

    below_match = re.search(r"(\d+(?:\.\d+)?)\s*만원\s*(?:이하|미만|이내|까지)", text)
    if below_match:
        max_price = int(float(below_match.group(1)) * 10000)

    above_match = re.search(r"(\d+(?:\.\d+)?)\s*만원\s*(?:이상|부터)", text)
    if above_match:
        min_price = int(float(above_match.group(1)) * 10000)

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*만원\s*(?:~|-|에서)\s*(\d+(?:\.\d+)?)\s*만원", text)
    if range_match:
        min_price = int(float(range_match.group(1)) * 10000)
        max_price = int(float(range_match.group(2)) * 10000)

    mid_match = re.search(r"(\d+(?:\.\d+)?)\s*만원대", text)
    if mid_match:
        base = int(float(mid_match.group(1)) * 10000)
        min_price = base
        max_price = base + 99999

    return max_price, min_price


def _extract_use_case(text: str) -> str | None:
    patterns = [
        r"([가-힣A-Za-z0-9\s]{2,20}?용(?:으로)?)",
        r"([가-힣A-Za-z0-9\s]{2,20}?선물용)",
        r"([가-힣A-Za-z0-9\s]{2,20}?입문자)",
        r"([가-힣A-Za-z0-9\s]{2,20}?자취방)",
        r"([가-힣A-Za-z0-9\s]{2,20}?러닝)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _extract_exclusions(text: str) -> list[str]:
    exclusions: list[str] = []
    patterns = [
        r"(?:제외|빼고|말고)\s*([가-힣A-Za-z0-9-]+)",
        r"([가-힣A-Za-z0-9-]+)\s*(?:제외|빼고|말고)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text):
            if match:
                exclusions.append(match.strip())
    return _dedupe(exclusions)


def _extract_keyword(text: str) -> str:
    tokens = [token for token in re.split(r"[\s,./|+\-()\[\]{}]+", text) if token]
    cleaned = []
    for token in tokens:
        normalized = token.strip()
        if len(normalized) < 2:
            continue
        if re.search(r"\d", normalized):
            continue
        if normalized in STOPWORDS:
            continue
        cleaned.append(normalized)

    filtered = [token for token in cleaned if token not in FEATURE_KEYWORDS and not token.endswith("용")]
    if filtered:
        return filtered[-1]
    if cleaned:
        return cleaned[-1]
    return text.strip() or "상품"


def parse_conditions_fallback(user_query: str) -> dict[str, Any]:
    text = user_query.strip()
    max_price, min_price = _extract_price_bounds(text)
    keyword = _extract_keyword(text)
    important_features = [feature for feature in FEATURE_KEYWORDS if feature in text]
    comparison_criteria = [criterion for criterion in COMPARISON_KEYWORDS if criterion in text]

    return {
        "keyword": keyword,
        "product_group": keyword,
        "max_price": max_price,
        "min_price": min_price,
        "important_features": _dedupe(important_features),
        "exclude_keywords": _extract_exclusions(text),
        "use_case": _extract_use_case(text),
        "comparison_criteria": _dedupe(comparison_criteria),
    }


def build_search_terms_fallback(user_query: str, intent: dict[str, Any]) -> list[str]:
    base = (intent.get("product_group") or intent.get("keyword") or user_query or "").strip()
    if not base:
        return ["쇼핑"]

    terms = [base]
    use_case = (intent.get("use_case") or "").strip()
    features = [str(feature).strip() for feature in (intent.get("important_features") or []) if str(feature).strip()]
    price_terms: list[str] = []

    max_price = intent.get("max_price")
    min_price = intent.get("min_price")
    if isinstance(max_price, int) and max_price > 0:
        price_terms.append(f"{max_price // 10000}만원 이하 {base}")
    elif isinstance(min_price, int) and min_price > 0:
        price_terms.append(f"{min_price // 10000}만원 이상 {base}")

    if use_case:
        terms.append(f"{use_case} {base}")
    for feature in features[:2]:
        terms.append(f"{feature} {base}")
        if use_case:
            terms.append(f"{use_case} {feature} {base}")
    terms.extend(price_terms)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = " ".join(term.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:5]


def build_clarification_questions(intent: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    if not intent.get("max_price") and not intent.get("min_price"):
        questions.append("예산은 어느 정도까지 생각하고 계신가요?")
    if not intent.get("use_case"):
        questions.append("주로 어떤 용도나 공간에서 사용할 제품인가요?")
    if not intent.get("important_features"):
        questions.append("꼭 필요한 기능이나 선호 조건이 있나요?")
    if not intent.get("exclude_keywords"):
        questions.append("피하고 싶은 브랜드나 조건이 있나요?")
    return questions[:3]


def _product_label(product: dict[str, Any]) -> str:
    price = product.get("lprice")
    price_text = f"{price:,}원" if isinstance(price, int) else "가격 정보 없음"
    mall = product.get("mall_name") or "판매처 정보 없음"
    return f"{product.get('title', '')} / {price_text} / {mall}"


def build_search_summary_fallback(user_query: str, intent: dict[str, Any], recommendations: list[dict[str, Any]], fallback_active: bool) -> str:
    header = "AI 요약은 현재 사용할 수 없지만, 네이버 쇼핑 검색 결과는 정상적으로 표시됩니다." if fallback_active else "추천 결과를 정리했습니다."
    if not recommendations:
        return f"{header}\n\n추천할 상품을 찾지 못했습니다. 검색 조건을 조금 넓혀 다시 찾아보세요."

    lines = [header, "", "추천 기준 요약:"]
    for idx, product in enumerate(recommendations[:3], start=1):
        caution = product.get("caution") or "제공된 정보 기준으로 판단했습니다."
        lines.append(f"{idx}. {_product_label(product)}")
        lines.append(f"   - 추천 이유: {product.get('reason') or '기본 검색 결과 기반 후보'}")
        lines.append(f"   - 주의할 점: {caution}")

    best = recommendations[0]
    cheapest = min(recommendations[:3], key=lambda item: item.get("lprice") or 10**18)
    lines.extend(
        [
            "",
            f"가성비 기준: {cheapest.get('title', '')}",
            f"안전한 선택: {best.get('title', '')}",
            f"조건 최적 선택: {best.get('title', '')}",
        ]
    )
    return "\n".join(lines)


def build_followup_answer_fallback(question: str, session_context: dict[str, Any], chat_history: list[dict[str, Any]], selected_product: dict[str, Any] | None = None) -> str:
    recommendations = session_context.get("recommendations") or []
    candidates = session_context.get("products") or recommendations
    selected_product = selected_product or {}

    if not recommendations:
        return "이전 검색 결과가 충분하지 않습니다. 조건을 조금 더 넓혀 다시 검색해보세요."

    normalized_question = question.lower()
    if "가성비" in normalized_question:
        chosen = min(recommendations[:3], key=lambda item: ((item.get("lprice") or 10**18), -(item.get("score") or 0)))
        return f"가성비 기준으로는 {chosen.get('title', '')}가 가장 무난합니다. 가격이 확인되고 점수가 높은 편이라 예산 대비 선택하기 좋습니다. 다음으로는 {recommendations[0].get('title', '')}도 같이 보시면 좋습니다."

    if selected_product.get("title") and any(token in normalized_question for token in ["이거", "선택", "괜찮아", "단점", "장점", "어때"]):
        chosen = selected_product
        return (
            f"선택한 상품은 {chosen.get('title', '')}입니다. 제공된 정보 기준으로는 {chosen.get('reason', '기본 후보')}가 강점입니다. "
            f"다만 실제 소음 dB나 리뷰 내용, 배송 속도는 확인되지 않았으니 상품 페이지에서 마지막 확인이 필요합니다."
        )

    if any(token in normalized_question for token in ["무난", "안전", "부모님", "선물"]):
        chosen = selected_product if selected_product.get("title") else recommendations[0]
        return f"무난한 선택은 {chosen.get('title', '')}입니다. 제공된 정보 기준으로 점수가 가장 높고 조건 적합도가 좋아 보입니다. 다만 상세 스펙이나 리뷰는 확인되지 않았으니 상품 페이지에서 최종 확인이 필요합니다."

    if any(token in normalized_question for token in ["조용", "저소음"]):
        quiet_candidates = [
            item
            for item in candidates
            if any(keyword in f"{item.get('title', '')} {item.get('category', '')} {item.get('reason', '')}" for keyword in ["조용", "저소음", "quiet"])
        ]
        chosen = quiet_candidates[0] if quiet_candidates else recommendations[0]
        return f"조용함 기준으로는 {chosen.get('title', '')}를 먼저 보시는 게 좋습니다. 검색 결과 안에서 저소음 관련 키워드가 가장 직접적으로 보이는 후보입니다."

    if any(token in normalized_question for token in ["비교", "차이", "1번", "2번"]):
        first = recommendations[0]
        second = recommendations[1] if len(recommendations) > 1 else None
        if second:
            return (
                f"1번은 {first.get('title', '')}, 2번은 {second.get('title', '')}입니다. "
                f"조건 적합도는 1번이 조금 더 앞서지만, 가격을 더 중시하면 2번이 더 나을 수 있습니다."
            )
        return f"현재 비교할 후보는 {first.get('title', '')} 하나가 가장 강합니다. 다른 기준이 있으면 조금 더 좁혀서 다시 비교해보세요."

    chosen = recommendations[0]
    return (
        f"추천 우선순위는 {chosen.get('title', '')}입니다. "
        f"점수와 조건 적합도를 기준으로 가장 앞서고, 다음 선택지는 {recommendations[1].get('title', '') if len(recommendations) > 1 else '추가 후보'}입니다."
    )


def normalize_title_key(title: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", (title or "").lower())


def is_similar_title(a: str, b: str) -> bool:
    if not a or not b:
        return False
    left = normalize_title_key(a)
    right = normalize_title_key(b)
    if not left or not right:
        return False
    if left == right:
        return True
    ratio = SequenceMatcher(None, left, right).ratio()
    return ratio >= 0.88

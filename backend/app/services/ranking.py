import re


ACCESSORY_KEYWORDS = [
    "필터",
    "리필",
    "액세서리",
    "케이스",
    "커버",
    "브라켓",
    "부품",
    "소모품",
    "호환",
    "리모컨",
]

ABNORMAL_TITLE_PATTERNS = r"(상품상세|상세페이지|직구|도매|테스트|샘플)"
OFFICIAL_MALL_PATTERNS = r"(공식|본사|브랜드|직영)"


def normalize_text(text: str | None) -> str:
    return (text or "").lower().replace(" ", "")


def tokenize_koreanish(text: str | None) -> list[str]:
    if not text:
        return []
    return [t for t in re.split(r"[\s,./|+\-()\[\]{}]+", text.lower()) if len(t) >= 2]


def _unique_tokens(values: list[str]) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tokens.append(normalized)
    return tokens


def _matched_tokens(tokens: list[str], *haystacks: str) -> list[str]:
    if not tokens:
        return []
    matches: list[str] = []
    for token in tokens:
        compact = token.replace(" ", "")
        if any(compact in haystack or token in haystack for haystack in haystacks):
            matches.append(token)
    return _unique_tokens(matches)


def _price_fit_score(price: int | None, min_price: int | None, max_price: int | None) -> tuple[int, list[str], list[str]]:
    if price is None:
        return -6, [], ["가격 정보가 없어 우선순위를 낮췄습니다."]

    score = 0
    reasons: list[str] = []
    cautions: list[str] = []

    if isinstance(max_price, int):
        if price <= max_price:
            score += 24
            reasons.append("예산 상한 안에서 비교 가능한 가격입니다.")

            ratio = price / max_price if max_price > 0 else 1
            if 0.55 <= ratio <= 1.0:
                score += 10
                reasons.append("예산 대비 가격대가 적절합니다.")
            elif 0.35 <= ratio < 0.55:
                score += 4
            elif ratio < 0.35:
                score -= 10
                cautions.append("가격이 너무 낮아 구성이나 상세 설명 확인이 필요합니다.")
        else:
            score -= 30
            cautions.append("예산 상한을 초과합니다.")

    if isinstance(min_price, int):
        if price >= min_price:
            score += 6
        else:
            score -= 12
            cautions.append("희망한 최소 가격대보다 낮아 품질 확인이 필요합니다.")

    if isinstance(min_price, int) and isinstance(max_price, int) and min_price < max_price:
        midpoint = (min_price + max_price) / 2
        band = max((max_price - min_price) / 2, 1)
        closeness = max(0.0, 1 - abs(price - midpoint) / band)
        if closeness > 0:
            score += int(closeness * 10)

    return score, _unique_tokens(reasons), _unique_tokens(cautions)


def rank_products(products: list[dict], conditions: dict, top_k: int = 3) -> tuple[list[dict], list[dict]]:
    keyword = conditions.get("keyword") or ""
    product_group = conditions.get("product_group") or keyword
    max_price = conditions.get("max_price")
    min_price = conditions.get("min_price")
    important_features = conditions.get("important_features") or []
    exclude_keywords = conditions.get("exclude_keywords") or []
    use_case = conditions.get("use_case") or ""
    comparison_criteria = conditions.get("comparison_criteria") or []

    keyword_tokens = tokenize_koreanish(keyword)
    group_tokens = tokenize_koreanish(product_group)
    use_case_tokens = tokenize_koreanish(use_case)
    feature_tokens = _unique_tokens(
        [token for feature in important_features for token in tokenize_koreanish(feature)]
    )
    comparison_tokens = _unique_tokens(
        [token for criterion in comparison_criteria for token in tokenize_koreanish(criterion)]
    )
    exclude_norms = [normalize_text(x) for x in exclude_keywords]

    ranked = []
    for product in products:
        title = product.get("title") or ""
        title_norm = normalize_text(title)
        category = product.get("category") or ""
        category_norm = normalize_text(category)
        mall_name = product.get("mall_name") or ""
        mall_norm = normalize_text(mall_name)
        search_term_norm = normalize_text(product.get("search_term"))
        price = product.get("lprice")

        score = 0
        reasons: list[str] = []
        cautions: list[str] = []

        matched_keywords = _matched_tokens(keyword_tokens, title_norm, category_norm, search_term_norm)
        if matched_keywords:
            score += min(34, 12 * len(matched_keywords))
            if keyword and normalize_text(keyword) in title_norm:
                score += 6
            reasons.append("상품명이나 카테고리가 검색 의도와 직접적으로 맞습니다.")

        matched_groups = _matched_tokens(group_tokens, title_norm, category_norm)
        if matched_groups:
            score += min(18, 7 * len(matched_groups))
            reasons.append("원하는 상품군과의 일치도가 높습니다.")

        matched_use_case = _matched_tokens(use_case_tokens, title_norm, category_norm)
        if matched_use_case:
            score += min(16, 5 * len(matched_use_case))
            reasons.append("사용 목적과 연결되는 단서가 보입니다.")

        matched_features = _matched_tokens(feature_tokens, title_norm, category_norm)
        if matched_features:
            score += min(28, 9 * len(matched_features))
            reasons.append(f"중요하게 본 조건({', '.join(matched_features[:2])})이 상품 정보에 반영됩니다.")

        matched_comparisons = _matched_tokens(comparison_tokens, title_norm, category_norm)
        if matched_comparisons:
            score += min(10, 4 * len(matched_comparisons))

        price_score, price_reasons, price_cautions = _price_fit_score(price, min_price, max_price)
        score += price_score
        reasons.extend(price_reasons)
        cautions.extend(price_cautions)

        if mall_name:
            score += 3
            if re.search(OFFICIAL_MALL_PATTERNS, mall_name):
                score += 6
                reasons.append("공식 판매처로 보이는 채널입니다.")
        else:
            cautions.append("판매처 정보가 부족합니다.")

        if search_term_norm and keyword and search_term_norm == normalize_text(keyword):
            score += 4

        if any(keyword in title_norm for keyword in ACCESSORY_KEYWORDS) and not any(
            token in title_norm for token in group_tokens + keyword_tokens
        ):
            score -= 18
            cautions.append("본품보다 소모품이나 액세서리일 가능성이 있습니다.")

        if re.search(ABNORMAL_TITLE_PATTERNS, title):
            score -= 18
            cautions.append("상품명이 비정상적이거나 일반 판매 상품처럼 보이지 않습니다.")

        if any(ex and ex in title_norm for ex in exclude_norms):
            score -= 60
            cautions.append("제외하고 싶은 조건과 겹치는 단어가 포함됩니다.")

        if not matched_keywords and not matched_groups:
            score -= 12

        if not matched_features and feature_tokens:
            cautions.append("중요 조건이 상품명에 직접 드러나지 않습니다.")

        product["score"] = max(score, 0)
        product["reason"] = " / ".join(_unique_tokens(reasons)) if reasons else "기본 검색 결과 기반 후보"
        product["caution"] = (
            " / ".join(_unique_tokens(cautions))
            if cautions
            else "제공된 상품 정보 기준으로 큰 위험 신호는 보이지 않았습니다."
        )
        ranked.append(product)

    ranked.sort(
        key=lambda item: (
            item.get("score", 0),
            -((item.get("lprice") or 10**12)),
        ),
        reverse=True,
    )
    return ranked, ranked[:top_k]

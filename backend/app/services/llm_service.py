import json
import re

from openai import OpenAI

from app.config import get_settings
from app.services.cache_service import build_cache_key, get_cache, set_cache

settings = get_settings()


def _create_client() -> OpenAI:
    if not settings.chatku_base_url:
        raise RuntimeError("CHATKU_BASE_URL이 설정되지 않았습니다.")
    return OpenAI(
        api_key=settings.chatku_api_key,
        base_url=settings.chatku_base_url,
        timeout=settings.chatku_timeout_seconds,
        max_retries=settings.chatku_max_retries,
    )


def _model_for(task: str) -> str:
    return settings.model_for_task(task)


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError("JSON 파싱 실패")


def plan_shopping_search(user_query: str) -> dict:
    if not settings.chatku_api_key:
        raise RuntimeError("CHATKU_API_KEY가 설정되지 않았습니다.")

    prompt = (
        "사용자 쇼핑 요청을 해석해 JSON만 출력하라.\n"
        "출력 형식:\n"
        '{'
        '"intent":{"keyword":"","product_group":"","max_price":null,"min_price":null,"important_features":[],"exclude_keywords":[],"use_case":null,"comparison_criteria":[]},'
        '"search_terms":[""]'
        '}\n'
        "규칙:\n"
        "- keyword는 핵심 검색어\n"
        "- product_group은 자연스러운 상품군\n"
        "- 가격은 원 단위 정수\n"
        "- search_terms는 네이버 쇼핑용 짧은 검색어 3~5개\n"
        f"사용자 요청: {user_query}"
    )

    client = _create_client()
    response = client.chat.completions.create(
        model=_model_for("planner"),
        temperature=0,
        max_tokens=280,
        messages=[
            {"role": "system", "content": "너는 쇼핑 planner다. JSON만 출력한다."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    parsed = _extract_json_object(content)
    intent = parsed.get("intent") or {}
    search_terms = parsed.get("search_terms") or []
    if not isinstance(search_terms, list):
        search_terms = []
    return {"intent": intent, "search_terms": [str(term).strip() for term in search_terms if str(term).strip()]}


def extract_conditions(user_query: str) -> dict:
    if not settings.chatku_api_key:
        raise RuntimeError("CHATKU_API_KEY가 설정되지 않았습니다.")

    prompt = f"""
사용자의 쇼핑 요청을 네이버 쇼핑 검색과 상품 비교에 사용할 JSON 조건으로 변환해라.
반드시 JSON만 출력하고, 설명 문장은 출력하지 마라.

사용자 요청: {user_query}

규칙:
- keyword는 네이버 쇼핑에 넣을 핵심 검색어로 작성한다.
- product_group은 keyword와 유사하더라도 상품군을 더 자연스럽게 적는다.
- 가격 표현이 있으면 원 단위 정수로 max_price 또는 min_price에 넣는다.
- 중요한 조건은 important_features에 넣는다.
- 원하지 않는 조건은 exclude_keywords에 넣는다.
- 비교 기준은 comparison_criteria에 넣는다.
- 모르면 null 또는 []로 둔다.

출력 형식:
{{
  "keyword": "",
    "product_group": "",
  "max_price": null,
  "min_price": null,
  "important_features": [],
  "exclude_keywords": [],
    "use_case": null,
    "comparison_criteria": []
}}
"""

    client = _create_client()
    response = client.chat.completions.create(
        model=_model_for("extractor"),
        temperature=0,
        max_tokens=180,
        messages=[
            {"role": "system", "content": "너는 쇼핑 검색 조건 추출기다. JSON만 출력한다."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or ""

    try:
        parsed = _extract_json_object(content)
    except ValueError:
        parsed = {
            "keyword": user_query,
            "product_group": user_query,
            "max_price": None,
            "min_price": None,
            "important_features": [],
            "exclude_keywords": [],
            "use_case": None,
            "comparison_criteria": [],
        }

    if not parsed.get("keyword"):
        parsed["keyword"] = user_query
    if not parsed.get("product_group"):
        parsed["product_group"] = parsed["keyword"]
    parsed.setdefault("max_price", None)
    parsed.setdefault("min_price", None)
    parsed.setdefault("important_features", [])
    parsed.setdefault("exclude_keywords", [])
    parsed.setdefault("use_case", None)
    parsed.setdefault("comparison_criteria", [])
    return parsed


def generate_search_queries(user_query: str, conditions: dict) -> list[str]:
    if not settings.chatku_api_key:
        raise RuntimeError("CHATKU_API_KEY가 설정되지 않았습니다.")

    prompt = f"""
사용자의 쇼핑 의도와 조건을 바탕으로 네이버 쇼핑 검색어 3~5개를 생성해라.
반드시 JSON만 출력하고, 설명 문장은 출력하지 마라.

사용자 요청: {user_query}
조건: {json.dumps(conditions, ensure_ascii=False)}

규칙:
- 검색어는 짧고 실제 검색에 쓸 수 있어야 한다.
- 원문을 그대로 복사하지 말고, 상품군 / 용도 / 예산 / 중요한 조건을 조합한다.
- 서로 다른 탐색 의도를 가진 검색어를 포함한다.

출력 형식:
{{
  "search_terms": ["", "", ""]
}}
"""

    client = _create_client()
    response = client.chat.completions.create(
        model=_model_for("extractor"),
        temperature=0,
        max_tokens=160,
        messages=[
            {"role": "system", "content": "너는 쇼핑 검색어 생성기다. JSON만 출력한다."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    parsed = _extract_json_object(content)
    search_terms = parsed.get("search_terms") or []
    if not isinstance(search_terms, list):
        raise ValueError("search_terms 형식이 올바르지 않습니다.")

    normalized_terms: list[str] = []
    for term in search_terms:
        term_text = str(term).strip()
        if term_text and term_text not in normalized_terms:
            normalized_terms.append(term_text)
    return normalized_terms


def summarize_recommendations(user_query: str, conditions: dict, recommendations: list[dict]) -> str:
    if not recommendations:
        return "추천할 상품을 찾지 못했습니다. 검색 조건을 조금 더 넓혀보세요."

    cache_key = build_cache_key(
        "llm_response",
        {
            "task": "summary",
            "query": user_query,
            "conditions": conditions,
            "recommendation_links": [item.get("link") for item in recommendations[:3]],
        },
    )
    cached = get_cache("llm_response", cache_key)
    if cached:
        return cached

    compact_products = [
        {
            "title": p.get("title"),
            "price": p.get("lprice"),
            "mall_name": p.get("mall_name"),
            "category": p.get("category"),
            "score": p.get("score"),
            "reason": p.get("reason"),
            "link": p.get("link"),
        }
        for p in recommendations
    ]

    prompt = f"""
너는 쇼핑 상품 비교 전문가다.
아래 사용자 요청과 추천 후보 3개를 바탕으로 한국어로 Rufus 스타일의 간결한 추천 결과를 작성해라.

사용자 요청:
{user_query}

AI가 추출한 조건:
{json.dumps(conditions, ensure_ascii=False)}

추천 후보:
{json.dumps(compact_products, ensure_ascii=False, indent=2)}

출력 형식:
## 추천 TOP 3

### 1. 상품명
- 가격:
- 판매처:
- 카테고리:
- 추천 이유:
- 주의할 점:

마지막에 "가성비 기준", "안전한 선택", "조건 최적 선택"을 각각 한 줄로 정리해라.
단, 제공된 상품 정보에 없는 리뷰 수, 배송 속도, 상세 스펙은 추측하지 마라.
"""

    client = _create_client()
    response = client.chat.completions.create(
        model=_model_for("summary"),
        temperature=0.2,
        max_tokens=220,
        messages=[
            {"role": "system", "content": "너는 과장하지 않고 제공된 정보만 근거로 상품을 비교한다."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "요약 생성에 실패했습니다."
    set_cache("llm_response", cache_key, content, settings.llm_cache_ttl_seconds)
    return content


def generate_agent_trace_line(user_query: str, intent: dict, top_product: dict | None = None) -> str:
    if not settings.chatku_api_key:
        raise RuntimeError("CHATKU_API_KEY가 설정되지 않았습니다.")

    cache_key = build_cache_key(
        "llm_response",
        {
            "task": "agent_trace",
            "query": user_query,
            "intent": intent,
            "top_product_link": (top_product or {}).get("link"),
            "top_product_price": (top_product or {}).get("lprice"),
        },
    )
    cached = get_cache("llm_response", cache_key)
    if cached:
        return cached

    compact_top_product = {
        "title": top_product.get("title"),
        "price": top_product.get("lprice"),
        "mall_name": top_product.get("mall_name"),
        "reason": top_product.get("reason"),
    } if top_product else None

    prompt = f"""
사용자 쇼핑 요청에 대한 진행 응답을 한국어 한 문장으로 작성하라.
규칙:
- 22자 이상 42자 이하
- 친절하지만 짧게
- 사용자가 방금 적용한 조건만 자연스럽게 요약
- 상품명, 브랜드명, 판매처명은 쓰지 마라
- "~조건을 반영해 다시 보여드릴게요", "~기준으로 다시 추렸습니다" 같은 톤
- 없는 정보 추측 금지
- 따옴표, 불릿, 번호 금지

사용자 요청: {user_query}
해석된 조건: {json.dumps(intent, ensure_ascii=False, separators=(",", ":"))}
현재 상위 후보: {json.dumps(compact_top_product, ensure_ascii=False, separators=(",", ":")) if compact_top_product else "없음"}
"""

    client = _create_client()
    response = client.chat.completions.create(
        model=_model_for("summary"),
        temperature=0.2,
        max_tokens=60,
        messages=[
            {"role": "system", "content": "너는 쇼핑 에이전트의 짧은 진행 응답만 작성한다."},
            {"role": "user", "content": prompt},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    final_content = content or "요청하신 조건을 반영한 상품 결과입니다."
    set_cache("llm_response", cache_key, final_content, settings.llm_cache_ttl_seconds)
    return final_content


def answer_followup(question: str, session_context: dict, chat_history: list[dict], selected_product: dict | None = None) -> str:
    if not settings.chatku_api_key:
        raise RuntimeError("CHATKU_API_KEY가 설정되지 않았습니다.")

    prompt = f"""
검색 세션과 선택 상품을 기준으로 후속 질문에 한국어로 짧게 답해라.
규칙:
- 없는 리뷰/배송/상세스펙은 추측 금지
- 핵심 결론 1~2문장
- 필요하면 비교 포인트 1문장

선택 상품: {json.dumps(selected_product, ensure_ascii=False, separators=(",", ":")) if selected_product else "없음"}
검색 세션: {json.dumps(session_context, ensure_ascii=False, separators=(",", ":"))}
최근 대화: {json.dumps(chat_history[-2:], ensure_ascii=False, separators=(",", ":"))}
질문: {question}
"""

    client = _create_client()
    response = client.chat.completions.create(
        model=_model_for("followup"),
        temperature=0.2,
        max_tokens=180,
        messages=[
            {"role": "system", "content": "너는 쇼핑 비교에 특화된 대화형 어시스턴트다."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or "답변 생성에 실패했습니다."

import re
from typing import Any

from app.services.fallback_service import build_clarification_questions, build_search_terms_fallback, parse_conditions_fallback
from app.services.cache_service import build_cache_key, get_cache, set_cache
from app.services.llm_service import plan_shopping_search
from app.config import get_settings

settings = get_settings()

FORCE_LLM_PATTERNS = [
    "그중",
    "그 중",
    "top3",
    "top 3",
    "하나만",
    "남겨",
    "최종",
    "비교",
    "차이",
    "더 좋은",
    "더 조용",
    "더 싼",
    "더 저렴",
    "리뷰",
    "평점",
    "이상만",
    "이하만",
    "제외하고",
    "빼고",
    "말고",
    "우선순위",
    "1순위",
    "2순위",
    "후보",
]

COMPLEXITY_HINTS = [
    "그리고",
    "하면서",
    "인데",
    "하지만",
    "대신",
    "or",
    "vs",
    "보다",
]


def _rule_signal_count(intent: dict[str, Any]) -> int:
    return sum(
        [
            int(bool(intent.get("keyword"))),
            int(intent.get("max_price") is not None or intent.get("min_price") is not None),
            int(bool(intent.get("important_features"))),
            int(bool(intent.get("exclude_keywords"))),
            int(bool(intent.get("use_case"))),
            int(bool(intent.get("comparison_criteria"))),
        ]
    )


def _analyze_query_complexity(user_query: str, fallback_intent: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(user_query.strip().split())
    lowered = text.lower()
    reasons: list[str] = []
    score = 0

    if any(pattern in lowered for pattern in FORCE_LLM_PATTERNS):
        score += 3
        reasons.append("후속 정제/비교 성격이 강한 요청")

    if any(hint in lowered for hint in COMPLEXITY_HINTS):
        score += 1
        reasons.append("조건 연결이나 비교 표현 포함")

    if len(re.findall(r"\d+", text)) >= 2:
        score += 1
        reasons.append("숫자 조건이 여러 개 포함됨")

    feature_count = len(fallback_intent.get("important_features") or [])
    exclude_count = len(fallback_intent.get("exclude_keywords") or [])
    if feature_count + exclude_count >= 2:
        score += 1
        reasons.append("세부 조건이 여러 개 포함됨")

    if len(text) >= 28:
        score += 1
        reasons.append("문장이 길어 해석 여지가 큼")

    rule_signal = _rule_signal_count(fallback_intent)
    if rule_signal <= 1:
        score += 2
        reasons.append("규칙 기반 추출 신호가 부족함")

    llm_required = score >= settings.planner_llm_threshold
    use_rule_only = not llm_required and rule_signal >= 2

    return {
        "score": score,
        "reasons": reasons,
        "rule_signal": rule_signal,
        "llm_required": llm_required,
        "use_rule_only": use_rule_only,
    }


def _merge_fallback_intent(intent: dict[str, Any], fallback_intent: dict[str, Any]) -> dict[str, Any]:
    merged = dict(intent)

    if fallback_intent.get("max_price") is not None:
        merged["max_price"] = fallback_intent["max_price"]
    if fallback_intent.get("min_price") is not None:
        merged["min_price"] = fallback_intent["min_price"]

    if fallback_intent.get("use_case") and not merged.get("use_case"):
        merged["use_case"] = fallback_intent["use_case"]

    merged["important_features"] = list(
        dict.fromkeys([*(merged.get("important_features") or []), *(fallback_intent.get("important_features") or [])])
    )
    merged["exclude_keywords"] = list(
        dict.fromkeys([*(merged.get("exclude_keywords") or []), *(fallback_intent.get("exclude_keywords") or [])])
    )
    merged["comparison_criteria"] = list(
        dict.fromkeys([*(merged.get("comparison_criteria") or []), *(fallback_intent.get("comparison_criteria") or [])])
    )

    if not merged.get("product_group") and fallback_intent.get("product_group"):
        merged["product_group"] = fallback_intent["product_group"]
    if not merged.get("keyword") and fallback_intent.get("keyword"):
        merged["keyword"] = fallback_intent["keyword"]

    return merged


def build_query_plan(user_query: str) -> dict[str, Any]:
    fallback_intent = parse_conditions_fallback(user_query)
    complexity = _analyze_query_complexity(user_query, fallback_intent)
    cache_key = build_cache_key("planner", {"query": user_query.strip()})
    cached_plan = get_cache("planner", cache_key)
    if cached_plan:
        cached_plan["cache_hit"] = True
        cached_plan["complexity"] = complexity
        return cached_plan

    llm_failed = False
    summary_mode = "llm"
    fallback_reason: str | None = None

    if complexity["use_rule_only"]:
        intent = fallback_intent
        search_terms = build_search_terms_fallback(user_query, fallback_intent)
        summary_mode = "rule"
    else:
        try:
            planned = plan_shopping_search(user_query)
            intent = planned.get("intent") or {}
            search_terms = planned.get("search_terms") or []
        except Exception:
            intent = fallback_intent
            search_terms = []
            llm_failed = True
            summary_mode = "fallback"
            fallback_reason = "ChatKU Gateway 실패로 조건 추출을 규칙 기반 파서로 대체했습니다."

    intent = _merge_fallback_intent(intent, fallback_intent)

    intent.setdefault("keyword", user_query.strip())
    intent.setdefault("product_group", intent.get("keyword", user_query.strip()))
    intent.setdefault("max_price", None)
    intent.setdefault("min_price", None)
    intent.setdefault("important_features", [])
    intent.setdefault("exclude_keywords", [])
    intent.setdefault("use_case", None)
    intent.setdefault("comparison_criteria", [])

    if not search_terms:
        search_terms = build_search_terms_fallback(user_query, intent)

    if llm_failed:
        search_terms = search_terms[:1]

    clarification_questions = build_clarification_questions(intent)

    result = {
        "intent": intent,
        "search_terms": search_terms,
        "llm_failed": llm_failed,
        "fallback_used": llm_failed,
        "summary_mode": summary_mode,
        "fallback_reason": fallback_reason,
        "clarification_questions": clarification_questions,
        "cache_hit": False,
        "planner_mode": "rule" if complexity["use_rule_only"] else "llm",
        "complexity": complexity,
    }
    set_cache("planner", cache_key, result, settings.planner_cache_ttl_seconds)
    return result

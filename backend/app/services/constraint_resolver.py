import re
from typing import Any


def _extract_result_limit(text: str) -> int | None:
    if match := re.search(r"(\d+)\s*개(?:만)?\s*(?:뽑|보여|추천|남겨)", text):
        return max(1, int(match.group(1)))
    if "하나만" in text or "1개만" in text:
        return 1
    if "두 개만" in text or "2개만" in text:
        return 2
    if "세 개만" in text or "3개만" in text:
        return 3
    return None


def _extract_min_review_count(text: str) -> int | None:
    if match := re.search(r"리뷰\s*(\d+)\s*개\s*(?:이상|넘는|이상인)", text):
        return int(match.group(1))
    if match := re.search(r"리뷰수\s*(\d+)\s*(?:이상|넘는)", text):
        return int(match.group(1))
    if "리뷰 많은" in text and any(keyword in text for keyword in ["이상", "넘는"]):
        return 1000
    return None


def _extract_min_rating(text: str) -> float | None:
    if match := re.search(r"평점\s*(\d(?:\.\d+)?)\s*(?:이상|넘는|이상인)", text):
        return float(match.group(1))
    return None


def _extract_required_shipping(text: str) -> list[str]:
    shipping = []
    for keyword in ["무료배송", "오늘출발", "빠른배송"]:
        if keyword in text and any(token in text for token in ["만", "우선", "만 남", "만 보여", "조건"]):
            shipping.append(keyword)
    return shipping


def _extract_scope_mode(text: str) -> str | None:
    if any(keyword in text for keyword in ["top3", "탑3", "상위 3", "이 셋", "셋 중", "세 개 중"]):
        return "top3_only"
    if any(keyword in text for keyword in ["현재 결과", "지금 결과", "이 결과"]):
        return "current_results"
    return None


def _clear_constraint_flags(text: str) -> dict[str, bool]:
    return {
        "clear_review": any(keyword in text for keyword in ["리뷰 조건 빼", "리뷰 조건 제거", "리뷰 상관없", "리뷰는 상관없"]),
        "clear_rating": any(keyword in text for keyword in ["평점 조건 빼", "평점 조건 제거", "평점 상관없"]),
        "clear_shipping": any(keyword in text for keyword in ["배송 조건 빼", "배송 조건 제거", "배송 상관없"]),
        "clear_limit": any(keyword in text for keyword in ["개수 제한 빼", "몇 개든", "개수 상관없"]),
        "clear_scope": any(keyword in text for keyword in ["전체 결과로", "전체에서 다시", "top3 말고 전체", "지금 결과 말고 전체"]),
    }


def resolve_hard_constraints(text: str, current: dict[str, Any] | None = None) -> dict[str, Any]:
    current = current or {}
    resolved = {
        "min_review_count": current.get("min_review_count"),
        "min_rating": current.get("min_rating"),
        "required_shipping": list(current.get("required_shipping") or []),
        "result_limit": current.get("result_limit"),
        "scope_mode": current.get("scope_mode"),
    }

    result_limit = _extract_result_limit(text)
    if result_limit is not None:
        resolved["result_limit"] = result_limit

    min_review_count = _extract_min_review_count(text)
    if min_review_count is not None:
        resolved["min_review_count"] = min_review_count

    min_rating = _extract_min_rating(text)
    if min_rating is not None:
        resolved["min_rating"] = min_rating

    required_shipping = _extract_required_shipping(text)
    if required_shipping:
        resolved["required_shipping"] = list(dict.fromkeys([*resolved["required_shipping"], *required_shipping]))

    scope_mode = _extract_scope_mode(text)
    if scope_mode:
        resolved["scope_mode"] = scope_mode

    clear_flags = _clear_constraint_flags(text)
    if clear_flags["clear_review"]:
        resolved["min_review_count"] = None
    if clear_flags["clear_rating"]:
        resolved["min_rating"] = None
    if clear_flags["clear_shipping"]:
        resolved["required_shipping"] = []
    if clear_flags["clear_limit"]:
        resolved["result_limit"] = None
    if clear_flags["clear_scope"]:
        resolved["scope_mode"] = None

    return resolved

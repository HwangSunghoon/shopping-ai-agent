import html
import re
import asyncio
import httpx
from app.config import get_settings
from app.services.cache_service import build_cache_key, get_cache, set_cache

settings = get_settings()

TAG_RE = re.compile(r"<[^>]+>")


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(TAG_RE.sub("", value)).strip()


def to_int(value: str | int | None) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


async def search_naver_shopping(query: str, display: int = 10, start: int = 1, sort: str = "sim") -> list[dict]:
    if not settings.naver_client_id or not settings.naver_client_secret:
        raise RuntimeError("NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 설정되지 않았습니다.")

    cache_key = build_cache_key(
        "naver_search",
        {
            "query": query.strip(),
            "display": min(max(display, 1), 100),
            "start": max(start, 1),
            "sort": sort,
        },
    )
    cached_products = get_cache("naver_search", cache_key)
    if cached_products is not None:
        return cached_products

    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    params = {
        "query": query,
        "display": min(max(display, 1), 100),
        "start": max(start, 1),
        "sort": sort,
    }

    last_error: Exception | None = None
    for attempt in range(settings.naver_max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.naver_timeout_seconds) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                break
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_error = exc
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) and exc.response else None
            should_retry = attempt < settings.naver_max_retries and (status_code is None or status_code >= 500 or status_code == 429)
            if not should_retry:
                raise
            await asyncio.sleep(0.25 * (attempt + 1))
    else:
        raise last_error or RuntimeError("네이버 쇼핑 API 호출에 실패했습니다.")

    products: list[dict] = []
    for item in data.get("items", []):
        category_parts = [
            item.get("category1"),
            item.get("category2"),
            item.get("category3"),
            item.get("category4"),
        ]
        category = " > ".join([c for c in category_parts if c])
        products.append(
            {
                "title": clean_html(item.get("title")),
                "link": item.get("link", ""),
                "image": item.get("image"),
                "mall_name": item.get("mallName"),
                "category": category,
                "lprice": to_int(item.get("lprice")),
                "score": 0,
                "reason": "",
            }
        )

    set_cache("naver_search", cache_key, products, settings.naver_cache_ttl_seconds)
    return products

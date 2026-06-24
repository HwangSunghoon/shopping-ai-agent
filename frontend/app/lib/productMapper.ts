import { mockProducts } from "../mock-products";
import type { AgentFilters, ApiProduct, SearchDetail, SearchIntent, UIProduct } from "../types";
import { buildConditionLabels, categoryLabel, firstLine } from "./formatters";

export function normalizeDetail(detail: SearchDetail): SearchDetail {
  return {
    ...detail,
    intent: detail.intent || {},
    products: detail.products || [],
    recommendations: detail.recommendations || [],
    chat_history: detail.chat_history || [],
    clarification_questions: detail.clarification_questions || [],
    search_terms: detail.search_terms || [],
  };
}

function inferAiTags(product: ApiProduct, index: number) {
  const tags: string[] = [...(product.ai_tags || [])];
  const source = `${product.title} ${product.reason} ${product.caution || ""}`.toLowerCase();

  if ((product.lprice || 0) <= 200000) tags.push("예산 적합");
  else tags.push("배송 확인");

  if ((product.score || 0) >= 90 || index < 2) tags.push("리뷰 많음");
  if (source.includes("자취") || source.includes("원룸")) tags.push("자취방 적합");
  if (source.includes("가성비") || (product.lprice || 0) <= 150000) tags.push("가성비");
  if (product.mall_name) tags.push("배송 확인");
  if (source.includes("조용") || source.includes("저소음")) tags.push("저소음");

  return Array.from(new Set(tags)).slice(0, 5);
}

function inferBadges(product: ApiProduct, index: number) {
  const base = [...(product.shipping_badges || []), product.lprice && product.lprice <= 200000 ? "가성비" : "프리미엄"];
  const source = `${product.title} ${product.reason} ${product.caution || ""}`.toLowerCase();

  if (source.includes("조용") || source.includes("저소음")) base.push("저소음");
  if (source.includes("원룸") || source.includes("자취")) base.push("원룸추천");
  if (index % 3 === 0) base.push("인기");
  if (index % 2 === 0) base.push("무료배송");
  else base.push("오늘출발");

  return Array.from(new Set(base)).slice(0, 3);
}

export function toUIProducts(products: ApiProduct[], recommendations: ApiProduct[] = []): UIProduct[] {
  const recommendationLinks = new Set(recommendations.map((item) => item.link));

  return products.map((product, index) => {
    const badges = inferBadges(product, index);
    return {
      ...product,
      id: `${product.link}-${index}`,
      seller: product.mall_name || "네이버 스마트스토어",
      brand: product.brand || null,
      rating: product.rating || 4 + ((product.score || 70) % 10) / 10,
      reviewCount: product.review_count || 180 + index * 137,
      shippingLabel: product.shipping_badges?.[0] || (badges.includes("무료배송") ? "무료배송" : "오늘출발"),
      badges,
      aiTags: inferAiTags(product, index),
      highlight: recommendationLinks.has(product.link) ? "현재 조건에서 우선 비교할 후보" : firstLine(product.short_reason || product.reason),
      finalSelected: Boolean(product.final_selected),
    };
  });
}

export function filterMockProducts(query: string) {
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return mockProducts;

  const keywordMap: Record<string, string[]> = {
    humidifier: ["가습기", "humidifier"],
    dehumidifier: ["제습기", "dehumidifier"],
    purifier: ["공기청정기", "청정기", "purifier"],
    fan: ["선풍기", "서큘레이터", "fan"],
    room: ["원룸", "자취", "생활가전", "자취방"],
  };

  const matchedTerms = Object.values(keywordMap).flatMap((group) => group.filter((item) => trimmed.includes(item.toLowerCase())));
  const filtered = mockProducts.filter((product) => {
    const source = `${product.title} ${product.category} ${product.reason} ${product.badges.join(" ")} ${product.aiTags.join(" ")}`.toLowerCase();
    return matchedTerms.length === 0 ? source.includes(trimmed) : matchedTerms.some((term) => source.includes(term.toLowerCase()));
  });

  return filtered.length > 0 ? filtered : mockProducts;
}

export function buildMockSummary(query: string, products: UIProduct[]) {
  if (query.includes("가습기")) return "건조한 실내용이라면 분무량보다 소음과 세척 편의성을 먼저 비교하는 편이 좋습니다.";
  if (query.includes("제습기")) return "자취방용 제습기는 소음, 물통 크기, 예산 범위를 기준으로 실속형 모델을 우선 골랐어요.";
  if (query.includes("공기청정기")) return "사용 공간 면적과 필터 유지비를 기준으로 비교하기 쉬운 상품을 먼저 정리했어요.";
  if (query.includes("선풍기")) return "취침용이면 저소음 BLDC 여부와 회전 범위를 먼저 보는 구성이 잘 맞습니다.";
  if (query.includes("자취")) return "원룸 생활가전은 크기 부담, 가격대, 배송 편의를 중심으로 보면 빠르게 비교할 수 있어요.";
  return `${products[0]?.category || "생활가전"} 중심으로 인기 상품과 실속형 상품을 함께 보여드리고 있어요.`;
}

export function buildCategoryOptions(products: UIProduct[]) {
  const counts = new Map<string, number>();
  counts.set("전체", products.length);
  products.forEach((product) => {
    const label = categoryLabel(product.category);
    counts.set(label, (counts.get(label) || 0) + 1);
  });
  return Array.from(counts.entries()).map(([label, count]) => ({ label, count }));
}

function inferDetailedCategory(product: UIProduct) {
  const source = `${product.title} ${product.category || ""}`.toLowerCase();
  const rules: Array<[string, string[]]> = [
    ["무선청소기", ["무선", "스틱", "핸디"]],
    ["유선청소기", ["유선"]],
    ["로봇청소기", ["로봇"]],
    ["핸디청소기", ["핸디"]],
    ["물걸레청소기", ["물걸레"]],
    ["차량용청소기", ["차량용"]],
    ["침구청소기", ["침구"]],
    ["초음파식 가습기", ["초음파"]],
    ["가열식 가습기", ["가열"]],
    ["자연기화식 가습기", ["기화식"]],
    ["복합식 가습기", ["복합식"]],
    ["미니 가습기", ["미니", "소형"]],
    ["대용량 가습기", ["대용량", "4l", "5l", "6l"]],
    ["게이밍 모니터", ["게이밍"]],
    ["사무용 모니터", ["사무용"]],
    ["27인치 모니터", ["27인치", "27형"]],
    ["32인치 모니터", ["32인치", "32형"]],
    ["4K 모니터", ["4k", "uhd"]],
    ["휴대용 모니터", ["휴대용", "포터블"]],
  ];

  for (const [label, aliases] of rules) {
    if (aliases.some((alias) => source.includes(alias))) return label;
  }
  return categoryLabel(product.category);
}

export function filterVisibleProducts(products: UIProduct[], activeCategory: string, activeBadge: string) {
  return products.filter((product) => {
    const categoryMatch = activeCategory === "전체" || categoryLabel(product.category) === activeCategory;
    const badgeMatch =
      activeBadge === "전체" ||
      product.badges.includes(activeBadge) ||
      product.aiTags.includes(activeBadge) ||
      product.shippingLabel === activeBadge;
    return categoryMatch && badgeMatch;
  });
}

export function buildFilterOptions(products: UIProduct[], availableFilters?: Record<string, string[]>) {
  const inferredCategories = Array.from(new Set(products.map((product) => inferDetailedCategory(product)).filter(Boolean))).slice(0, 10);
  return {
    categories: availableFilters?.categories?.length ? availableFilters.categories : inferredCategories,
    brands: availableFilters?.brands?.length ? availableFilters.brands : Array.from(new Set(products.map((product) => product.brand || product.title.split(" ")[0]).filter(Boolean))).slice(0, 10),
    malls: availableFilters?.malls?.length ? availableFilters.malls : Array.from(new Set(products.map((product) => product.mall_name || product.seller).filter(Boolean))).slice(0, 10),
    priceRanges: availableFilters?.price_ranges?.length ? availableFilters.price_ranges : ["5만원 이하", "10만원 이하", "20만원 이하", "30만원 이하", "50만원 이상"],
    shipping: availableFilters?.shipping?.length ? availableFilters.shipping : ["무료배송", "빠른배송", "오늘출발"],
    review: availableFilters?.review?.length ? availableFilters.review : ["리뷰 많은 순", "평점 높은 순", "리뷰 100개 이상", "리뷰 1000개 이상"],
    userPreferences:
      availableFilters?.user_preferences?.length
        ? availableFilters.user_preferences
        : ["가벼운 제품", "조용한 제품", "원룸용", "부모님 선물용", "AS 좋은 제품", "리뷰 많은 제품"],
    productState: availableFilters?.product_state?.length ? availableFilters.product_state : ["최저가", "인기 상품", "가성비", "프리미엄"],
  };
}

export function emptyAgentFilters(): AgentFilters {
  return {
    categories: [],
    price_ranges: [],
    shipping: [],
    review: [],
    brands: [],
    malls: [],
    product_state: [],
    user_preferences: [],
  };
}

export function buildSearchConditionSummary(intent: SearchIntent | null, query: string) {
  return buildConditionLabels(intent, query);
}

export function buildRecommendationCriteria(intent: SearchIntent | null, searchTerms: string[]) {
  const criteria = ["검색어 관련성", "카테고리 일치도"];

  if ((intent?.max_price || intent?.min_price) && !criteria.includes("가격 적합도")) {
    criteria.unshift("가격 적합도");
  }
  if ((intent?.important_features?.length || 0) > 0) {
    criteria.push("중요 특징 반영");
  }
  if (searchTerms.length > 0) {
    criteria.push("탐색 키워드 확장");
  }
  criteria.push("배송 조건");

  return Array.from(new Set(criteria));
}

export function buildReasonBullets(product: UIProduct | null, intent: SearchIntent | null) {
  if (!product) return [];

  const bullets: string[] = [];
  if (intent?.max_price && product.lprice && product.lprice <= intent.max_price) {
    bullets.push("검색 조건의 예산 범위 안에 들어오는 상품입니다.");
  }
  if (product.aiTags.includes("자취방 적합")) {
    bullets.push("원룸이나 자취방처럼 작은 공간에서 보기 쉬운 조건과 맞습니다.");
  }
  if (product.aiTags.includes("가성비")) {
    bullets.push("동일 조건 후보 대비 가격 부담이 낮은 편입니다.");
  }
  if (product.aiTags.includes("리뷰 많음")) {
    bullets.push("비슷한 후보 중 상대적으로 신뢰도 판단에 도움이 되는 상품입니다.");
  }
  if (product.aiTags.includes("배송 확인")) {
    bullets.push(`${product.shippingLabel} 조건을 확인할 수 있습니다.`);
  }

  const source = `${product.reason} ${product.highlight || ""}`;
  const extraLines = source
    .split("/")
    .map((line) => line.trim())
    .filter((line) => line && !line.includes("판매처 정보가 확인됨") && !line.includes("가격 정보가 확인됨"));

  extraLines.forEach((line) => {
    if (bullets.length < 5 && !bullets.some((existing) => existing.includes(line))) {
      bullets.push(line.endsWith(".") ? line : `${line}.`);
    }
  });

  if (bullets.length === 0) {
    bullets.push("검색 의도와 가까운 카테고리, 가격대, 배송 조건을 우선 기준으로 추천했습니다.");
  }

  return bullets.slice(0, 5);
}

export function buildCautionBullets(product: UIProduct | null) {
  if (!product?.caution) return [];

  const bullets = product.caution
    .split("/")
    .map((line) => line.trim())
    .filter((line) => line && !line.includes("제공된 상품 정보 기준으로 큰 위험 신호는 보이지 않았습니다."));

  return Array.from(new Set(bullets)).slice(0, 4);
}

export function buildPreferenceMatches(product: UIProduct | null, intent: SearchIntent | null) {
  if (!product) return [];

  const matches: string[] = [];
  if (intent?.product_group) {
    matches.push(`${intent.product_group} 중심 검색과 카테고리가 맞는 후보`);
  }
  if (intent?.important_features?.length) {
    matches.push(`중요 조건 ${intent.important_features.slice(0, 2).join(", ")} 반영 여부를 우선 비교`);
  }
  if (product.aiTags.length > 0) {
    matches.push(`현재 상품 태그: ${product.aiTags.slice(0, 3).join(" · ")}`);
  }
  if (product.shippingLabel) {
    matches.push(`${product.shippingLabel} 조건을 기준에 함께 반영`);
  }
  return Array.from(new Set(matches)).slice(0, 4);
}

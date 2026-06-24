import type { SearchIntent } from "../types";

export function formatPrice(price?: number | null) {
  if (price === null || price === undefined) return "가격 문의";
  return `${price.toLocaleString("ko-KR")}원`;
}

export function firstLine(text: string) {
  return text.split("\n").find(Boolean)?.trim() || text;
}

export function categoryLabel(category?: string | null) {
  return category?.split(">")[1]?.trim() || category || "생활가전";
}

export function buildConditionLabels(intent: SearchIntent | null, query: string) {
  const labels: string[] = [];

  if (intent?.product_group || intent?.keyword) {
    labels.push(intent.product_group || intent.keyword || "상품");
  }

  if (intent?.max_price) {
    labels.push(`${Math.floor(intent.max_price / 10000)}만원 이하`);
  } else if (query.includes("10만원대")) {
    labels.push("10만원대");
  }

  if (intent?.use_case) {
    labels.push(intent.use_case);
  } else if (query.includes("자취") || query.includes("원룸")) {
    labels.push("자취방용");
  }

  const features = intent?.important_features?.filter(Boolean) || [];
  if (features.length > 0) {
    labels.push(`${features[0]} 중심`);
  } else if (query.includes("조용") || query.includes("저소음")) {
    labels.push("저소음 중심");
  }

  if (labels.length === 0) {
    return query ? [query] : ["생활가전", "실속형 추천"];
  }

  return labels.slice(0, 4);
}

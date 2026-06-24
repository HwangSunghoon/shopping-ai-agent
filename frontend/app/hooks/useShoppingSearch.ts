"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchAgentFeedback, fetchAgentFinalSelect, fetchAgentRefine, fetchAgentSearch, fetchHistory } from "../lib/api";
import { emptyAgentFilters, filterMockProducts, toUIProducts } from "../lib/productMapper";
import type {
  AgentFilters,
  AgentSearchResponse,
  FeedbackEventType,
  HomeShowcaseSection,
  HistoryItem,
  SearchIntent,
  ShoppingConversationState,
  UIProduct,
} from "../types";

const loadingSteps = ["조건 분석 중", "상품 검색 중", "추천 기준 정리 중"] as const;
const HOME_QUERY = "생활가전";
const USER_ID = "demo-user";
const HOME_USER_ID = "home-showcase";
const DISPLAY_COUNT = 20;
const HOME_SECTION_CONFIG: Array<{ id: string; title: string; query: string; imageOnly?: boolean }> = [
  { id: "best", title: "BEST 상품", query: "생활가전", imageOnly: true },
  { id: "personal", title: "고객님을 위한 상품", query: "가습기" },
  { id: "today", title: "오늘의 추천 상품", query: "제습기" },
];
const HOME_SECTION_DISPLAY = 6;
const HOME_CACHE_KEY = "shopping-agent-home-sections-v4";

type ConversationTrailEntry = {
  question: string;
  answer: string;
};

function buildHomeFallbackSections() {
  return HOME_SECTION_CONFIG.map((section) => ({
    id: section.id,
    title: section.title,
    query: section.query,
    products: toUIProducts(filterMockProducts(section.query)).slice(0, HOME_SECTION_DISPLAY),
    hasMore: false,
    nextPage: null,
    loadingMore: false,
    imageOnly: Boolean(section.imageOnly),
  })).filter((section) => section.products.length > 0);
}

function readHomeCache(): HomeShowcaseSection[] {
  if (typeof window === "undefined") return [];

  try {
    const raw = window.localStorage.getItem(HOME_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as { sections?: HomeShowcaseSection[]; expiresAt?: number };
    if (!parsed.sections?.length || !parsed.expiresAt || parsed.expiresAt < Date.now()) {
      window.localStorage.removeItem(HOME_CACHE_KEY);
      return [];
    }
    return parsed.sections;
  } catch {
    return [];
  }
}

function writeHomeCache(sections: HomeShowcaseSection[]) {
  if (typeof window === "undefined" || sections.length === 0) return;

  window.localStorage.setItem(
    HOME_CACHE_KEY,
    JSON.stringify({
      sections,
      expiresAt: Date.now() + 1000 * 60 * 5,
    }),
  );
}

function mergeProducts(existing: UIProduct[], incoming: UIProduct[]) {
  const next = [...existing];
  const seen = new Set(existing.map((product) => product.link));
  incoming.forEach((product) => {
    if (seen.has(product.link)) return;
    seen.add(product.link);
    next.push(product);
  });
  return next;
}

function emptyConversationState(originalQuery = ""): ShoppingConversationState {
  return {
    original_query: originalQuery,
    refined_queries: [],
    extracted_preferences: {
      category: null,
      subcategories: [],
      budget_min: null,
      budget_max: null,
      usage_context: [],
      preferred_features: [],
      disliked_features: [],
      preferred_brands: [],
      excluded_brands: [],
      sort_intent: null,
    },
    constraints: {
      min_review_count: null,
      min_rating: null,
      required_shipping: [],
      result_limit: null,
      scope_mode: null,
    },
    user_feedback: {
      liked_product_ids: [],
      disliked_product_ids: [],
      too_expensive_product_ids: [],
      hidden_product_ids: [],
    },
    final_selected_product_id: null,
  };
}

function buildAssistantTrace(query: string, response: AgentSearchResponse) {
  if (response.assistant_trace?.trim()) {
    return response.assistant_trace.trim();
  }

  const intent = response.interpreted_intent || {};
  const context = response.conversation_context;
  const keyword = intent.product_group || intent.keyword || "요청하신 조건";
  const feature = intent.important_features?.[0];
  const priceText = intent.max_price
    ? `${Math.floor(intent.max_price / 10000)}만원 이하`
    : intent.min_price
      ? `${Math.floor(intent.min_price / 10000)}만원 이상`
      : "";
  const lowered = query.toLowerCase();
  const minReviewCount = context?.constraints?.min_review_count;
  const shippingText = context?.constraints?.required_shipping?.[0];

  if (minReviewCount) return `네, 리뷰 ${minReviewCount}개 이상 기준으로 다시 추렸습니다.`;
  if (lowered.includes("리뷰")) return "네, 리뷰 많은 상품 기준으로 다시 추렸습니다.";
  if (lowered.includes("top3") || lowered.includes("top 3") || lowered.includes("하나만") || lowered.includes("남겨")) {
    return "네, 후보를 더 좁혀 다시 정리했습니다.";
  }
  if (lowered.includes("정렬")) return "네, 요청하신 기준으로 다시 정렬했습니다.";
  if (shippingText) return `네, ${shippingText} 조건을 반영해 다시 보여드릴게요.`;
  if (feature) return `네, ${feature} 조건을 우선 반영해 다시 골랐습니다.`;
  if (priceText) return `네, ${priceText} 조건에 맞춰 다시 추렸습니다.`;
  return `네, ${keyword} 조건을 반영해 다시 보여드릴게요.`;
}

export function useShoppingSearch() {
  const [searchQuery, setSearchQuery] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [products, setProducts] = useState<UIProduct[]>([]);
  const [homeSections, setHomeSections] = useState<HomeShowcaseSection[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<UIProduct | null>(null);
  const [mode, setMode] = useState<"home" | "search">("home");
  const [currentQuery, setCurrentQuery] = useState(HOME_QUERY);
  const [currentIntent, setCurrentIntent] = useState<SearchIntent | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationContext, setConversationContext] = useState<ShoppingConversationState>(emptyConversationState());
  const [selectedFilters, setSelectedFilters] = useState<AgentFilters>(emptyAgentFilters());
  const [availableFilters, setAvailableFilters] = useState<Record<string, string[]>>({});
  const [hasMore, setHasMore] = useState(false);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);
  const [error, setError] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [pendingFeedbackKey, setPendingFeedbackKey] = useState<string | null>(null);
  const [feedbackPreferences, setFeedbackPreferences] = useState<Record<string, unknown> | null>(null);
  const [recommendationDebug, setRecommendationDebug] = useState<Record<string, unknown> | null>(null);
  const [recommendationReason, setRecommendationReason] = useState("");
  const [topRecommendationLink, setTopRecommendationLink] = useState<string | null>(null);
  const [searchTerms, setSearchTerms] = useState<string[]>([]);
  const [finalizing, setFinalizing] = useState(false);
  const [lastAction, setLastAction] = useState<{ type: "search" | "refine"; value: string } | null>(null);
  const [conversationTrail, setConversationTrail] = useState<ConversationTrailEntry[]>([]);

  useEffect(() => {
    async function loadInitialHistory() {
      try {
        const data = await fetchHistory();
        setHistory(data);
      } catch {
        return;
      }
    }

    void loadInitialHistory();
  }, []);

  useEffect(() => {
    const cachedSections = readHomeCache();
    if (cachedSections.length === 0) return;

    const cachedProducts = cachedSections.flatMap((section) => section.products);
    setHomeSections(cachedSections);
    setProducts(cachedProducts);
    setSelectedProduct(cachedProducts[0] || null);
    setTopRecommendationLink(cachedProducts[0]?.link || null);
  }, []);

  useEffect(() => {
    void loadHomeProducts();
  }, []);

  useEffect(() => {
    if (!isLoading) {
      setLoadingStepIndex(0);
      return;
    }

    const intervalId = window.setInterval(() => {
      setLoadingStepIndex((current) => (current + 1) % loadingSteps.length);
    }, 900);

    return () => window.clearInterval(intervalId);
  }, [isLoading]);

  useEffect(() => {
    if (!selectedProduct && products.length > 0) {
      setSelectedProduct(products[0]);
    }
  }, [products, selectedProduct]);

  const loadingStep = loadingSteps[loadingStepIndex];
  const fallbackProducts = useMemo(() => toUIProducts(filterMockProducts(searchQuery || currentQuery)), [currentQuery, searchQuery]);

  function applyResponse(response: AgentSearchResponse, options?: { append?: boolean; forceMode?: "home" | "search" }) {
    const mappedProducts = toUIProducts(response.products, response.top_recommendation ? [response.top_recommendation] : []);
    const mergedProducts = options?.append ? mergeProducts(products, mappedProducts) : mappedProducts;
    setProducts(mergedProducts);
    setSelectedProduct((current) => {
      if (current && mergedProducts.some((product) => product.link === current.link)) {
        return mergedProducts.find((product) => product.link === current.link) || current;
      }
      return mergedProducts[0] || null;
    });
    setMode(options?.forceMode || "search");
    setCurrentQuery(response.applied_query);
    setCurrentIntent(response.interpreted_intent);
    setConversationId(response.conversation_id);
    setConversationContext(response.conversation_context);
    setAvailableFilters(response.available_filters || {});
    setHasMore(response.has_more);
    setNextPage(response.next_page || null);
    setRecommendationReason(response.recommendation_reason || "");
    setTopRecommendationLink(response.top_recommendation?.link || mappedProducts[0]?.link || null);
    setSearchTerms(response.expanded_queries || []);
    setRecommendationDebug(response.debug || null);
    setError("");
  }

  async function loadHomeProducts() {
    setIsLoading(true);
    setMode("home");
    setSearchQuery("");
    setSelectedFilters(emptyAgentFilters());
    setConversationContext(emptyConversationState());
    const fallbackSections = buildHomeFallbackSections();
    const fallbackHomeProducts = fallbackSections.flatMap((section) => section.products);
    setError("");

    try {
      const nextSections: HomeShowcaseSection[] = [];
      for (const section of HOME_SECTION_CONFIG) {
        try {
          const result = await fetchAgentSearch({
            userId: HOME_USER_ID,
            query: section.query,
            page: 1,
            display: HOME_SECTION_DISPLAY,
            trackEvent: false,
            searchTermLimit: 1,
            filters: emptyAgentFilters(),
          });
          const apiProducts = toUIProducts(
            result.products || [],
            result.top_recommendation ? [result.top_recommendation] : [],
          );
          nextSections.push({
            id: section.id,
            title: section.title,
            query: section.query,
            products: apiProducts,
            hasMore: Boolean(result.has_more),
            nextPage: result.next_page || null,
            loadingMore: false,
            imageOnly: Boolean(section.imageOnly),
          });
        } catch {
          const fallbackSectionProducts = toUIProducts(filterMockProducts(section.query)).slice(0, HOME_SECTION_DISPLAY);
          nextSections.push({
            id: section.id,
            title: section.title,
            query: section.query,
            products: fallbackSectionProducts,
            hasMore: false,
            nextPage: null,
            loadingMore: false,
            imageOnly: Boolean(section.imageOnly),
          });
        }
      }

      setHomeSections(nextSections);
      writeHomeCache(nextSections);
      const mergedHomeProducts = nextSections.flatMap((section) => section.products);
      setProducts(mergedHomeProducts.length > 0 ? mergedHomeProducts : fallbackProducts);
      setSelectedProduct(mergedHomeProducts[0] || fallbackProducts[0] || null);
      setCurrentQuery(HOME_QUERY);
      setCurrentIntent(null);
      setConversationId(null);
      setAvailableFilters({});
      setHasMore(false);
      setNextPage(null);
      setRecommendationReason("");
      setTopRecommendationLink(mergedHomeProducts[0]?.link || fallbackProducts[0]?.link || null);
      setSearchTerms([]);
      setRecommendationDebug(null);
      setError("");
      setLastAction({ type: "search", value: HOME_QUERY });
      setConversationTrail([]);
    } catch {
      setProducts(fallbackHomeProducts.length > 0 ? fallbackHomeProducts : fallbackProducts);
      setSelectedProduct(fallbackHomeProducts[0] || fallbackProducts[0] || null);
      setHomeSections(fallbackSections);
      writeHomeCache(fallbackSections);
      setHasMore(false);
      setNextPage(null);
      setRecommendationReason("");
      setSearchTerms([]);
      setError("");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadMoreHomeSection(sectionId: string) {
    const target = homeSections.find((section) => section.id === sectionId);
    if (!target || !target.hasMore || !target.nextPage || target.loadingMore) return;

    setHomeSections((current) =>
      current.map((section) => (section.id === sectionId ? { ...section, loadingMore: true } : section)),
    );

    try {
      const response = await fetchAgentSearch({
        userId: HOME_USER_ID,
        query: target.query,
        page: target.nextPage,
        display: 10,
        trackEvent: false,
        searchTermLimit: 2,
        filters: emptyAgentFilters(),
      });
      const incomingProducts = toUIProducts(response.products || [], response.top_recommendation ? [response.top_recommendation] : []);

      setHomeSections((current) => {
        const nextSections = current.map((section) =>
          section.id === sectionId
            ? {
                ...section,
                products: mergeProducts(section.products, incomingProducts),
                hasMore: response.has_more,
                nextPage: response.next_page || null,
                loadingMore: false,
              }
            : section,
        );
        writeHomeCache(nextSections);
        return nextSections;
      });
      setProducts((current) => mergeProducts(current, incomingProducts));
    } catch {
      setHomeSections((current) =>
        current.map((section) => (section.id === sectionId ? { ...section, hasMore: false, nextPage: null, loadingMore: false } : section)),
      );
    }
  }

  async function submitSearchPrompt(query?: string) {
    const text = (query ?? searchQuery).trim();
    if (!text) return;

    setIsLoading(true);
    setFeedbackMessage("");

    try {
      if (mode === "home" || !conversationId) {
        const response = await fetchAgentSearch({
          userId: USER_ID,
          query: text,
          page: 1,
          display: DISPLAY_COUNT,
          filters: selectedFilters,
          conversationContext: emptyConversationState(text),
        });
        applyResponse(response, { forceMode: "search" });
        setLastAction({ type: "search", value: text });
        setConversationTrail([{ question: text, answer: buildAssistantTrace(text, response) }]);
      } else {
        const response = await fetchAgentRefine({
          userId: USER_ID,
          conversationId,
          message: text,
          page: 1,
          display: DISPLAY_COUNT,
          filters: selectedFilters,
          currentProductIds: products.map((product) => product.link),
          currentTop3Ids: products.slice(0, 3).map((product) => product.link),
          currentProducts: products,
          currentTop3Products: products.slice(0, 3),
          conversationContext,
        });
        applyResponse(response, { forceMode: "search" });
        setLastAction({ type: "refine", value: text });
        setConversationTrail((current) => [...current, { question: text, answer: buildAssistantTrace(text, response) }]);
      }

      setSearchQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "상품을 불러오지 못했습니다.");
      if (mode === "home") {
        setProducts(fallbackProducts);
        setSelectedProduct(fallbackProducts[0] || null);
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function loadMore() {
    if (!hasMore || !nextPage || isLoadingMore) return;

    setIsLoadingMore(true);

    try {
      if (mode === "home") {
        const response = await fetchAgentSearch({
          userId: USER_ID,
          query: currentQuery,
          conversationId,
          page: nextPage,
          display: DISPLAY_COUNT,
          filters: selectedFilters,
          conversationContext,
        });
        applyResponse(response, { append: true, forceMode: "home" });
      } else if (conversationId && lastAction?.type === "refine") {
        const response = await fetchAgentRefine({
          userId: USER_ID,
          conversationId,
          message: lastAction.value,
          page: nextPage,
          display: DISPLAY_COUNT,
          filters: selectedFilters,
          currentProductIds: products.map((product) => product.link),
          currentTop3Ids: products.slice(0, 3).map((product) => product.link),
          conversationContext,
        });
        applyResponse(response, { append: true, forceMode: "search" });
      } else {
        const response = await fetchAgentSearch({
          userId: USER_ID,
          query: currentQuery,
          conversationId,
          page: nextPage,
          display: DISPLAY_COUNT,
          filters: selectedFilters,
          conversationContext,
        });
        applyResponse(response, { append: true, forceMode: mode });
      }
    } catch {
      setHasMore(false);
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function applyFilters(nextFilters: AgentFilters) {
    setSelectedFilters(nextFilters);
    if (mode === "home") return;
    if (!conversationId) return;

    setIsLoading(true);
    try {
      const response = await fetchAgentSearch({
        userId: USER_ID,
        query: currentQuery,
        conversationId,
        page: 1,
        display: DISPLAY_COUNT,
        filters: nextFilters,
        conversationContext,
      });
      applyResponse(response, { forceMode: "search" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "필터를 적용하지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  async function sendProductFeedback(product: UIProduct, eventType: FeedbackEventType, reason?: string) {
    const feedbackKey = `${product.id}:${eventType}`;
    setPendingFeedbackKey(feedbackKey);
    setFeedbackMessage("");
    try {
      const response = await fetchAgentFeedback({
        userId: USER_ID,
        conversationId,
        productId: product.link,
        eventType,
        metadata: {
          title: product.title,
          price: product.lprice,
          category: product.category,
          brand: product.brand,
          mall_name: product.mall_name || product.seller,
          query: currentQuery,
          reason: reason || null,
        },
      });
      setFeedbackPreferences(response.preferences);
      setFeedbackMessage(`피드백이 반영되었습니다. 업데이트된 선호 ${response.updated_preference_count}건`);
      setConversationContext((current) => {
        const next = structuredClone(current);
        if (eventType === "like" && !next.user_feedback.liked_product_ids.includes(product.link)) next.user_feedback.liked_product_ids.push(product.link);
        if ((eventType === "dislike" || eventType === "not_relevant") && !next.user_feedback.disliked_product_ids.includes(product.link)) {
          next.user_feedback.disliked_product_ids.push(product.link);
        }
        if (eventType === "too_expensive" && !next.user_feedback.too_expensive_product_ids.includes(product.link)) {
          next.user_feedback.too_expensive_product_ids.push(product.link);
        }
        if (eventType === "not_relevant" && !next.user_feedback.hidden_product_ids.includes(product.link)) {
          next.user_feedback.hidden_product_ids.push(product.link);
        }
        return next;
      });
    } catch (err) {
      setFeedbackMessage(err instanceof Error ? err.message : "피드백 저장에 실패했습니다.");
    } finally {
      setPendingFeedbackKey(null);
    }
  }

  async function finalizeProduct(product: UIProduct) {
    if (!conversationId) return;
    setFinalizing(true);
    try {
      await fetchAgentFinalSelect({
        userId: USER_ID,
        conversationId,
        productId: product.link,
        product,
      });
      setConversationContext((current) => ({ ...current, final_selected_product_id: product.link }));
      setProducts((current) => current.map((item) => ({ ...item, finalSelected: item.link === product.link })));
      setSelectedProduct((current) => (current ? { ...current, finalSelected: current.link === product.link } : current));
      setFeedbackMessage("최종 추천 상품으로 저장했습니다.");
      window.location.href = product.link;
    } catch (err) {
      setFeedbackMessage(err instanceof Error ? err.message : "최종 선택 저장에 실패했습니다.");
    } finally {
      setFinalizing(false);
    }
  }

  function toggleFilter(group: keyof AgentFilters, value: string) {
    const nextFilters: AgentFilters = {
      ...selectedFilters,
      [group]: selectedFilters[group].includes(value)
        ? selectedFilters[group].filter((item) => item !== value)
        : [...selectedFilters[group], value],
    };
    void applyFilters(nextFilters);
  }

  function resetFilters() {
    void applyFilters(emptyAgentFilters());
  }

  async function resetHome() {
    await loadHomeProducts();
  }

  return {
    searchQuery,
    setSearchQuery,
    history,
    mode,
    currentQuery,
    currentIntent,
    selectedProduct,
    setSelectedProduct,
    products,
    homeSections,
    hasMore,
    isLoading,
    isLoadingMore,
    loadingStep,
    error,
    feedbackMessage,
    pendingFeedbackKey,
    feedbackPreferences,
    recommendationDebug,
    recommendationReason,
    topRecommendationLink,
    searchTerms,
    conversationTrail,
    selectedFilters,
    availableFilters,
    conversationContext,
    finalizing,
    submitSearchPrompt,
    loadMoreHomeSection,
    loadMore,
    toggleFilter,
    resetFilters,
    resetHome,
    sendProductFeedback,
    finalizeProduct,
  };
}

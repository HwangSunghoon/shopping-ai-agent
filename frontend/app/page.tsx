"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { FilterSidebar } from "./components/FilterSidebar";
import { HomeProductShowcase } from "./components/HomeProductShowcase";
import { ProductGrid } from "./components/ProductGrid";
import { SearchHeader } from "./components/SearchHeader";
import { SearchLoadingState } from "./components/SearchLoadingState";
import { SelectedProductInsight } from "./components/SelectedProductInsight";
import { defaultQueries } from "./mock-products";
import { useShoppingSearch } from "./hooks/useShoppingSearch";
import {
  buildCautionBullets,
  buildFilterOptions,
  buildPreferenceMatches,
  buildReasonBullets,
} from "./lib/productMapper";

export default function Home() {
  const {
    searchQuery,
    setSearchQuery,
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
  } = useShoppingSearch();

  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hasMore || isLoadingMore || !loadMoreRef.current) return;

    const target = loadMoreRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          void loadMore();
        }
      },
      { rootMargin: "220px 0px" },
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, loadMore]);

  const reasonBullets = useMemo(() => buildReasonBullets(selectedProduct, currentIntent), [selectedProduct, currentIntent]);
  const cautionBullets = useMemo(() => buildCautionBullets(selectedProduct), [selectedProduct]);
  const preferenceMatches = useMemo(() => buildPreferenceMatches(selectedProduct, currentIntent), [selectedProduct, currentIntent]);
  const filterOptions = useMemo(() => buildFilterOptions(products, availableFilters), [products, availableFilters]);
  const hasNoResults = !isLoading && products.length === 0;
  const homeCategories = ["생활가전", "무선청소기", "가습기", "모니터", "키보드", "공기청정기", "이어폰", "노트북 주변기기"];
  const collapseToTop = Boolean(conversationContext.final_selected_product_id || conversationContext.extracted_preferences.sort_intent === "final_pick");
  const promptSuggestions = useMemo(() => {
    if (mode !== "search") return [];

    const keyword = currentIntent?.keyword?.trim();
    const productGroup = currentIntent?.product_group?.trim();
    const useCase = currentIntent?.use_case?.trim();
    const feature = currentIntent?.important_features?.[0]?.trim();
    const secondFeature = currentIntent?.important_features?.[1]?.trim();
    const priceText = currentIntent?.max_price ? `${Math.floor(currentIntent.max_price / 10000)}만원 이하` : currentIntent?.min_price ? `${Math.floor(currentIntent.min_price / 10000)}만원 이상` : "";
    const categoryText = productGroup || keyword;

    const suggestions = [
      categoryText ? `지금 결과에서 ${categoryText} 중 리뷰 많은 상품만 보여줘` : null,
      categoryText && priceText ? `지금 결과에서 ${priceText} 조건만 다시 맞춰줘` : null,
      categoryText && useCase ? `지금 결과에서 ${useCase}에 더 잘 맞는 상품만 남겨줘` : null,
      categoryText && feature ? `지금 결과에서 ${feature} 기준으로 다시 정렬해줘` : null,
      categoryText && secondFeature ? `지금 결과에서 ${feature}, ${secondFeature} 둘 다 맞는 상품만 보여줘` : null,
      categoryText ? `top3 중 하나만 남기고 왜 그 상품이 제일 맞는지 설명해줘` : null,
      categoryText ? `지금 후보들 중 가성비가 가장 좋은 순서로 다시 보여줘` : null,
      searchTerms[0] ? `${searchTerms[0]} 기준으로 비슷한 대안도 찾아줘` : null,
      conversationTrail.length > 0 ? `방금 조건까지 반영해서 더 조용한 상품만 다시 골라줘` : null,
    ].filter((value): value is string => Boolean(value));

    return Array.from(new Set(suggestions)).slice(0, 6);
  }, [mode, currentIntent, searchTerms, conversationTrail]);
  return (
    <main className="shoppingPage viewportLayout">
      <SearchHeader
        query={searchQuery}
        loading={isLoading}
        mode={mode}
        promptSuggestions={promptSuggestions}
        conversationItems={conversationTrail}
        onQueryChange={setSearchQuery}
        onSearch={() => void submitSearchPrompt(searchQuery)}
        onHome={() => void resetHome()}
        quickQueries={defaultQueries}
        onQuickQuery={(query) => {
          setSearchQuery(query);
          void submitSearchPrompt(query);
        }}
      />

      {mode === "home" ? (
        <section className="homeDiscoveryPanel" id="today-picks">
          <div className="homeKeywordStrip">
            <strong>인기 키워드</strong>
            <div className="quickQueryRow compact">
              {homeCategories.map((item) => (
                <button key={item} type="button" className="quickQueryChip" onClick={() => void submitSearchPrompt(item)}>
                  {item}
                </button>
              ))}
            </div>
          </div>

          {mode !== "home" && error ? <ErrorState message={error} /> : null}

          <HomeProductShowcase
            sections={homeSections}
            selectedProduct={selectedProduct}
            topRecommendationLink={topRecommendationLink}
            onSelect={setSelectedProduct}
            onFeedback={sendProductFeedback}
            pendingFeedbackKey={pendingFeedbackKey}
            onLoadMore={loadMoreHomeSection}
          />
        </section>
      ) : (
        <section className="shoppingLayout resultsPageLayout" id="results">
          <FilterSidebar options={filterOptions} selectedFilters={selectedFilters} resultCount={products.length} onToggle={toggleFilter} onReset={resetFilters} />

          <div className="resultsColumn scrollColumn">
            {isLoading ? (
              <SearchLoadingState currentStep={loadingStep} />
            ) : error ? (
              <ErrorState message={error} />
            ) : hasNoResults ? (
              <EmptyState title="조건에 맞는 상품이 아직 없습니다" description="가격대나 필터를 조금 넓혀서 다시 찾아보세요. 예: 리뷰 많은 상품, 무료배송만 보기" />
            ) : (
              <ProductGrid
                products={products}
                selectedProduct={selectedProduct}
                topRecommendationLink={topRecommendationLink}
                loadingMore={isLoadingMore}
                hasMore={hasMore}
                collapseToTop={collapseToTop}
                onLoadMore={() => void loadMore()}
                loadMoreRef={loadMoreRef}
                onSelect={setSelectedProduct}
                onFeedback={sendProductFeedback}
                pendingFeedbackKey={pendingFeedbackKey}
              />
            )}
          </div>

          <div className="rightRail">
            <SelectedProductInsight
              selectedProduct={selectedProduct}
              recommendationReason={recommendationReason}
              reasonBullets={reasonBullets}
              cautionBullets={cautionBullets}
              preferenceMatches={preferenceMatches}
              feedbackMessage={feedbackMessage}
              pendingFeedbackKey={pendingFeedbackKey}
              finalizing={finalizing}
              onFeedback={sendProductFeedback}
              onFinalSelect={finalizeProduct}
            />
          </div>
        </section>
      )}
    </main>
  );
}

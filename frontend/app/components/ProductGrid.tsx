import type { RefObject } from "react";
import type { FeedbackEventType, UIProduct } from "../types";
import { ProductCard } from "./ProductCard";

type ProductGridProps = {
  products: UIProduct[];
  selectedProduct: UIProduct | null;
  topRecommendationLink?: string | null;
  loadingMore: boolean;
  hasMore: boolean;
  collapseToTop?: boolean;
  onLoadMore: () => void;
  loadMoreRef: RefObject<HTMLDivElement | null>;
  onSelect: (product: UIProduct) => void;
  onFeedback: (product: UIProduct, eventType: FeedbackEventType, reason?: string) => void;
  pendingFeedbackKey: string | null;
};

export function ProductGrid({
  products,
  selectedProduct,
  topRecommendationLink,
  loadingMore,
  hasMore,
  collapseToTop = false,
  onLoadMore,
  loadMoreRef,
  onSelect,
  onFeedback,
  pendingFeedbackKey,
}: ProductGridProps) {
  const topProducts = collapseToTop ? products.slice(0, 1) : products.slice(0, 3);
  const remainingProducts = collapseToTop ? [] : products.slice(3);

  return (
    <section className="gridSection cleanSection">
      <div className="gridSectionHeader">
        <div>
          <p className="sectionEyebrow">상품 결과</p>
          <h2>{products.length}개 상품</h2>
        </div>
      </div>

      {topProducts.length > 0 ? (
        <div className="productTopSection">
          <div className="subSectionHeader">
            <strong>{collapseToTop ? "최종 추천 상품" : "TOP 3 추천"}</strong>
          </div>
          <div className="topProductGrid">
            {topProducts.map((product, index) => (
              <ProductCard
                key={product.id}
                product={product}
                selected={selectedProduct?.link === product.link}
                recommended={topRecommendationLink === product.link}
                topRank={index + 1}
                onSelect={onSelect}
                onFeedback={onFeedback}
                pendingFeedbackKey={pendingFeedbackKey}
              />
            ))}
          </div>
        </div>
      ) : null}

      {remainingProducts.length > 0 ? (
        <div className="productListSection">
          <div className="subSectionHeader">
            <strong>전체 상품</strong>
          </div>
          <div className="productGrid dense searchResultsGrid">
            {remainingProducts.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                selected={selectedProduct?.link === product.link}
                recommended={topRecommendationLink === product.link}
                onSelect={onSelect}
                onFeedback={onFeedback}
                pendingFeedbackKey={pendingFeedbackKey}
              />
            ))}
          </div>
        </div>
      ) : null}

      {hasMore ? (
        <div className="gridLoadMore" ref={loadMoreRef}>
          {loadingMore ? (
            <div className="inlineLoader" aria-label="상품 더 불러오는 중">
              <span />
              <span />
              <span />
            </div>
          ) : (
            <button type="button" className="loadMoreButton" onClick={onLoadMore}>
              상품 더 보기
            </button>
          )}
        </div>
      ) : null}
    </section>
  );
}

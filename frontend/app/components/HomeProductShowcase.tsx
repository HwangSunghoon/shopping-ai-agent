"use client";

import { useEffect, useRef } from "react";

import type { FeedbackEventType, HomeShowcaseSection, UIProduct } from "../types";
import { ProductCard } from "./ProductCard";

type HomeProductShowcaseProps = {
  sections: HomeShowcaseSection[];
  selectedProduct: UIProduct | null;
  topRecommendationLink?: string | null;
  pendingFeedbackKey: string | null;
  onSelect: (product: UIProduct) => void;
  onFeedback: (product: UIProduct, eventType: FeedbackEventType, reason?: string) => void;
  onLoadMore: (sectionId: string) => void;
};

export function HomeProductShowcase({
  sections,
  selectedProduct,
  topRecommendationLink,
  pendingFeedbackKey,
  onSelect,
  onFeedback,
  onLoadMore,
}: HomeProductShowcaseProps) {
  return (
    <div className="homeShowcaseList">
      {sections.map((section) => (
        <HomeRail
          key={section.id}
          section={section}
          selectedProduct={selectedProduct}
          topRecommendationLink={topRecommendationLink}
          pendingFeedbackKey={pendingFeedbackKey}
          onSelect={onSelect}
          onFeedback={onFeedback}
          onLoadMore={onLoadMore}
        />
      ))}
    </div>
  );
}

type HomeRailProps = Omit<HomeProductShowcaseProps, "sections" | "onLoadMore"> & {
  section: HomeShowcaseSection;
  onLoadMore: (sectionId: string) => void;
};

function HomeRail({ section, selectedProduct, topRecommendationLink, pendingFeedbackKey, onSelect, onFeedback, onLoadMore }: HomeRailProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const sectionAnchorId =
    section.id === "best" ? "home-best" : section.id === "personal" ? "home-personal" : section.id === "today" ? "home-today" : undefined;

  useEffect(() => {
    const element = scrollerRef.current;
    if (!element || !section.hasMore || section.loadingMore) return;

    function handleScroll() {
      const current = scrollerRef.current;
      if (!current) return;
      const nearEnd = current.scrollLeft + current.clientWidth >= current.scrollWidth - 420;
      if (nearEnd) {
        onLoadMore(section.id);
      }
    }

    element.addEventListener("scroll", handleScroll, { passive: true });
    return () => element.removeEventListener("scroll", handleScroll);
  }, [section.id, section.hasMore, section.loadingMore, onLoadMore]);

  return (
    <section className="homeRailSection" id={sectionAnchorId}>
      <div className="gridSectionHeader homeRailHeader">
        <div>
          <p className="sectionEyebrow">상품 결과</p>
          <h2>{section.title}</h2>
        </div>
      </div>

      <div className="homeRailScroller" ref={scrollerRef}>
        {section.imageOnly
          ? section.products.map((product) => (
              <div key={product.id} className="bestImageCard">
                <a href={product.link} target="_blank" rel="noreferrer" className="bestImageLink">
                  <img src={product.image || ""} alt={product.title} />
                </a>
                <button
                  type="button"
                  className="bestLikeButton"
                  onClick={() => onFeedback(product, "like", "BEST 상품 좋아요")}
                  disabled={pendingFeedbackKey === `${product.id}:like`}
                  aria-label={`${product.title} 좋아요`}
                >
                  {pendingFeedbackKey === `${product.id}:like` ? "..." : "♡"}
                </button>
              </div>
            ))
          : section.products.map((product) => (
              <div key={product.id} className="homeRailCardSlot">
                <ProductCard
                  product={product}
                  selected={selectedProduct?.link === product.link}
                  recommended={topRecommendationLink === product.link}
                  onSelect={onSelect}
                  onFeedback={onFeedback}
                  pendingFeedbackKey={pendingFeedbackKey}
                />
              </div>
            ))}

        {section.loadingMore
          ? Array.from({ length: 3 }).map((_, index) =>
              section.imageOnly ? (
                <div key={`best-skeleton-${index}`} className="bestImageCard railSkeletonCard" aria-hidden="true">
                  <div className="railSkeletonImage shimmerBlock" />
                </div>
              ) : (
                <div key={`card-skeleton-${index}`} className="homeRailCardSlot railSkeletonProduct" aria-hidden="true">
                  <div className="railSkeletonProductCard">
                    <div className="railSkeletonImage shimmerBlock" />
                    <div className="railSkeletonLine shimmerBlock short" />
                    <div className="railSkeletonLine shimmerBlock medium" />
                    <div className="railSkeletonLine shimmerBlock price" />
                  </div>
                </div>
              ),
            )
          : null}
      </div>
    </section>
  );
}

"use client";

import type { MouseEvent } from "react";

import { formatPrice } from "../lib/formatters";
import type { FeedbackEventType, UIProduct } from "../types";

type ProductCardProps = {
  product: UIProduct;
  selected: boolean;
  recommended: boolean;
  topRank?: number;
  onSelect: (product: UIProduct) => void;
  onFeedback: (product: UIProduct, eventType: FeedbackEventType, reason?: string) => void;
  pendingFeedbackKey: string | null;
};

export function ProductCard({ product, selected, recommended, topRank, onSelect, onFeedback, pendingFeedbackKey }: ProductCardProps) {
  function handleFeedbackClick(event: MouseEvent<HTMLButtonElement>, eventType: FeedbackEventType, reason: string) {
    event.stopPropagation();
    onFeedback(product, eventType, reason);
  }

  return (
    <article className={`productCard ${selected ? "selected" : ""} ${topRank ? "topRankCard" : ""}`}>
      <button type="button" className="productCardButton" onClick={() => onSelect(product)}>
        <div className="productImageWrap">
          <img src={product.image || ""} alt={product.title} />
          <div className="productBadgeRow">
            {recommended ? <span className="cardBadge recommend">AI 추천</span> : null}
            {topRank ? <span className="cardBadge topRank">TOP {topRank}</span> : null}
            {product.badges.slice(0, 2).map((badge) => (
              <span key={badge} className="cardBadge neutral">
                {badge}
              </span>
            ))}
          </div>
        </div>

        <div className="productCardBody">
          <div className="productSeller">{product.seller}</div>
          <h3>{product.title}</h3>
          <div className="priceLine">{formatPrice(product.lprice)}</div>
          <div className="ratingLine">
            <span>평점 {product.rating.toFixed(1)}</span>
            <span>리뷰 {product.reviewCount.toLocaleString("ko-KR")}</span>
            <span>{product.shippingLabel}</span>
          </div>
          <div className="productSellerMeta">
            <span>{product.mall_name || product.seller}</span>
            {product.brand ? <span>{product.brand}</span> : null}
          </div>
          <div className="aiTagRow">
            {product.aiTags.map((tag) => (
              <span key={tag} className="aiTag">
                {tag}
              </span>
            ))}
          </div>
        </div>
      </button>

      <div className="productCardFooter">
        <div className="productFooterTags clean">
          {product.badges.slice(0, 3).map((badge) => (
            <span key={badge} className="miniTag">
              {badge}
            </span>
          ))}
        </div>
        <div className="feedbackCluster">
          <button
            type="button"
            className="feedbackButton small"
            onClick={(event) => handleFeedbackClick(event, "like", "마음에 드는 상품")}
            disabled={pendingFeedbackKey === `${product.id}:like`}
          >
            {pendingFeedbackKey === `${product.id}:like` ? "저장 중" : "좋아요"}
          </button>
          <button
            type="button"
            className="feedbackButton subtle small"
            onClick={(event) => handleFeedbackClick(event, "dislike", "선호하지 않는 상품")}
            disabled={pendingFeedbackKey === `${product.id}:dislike`}
          >
            {pendingFeedbackKey === `${product.id}:dislike` ? "저장 중" : "별로예요"}
          </button>
          <button
            type="button"
            className="feedbackButton subtle small"
            onClick={(event) => handleFeedbackClick(event, "not_relevant", "관련도가 낮음")}
            disabled={pendingFeedbackKey === `${product.id}:not_relevant`}
          >
            {pendingFeedbackKey === `${product.id}:not_relevant` ? "저장 중" : "관심없음"}
          </button>
          <button
            type="button"
            className="feedbackButton subtle small"
            onClick={(event) => handleFeedbackClick(event, "too_expensive", "가격이 부담됨")}
            disabled={pendingFeedbackKey === `${product.id}:too_expensive`}
          >
            {pendingFeedbackKey === `${product.id}:too_expensive` ? "저장 중" : "비싸요"}
          </button>
        </div>
        <div className="productActionGroup">
          <a href={product.link} target="_blank" rel="noreferrer" className="viewButton" onClick={(event) => event.stopPropagation()}>
            상품 보기
          </a>
        </div>
      </div>
    </article>
  );
}

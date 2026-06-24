"use client";

import { formatPrice } from "../lib/formatters";
import type { FeedbackEventType, UIProduct } from "../types";

type SelectedProductInsightProps = {
  selectedProduct: UIProduct | null;
  recommendationReason: string;
  reasonBullets: string[];
  cautionBullets: string[];
  preferenceMatches: string[];
  feedbackMessage: string;
  pendingFeedbackKey: string | null;
  finalizing: boolean;
  onFeedback: (product: UIProduct, eventType: FeedbackEventType, reason?: string) => void;
  onFinalSelect: (product: UIProduct) => void;
};

export function SelectedProductInsight({
  selectedProduct,
  recommendationReason,
  reasonBullets,
  cautionBullets,
  preferenceMatches,
  feedbackMessage,
  pendingFeedbackKey,
  finalizing,
  onFeedback,
  onFinalSelect,
}: SelectedProductInsightProps) {
  if (!selectedProduct) {
    return <section className="insightCard largeInsightCard"><div className="placeholderBox">상품을 선택하면 이 영역에서 추천 이유를 자세히 볼 수 있습니다.</div></section>;
  }

  const mergedReasonBullets = recommendationReason
    ? [recommendationReason, ...reasonBullets.filter((reason) => reason !== recommendationReason)]
    : reasonBullets;

  return (
    <section className="insightCard largeInsightCard">
      <div className="gridSectionHeader compact">
        <div>
          <p className="sectionEyebrow">{selectedProduct.finalSelected ? "최종 추천 상품" : "추천 이유"}</p>
          <h2>{selectedProduct.finalSelected ? "이 상품을 최종 추천합니다" : "이 상품을 자세히 살펴보세요"}</h2>
        </div>
      </div>

      <div className="selectedInsight expanded">
        <div className="insightHero">
          <img src={selectedProduct.image || ""} alt={selectedProduct.title} />
          <div>
            <strong>{selectedProduct.title}</strong>
            <div className="priceLine">{formatPrice(selectedProduct.lprice)}</div>
            <div className="ratingLine">
              <span>{selectedProduct.seller}</span>
              <span>평점 {selectedProduct.rating.toFixed(1)}</span>
              <span>리뷰 {selectedProduct.reviewCount.toLocaleString("ko-KR")}</span>
            </div>
          </div>
        </div>

        <div className="insightSubSection insightRoundedSection">
          <strong>왜 추천했나요</strong>
          <ul className="reasonBulletList">
            {mergedReasonBullets.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>

        {preferenceMatches.length > 0 ? (
          <div className="insightSubSection insightRoundedSection">
            <strong>사용자 조건과의 연결</strong>
            <ul className="reasonBulletList preference">
              {preferenceMatches.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {cautionBullets.length > 0 ? (
          <div className="insightSubSection">
            <strong>주의할 점</strong>
            <ul className="reasonBulletList caution">
              {cautionBullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="selectedFeedbackRow">
          <button
            type="button"
            className="feedbackButton"
            onClick={() => onFeedback(selectedProduct, "like", "선택 상품 좋아요")}
            disabled={pendingFeedbackKey === `${selectedProduct.id}:like`}
          >
            {pendingFeedbackKey === `${selectedProduct.id}:like` ? "저장 중" : "좋아요"}
          </button>
          <button
            type="button"
            className="feedbackButton subtle"
            onClick={() => onFeedback(selectedProduct, "too_expensive", "선택 상품 가격 부담")}
            disabled={pendingFeedbackKey === `${selectedProduct.id}:too_expensive`}
          >
            {pendingFeedbackKey === `${selectedProduct.id}:too_expensive` ? "저장 중" : "비싸요"}
          </button>
          <button
            type="button"
            className="feedbackButton subtle"
            onClick={() => onFeedback(selectedProduct, "not_relevant", "선택 상품 관심 없음")}
            disabled={pendingFeedbackKey === `${selectedProduct.id}:not_relevant`}
          >
            {pendingFeedbackKey === `${selectedProduct.id}:not_relevant` ? "저장 중" : "관심없음"}
          </button>
        </div>

        <button type="button" className="finalSelectButton" onClick={() => onFinalSelect(selectedProduct)} disabled={finalizing}>
          {finalizing ? "최종 추천 저장 중" : "이 상품으로 최종 선택"}
        </button>

        {feedbackMessage ? <div className="feedbackInlineMessage">{feedbackMessage}</div> : null}
      </div>
    </section>
  );
}

import type { DebugSnapshot } from "../types";

type DebugPanelProps = {
  snapshot: DebugSnapshot;
};

function renderPreferenceEntries(preferences: Record<string, unknown> | null | undefined) {
  if (!preferences) {
    return <div className="debugEmpty">아직 피드백으로 누적된 선호 정보가 없습니다.</div>;
  }

  const entries = Object.entries(preferences).filter(([, value]) => {
    if (Array.isArray(value)) return value.length > 0;
    return value !== null && value !== undefined && value !== "";
  });

  if (entries.length === 0) {
    return <div className="debugEmpty">아직 피드백으로 누적된 선호 정보가 없습니다.</div>;
  }

  return (
    <div className="debugPreferenceList">
      {entries.map(([key, value]) => (
        <div key={key} className="debugPreferenceItem">
          <strong>{key}</strong>
          <span>{Array.isArray(value) ? value.join(" · ") : String(value)}</span>
        </div>
      ))}
    </div>
  );
}

function renderRecommendationPreferences(
  preferences: Array<{ key: string; value: unknown }> | undefined,
) {
  if (!preferences || preferences.length === 0) {
    return <div className="debugEmpty">이번 추천에 직접 반영된 선호 정보가 없습니다.</div>;
  }

  return (
    <div className="debugPreferenceList">
      {preferences.map((item) => (
        <div key={item.key} className="debugPreferenceItem">
          <strong>{item.key}</strong>
          <span>{Array.isArray(item.value) ? item.value.join(" · ") : String(item.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function DebugPanel({ snapshot }: DebugPanelProps) {
  return (
    <section className="insightCard insightScrollable">
      <div className="gridSectionHeader compact">
        <div>
          <p className="sectionEyebrow">debug</p>
          <h2>추천 판단 정보</h2>
        </div>
      </div>

      <div className="debugSection">
        <strong>현재 검색</strong>
        <div className="debugValue">{snapshot.query || "기본 추천 상품 보기"}</div>
      </div>

      <div className="debugSection">
        <strong>검색 해석</strong>
        <div className="criteriaList">
          {snapshot.interpretation.map((item) => (
            <span key={item} className="criteriaTag">
              {item}
            </span>
          ))}
        </div>
      </div>

      <div className="debugSection">
        <strong>적용 중 필터</strong>
        <div className="debugPreferenceList">
          <div className="debugPreferenceItem">
            <strong>카테고리</strong>
            <span>{snapshot.activeCategory}</span>
          </div>
          <div className="debugPreferenceItem">
            <strong>배송</strong>
            <span>{snapshot.activeShippingFilters.length > 0 ? snapshot.activeShippingFilters.join(" · ") : "전체"}</span>
          </div>
          <div className="debugPreferenceItem">
            <strong>가격대</strong>
            <span>{snapshot.activePriceRange}</span>
          </div>
          <div className="debugPreferenceItem">
            <strong>정렬</strong>
            <span>{snapshot.activeSort}</span>
          </div>
        </div>
      </div>

      <div className="debugSection">
        <strong>탐색 키워드</strong>
        <div className="debugValue">{snapshot.searchTerms.length > 0 ? snapshot.searchTerms.join(" · ") : "없음"}</div>
      </div>

      <div className="debugSection">
        <strong>선택 상품</strong>
        <div className="debugValue">{snapshot.selectedProductTitle || "선택된 상품 없음"}</div>
      </div>

      <div className="debugSection">
        <strong>최근 피드백 결과</strong>
        <div className="debugValue">{snapshot.feedbackMessage || "아직 없음"}</div>
      </div>

      <div className="debugSection">
        <strong>누적 사용자 선호</strong>
        {renderPreferenceEntries(snapshot.feedbackPreferences)}
      </div>

      <div className="debugSection">
        <strong>이번 추천에 반영된 선호</strong>
        {renderRecommendationPreferences(snapshot.recommendationPreferences)}
      </div>

      <div className="debugSection">
        <strong>추천 API debug</strong>
        <div className="debugValue">
          {snapshot.recommendationDebug ? JSON.stringify(snapshot.recommendationDebug, null, 2) : "없음"}
        </div>
      </div>
    </section>
  );
}

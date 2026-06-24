type AIRecommendationSummaryProps = {
  title: string;
  summary: string;
  searchTerms: string[];
  fallbackReason?: string;
  recommendationCount: number;
};

function summarizeLines(text: string) {
  return text
    .split("\n")
    .map((line) => line.trim().replace(/^[-#*\d.\s]+/, ""))
    .filter(Boolean)
    .slice(0, 3);
}

export function AIRecommendationSummary({
  title,
  summary,
  searchTerms,
  fallbackReason,
  recommendationCount,
}: AIRecommendationSummaryProps) {
  const lines = summarizeLines(summary);

  return (
    <section className="summaryPanel">
      <div>
        <p className="sectionEyebrow">AI 추천 요약</p>
        <h2>{title}</h2>
      </div>

      <div className="summaryPoints">
        {lines.length > 0 ? (
          lines.map((line) => (
            <div className="summaryPoint" key={line}>
              {line}
            </div>
          ))
        ) : (
          <div className="summaryPoint">소음, 가격, 사용 공간을 기준으로 실속형 상품을 먼저 정리했어요.</div>
        )}
      </div>

      <div className="summaryMetaRow">
        <span>추천 후보 {recommendationCount}개</span>
        {searchTerms.length > 0 ? <span>탐색 키워드: {searchTerms.join(" · ")}</span> : null}
        {fallbackReason ? <span>{fallbackReason}</span> : null}
      </div>
    </section>
  );
}

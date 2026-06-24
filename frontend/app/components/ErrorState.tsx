type ErrorStateProps = {
  message: string;
};

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <section className="feedbackState error">
      <div className="gridSectionHeader compact">
        <div>
          <p className="sectionEyebrow">검색 오류</p>
          <h2>검색 조건을 조금 넓혀 다시 시도해 주세요</h2>
        </div>
      </div>
      <p>{message}</p>
    </section>
  );
}

type EmptyStateProps = {
  title: string;
  description: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <section className="feedbackState">
      <div className="gridSectionHeader compact">
        <div>
          <p className="sectionEyebrow">검색 결과 없음</p>
          <h2>{title}</h2>
        </div>
      </div>
      <p>{description}</p>
    </section>
  );
}

type SearchLoadingStateProps = {
  currentStep: string;
};

export function SearchLoadingState({ currentStep }: SearchLoadingStateProps) {
  return (
    <section className="loadingStateCard">
      <div className="serviceLoader">
        <div className="serviceLoaderOrb" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="serviceLoaderText">
          <p className="sectionEyebrow">검색 중</p>
          <h2>조건을 추출해 최적의 상품을 찾고 있습니다</h2>
          <span>{currentStep}</span>
        </div>
      </div>
    </section>
  );
}

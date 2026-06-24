type SearchConditionBarProps = {
  labels: string[];
  query: string;
};

export function SearchConditionBar({ labels, query }: SearchConditionBarProps) {
  return (
    <section className="conditionBar">
      <div className="conditionBarBody">
        <div className="conditionBarLabel">현재 적용된 조건</div>
        <p className="conditionQueryText">{query}</p>
        <div className="conditionChipRow">
          {labels.map((label) => (
            <span key={label} className="conditionChip">
              {label}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

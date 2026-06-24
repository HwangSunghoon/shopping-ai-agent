"use client";

import type { AgentFilters } from "../types";

type FilterSidebarProps = {
  options: {
    categories: string[];
    brands: string[];
    malls: string[];
    priceRanges: string[];
    shipping: string[];
    review: string[];
    userPreferences: string[];
    productState: string[];
  };
  selectedFilters: AgentFilters;
  resultCount: number;
  onToggle: (group: keyof AgentFilters, value: string) => void;
  onReset: () => void;
};

function FilterGroup({
  title,
  values,
  selected,
  onToggle,
}: {
  title: string;
  values: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  if (values.length === 0) return null;
  return (
    <section className="filterCard integrated">
      <div className="filterSectionTitle">{title}</div>
      <div className="filterTagGrid">
        {values.map((value) => (
          <button key={value} type="button" className={`filterTag ${selected.includes(value) ? "active" : ""}`} onClick={() => onToggle(value)}>
            {value}
          </button>
        ))}
      </div>
    </section>
  );
}

export function FilterSidebar({ options, selectedFilters, resultCount, onToggle, onReset }: FilterSidebarProps) {
  return (
    <aside className="filterSidebar">
      <div className="filterPanelHeader">
        <div>
          <p className="sectionEyebrow">필터</p>
          <strong>{resultCount}개 상품</strong>
        </div>
        <button type="button" className="textButton" onClick={onReset}>
          초기화
        </button>
      </div>

      <FilterGroup title="카테고리" values={options.categories} selected={selectedFilters.categories} onToggle={(value) => onToggle("categories", value)} />
      <FilterGroup title="가격대" values={options.priceRanges} selected={selectedFilters.price_ranges} onToggle={(value) => onToggle("price_ranges", value)} />
      <FilterGroup title="배송" values={options.shipping} selected={selectedFilters.shipping} onToggle={(value) => onToggle("shipping", value)} />
      <FilterGroup title="리뷰" values={options.review} selected={selectedFilters.review} onToggle={(value) => onToggle("review", value)} />
      <FilterGroup title="브랜드" values={options.brands} selected={selectedFilters.brands} onToggle={(value) => onToggle("brands", value)} />
      <FilterGroup title="쇼핑몰" values={options.malls} selected={selectedFilters.malls} onToggle={(value) => onToggle("malls", value)} />
      <FilterGroup title="상품 상태" values={options.productState} selected={selectedFilters.product_state} onToggle={(value) => onToggle("product_state", value)} />
      <FilterGroup title="사용자 선호" values={options.userPreferences} selected={selectedFilters.user_preferences} onToggle={(value) => onToggle("user_preferences", value)} />
    </aside>
  );
}

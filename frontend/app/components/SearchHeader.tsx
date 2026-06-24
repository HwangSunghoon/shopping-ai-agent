"use client";

import { ConversationTrail } from "./ConversationTrail";

type SearchHeaderProps = {
  query: string;
  loading: boolean;
  mode: "home" | "search";
  promptSuggestions?: string[];
  conversationItems?: Array<{ question: string; answer: string }>;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  onHome: () => void;
  quickQueries: string[];
  onQuickQuery: (query: string) => void;
};

export function SearchHeader({
  query,
  loading,
  mode,
  promptSuggestions = [],
  conversationItems = [],
  onQueryChange,
  onSearch,
  onHome,
  quickQueries,
  onQuickQuery,
}: SearchHeaderProps) {
  return (
    <header className="storeHeader">
      <div className="storeHeaderTop">
        <button type="button" className="storeBrand" onClick={onHome}>
          <div className="storeLogo" aria-hidden="true">
            <span className="storeLogoDot" />
          </div>
          <div>
            <strong>Shopping AI Agent</strong>
          </div>
        </button>

        <nav className="storeMenu" aria-label="쇼핑 메뉴">
          <a href="#home-best">BEST 상품</a>
          <a href="#home-personal">고객님을 위한 상품</a>
          <a href="#home-today">오늘의 추천 상품</a>
        </nav>
      </div>

      <div className="storeSearchRow">
        <div className={`storeSearchStack ${mode === "search" ? "searchConversationPanel" : ""}`}>
          {mode === "search" && conversationItems.length > 0 ? <ConversationTrail items={conversationItems} compact /> : null}
          <div className="storeSearch">
            <input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder={
                mode === "home"
                  ? "예: 10만원대 원룸용 무선청소기 추천해줘"
                  : "예: 방금 결과에서 리뷰 많은 상품만 남겨줘"
              }
            />
            <button type="button" onClick={onSearch} disabled={loading}>
              {loading ? "불러오는 중" : mode === "home" ? "검색" : "조건 반영"}
            </button>
          </div>
        </div>
      </div>

      <div className={`quickQueryRow ${mode === "home" ? "homeQuickKeywords" : "searchPromptSuggestions"}`}>
        {(mode === "home" ? quickQueries : promptSuggestions).map((item) => (
          <button key={item} type="button" className="quickQueryChip" onClick={() => onQuickQuery(item)}>
            {item}
          </button>
        ))}
      </div>
    </header>
  );
}

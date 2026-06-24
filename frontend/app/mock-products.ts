import type { UIProduct } from "./types";

function productLink(title: string) {
  return `https://search.shopping.naver.com/search/all?query=${encodeURIComponent(title)}`;
}

function createThumbnail(label: string, accent: string, shape: "humidifier" | "dehumidifier" | "purifier" | "fan" | "appliance") {
  const shapeMarkup =
    shape === "humidifier"
      ? '<rect x="92" y="92" width="116" height="110" rx="24" fill="#ffffff"/><rect x="118" y="118" width="64" height="12" rx="6" fill="#d1fae5"/><circle cx="150" cy="98" r="18" fill="#dcfce7"/><path d="M122 82c8-14 18-21 28-26 6 12 5 26-2 36-9 1-19-1-26-10Z" fill="#86efac"/>'
      : shape === "dehumidifier"
        ? '<rect x="92" y="66" width="116" height="142" rx="24" fill="#ffffff"/><rect x="116" y="90" width="68" height="10" rx="5" fill="#d1fae5"/><rect x="118" y="114" width="64" height="66" rx="12" fill="#ecfdf5"/><path d="M150 124c16 19 21 31 21 43 0 12-9 22-21 22s-21-10-21-22c0-12 5-24 21-43Z" fill="#86efac"/>'
        : shape === "purifier"
          ? '<rect x="94" y="60" width="112" height="148" rx="26" fill="#ffffff"/><rect x="114" y="86" width="72" height="12" rx="6" fill="#d1fae5"/><rect x="116" y="110" width="68" height="74" rx="12" fill="#f0fdf4"/><path d="M116 132h68M116 148h68M116 164h68" stroke="#86efac" stroke-width="8" stroke-linecap="round"/>'
          : shape === "fan"
            ? '<circle cx="150" cy="118" r="50" fill="#ffffff"/><circle cx="150" cy="118" r="14" fill="#bbf7d0"/><path d="M150 68c20 0 30 22 18 38-12 14-33 7-38-9-5-16 4-29 20-29ZM193 143c10 18-6 38-25 34-18-4-24-26-12-38 11-12 27-11 37 4ZM112 145c13-14 37-8 39 11 2 18-18 31-35 24-15-7-17-23-4-35Z" fill="#86efac"/><rect x="143" y="164" width="14" height="44" rx="7" fill="#ffffff"/>'
            : '<rect x="92" y="82" width="116" height="124" rx="24" fill="#ffffff"/><rect x="110" y="110" width="80" height="16" rx="8" fill="#dcfce7"/><rect x="118" y="140" width="64" height="42" rx="12" fill="#f0fdf4"/><circle cx="150" cy="160" r="14" fill="#86efac"/>';

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="100%" stop-color="${accent}22"/>
        </linearGradient>
      </defs>
      <rect width="300" height="300" rx="28" fill="url(#g)"/>
      <rect x="24" y="24" width="252" height="252" rx="26" fill="#f8fafc" stroke="${accent}33"/>
      ${shapeMarkup}
      <text x="150" y="252" text-anchor="middle" font-size="18" font-family="Apple SD Gothic Neo, Noto Sans KR, sans-serif" fill="#334155">${label}</text>
    </svg>
  `;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export const mockProducts: UIProduct[] = [
  {
    id: "humidifier-1",
    title: "에코미스트 저소음 대용량 가습기 4L",
    link: productLink("에코미스트 저소음 대용량 가습기 4L"),
    image: createThumbnail("가습기", "#22c55e", "humidifier"),
    mall_name: "리빙하우스",
    category: "생활가전 > 가습기",
    lprice: 109000,
    score: 93,
    reason: "10만원대 예산과 저소음 사용 목적에 잘 맞는 대용량 모델입니다.",
    caution: "취침용이면 실제 물보충 주기와 세척 편의성을 함께 확인하세요.",
    rank: 1,
    seller: "리빙하우스",
    rating: 4.8,
    reviewCount: 1284,
    shippingLabel: "무료배송",
    badges: ["인기", "저소음", "대용량"],
    aiTags: ["예산 적합", "리뷰 많음", "자취방 적합", "배송 확인"],
    highlight: "원룸과 침실용으로 많이 찾는 구성",
  },
  {
    id: "humidifier-2",
    title: "클린에어 UV 살균 초음파 가습기",
    link: productLink("클린에어 UV 살균 초음파 가습기"),
    image: createThumbnail("가습기", "#16a34a", "humidifier"),
    mall_name: "클린리빙",
    category: "생활가전 > 가습기",
    lprice: 89000,
    score: 89,
    reason: "예산을 낮추면서 살균 기능을 원하는 경우 균형이 좋습니다.",
    caution: "분무량이 강한 편이라 좁은 방에서는 단계 조절이 필요할 수 있습니다.",
    seller: "클린리빙",
    rating: 4.6,
    reviewCount: 842,
    shippingLabel: "오늘출발",
    badges: ["가성비", "살균", "베스트"],
    aiTags: ["가성비", "예산 적합", "배송 확인"],
    highlight: "10만원 이하로 맞추기 쉬운 가성비형",
  },
  {
    id: "dehumidifier-1",
    title: "신일 슬림 13L 제습기 원룸 드레스룸용",
    link: productLink("신일 슬림 13L 제습기 원룸 드레스룸용"),
    image: createThumbnail("제습기", "#16a34a", "dehumidifier"),
    mall_name: "신일공식",
    category: "생활가전 > 제습기",
    lprice: 199000,
    score: 95,
    reason: "자취방과 드레스룸 용도에서 용량과 가격 균형이 우수합니다.",
    caution: "이동 소음과 물통 크기는 사용 공간 기준으로 다시 확인하는 편이 좋습니다.",
    rank: 1,
    seller: "신일공식",
    rating: 4.7,
    reviewCount: 2156,
    shippingLabel: "무료배송",
    badges: ["인기", "원룸추천", "조용한편"],
    aiTags: ["예산 적합", "자취방 적합", "리뷰 많음", "배송 확인"],
    highlight: "20만원 이하 자취방용 대표 후보",
  },
  {
    id: "dehumidifier-2",
    title: "듀플렉스 D11 11L 제습기 화이트",
    link: productLink("듀플렉스 D11 11L 제습기 화이트"),
    image: createThumbnail("제습기", "#22c55e", "dehumidifier"),
    mall_name: "듀플렉스",
    category: "생활가전 > 제습기",
    lprice: 169000,
    score: 91,
    reason: "예산 여유를 남기면서 기본 제습 성능을 확보하기 좋은 모델입니다.",
    caution: "넓은 공간보다는 원룸과 작은 방 중심 사용에 적합합니다.",
    seller: "듀플렉스",
    rating: 4.5,
    reviewCount: 964,
    shippingLabel: "오늘출발",
    badges: ["가성비", "원룸추천", "실속형"],
    aiTags: ["가성비", "예산 적합", "자취방 적합", "배송 확인"],
    highlight: "가격 우선 비교에 유리한 구성",
  },
  {
    id: "purifier-1",
    title: "브리즈360 공기청정기 20평형",
    link: productLink("브리즈360 공기청정기 20평형"),
    image: createThumbnail("공기청정기", "#16a34a", "purifier"),
    mall_name: "브리즈홈",
    category: "생활가전 > 공기청정기",
    lprice: 187000,
    score: 88,
    reason: "거실과 원룸 모두 무난하게 커버하는 중형 공기청정기입니다.",
    caution: "필터 교체 주기와 유지비는 별도로 비교하는 것이 좋습니다.",
    seller: "브리즈홈",
    rating: 4.6,
    reviewCount: 1503,
    shippingLabel: "무료배송",
    badges: ["인기", "중형", "필터관리"],
    aiTags: ["리뷰 많음", "배송 확인"],
    highlight: "미세먼지 시즌에 수요가 높은 상품",
  },
  {
    id: "purifier-2",
    title: "라이트에어 슬림 공기청정기 원룸형",
    link: productLink("라이트에어 슬림 공기청정기 원룸형"),
    image: createThumbnail("공기청정기", "#22c55e", "purifier"),
    mall_name: "라이트에어",
    category: "생활가전 > 공기청정기",
    lprice: 119000,
    score: 84,
    reason: "작은 공간용으로 크기 부담이 적고 가격대가 가볍습니다.",
    caution: "거실급 면적에는 부족할 수 있습니다.",
    seller: "라이트에어",
    rating: 4.4,
    reviewCount: 512,
    shippingLabel: "무료배송",
    badges: ["원룸추천", "슬림형", "실속형"],
    aiTags: ["예산 적합", "자취방 적합", "배송 확인"],
  },
  {
    id: "fan-1",
    title: "쿨윈드 BLDC 저소음 선풍기",
    link: productLink("쿨윈드 BLDC 저소음 선풍기"),
    image: createThumbnail("선풍기", "#16a34a", "fan"),
    mall_name: "쿨윈드",
    category: "생활가전 > 선풍기",
    lprice: 129000,
    score: 87,
    reason: "취침용과 자취방 사용에 맞는 저소음 BLDC 타입입니다.",
    caution: "높이 조절 범위와 리모컨 포함 여부를 확인하세요.",
    seller: "쿨윈드",
    rating: 4.7,
    reviewCount: 1310,
    shippingLabel: "오늘출발",
    badges: ["저소음", "BLDC", "인기"],
    aiTags: ["저소음", "리뷰 많음", "배송 확인"],
    highlight: "여름 시즌 검색량이 높은 대표 상품",
  },
  {
    id: "fan-2",
    title: "모던에어 무선 서큘레이터 선풍기",
    link: productLink("모던에어 무선 서큘레이터 선풍기"),
    image: createThumbnail("선풍기", "#22c55e", "fan"),
    mall_name: "모던에어",
    category: "생활가전 > 선풍기",
    lprice: 99000,
    score: 82,
    reason: "무선 사용과 이동성을 중요하게 볼 때 장점이 있습니다.",
    caution: "장시간 강풍 사용 시 배터리 지속시간을 체크하세요.",
    seller: "모던에어",
    rating: 4.3,
    reviewCount: 438,
    shippingLabel: "무료배송",
    badges: ["무선", "서큘레이터", "가성비"],
    aiTags: ["가성비", "예산 적합", "배송 확인"],
  },
  {
    id: "appliance-1",
    title: "미니홈 원룸 생활가전 패키지",
    link: productLink("미니홈 원룸 생활가전 패키지"),
    image: createThumbnail("자취가전", "#16a34a", "appliance"),
    mall_name: "미니홈",
    category: "자취용품 > 생활가전",
    lprice: 149000,
    score: 80,
    reason: "자취 시작용으로 필요한 소형 가전을 묶어서 비교하기 좋습니다.",
    caution: "개별 구매 대비 실제 혜택을 확인해 보세요.",
    seller: "미니홈",
    rating: 4.2,
    reviewCount: 289,
    shippingLabel: "무료배송",
    badges: ["자취추천", "패키지", "입문용"],
    aiTags: ["자취방 적합", "배송 확인"],
  },
  {
    id: "appliance-2",
    title: "데일리케어 스마트 생활가전 세트",
    link: productLink("데일리케어 스마트 생활가전 세트"),
    image: createThumbnail("생활가전", "#22c55e", "appliance"),
    mall_name: "데일리케어",
    category: "자취용품 > 생활가전",
    lprice: 219000,
    score: 78,
    reason: "생활가전 구성 품목이 넓어 처음 장만할 때 보기 좋습니다.",
    caution: "단품보다 예산이 높아 필요 품목 위주로 비교하는 편이 좋습니다.",
    seller: "데일리케어",
    rating: 4.1,
    reviewCount: 198,
    shippingLabel: "오늘출발",
    badges: ["자취추천", "오늘출발", "구성형"],
    aiTags: ["자취방 적합", "배송 확인"],
  },
];

export const defaultQueries = [
  "10만원대 가습기 추천해줘",
  "20만원 이하 자취방용 조용한 제습기 추천해줘",
  "원룸 공기청정기 추천",
  "여름용 저소음 선풍기 추천",
];

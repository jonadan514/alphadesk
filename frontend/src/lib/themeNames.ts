// 자동 생성 - 직접 수정하지 말 것. scripts/gen_theme_names.py 로 config/themes.yaml에서 만든다.
// 보관(archived) 테마도 포함한다 - 과거 주차 데이터를 볼 때 이름이 필요하다.
export const THEME_NAMES: Record<string, { ko: string; en: string }> = {
  ai_semiconductor: { ko: "AI 반도체", en: "AI Semiconductors" },
  datacenter_power: { ko: "데이터센터 전력", en: "Datacenter Power" },
  datacenter_cooling: { ko: "데이터센터 냉각", en: "Datacenter Cooling" },
  ai_software: { ko: "AI 소프트웨어·에이전트", en: "AI Software & Agents" },
  semi_equipment: { ko: "반도체 장비·소재", en: "Semiconductor Equipment & Materials" },
  power_grid: { ko: "전력망·송배전", en: "Power Grid & Transmission" },
  nuclear_smr: { ko: "원전·SMR", en: "Nuclear & SMR" },
  renewable_energy: { ko: "재생에너지", en: "Renewable Energy" },
  energy_storage: { ko: "에너지저장(ESS)", en: "Energy Storage" },
  lng_gas: { ko: "천연가스·LNG", en: "Natural Gas & LNG" },
  cable_wire: { ko: "전선·케이블", en: "Cable & Wire" },
  shipbuilding: { ko: "조선", en: "Shipbuilding" },
  defense: { ko: "방산", en: "Defense" },
  aerospace_space: { ko: "항공우주·위성", en: "Aerospace & Space" },
  construction_machinery: { ko: "건설기계", en: "Construction Machinery" },
  infra_construction: { ko: "인프라 건설", en: "Infrastructure & Construction" },
  factory_automation: { ko: "산업자동화", en: "Factory Automation" },
  glp1_obesity: { ko: "비만치료제", en: "GLP-1 / Obesity Drugs" },
  biosimilar: { ko: "바이오시밀러", en: "Biosimilars" },
  cdmo: { ko: "CDMO·위탁생산", en: "CDMO / Contract Manufacturing" },
  medical_device: { ko: "의료기기", en: "Medical Devices" },
  neuro_alzheimer: { ko: "치매·신경질환", en: "Neuro & Alzheimer's" },
  k_beauty: { ko: "K-뷰티", en: "K-Beauty" },
  k_food: { ko: "K-푸드", en: "K-Food" },
  k_content: { ko: "K-콘텐츠·엔터", en: "K-Content & Entertainment" },
  game: { ko: "게임", en: "Games" },
  travel_airline: { ko: "여행·항공", en: "Travel & Airlines" },
  battery: { ko: "2차전지", en: "Batteries" },
  ev_value_chain: { ko: "전기차 밸류체인", en: "EV Value Chain" },
  autonomous_driving: { ko: "자율주행", en: "Autonomous Driving" },
  physical_ai: { ko: "피지컬 AI", en: "Physical AI" },
  humanoid_robot: { ko: "휴머노이드 로봇", en: "Humanoid Robots" },
  rare_earth: { ko: "희토류·핵심광물", en: "Rare Earths & Critical Minerals" },
  copper_metals: { ko: "구리·산업금속", en: "Copper & Industrial Metals" },
  specialty_gas: { ko: "특수가스·소재", en: "Specialty Gases & Materials" },
  petrochemical: { ko: "석유화학 업황", en: "Petrochemicals" },
};

export function themeName(themeId: string): { ko: string; en: string } {
  return THEME_NAMES[themeId] ?? { ko: themeId, en: "" };
}

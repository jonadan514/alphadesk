// config/themes.yaml의 name_ko/name_en을 그대로 옮김 (Phase A = 미국 시장 테마만).
// themes.yaml에 테마가 추가/변경되면 여기도 같이 갱신해야 한다.
export const THEME_NAMES: Record<string, { ko: string; en: string }> = {
  ai_semiconductor: { ko: "AI 반도체", en: "AI Semiconductors" },
  datacenter_power: { ko: "데이터센터 전력", en: "Datacenter Power" },
  datacenter_cooling: { ko: "데이터센터 냉각", en: "Datacenter Cooling" },
  ai_software: { ko: "AI 소프트웨어·에이전트", en: "AI Software & Agents" },
  semi_equipment: { ko: "반도체 장비·소재", en: "Semiconductor Equipment & Materials" },
  power_grid: { ko: "전력망·송배전", en: "Power Grid & Transmission" },
  shipbuilding: { ko: "조선", en: "Shipbuilding" },
  nuclear_smr: { ko: "원전·SMR", en: "Nuclear & SMR" },
  renewable_energy: { ko: "재생에너지", en: "Renewable Energy" },
  energy_storage: { ko: "에너지저장(ESS)", en: "Energy Storage" },
  lng_gas: { ko: "천연가스·LNG", en: "Natural Gas & LNG" },
  cable_wire: { ko: "전선·케이블", en: "Cable & Wire" },
  defense: { ko: "방산", en: "Defense" },
  aerospace_space: { ko: "항공우주·위성", en: "Aerospace & Space" },
  construction_machinery: { ko: "건설기계·인프라", en: "Construction Machinery & Infrastructure" },
  factory_automation: { ko: "산업자동화", en: "Factory Automation" },
  glp1_obesity: { ko: "비만치료제", en: "GLP-1 / Obesity Drugs" },
  biosimilar: { ko: "바이오시밀러", en: "Biosimilars" },
  cdmo: { ko: "CDMO·위탁생산", en: "CDMO / Contract Manufacturing" },
  medical_device: { ko: "의료기기", en: "Medical Devices" },
  neuro_alzheimer: { ko: "치매·신경질환", en: "Neuro & Alzheimer's" },
  travel_airline: { ko: "여행·항공", en: "Travel & Airlines" },
  battery: { ko: "2차전지", en: "Batteries" },
  ev_value_chain: { ko: "전기차 밸류체인", en: "EV Value Chain" },
  autonomous_driving: { ko: "자율주행", en: "Autonomous Driving" },
  physical_ai: { ko: "피지컬 AI", en: "Physical AI" },
  rare_earth: { ko: "희토류·핵심광물", en: "Rare Earths & Critical Minerals" },
  copper_metals: { ko: "구리·산업금속", en: "Copper & Industrial Metals" },
  specialty_gas: { ko: "특수가스·소재", en: "Specialty Gases & Materials" },
  petrochemical: { ko: "석유화학 업황", en: "Petrochemicals" },
};

export function themeName(themeId: string): { ko: string; en: string } {
  return THEME_NAMES[themeId] ?? { ko: themeId, en: "" };
}

// 체제별 손절 기준 — /risk 탭(KR 뷰)의 "지금 적용할 기준" 표와 동일한 값.
// 한 곳에서 관리해 포트폴리오 손절 모니터와 리스크 탭이 항상 같은 숫자를 쓰도록 한다.
export const STOP_LOSS_PCT: Record<string, number> = {
  risk_on: 10,
  neutral: 8,
  risk_off: 5,
  crisis: 3,
};

export function stopLossPct(regime: string | null | undefined): number {
  return STOP_LOSS_PCT[regime ?? "neutral"] ?? STOP_LOSS_PCT.neutral;
}

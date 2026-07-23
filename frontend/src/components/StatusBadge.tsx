// 범용 상태 배지 — 체크리스트·지표 판정 등에서 재사용 (2026-07 UI 개선)
// SignalBadge(GO/CAUTION/STOP 전용)를 일반화한 버전.
// 핵심: "미입력(PENDING)"과 "실제 미충족(FAIL)"을 색으로 구분한다.

export type StatusKind = "PASS" | "WARN" | "FAIL" | "PENDING" | "INFO";

const STATUS_STYLE: Record<StatusKind, { color: string; defaultLabel: string }> = {
  PASS:    { color: "#4ade80", defaultLabel: "통과" },   // --good
  WARN:    { color: "#facc15", defaultLabel: "확인" },   // --warn
  FAIL:    { color: "#f87171", defaultLabel: "미충족" }, // --danger
  PENDING: { color: "#8b8271", defaultLabel: "대기" },   // --text-muted (미입력/미선택 — 실패 아님)
  INFO:    { color: "#6fb3b8", defaultLabel: "참고" },   // --info (판정 미포함 참고 항목)
};

interface StatusBadgeProps {
  status: StatusKind;
  label?: string;          // 없으면 상태별 기본 라벨
  size?: "sm" | "md";
}

export default function StatusBadge({ status, label, size = "sm" }: StatusBadgeProps) {
  const { color, defaultLabel } = STATUS_STYLE[status];
  const px = size === "md" ? "px-3 py-1 text-[13px]" : "px-2 py-0.5 text-[12px]";
  return (
    <span
      className={`inline-block font-bold ${px}`}
      style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}
    >
      {label ?? defaultLabel}
    </span>
  );
}

// 편의 헬퍼: 자동 판정 항목의 boolean pass + 입력 대기 여부를 상태로 변환
export function toStatus(opts: {
  pass: boolean;
  pending?: boolean;   // 아직 입력·선택 전이면 true
  info?: boolean;      // 판정에 미포함되는 참고 항목이면 true
  warnOnFail?: boolean; // 미충족 시 FAIL 대신 WARN으로 표시
}): StatusKind {
  if (opts.info) return "INFO";
  if (opts.pending) return "PENDING";
  if (opts.pass) return "PASS";
  return opts.warnOnFail ? "WARN" : "FAIL";
}

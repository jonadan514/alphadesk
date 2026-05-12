interface SignalBadgeProps {
  signal: string;          // "GO" | "CAUTION" | "STOP" | any string
  color?: string;          // override — hex like "#39ff8f"
  size?: "sm" | "md";
}

const SIGNAL_CLASS: Record<string, string> = {
  GO:      "badge-go",
  CAUTION: "badge-caution",
  STOP:    "badge-stop",
};

export default function SignalBadge({ signal, color, size = "sm" }: SignalBadgeProps) {
  const cls = SIGNAL_CLASS[signal];
  const px  = size === "md" ? "px-3 py-1 text-[13px]" : "px-2 py-0.5 text-[12px]";

  if (cls && !color) {
    return (
      <span className={`inline-block rounded-lg font-bold ${px} ${cls}`}>
        {signal}
      </span>
    );
  }

  // Custom color — keep the "22 / 44" alpha tint convention
  const bg     = `${color}1a`;
  const border = `1px solid ${color}33`;
  return (
    <span
      className={`inline-block rounded-lg font-bold ${px}`}
      style={{ background: bg, color: color ?? "var(--text-primary)", border }}
    >
      {signal}
    </span>
  );
}

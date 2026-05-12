import US from "country-flag-icons/react/3x2/US";
import KR from "country-flag-icons/react/3x2/KR";

type Market = "US" | "KR";

export default function FlagIcon({ market, size = 16 }: { market: Market; size?: number }) {
  const Flag = market === "US" ? US : KR;
  return <Flag style={{ width: size, height: "auto", borderRadius: 2, display: "inline-block", verticalAlign: "middle" }} />;
}

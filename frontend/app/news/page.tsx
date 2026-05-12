"use client";

import { useEffect, useState, useCallback } from "react";
import { useMarket } from "@/src/contexts/MarketContext";
import { Newspaper, RefreshCw, ExternalLink, Clock } from "lucide-react";

interface NewsItem {
  id: number;
  title: string;
  title_ko: string | null;
  url: string;
  source: string;
  market: string;
  sector: string;
  published_at: string | null;
  fetched_at: string;
}

interface SectorCount {
  sector: string;
  cnt: number;
}

const SECTOR_COLORS: Record<string, string> = {
  "AI·반도체":   "#a78bfa",
  "빅테크":      "#60a5fa",
  "거시경제":    "#34d399",
  "에너지":      "#fbbf24",
  "금융":        "#f87171",
  "헬스케어":    "#fb7185",
  "무역·지정학": "#f97316",
  "일반":        "#6b7280",
};

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const h = Math.floor(diff / 3_600_000);
  if (h < 1) return "방금";
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  return `${d}일 전`;
}

export default function NewsPage() {
  const { market } = useMarket();
  const [items, setItems]     = useState<NewsItem[]>([]);
  const [sectors, setSectors] = useState<SectorCount[]>([]);
  const [selSector, setSelSector] = useState<string>("전체");
  const [days, setDays]       = useState(7);
  const [loading, setLoading] = useState(false);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);

  const load = useCallback(async (d: number, sec: string) => {
    setLoading(true);
    try {
      const sectorParam = sec !== "전체" ? `&sector=${encodeURIComponent(sec)}` : "";
      const res = await fetch(`/api/data/news?market=${market}&days=${d}${sectorParam}&limit=80`);
      if (!res.ok) return;
      const data = await res.json();
      setItems(data.items ?? []);
      setSectors([{ sector: "전체", cnt: (data.sectors ?? []).reduce((s: number, r: SectorCount) => s + r.cnt, 0) }, ...(data.sectors ?? [])]);
      setLastFetch(new Date());
    } finally {
      setLoading(false);
    }
  }, [market]);

  useEffect(() => {
    setSelSector("전체");
    load(days, "전체");
  }, [market, days, load]);

  const handleSector = (s: string) => {
    setSelSector(s);
    load(days, s);
  };

  return (
    <div className="flex flex-col h-full" style={{ background: "#0e0e0e", color: "#e5e7eb" }}>
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: "#1f2937" }}>
        <div className="flex items-center gap-2">
          <Newspaper size={18} style={{ color: "#39ff8f" }} />
          <h1 className="text-base font-bold">주간 뉴스 다이제스트</h1>
          <span className="text-xs px-2 py-0.5 rounded-full ml-1" style={{ background: "#1a2e1a", color: "#39ff8f", border: "1px solid #39ff8f44" }}>
            {market}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Days selector */}
          <div className="flex gap-1">
            {[3, 7, 14].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className="text-xs px-2 py-1 rounded transition-colors"
                style={{
                  background: days === d ? "#39ff8f22" : "#1a1a1a",
                  color: days === d ? "#39ff8f" : "#6b7280",
                  border: `1px solid ${days === d ? "#39ff8f55" : "#2a2a2a"}`,
                }}
              >
                {d}일
              </button>
            ))}
          </div>

          {lastFetch && (
            <span className="text-xs" style={{ color: "#4b5563" }}>
              {lastFetch.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} 기준
            </span>
          )}

          <button
            onClick={() => load(days, selSector)}
            disabled={loading}
            className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg transition-colors"
            style={{ background: "#1a1a1a", border: "1px solid #2a2a2a", color: "#9ca3af" }}
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            새로고침
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Sector sidebar */}
        <div className="shrink-0 w-40 border-r overflow-y-auto py-3 px-2 flex flex-col gap-1" style={{ borderColor: "#1f2937" }}>
          {sectors.map(({ sector, cnt }) => {
            const color = SECTOR_COLORS[sector] ?? "#6b7280";
            const active = selSector === sector;
            return (
              <button
                key={sector}
                onClick={() => handleSector(sector)}
                className="flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left text-xs transition-colors"
                style={{
                  background: active ? `${color}18` : "transparent",
                  border: `1px solid ${active ? color + "55" : "transparent"}`,
                  color: active ? color : "#6b7280",
                }}
              >
                <span className="truncate">{sector}</span>
                <span
                  className="shrink-0 ml-1 text-[10px] px-1.5 rounded-full"
                  style={{ background: active ? color + "22" : "#1a1a1a", color: active ? color : "#4b5563" }}
                >
                  {cnt}
                </span>
              </button>
            );
          })}
        </div>

        {/* Article list */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex items-center justify-center h-40 text-sm" style={{ color: "#4b5563" }}>
              불러오는 중...
            </div>
          )}

          {!loading && items.length === 0 && (
            <div className="flex flex-col items-center justify-center h-40 gap-2" style={{ color: "#4b5563" }}>
              <Newspaper size={32} />
              <p className="text-sm">뉴스가 없습니다.</p>
              <p className="text-xs">fetch_news.py를 실행해 데이터를 수집하세요.</p>
            </div>
          )}

          {!loading && items.length > 0 && (
            <div className="flex flex-col gap-2">
              {items.map((item) => {
                const color = SECTOR_COLORS[item.sector] ?? "#6b7280";
                return (
                  <a
                    key={item.id}
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex flex-col gap-1 px-4 py-3 rounded-xl transition-colors"
                    style={{ background: "#111", border: "1px solid #1f2937" }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#2a2a2a")}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#1f2937")}
                  >
                    <div className="flex items-start gap-2">
                      {/* Sector badge */}
                      <span
                        className="shrink-0 mt-0.5 text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: color + "18", color, border: `1px solid ${color}33` }}
                      >
                        {item.sector}
                      </span>
                      {/* Title */}
                      <div className="flex-1 flex flex-col gap-0.5">
                        <p
                          className="text-sm font-medium leading-snug group-hover:text-white transition-colors"
                          style={{ color: "#d1d5db" }}
                        >
                          {item.title_ko ?? item.title}
                        </p>
                        {item.title_ko && (
                          <p className="text-[11px] leading-snug" style={{ color: "#4b5563" }}>
                            {item.title}
                          </p>
                        )}
                      </div>
                      <ExternalLink size={12} className="shrink-0 mt-0.5 opacity-0 group-hover:opacity-60 transition-opacity" style={{ color: "#9ca3af" }} />
                    </div>

                    <div className="flex items-center gap-2 ml-[52px]">
                      <span className="text-[11px]" style={{ color: "#4b5563" }}>{item.source}</span>
                      {item.published_at && (
                        <>
                          <span style={{ color: "#2a2a2a" }}>·</span>
                          <span className="flex items-center gap-0.5 text-[11px]" style={{ color: "#4b5563" }}>
                            <Clock size={9} />
                            {timeAgo(item.published_at)}
                          </span>
                        </>
                      )}
                    </div>
                  </a>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

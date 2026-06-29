"use client";

import { useEffect, useState } from "react";

interface AdviceData {
  content: string;
  snapshot: {
    totalAssets: number;
    totalDebts: number;
    netWorth: number;
    fixedIncome: number;
    fixedExpense: number;
    savingsRate: number;
  };
  created_at: string;
}

function krwShort(v: number) {
  const abs = Math.abs(v);
  if (abs >= 1_0000_0000) return `${(v / 1_0000_0000).toFixed(1)}억`;
  if (abs >= 1_0000) return `${Math.round(v / 1_0000)}만`;
  return `${v.toLocaleString("ko-KR")}`;
}

function timeAgo(iso: string) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
  if (diff < 1) return "방금";
  if (diff < 60) return `${diff}분 전`;
  const h = Math.floor(diff / 60);
  if (h < 24) return `${h}시간 전`;
  return `${Math.floor(h / 24)}일 전`;
}

// bold(**text**) → <strong>, newline → <br>
function renderMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <strong key={i} className="text-white">{p.slice(2, -2)}</strong>;
    }
    return p.split("\n").map((line, j, arr) => (
      <span key={`${i}-${j}`}>{line}{j < arr.length - 1 && <br />}</span>
    ));
  });
}

export default function AdvicePage() {
  const [data, setData] = useState<AdviceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [initial, setInitial] = useState(true);

  async function load() {
    setInitial(false);
    const res = await fetch("/api/advice").then(r => r.json()).catch(() => null);
    if (res && res.content) setData(res);
  }

  useEffect(() => { load(); }, []);

  async function analyze() {
    setLoading(true);
    setError("");
    const res = await fetch("/api/advice", { method: "POST" }).then(r => r.json()).catch(() => null);
    if (res?.error) { setError(res.error); }
    else if (res?.content) { setData(res); }
    setLoading(false);
  }

  const snap = data?.snapshot;

  return (
    <div className="space-y-4 max-w-xl">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-bold text-white">AI 재무 조언</h1>
        {data && (
          <span className="text-[11px]" style={{ color: "#4b5563" }}>{timeAgo(data.created_at)} 분석</span>
        )}
      </div>

      {/* 데이터 스냅샷 요약 */}
      {snap && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "순 자산",   value: krwShort(snap.netWorth),    color: snap.netWorth >= 0 ? "#39ff8f" : "#ef4444" },
            { label: "월 저축",   value: krwShort(snap.fixedIncome - snap.fixedExpense), color: "#60a5fa" },
            { label: "저축률",    value: `${snap.savingsRate}%`,      color: snap.savingsRate >= 20 ? "#39ff8f" : snap.savingsRate >= 10 ? "#facc15" : "#ef4444" },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl p-3 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
              <p className="text-[11px] mb-1" style={{ color: "#6e6e6e" }}>{label}</p>
              <p className="text-sm font-black" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* 분석 요청 버튼 */}
      <button
        onClick={analyze}
        disabled={loading}
        className="w-full py-3 rounded-xl text-sm font-bold transition-opacity"
        style={{
          background: loading ? "#1c1c1c" : "#a78bfa18",
          color: loading ? "#4b5563" : "#a78bfa",
          border: `1px solid ${loading ? "#2e2e2e" : "#a78bfa33"}`,
        }}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: "#a78bfa", borderTopColor: "transparent" }} />
            AI가 분석 중…
          </span>
        ) : data ? "재분석 요청" : "AI 분석 시작"}
      </button>

      {error && (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: "#ef444410", border: "1px solid #ef444430", color: "#ef4444" }}>
          {error}
        </div>
      )}

      {/* AI 분석 결과 */}
      {data?.content && (
        <div className="rounded-2xl p-5 space-y-1" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base">✨</span>
            <span className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#a78bfa" }}>AI 분석 결과</span>
          </div>
          <p className="text-sm leading-relaxed" style={{ color: "#9ca3af", whiteSpace: "pre-wrap" }}>
            {renderMarkdown(data.content)}
          </p>
        </div>
      )}

      {!data && !loading && !error && !initial && (
        <div className="rounded-2xl p-8 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
          <p className="text-sm" style={{ color: "#4b5563" }}>자산현황과 현금흐름 데이터를 먼저 입력한 뒤<br />AI 분석을 요청해보세요.</p>
        </div>
      )}

      {/* 안내 */}
      <div className="rounded-xl px-4 py-3" style={{ background: "#141414", border: "1px solid #1e1e1e" }}>
        <p className="text-[11px]" style={{ color: "#4b5563" }}>
          입력된 자산현황·현금흐름 데이터를 기반으로 GPT-4o가 분석합니다. 투자 의사결정은 본인 판단 하에 이루어져야 합니다.
        </p>
      </div>
    </div>
  );
}

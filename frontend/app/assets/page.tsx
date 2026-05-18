"use client";

import { useEffect, useState } from "react";

const CATEGORIES = [
  { key: "stocks",      label: "주식",     color: "#39ff8f", emoji: "📈" },
  { key: "savings",     label: "예적금",   color: "#60a5fa", emoji: "🏦" },
  { key: "real_estate", label: "부동산",   color: "#f97316", emoji: "🏠" },
  { key: "pension",     label: "연금",     color: "#a78bfa", emoji: "🏛️" },
  { key: "bitcoin",     label: "비트코인", color: "#f59e0b", emoji: "₿"  },
] as const;

type CategoryKey = typeof CATEGORIES[number]["key"];

interface AssetItem {
  id: number;
  category: CategoryKey;
  name: string;
  amount: number;
  note: string | null;
}

function krw(v: number) {
  if (v >= 1_0000_0000) return `${(v / 1_0000_0000).toFixed(1)}억`;
  if (v >= 1_0000) return `${(v / 1_0000).toFixed(0)}만`;
  return `${Math.round(v).toLocaleString("ko-KR")}`;
}
function krwFull(v: number) {
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

// ── SVG 도넛 차트 ──────────────────────────────────────────────────────────────
function DonutChart({ segments }: { segments: { color: string; pct: number }[] }) {
  const r = 70;
  const cx = 90;
  const cy = 90;
  const circ = 2 * Math.PI * r;
  let offset = circ * 0.25;

  return (
    <svg width={180} height={180} viewBox="0 0 180 180">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e1e1e" strokeWidth={22} />
      {segments.filter(s => s.pct > 0).map((s, i) => {
        const dash = s.pct * circ;
        const el = (
          <circle
            key={i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={s.color}
            strokeWidth={22}
            strokeDasharray={`${dash} ${circ - dash}`}
            strokeDashoffset={offset}
            strokeLinecap="butt"
          />
        );
        offset -= dash;
        return el;
      })}
    </svg>
  );
}

// ── 항목 추가/수정 모달 ────────────────────────────────────────────────────────
function ItemModal({
  category, item, onClose, onSave,
}: {
  category: typeof CATEGORIES[number];
  item?: AssetItem;
  onClose: () => void;
  onSave: () => void;
}) {
  const [name, setName] = useState(item?.name ?? "");
  const [amount, setAmount] = useState(item ? String(item.amount) : "");
  const [note, setNote] = useState(item?.note ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (!name || !amount) { setError("이름과 금액을 입력하세요"); return; }
    setLoading(true);
    setError("");
    const res = item
      ? await fetch(`/api/assets/${item.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, amount: Number(amount), note: note || null }),
        })
      : await fetch("/api/assets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ category: category.key, name, amount: Number(amount), note: note || null }),
        });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류"); setLoading(false); return; }
    onSave();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white">
            {category.emoji} {category.label} {item ? "수정" : "추가"}
          </h2>
          <button onClick={onClose} style={{ color: "#6e6e6e" }}>✕</button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>항목명</label>
            <input
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder={
                category.key === "savings" ? "예: KB 정기예금" :
                category.key === "real_estate" ? "예: 서울 아파트" :
                category.key === "pension" ? "예: 국민연금" :
                category.key === "bitcoin" ? "예: 비트코인" : "예: 삼성전자 등"
              }
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>금액 (원)</label>
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              placeholder="50000000"
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
            {Number(amount) > 0 && (
              <p className="text-[12px] mt-1" style={{ color: "#6e6e6e" }}>{krwFull(Number(amount))}</p>
            )}
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>메모 (선택)</label>
            <input
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="예: 만기 2026-12"
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
        </div>

        {error && <p className="text-[12px] text-red-400 mt-2">{error}</p>}

        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222", color: "#6e6e6e" }}>취소</button>
          <button
            onClick={submit}
            disabled={loading}
            className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: `${category.color}18`, color: category.color, border: `1px solid ${category.color}33` }}
          >
            {loading ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 메인 페이지 ────────────────────────────────────────────────────────────────
export default function AssetsPage() {
  const [items, setItems] = useState<AssetItem[]>([]);
  const [expanded, setExpanded] = useState<CategoryKey | null>(null);
  const [modal, setModal] = useState<{ category: typeof CATEGORIES[number]; item?: AssetItem } | null>(null);

  async function load() {
    const res = await fetch("/api/assets").then(r => r.json()).catch(() => []);
    setItems(Array.isArray(res) ? res : []);
  }

  useEffect(() => { load(); }, []);

  async function deleteItem(id: number) {
    await fetch(`/api/assets/${id}`, { method: "DELETE" });
    load();
  }

  const totalByCategory = Object.fromEntries(
    CATEGORIES.map(c => [c.key, items.filter(i => i.category === c.key).reduce((s, i) => s + i.amount, 0)])
  );
  const total = Object.values(totalByCategory).reduce((s, v) => s + v, 0);

  const segments = CATEGORIES.map(c => ({
    color: c.color,
    pct: total > 0 ? totalByCategory[c.key] / total : 0,
  }));

  return (
    <div className="space-y-4 max-w-xl">
      <h1 className="text-base font-bold text-white">자산현황</h1>

      {/* 총 자산 + 도넛 차트 */}
      <div className="rounded-2xl p-5 flex items-center gap-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <div className="shrink-0">
          <DonutChart segments={segments} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[12px] mb-1" style={{ color: "#6e6e6e" }}>총 자산</p>
          <p className="text-2xl font-black text-white mb-3">{krwFull(total)}</p>
          <div className="space-y-1.5">
            {CATEGORIES.map(c => {
              const amt = totalByCategory[c.key];
              const pct = total > 0 ? (amt / total * 100).toFixed(1) : "0.0";
              if (amt === 0) return null;
              return (
                <div key={c.key} className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: c.color }} />
                  <span className="text-[12px] flex-1" style={{ color: "#a8a8a8" }}>{c.label}</span>
                  <span className="text-[12px] font-bold" style={{ color: c.color }}>{pct}%</span>
                  <span className="text-[12px]" style={{ color: "#6e6e6e" }}>{krw(amt)}</span>
                </div>
              );
            })}
            {total === 0 && (
              <p className="text-[12px]" style={{ color: "#4b5563" }}>아래에서 자산을 추가하세요</p>
            )}
          </div>
        </div>
      </div>

      {/* 카테고리별 카드 */}
      {CATEGORIES.map(cat => {
        const catItems = items.filter(i => i.category === cat.key);
        const catTotal = catItems.reduce((s, i) => s + i.amount, 0);
        const isOpen = expanded === cat.key;

        return (
          <div key={cat.key} className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
            {/* 헤더 */}
            <button
              className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/5"
              style={{ background: "#1c1c1c" }}
              onClick={() => setExpanded(isOpen ? null : cat.key)}
            >
              <span className="text-lg">{cat.emoji}</span>
              <span className="font-bold text-white flex-1">{cat.label}</span>
              <span className="text-sm font-black" style={{ color: cat.color }}>
                {catTotal > 0 ? krwFull(catTotal) : "—"}
              </span>
              <span className="text-[12px] ml-2" style={{ color: "#4b5563" }}>{isOpen ? "▲" : "▼"}</span>
            </button>

            {/* 항목 리스트 */}
            {isOpen && (
              <div style={{ background: "#141414", borderTop: "1px solid #2e2e2e" }}>
                {catItems.length === 0 ? (
                  <p className="px-4 py-3 text-[12px]" style={{ color: "#4b5563" }}>등록된 항목 없음</p>
                ) : (
                  catItems.map(item => (
                    <div key={item.id} className="flex items-center gap-3 px-4 py-2.5" style={{ borderBottom: "1px solid #1e1e1e" }}>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-white truncate">{item.name}</p>
                        {item.note && <p className="text-[11px] truncate" style={{ color: "#6e6e6e" }}>{item.note}</p>}
                      </div>
                      <p className="text-sm font-bold shrink-0" style={{ color: cat.color }}>{krwFull(item.amount)}</p>
                      <button
                        onClick={() => setModal({ category: cat, item })}
                        className="text-[12px] px-2 py-1 rounded"
                        style={{ background: "#222", color: "#6e6e6e" }}
                      >수정</button>
                      <button
                        onClick={() => deleteItem(item.id)}
                        className="text-[12px] px-2 py-1 rounded"
                        style={{ background: "#ef444410", color: "#ef4444" }}
                      >삭제</button>
                    </div>
                  ))
                )}
                <div className="px-4 py-2">
                  <button
                    onClick={() => setModal({ category: cat })}
                    className="text-[12px] font-bold px-3 py-1.5 rounded-lg"
                    style={{ background: `${cat.color}12`, color: cat.color, border: `1px solid ${cat.color}25` }}
                  >
                    + 추가
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {modal && (
        <ItemModal
          category={modal.category}
          item={modal.item}
          onClose={() => setModal(null)}
          onSave={() => { setModal(null); load(); }}
        />
      )}
    </div>
  );
}

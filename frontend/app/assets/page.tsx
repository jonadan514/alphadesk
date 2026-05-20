"use client";

import { useEffect, useState } from "react";

const ASSET_CATEGORIES = [
  { key: "stocks",      label: "주식",     color: "#39ff8f", emoji: "📈" },
  { key: "savings",     label: "예적금",   color: "#60a5fa", emoji: "🏦" },
  { key: "real_estate", label: "부동산",   color: "#f97316", emoji: "🏠" },
  { key: "pension",     label: "연금",     color: "#a78bfa", emoji: "🏛️" },
  { key: "bitcoin",     label: "비트코인", color: "#f59e0b", emoji: "₿"  },
] as const;

const DEBT_CATEGORIES = [
  { key: "mortgage",    label: "주택담보대출", color: "#ef4444", emoji: "🏦" },
  { key: "credit_loan", label: "신용대출",     color: "#f87171", emoji: "💳" },
  { key: "other_debt",  label: "기타 부채",    color: "#9ca3af", emoji: "📝" },
] as const;

const ALL_CATEGORIES = [...ASSET_CATEGORIES, ...DEBT_CATEGORIES];
type CategoryKey = typeof ALL_CATEGORIES[number]["key"];

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
  const r = 70, cx = 90, cy = 90;
  const circ = 2 * Math.PI * r;
  let offset = circ * 0.25;
  return (
    <svg width={180} height={180} viewBox="0 0 180 180">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e1e1e" strokeWidth={22} />
      {segments.filter(s => s.pct > 0).map((s, i) => {
        const dash = s.pct * circ;
        const el = (
          <circle key={i} cx={cx} cy={cy} r={r} fill="none"
            stroke={s.color} strokeWidth={22}
            strokeDasharray={`${dash} ${circ - dash}`}
            strokeDashoffset={offset} strokeLinecap="butt"
          />
        );
        offset -= dash;
        return el;
      })}
    </svg>
  );
}

// ── 항목 추가/수정 모달 ────────────────────────────────────────────────────────
function ItemModal({ category, item, onClose, onSave }: {
  category: typeof ALL_CATEGORIES[number];
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

  const isDebt = DEBT_CATEGORIES.some(d => d.key === category.key);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white">{category.emoji} {category.label} {item ? "수정" : "추가"}</h2>
          <button onClick={onClose} style={{ color: "#6e6e6e" }}>✕</button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>항목명</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)}
              placeholder={
                category.key === "mortgage" ? "예: 국민은행 주담대" :
                category.key === "credit_loan" ? "예: 카카오뱅크 신용대출" :
                category.key === "savings" ? "예: KB 정기예금" :
                category.key === "real_estate" ? "예: 서울 아파트" :
                category.key === "pension" ? "예: 국민연금" : "항목명"
              }
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>
              {isDebt ? "잔액 (원)" : "금액 (원)"}
            </label>
            <input type="number" value={amount} onChange={e => setAmount(e.target.value)}
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
            <input value={note} onChange={e => setNote(e.target.value)}
              placeholder={isDebt ? "예: 금리 3.5%, 만기 2030-06" : "예: 만기 2026-12"}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
        </div>
        {error && <p className="text-[12px] text-red-400 mt-2">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222", color: "#6e6e6e" }}>취소</button>
          <button onClick={submit} disabled={loading} className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: `${category.color}18`, color: category.color, border: `1px solid ${category.color}33` }}>
            {loading ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 카테고리 카드 ──────────────────────────────────────────────────────────────
function CategoryCard({ cat, items, expanded, onToggle, onAdd, onEdit, onDelete }: {
  cat: typeof ALL_CATEGORIES[number];
  items: AssetItem[];
  expanded: boolean;
  onToggle: () => void;
  onAdd: () => void;
  onEdit: (item: AssetItem) => void;
  onDelete: (id: number) => void;
}) {
  const total = items.reduce((s, i) => s + i.amount, 0);
  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
      <button className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/5"
        style={{ background: "#1c1c1c" }} onClick={onToggle}>
        <span className="text-lg">{cat.emoji}</span>
        <span className="font-bold text-white flex-1">{cat.label}</span>
        <span className="text-sm font-black" style={{ color: cat.color }}>
          {total > 0 ? krwFull(total) : "—"}
        </span>
        <span className="text-[12px] ml-2" style={{ color: "#4b5563" }}>{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div style={{ background: "#141414", borderTop: "1px solid #2e2e2e" }}>
          {items.length === 0
            ? <p className="px-4 py-3 text-[12px]" style={{ color: "#4b5563" }}>등록된 항목 없음</p>
            : items.map(item => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-2.5" style={{ borderBottom: "1px solid #1e1e1e" }}>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-white truncate">{item.name}</p>
                  {item.note && <p className="text-[11px] truncate" style={{ color: "#6e6e6e" }}>{item.note}</p>}
                </div>
                <p className="text-sm font-bold shrink-0" style={{ color: cat.color }}>{krwFull(item.amount)}</p>
                <button onClick={() => onEdit(item)} className="text-[12px] px-2 py-1 rounded" style={{ background: "#222", color: "#6e6e6e" }}>수정</button>
                <button onClick={() => onDelete(item.id)} className="text-[12px] px-2 py-1 rounded" style={{ background: "#ef444410", color: "#ef4444" }}>삭제</button>
              </div>
            ))
          }
          <div className="px-4 py-2">
            <button onClick={onAdd} className="text-[12px] font-bold px-3 py-1.5 rounded-lg"
              style={{ background: `${cat.color}12`, color: cat.color, border: `1px solid ${cat.color}25` }}>
              + 추가
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── 메인 페이지 ────────────────────────────────────────────────────────────────
export default function AssetsPage() {
  const [items, setItems] = useState<AssetItem[]>([]);
  const [expanded, setExpanded] = useState<CategoryKey | null>(null);
  const [modal, setModal] = useState<{ category: typeof ALL_CATEGORIES[number]; item?: AssetItem } | null>(null);

  async function load() {
    const res = await fetch("/api/assets").then(r => r.json()).catch(() => []);
    setItems(Array.isArray(res) ? res : []);
  }
  useEffect(() => { load(); }, []);

  async function deleteItem(id: number) {
    await fetch(`/api/assets/${id}`, { method: "DELETE" });
    load();
  }

  const totalAssets = ASSET_CATEGORIES.reduce((s, c) =>
    s + items.filter(i => i.category === c.key).reduce((a, i) => a + i.amount, 0), 0);
  const totalDebts = DEBT_CATEGORIES.reduce((s, c) =>
    s + items.filter(i => i.category === c.key).reduce((a, i) => a + i.amount, 0), 0);
  const netWorth = totalAssets - totalDebts;

  const assetSegments = ASSET_CATEGORIES.map(c => ({
    color: c.color,
    pct: totalAssets > 0 ? items.filter(i => i.category === c.key).reduce((s, i) => s + i.amount, 0) / totalAssets : 0,
  }));

  function toggle(key: CategoryKey) {
    setExpanded(prev => prev === key ? null : key);
  }

  return (
    <div className="space-y-4 max-w-xl">
      <h1 className="text-base font-bold text-white">자산현황</h1>

      {/* 순자산 요약 카드 */}
      <div className="rounded-2xl p-5 flex items-center gap-6" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
        <div className="shrink-0 relative">
          <DonutChart segments={assetSegments} />
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>순자산</p>
            <p className="text-base font-black" style={{ color: netWorth >= 0 ? "#39ff8f" : "#ef4444" }}>
              {krw(Math.abs(netWorth))}
            </p>
          </div>
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <div>
            <p className="text-[11px]" style={{ color: "#6e6e6e" }}>총 자산</p>
            <p className="text-lg font-black text-white">{krwFull(totalAssets)}</p>
          </div>
          <div style={{ borderTop: "1px solid #2e2e2e", paddingTop: "8px" }}>
            <p className="text-[11px]" style={{ color: "#6e6e6e" }}>총 부채</p>
            <p className="text-base font-black" style={{ color: totalDebts > 0 ? "#ef4444" : "#4b5563" }}>
              {totalDebts > 0 ? `- ${krwFull(totalDebts)}` : "—"}
            </p>
          </div>
          <div style={{ borderTop: "1px solid #2e2e2e", paddingTop: "8px" }}>
            <p className="text-[11px]" style={{ color: "#6e6e6e" }}>순자산</p>
            <p className="text-base font-black" style={{ color: netWorth >= 0 ? "#39ff8f" : "#ef4444" }}>
              {krwFull(Math.abs(netWorth))}{netWorth < 0 ? " (부채 초과)" : ""}
            </p>
          </div>
        </div>
      </div>

      {/* 자산 카테고리 */}
      <p className="text-[11px] font-bold uppercase tracking-widest px-1" style={{ color: "#6e6e6e" }}>자산</p>
      {ASSET_CATEGORIES.map(cat => (
        <CategoryCard key={cat.key} cat={cat}
          items={items.filter(i => i.category === cat.key)}
          expanded={expanded === cat.key}
          onToggle={() => toggle(cat.key)}
          onAdd={() => setModal({ category: cat })}
          onEdit={item => setModal({ category: cat, item })}
          onDelete={deleteItem}
        />
      ))}

      {/* 부채 카테고리 */}
      <p className="text-[11px] font-bold uppercase tracking-widest px-1 mt-2" style={{ color: "#6e6e6e" }}>부채</p>
      {DEBT_CATEGORIES.map(cat => (
        <CategoryCard key={cat.key} cat={cat}
          items={items.filter(i => i.category === cat.key)}
          expanded={expanded === cat.key}
          onToggle={() => toggle(cat.key)}
          onAdd={() => setModal({ category: cat })}
          onEdit={item => setModal({ category: cat, item })}
          onDelete={deleteItem}
        />
      ))}

      {modal && (
        <ItemModal category={modal.category} item={modal.item}
          onClose={() => setModal(null)}
          onSave={() => { setModal(null); load(); }}
        />
      )}
    </div>
  );
}

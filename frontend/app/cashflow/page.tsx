"use client";

import { useEffect, useState } from "react";

interface YearlyData {
  month: string;
  income: number;
  expense: number;
  net: number;
}

interface FixedItem {
  id: number;
  type: "income" | "expense";
  name: string;
  amount: number;
  note: string | null;
}

interface Entry {
  id: number;
  month: string;
  type: "income" | "expense";
  name: string;
  amount: number;
  note: string | null;
}

function krwFull(v: number) {
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

function krwShort(v: number) {
  const abs = Math.abs(v);
  if (abs >= 1_0000_0000) return `${(v / 1_0000_0000).toFixed(1)}억`;
  if (abs >= 1_0000) return `${Math.round(v / 1_0000)}만`;
  return `${Math.round(v).toLocaleString("ko-KR")}`;
}

// ── 연간 바 차트 ───────────────────────────────────────────────────────────────
function YearlyChart({ data, year, onYearChange }: {
  data: YearlyData[];
  year: number;
  onYearChange: (y: number) => void;
}) {
  const W = 520, H = 220, PL = 46, PR = 8, PT = 12, PB = 36;
  const chartW = W - PL - PR;
  const chartH = H - PT - PB;
  const MONTH_LABELS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];

  const maxVal = Math.max(...data.map(d => Math.max(d.income, d.expense)), 1);
  const minNet = Math.min(...data.map(d => d.net), 0);
  const maxNet = Math.max(...data.map(d => d.net), 0);
  // unified scale: bars and line share same axis if net fits; expand if needed
  const yMax = Math.max(maxVal, maxNet) * 1.1 || 1;
  const yMin = Math.min(0, minNet * 1.1);
  const yRange = yMax - yMin;

  function scaleY(v: number) {
    return PT + chartH - ((v - yMin) / yRange) * chartH;
  }

  const slotW = chartW / 12;
  const barW = slotW * 0.28;
  const gap = barW * 0.4;

  // y-axis ticks
  const tickCount = 4;
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => yMin + (yRange / tickCount) * i);

  // net line points
  const linePoints = data.map((d, i) => {
    const x = PL + slotW * i + slotW / 2;
    const y = scaleY(d.net);
    return `${x},${y}`;
  }).join(" ");

  const zeroY = scaleY(0);

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid #2e2e2e" }}>
        <span className="text-sm font-bold text-white">연간 현금흐름</span>
        <div className="flex items-center gap-2">
          <button onClick={() => onYearChange(year - 1)} className="px-2 py-1 rounded text-[12px]" style={{ background: "#222", color: "#6e6e6e" }}>◀</button>
          <span className="text-[13px] font-bold text-white w-12 text-center">{year}</span>
          <button onClick={() => onYearChange(year + 1)} className="px-2 py-1 rounded text-[12px]" style={{ background: "#222", color: "#6e6e6e" }}>▶</button>
        </div>
      </div>
      {/* legend */}
      <div className="flex gap-4 px-4 pt-3 pb-1">
        {[["#39ff8f","수입"],["#ef4444","지출"],["#60a5fa","순현금흐름"]].map(([c, l]) => (
          <div key={l} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: c }} />
            <span className="text-[11px]" style={{ color: "#6e6e6e" }}>{l}</span>
          </div>
        ))}
      </div>
      <div className="overflow-x-auto">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: "block", minWidth: W }}>
          {/* y-axis grid + labels */}
          {ticks.map((t, i) => {
            const y = scaleY(t);
            return (
              <g key={i}>
                <line x1={PL} x2={W - PR} y1={y} y2={y} stroke="#2e2e2e" strokeWidth={1} />
                <text x={PL - 4} y={y + 4} textAnchor="end" fontSize={9} fill="#4b5563">{krwShort(t)}</text>
              </g>
            );
          })}
          {/* zero line (bold if negative values exist) */}
          {yMin < 0 && (
            <line x1={PL} x2={W - PR} y1={zeroY} y2={zeroY} stroke="#444" strokeWidth={1} strokeDasharray="3,2" />
          )}
          {/* bars */}
          {data.map((d, i) => {
            const slotX = PL + slotW * i;
            const cx = slotX + slotW / 2;
            const incX = cx - gap / 2 - barW;
            const expX = cx + gap / 2;
            const incH = Math.max(1, ((d.income - Math.max(0, yMin)) / yRange) * chartH);
            const expH = Math.max(1, ((d.expense - Math.max(0, yMin)) / yRange) * chartH);
            const incY = scaleY(d.income);
            const expY = scaleY(d.expense);
            return (
              <g key={i}>
                <rect x={incX} y={incY} width={barW} height={incH} fill="#39ff8f" opacity={0.75} rx={2} />
                <rect x={expX} y={expY} width={barW} height={expH} fill="#ef4444" opacity={0.75} rx={2} />
                <text x={slotX + slotW / 2} y={H - PB + 14} textAnchor="middle" fontSize={9} fill="#4b5563">{MONTH_LABELS[i]}</text>
              </g>
            );
          })}
          {/* net cashflow line */}
          <polyline points={linePoints} fill="none" stroke="#60a5fa" strokeWidth={2} strokeLinejoin="round" />
          {data.map((d, i) => {
            const x = PL + slotW * i + slotW / 2;
            const y = scaleY(d.net);
            return <circle key={i} cx={x} cy={y} r={3} fill="#60a5fa" />;
          })}
        </svg>
      </div>
    </div>
  );
}

function currentMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// ── 고정 항목 추가 모달 ────────────────────────────────────────────────────────
function FixedModal({ type, item, onClose, onSave }: {
  type: "income" | "expense";
  item?: FixedItem;
  onClose: () => void;
  onSave: () => void;
}) {
  const [name, setName] = useState(item?.name ?? "");
  const [amount, setAmount] = useState(item ? String(item.amount) : "");
  const [note, setNote] = useState(item?.note ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const color = type === "income" ? "#39ff8f" : "#ef4444";
  const label = type === "income" ? "수입" : "지출";

  async function submit() {
    if (!name || !amount) { setError("이름과 금액을 입력하세요"); return; }
    setLoading(true);
    const res = item
      ? await fetch(`/api/cashflow/fixed/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, amount: Number(amount), note: note || null }) })
      : await fetch("/api/cashflow/fixed", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type, name, amount: Number(amount), note: note || null }) });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류"); setLoading(false); return; }
    onSave();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white">고정 {label} {item ? "수정" : "추가"}</h2>
          <button onClick={onClose} style={{ color: "#6e6e6e" }}>✕</button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>항목명</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)}
              placeholder={type === "income" ? "예: 월급, 임대수입" : "예: 관리비, 보험료"}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>월 금액 (원)</label>
            <input type="number" value={amount} onChange={e => setAmount(e.target.value)}
              placeholder="3000000"
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
            {Number(amount) > 0 && <p className="text-[12px] mt-1" style={{ color: "#6e6e6e" }}>{krwFull(Number(amount))}</p>}
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>메모 (선택)</label>
            <input value={note} onChange={e => setNote(e.target.value)}
              placeholder="예: 매월 25일 지급"
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
        </div>
        {error && <p className="text-[12px] text-red-400 mt-2">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222", color: "#6e6e6e" }}>취소</button>
          <button onClick={submit} disabled={loading} className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: `${color}18`, color, border: `1px solid ${color}33` }}>
            {loading ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 변동 항목 추가 모달 ────────────────────────────────────────────────────────
function EntryModal({ type, month, onClose, onSave }: {
  type: "income" | "expense";
  month: string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const color = type === "income" ? "#39ff8f" : "#ef4444";
  const label = type === "income" ? "수입" : "지출";

  async function submit() {
    if (!name || !amount) { setError("이름과 금액을 입력하세요"); return; }
    setLoading(true);
    const res = await fetch("/api/cashflow/entries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month, type, name, amount: Number(amount), note: note || null }),
    });
    const data = await res.json();
    if (!res.ok) { setError(data.error ?? "오류"); setLoading(false); return; }
    onSave();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.8)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-full max-w-sm" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white">{month} 추가 {label}</h2>
          <button onClick={onClose} style={{ color: "#6e6e6e" }}>✕</button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>항목명</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)}
              placeholder={type === "income" ? "예: 보너스, 부수입" : "예: 여행, 의료비"}
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>금액 (원)</label>
            <input type="number" value={amount} onChange={e => setAmount(e.target.value)}
              placeholder="500000"
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
            {Number(amount) > 0 && <p className="text-[12px] mt-1" style={{ color: "#6e6e6e" }}>{krwFull(Number(amount))}</p>}
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>메모 (선택)</label>
            <input value={note} onChange={e => setNote(e.target.value)}
              placeholder="메모"
              className="w-full rounded-lg px-3 py-2 text-sm text-white outline-none"
              style={{ background: "#222", border: "1px solid #333" }}
            />
          </div>
        </div>
        {error && <p className="text-[12px] text-red-400 mt-2">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222", color: "#6e6e6e" }}>취소</button>
          <button onClick={submit} disabled={loading} className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: `${color}18`, color, border: `1px solid ${color}33` }}>
            {loading ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 고정 항목 관리 패널 ────────────────────────────────────────────────────────
function FixedSection({ type, items, onAdd, onEdit, onDelete }: {
  type: "income" | "expense";
  items: FixedItem[];
  onAdd: () => void;
  onEdit: (item: FixedItem) => void;
  onDelete: (id: number) => void;
}) {
  const color = type === "income" ? "#39ff8f" : "#ef4444";
  const label = type === "income" ? "고정 수입" : "고정 지출";
  const total = items.reduce((s, i) => s + i.amount, 0);

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
      <div className="flex items-center justify-between px-4 py-3" style={{ background: "#1c1c1c" }}>
        <span className="font-bold text-white text-sm">{label}</span>
        <span className="text-sm font-black" style={{ color }}>{total > 0 ? krwFull(total) : "—"}</span>
      </div>
      <div style={{ background: "#141414", borderTop: "1px solid #2e2e2e" }}>
        {items.length === 0
          ? <p className="px-4 py-3 text-[12px]" style={{ color: "#4b5563" }}>등록된 고정 항목 없음</p>
          : items.map(item => (
            <div key={item.id} className="flex items-center gap-3 px-4 py-2.5" style={{ borderBottom: "1px solid #1e1e1e" }}>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-white truncate">{item.name}</p>
                {item.note && <p className="text-[11px] truncate" style={{ color: "#6e6e6e" }}>{item.note}</p>}
              </div>
              <p className="text-sm font-bold shrink-0" style={{ color }}>{krwFull(item.amount)}</p>
              <button onClick={() => onEdit(item)} className="text-[12px] px-2 py-1 rounded" style={{ background: "#222", color: "#6e6e6e" }}>수정</button>
              <button onClick={() => onDelete(item.id)} className="text-[12px] px-2 py-1 rounded" style={{ background: "#ef444410", color: "#ef4444" }}>삭제</button>
            </div>
          ))
        }
        <div className="px-4 py-2">
          <button onClick={onAdd} className="text-[12px] font-bold px-3 py-1.5 rounded-lg"
            style={{ background: `${color}12`, color, border: `1px solid ${color}25` }}>
            + 추가
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 변동 항목 섹션 ─────────────────────────────────────────────────────────────
function EntrySection({ type, entries, fixedTotal, onAdd, onDelete }: {
  type: "income" | "expense";
  entries: Entry[];
  fixedTotal: number;
  onAdd: () => void;
  onDelete: (id: number) => void;
}) {
  const color = type === "income" ? "#39ff8f" : "#ef4444";
  const label = type === "income" ? "수입" : "지출";
  const varTotal = entries.reduce((s, e) => s + e.amount, 0);
  const grandTotal = fixedTotal + varTotal;

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
      <div className="flex items-center justify-between px-4 py-3" style={{ background: "#1c1c1c" }}>
        <div>
          <span className="font-bold text-white text-sm">{label}</span>
          <span className="text-[11px] ml-2" style={{ color: "#6e6e6e" }}>고정 {krwFull(fixedTotal)}{varTotal > 0 ? ` + 추가 ${krwFull(varTotal)}` : ""}</span>
        </div>
        <span className="text-sm font-black" style={{ color }}>{krwFull(grandTotal)}</span>
      </div>
      {entries.length > 0 && (
        <div style={{ background: "#141414", borderTop: "1px solid #2e2e2e" }}>
          {entries.map(entry => (
            <div key={entry.id} className="flex items-center gap-3 px-4 py-2.5" style={{ borderBottom: "1px solid #1e1e1e" }}>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-white truncate">{entry.name}</p>
                {entry.note && <p className="text-[11px] truncate" style={{ color: "#6e6e6e" }}>{entry.note}</p>}
              </div>
              <p className="text-sm font-bold shrink-0" style={{ color }}>{krwFull(entry.amount)}</p>
              <button onClick={() => onDelete(entry.id)} className="text-[12px] px-2 py-1 rounded" style={{ background: "#ef444410", color: "#ef4444" }}>삭제</button>
            </div>
          ))}
        </div>
      )}
      <div style={{ background: "#141414", borderTop: entries.length > 0 ? "1px solid #2e2e2e" : "none" }}>
        <div className="px-4 py-2">
          <button onClick={onAdd} className="text-[12px] font-bold px-3 py-1.5 rounded-lg"
            style={{ background: `${color}12`, color, border: `1px solid ${color}25` }}>
            + 이번달 추가 {label}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 메인 페이지 ────────────────────────────────────────────────────────────────
type ModalState =
  | { kind: "fixed-add"; type: "income" | "expense" }
  | { kind: "fixed-edit"; item: FixedItem }
  | { kind: "entry-add"; type: "income" | "expense" };

export default function CashflowPage() {
  const [month, setMonth] = useState(currentMonth());
  const [fixedItems, setFixedItems] = useState<FixedItem[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [modal, setModal] = useState<ModalState | null>(null);
  const [showFixed, setShowFixed] = useState(false);
  const [yearlyData, setYearlyData] = useState<YearlyData[]>([]);
  const [chartYear, setChartYear] = useState(new Date().getFullYear());

  async function loadFixed() {
    const res = await fetch("/api/cashflow/fixed").then(r => r.json()).catch(() => []);
    setFixedItems(Array.isArray(res) ? res : []);
  }

  async function loadEntries(m: string) {
    const res = await fetch(`/api/cashflow/entries?month=${m}`).then(r => r.json()).catch(() => []);
    setEntries(Array.isArray(res) ? res : []);
  }

  async function loadYearly(y: number) {
    const res = await fetch(`/api/cashflow/yearly?year=${y}`).then(r => r.json()).catch(() => []);
    setYearlyData(Array.isArray(res) ? res : []);
  }

  useEffect(() => { loadFixed(); }, []);
  useEffect(() => { loadEntries(month); }, [month]);
  useEffect(() => { loadYearly(chartYear); }, [chartYear]);

  async function deleteFixed(id: number) {
    await fetch(`/api/cashflow/fixed/${id}`, { method: "DELETE" });
    loadFixed();
  }

  async function deleteEntry(id: number) {
    await fetch(`/api/cashflow/entries/${id}`, { method: "DELETE" });
    loadEntries(month);
  }

  function onModalSave() {
    setModal(null);
    loadFixed();
    loadEntries(month);
    loadYearly(chartYear);
  }

  const fixedIncome = fixedItems.filter(i => i.type === "income");
  const fixedExpense = fixedItems.filter(i => i.type === "expense");
  const varEntries = entries.filter(e => e.type === "income" || e.type === "expense");
  const varIncome = entries.filter(e => e.type === "income");
  const varExpense = entries.filter(e => e.type === "expense");

  const fixedIncomeTotal = fixedIncome.reduce((s, i) => s + i.amount, 0);
  const fixedExpenseTotal = fixedExpense.reduce((s, i) => s + i.amount, 0);
  const varIncomeTotal = varIncome.reduce((s, i) => s + i.amount, 0);
  const varExpenseTotal = varExpense.reduce((s, i) => s + i.amount, 0);

  const totalIncome = fixedIncomeTotal + varIncomeTotal;
  const totalExpense = fixedExpenseTotal + varExpenseTotal;
  const netCash = totalIncome - totalExpense;

  // month navigation
  function prevMonth() {
    const [y, m] = month.split("-").map(Number);
    const d = new Date(y, m - 2);
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  }
  function nextMonth() {
    const [y, m] = month.split("-").map(Number);
    const d = new Date(y, m);
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  }

  return (
    <div className="space-y-4 max-w-xl">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-bold text-white">현금흐름</h1>
        <button onClick={() => setShowFixed(v => !v)} className="text-[12px] px-3 py-1.5 rounded-lg font-bold"
          style={{ background: "#1c1c1c", color: "#6e6e6e", border: "1px solid #2e2e2e" }}>
          {showFixed ? "월별 보기" : "고정 항목 관리"}
        </button>
      </div>

      {/* ── 고정 항목 관리 모드 ── */}
      {showFixed ? (
        <div className="space-y-3">
          <p className="text-[11px] font-bold uppercase tracking-widest px-1" style={{ color: "#6e6e6e" }}>고정 항목 관리</p>
          <FixedSection type="income" items={fixedIncome}
            onAdd={() => setModal({ kind: "fixed-add", type: "income" })}
            onEdit={item => setModal({ kind: "fixed-edit", item })}
            onDelete={deleteFixed}
          />
          <FixedSection type="expense" items={fixedExpense}
            onAdd={() => setModal({ kind: "fixed-add", type: "expense" })}
            onEdit={item => setModal({ kind: "fixed-edit", item })}
            onDelete={deleteFixed}
          />
        </div>
      ) : (
        <>
          {/* ── 월 선택 ── */}
          <div className="flex items-center gap-3">
            <button onClick={prevMonth} className="px-3 py-1.5 rounded-lg text-sm" style={{ background: "#1c1c1c", color: "#6e6e6e", border: "1px solid #2e2e2e" }}>◀</button>
            <span className="text-sm font-bold text-white flex-1 text-center">{month}</span>
            <button onClick={nextMonth} className="px-3 py-1.5 rounded-lg text-sm" style={{ background: "#1c1c1c", color: "#6e6e6e", border: "1px solid #2e2e2e" }}>▶</button>
          </div>

          {/* ── 요약 카드 ── */}
          <div className="rounded-2xl p-5" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <p className="text-[11px] mb-1" style={{ color: "#6e6e6e" }}>총 수입</p>
                <p className="text-sm font-black" style={{ color: "#39ff8f" }}>{krwFull(totalIncome)}</p>
              </div>
              <div className="text-center" style={{ borderLeft: "1px solid #2e2e2e", borderRight: "1px solid #2e2e2e" }}>
                <p className="text-[11px] mb-1" style={{ color: "#6e6e6e" }}>총 지출</p>
                <p className="text-sm font-black" style={{ color: "#ef4444" }}>{krwFull(totalExpense)}</p>
              </div>
              <div className="text-center">
                <p className="text-[11px] mb-1" style={{ color: "#6e6e6e" }}>순 현금흐름</p>
                <p className="text-sm font-black" style={{ color: netCash >= 0 ? "#39ff8f" : "#ef4444" }}>
                  {netCash >= 0 ? "+" : ""}{krwFull(netCash)}
                </p>
              </div>
            </div>
            {netCash > 0 && totalIncome > 0 && (
              <div className="mt-3 pt-3" style={{ borderTop: "1px solid #2e2e2e" }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px]" style={{ color: "#6e6e6e" }}>저축률</span>
                  <span className="text-[12px] font-bold" style={{ color: "#39ff8f" }}>{Math.round((netCash / totalIncome) * 100)}%</span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "#2e2e2e" }}>
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, (netCash / totalIncome) * 100)}%`, background: "#39ff8f" }} />
                </div>
              </div>
            )}
          </div>

          {/* ── 수입 섹션 ── */}
          <p className="text-[11px] font-bold uppercase tracking-widest px-1" style={{ color: "#6e6e6e" }}>수입</p>
          <EntrySection type="income" entries={varIncome} fixedTotal={fixedIncomeTotal}
            onAdd={() => setModal({ kind: "entry-add", type: "income" })}
            onDelete={deleteEntry}
          />

          {/* ── 지출 섹션 ── */}
          <p className="text-[11px] font-bold uppercase tracking-widest px-1 mt-2" style={{ color: "#6e6e6e" }}>지출</p>
          <EntrySection type="expense" entries={varExpense} fixedTotal={fixedExpenseTotal}
            onAdd={() => setModal({ kind: "entry-add", type: "expense" })}
            onDelete={deleteEntry}
          />

          {/* ── 연간 차트 ── */}
          {yearlyData.length > 0 && (
            <YearlyChart
              data={yearlyData}
              year={chartYear}
              onYearChange={y => setChartYear(y)}
            />
          )}
        </>
      )}

      {/* ── 모달 ── */}
      {modal?.kind === "fixed-add" && (
        <FixedModal type={modal.type} onClose={() => setModal(null)} onSave={onModalSave} />
      )}
      {modal?.kind === "fixed-edit" && (
        <FixedModal type={modal.item.type} item={modal.item} onClose={() => setModal(null)} onSave={onModalSave} />
      )}
      {modal?.kind === "entry-add" && (
        <EntryModal type={modal.type} month={month} onClose={() => setModal(null)} onSave={onModalSave} />
      )}
    </div>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { Target, TrendingUp, Wallet, Settings, Plus, Trash2, ChevronDown, ChevronUp } from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────────
function krw(v: number) {
  if (Math.abs(v) >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억`;
  if (Math.abs(v) >= 10_000)      return `${Math.round(v / 10_000).toLocaleString("ko-KR")}만`;
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}
function krwFull(v: number) {
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}
function pct(v: number, d = 1) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;
}

const MONTH_LABELS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];

// ── Projection calculator ──────────────────────────────────────────────────────
function buildProjection(
  currentAssets: number,
  annualCapacity: number,
  targetAmount: number,
  targetYear: number,
  rate: number,
  startYear: number,
  monthlyEntries: any[],
) {
  const rows: { year: number; invested: number; projected: number; isActual: boolean }[] = [];
  const currentYear = new Date().getFullYear();

  // Find the most recent portfolio_value entered (use as base if available)
  const sorted = [...monthlyEntries].sort((a, b) => b.year * 100 + b.month - (a.year * 100 + a.month));
  const latestSnap = sorted.find((e) => e.portfolio_value != null);

  let base = currentAssets;
  let baseYear = startYear;

  if (latestSnap) {
    base = latestSnap.portfolio_value;
    baseYear = latestSnap.year;
  }

  // Cumulative invested (all entries up to baseYear)
  const totalInvested = monthlyEntries.reduce((s, e) => s + e.total_amount, 0);

  for (let y = startYear; y <= Math.max(targetYear, currentYear + 1); y++) {
    const yearsFromBase = y - baseYear;
    const projected = yearsFromBase <= 0
      ? base
      : base * Math.pow(1 + rate, yearsFromBase) + annualCapacity * ((Math.pow(1 + rate, yearsFromBase) - 1) / rate);
    rows.push({
      year: y,
      invested: totalInvested + Math.max(0, y - currentYear) * annualCapacity,
      projected: Math.round(projected),
      isActual: y <= currentYear,
    });
  }
  return rows;
}

// ── Profile Setup Modal ────────────────────────────────────────────────────────
function ProfileModal({ initial, onSave, onClose }: {
  initial: any | null;
  onSave: (p: any) => void;
  onClose: () => void;
}) {
  const now = new Date();
  const [form, setForm] = useState({
    birth_year:      String(initial?.birth_year ?? 1988),
    target_year:     String(initial?.target_year ?? 2033),
    target_amount:   String(initial?.target_amount ? Math.round(initial.target_amount / 10000) : 100000),
    current_assets:  String(initial?.current_assets ? Math.round(initial.current_assets / 10000) : 1000),
    annual_capacity: String(initial?.annual_capacity ? Math.round(initial.annual_capacity / 10000) : 5000),
    pension_limit:   String(initial?.pension_limit ? Math.round(initial.pension_limit / 10000) : 1200),
    irp_limit:       String(initial?.irp_limit ? Math.round(initial.irp_limit / 10000) : 600),
    isa_limit:       String(initial?.isa_limit ? Math.round(initial.isa_limit / 10000) : 2000),
    expected_rate:   String(initial?.expected_rate ? Math.round(initial.expected_rate * 100) : 15),
  });
  const [saving, setSaving] = useState(false);

  function f(k: string) { return (e: React.ChangeEvent<HTMLInputElement>) => setForm((p) => ({ ...p, [k]: e.target.value })); }

  const birthYearNum = Number(form.birth_year);
  const isValidBirth = form.birth_year.length === 4 && birthYearNum >= 1900 && birthYearNum <= new Date().getFullYear() - 10;
  const age = isValidBirth ? now.getFullYear() - birthYearNum + 1 : null;
  const yearsLeft = Number(form.target_year) - now.getFullYear();

  async function save() {
    setSaving(true);
    await fetch("/api/workbook/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        birth_year:      Number(form.birth_year),
        target_year:     Number(form.target_year),
        target_amount:   Number(form.target_amount) * 10000,
        current_assets:  Number(form.current_assets) * 10000,
        annual_capacity: Number(form.annual_capacity) * 10000,
        pension_limit:   Number(form.pension_limit) * 10000,
        irp_limit:       Number(form.irp_limit) * 10000,
        isa_limit:       Number(form.isa_limit) * 10000,
        expected_rate:   Number(form.expected_rate) / 100,
      }),
    });
    onSave({});
    setSaving(false);
  }

  const Field = ({ label, k, unit = "만원", hint }: { label: string; k: string; unit?: string; hint?: string }) => (
    <div className="min-w-0">
      <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={form[k as keyof typeof form]}
          onChange={f(k)}
          onWheel={(e) => e.currentTarget.blur()}
          className="flex-1 min-w-0 rounded-lg px-3 py-2 text-sm text-white outline-none"
          style={{ background: "#222222", border: "1px solid #2e2e2e" }}
        />
        {unit && <span className="text-[12px] shrink-0" style={{ color: "#6e6e6e" }}>{unit}</span>}
      </div>
      {hint && <p className="text-[12px] mt-1" style={{ color: "#4a4a4a" }}>{hint}</p>}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" style={{ background: "rgba(0,0,0,0.85)" }} onClick={onClose}>
      <div className="flex min-h-full items-center justify-center p-4">
      <div className="rounded-2xl p-6 w-full max-w-lg my-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-bold text-white">투자 프로필 설정</h2>
          <button onClick={onClose} style={{ color: "#6e6e6e" }}>✕</button>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="출생연도" k="birth_year" unit="년" />
            <Field label="목표 연도" k="target_year" unit="년" />
          </div>
          {age !== null && age > 0 && yearsLeft > 0 && (
            <p className="text-[12px]" style={{ color: "#facc15" }}>
              현재 {age}세 · 목표까지 {yearsLeft}년
            </p>
          )}

          <div className="h-px" style={{ background: "#202020" }} />

          <Field label="목표 금융자산" k="target_amount" hint={`${krw(Number(form.target_amount) * 10000)}`} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="현재 금융자산" k="current_assets" hint={krw(Number(form.current_assets) * 10000)} />
            <Field label="연간 투입 가능" k="annual_capacity" hint={`월 ${krw(Number(form.annual_capacity) * 10000 / 12)}`} />
          </div>

          <div className="h-px" style={{ background: "#202020" }} />
          <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>연간 계좌 한도</p>

          <div className="flex items-start gap-2">
            <div className="grid grid-cols-3 gap-3 flex-1">
              <Field label="연금저축" k="pension_limit" unit="" hint="부부합산" />
              <Field label="IRP" k="irp_limit" unit="" hint="부부합산" />
              <Field label="ISA" k="isa_limit" unit="" />
            </div>
            <span className="text-[12px] shrink-0 mt-7" style={{ color: "#6e6e6e" }}>만원</span>
          </div>

          <div className="h-px" style={{ background: "#202020" }} />
          <Field label="기대 수익률" k="expected_rate" unit="%" hint="보수적 10-12%, 적극적 15-20%" />
        </div>

        <div className="flex gap-2 mt-6">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222222", color: "#6e6e6e" }}>취소</button>
          <button onClick={save} disabled={saving} className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
            {saving ? "저장 중…" : "저장하기"}
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}

// ── Monthly Entry Modal ────────────────────────────────────────────────────────
function MonthlyModal({ profile, annualUsage, existing, onSave, onClose }: {
  profile: any;
  annualUsage: Record<string, any>;
  existing?: any;
  onSave: () => void;
  onClose: () => void;
}) {
  const now = new Date();
  const [year, setYear]   = useState(String(existing?.year ?? now.getFullYear()));
  const [month, setMonth] = useState(String(existing?.month ?? now.getMonth() + 1));
  const [total, setTotal] = useState(String(existing?.total_amount ? Math.round(existing.total_amount / 10000) : ""));
  const [pension, setPension] = useState(String(existing?.pension ? Math.round(existing.pension / 10000) : ""));
  const [irp, setIrp]     = useState(String(existing?.irp ? Math.round(existing.irp / 10000) : ""));
  const [isa, setIsa]     = useState(String(existing?.isa ? Math.round(existing.isa / 10000) : ""));
  const [general, setGeneral] = useState(String(existing?.general ? Math.round(existing.general / 10000) : ""));
  const [pfValue, setPfValue] = useState(String(existing?.portfolio_value ? Math.round(existing.portfolio_value / 10000) : ""));
  const [note, setNote]   = useState(existing?.note ?? "");
  const [saving, setSaving] = useState(false);

  const y = Number(year);
  const usage = annualUsage?.[y] ?? { pension: 0, irp: 0, isa: 0 };
  const pensionLeft = Math.max(0, (profile?.pension_limit ?? 12000000) - usage.pension);
  const irpLeft     = Math.max(0, (profile?.irp_limit ?? 6000000) - usage.irp);
  const isaLeft     = Math.max(0, (profile?.isa_limit ?? 20000000) - usage.isa);

  function autoAllocate() {
    let rem = Number(total) * 10000;
    const p = Math.min(rem, pensionLeft); rem -= p;
    const i = Math.min(rem, irpLeft);    rem -= i;
    const s = Math.min(rem, isaLeft);    rem -= s;
    setPension(String(Math.round(p / 10000)));
    setIrp(String(Math.round(i / 10000)));
    setIsa(String(Math.round(s / 10000)));
    setGeneral(String(Math.round(rem / 10000)));
  }

  const allocSum = (Number(pension) + Number(irp) + Number(isa) + Number(general)) * 10000;
  const totalAmt = Number(total) * 10000;
  const diff = totalAmt - allocSum;

  async function save() {
    setSaving(true);
    await fetch("/api/workbook/monthly", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        year: y, month: Number(month),
        total_amount: totalAmt,
        pension: Number(pension) * 10000,
        irp:     Number(irp)     * 10000,
        isa:     Number(isa)     * 10000,
        general: Number(general) * 10000,
        portfolio_value: pfValue ? Number(pfValue) * 10000 : null,
        note: note || null,
      }),
    });
    onSave();
    setSaving(false);
  }

  const inp = "w-full rounded-lg px-3 py-2 text-sm text-white outline-none";
  const inpStyle = { background: "#222222", border: "1px solid #2e2e2e" };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" style={{ background: "rgba(0,0,0,0.85)" }} onClick={onClose}>
      <div className="flex min-h-full items-center justify-center p-4">
      <div className="rounded-2xl p-5 w-full max-w-sm my-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-white">월별 투자 입력</h2>
          <button onClick={onClose} style={{ color: "#6e6e6e" }}>✕</button>
        </div>

        {/* Year / Month */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>연도</label>
            <input type="number" value={year} onChange={(e) => setYear(e.target.value)} onWheel={(e) => e.currentTarget.blur()} className={inp} style={inpStyle} />
          </div>
          <div>
            <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>월</label>
            <select value={month} onChange={(e) => setMonth(e.target.value)}
              className={inp} style={{ ...inpStyle, appearance: "none" }}>
              {MONTH_LABELS.map((l, i) => <option key={i+1} value={i+1}>{l}</option>)}
            </select>
          </div>
        </div>

        {/* Total */}
        <div className="mb-3">
          <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>이달 총 투입금액 (만원)</label>
          <input type="number" value={total} onChange={(e) => setTotal(e.target.value)} onWheel={(e) => e.currentTarget.blur()} className={inp} style={inpStyle} placeholder="예: 417" />
        </div>

        {/* Remaining limits info */}
        {profile && Number(total) > 0 && (
          <div className="rounded-lg p-3 mb-2 text-[12px] space-y-1" style={{ background: "#111111", border: "1px solid #2e2e2e" }}>
            <p className="font-bold mb-1.5" style={{ color: "#6e6e6e" }}>{y}년 잔여 한도</p>
            {[
              { label: "연금저축", left: pensionLeft },
              { label: "IRP", left: irpLeft },
              { label: "ISA", left: isaLeft },
            ].map(({ label, left }) => (
              <div key={label} className="flex justify-between">
                <span style={{ color: "#6e6e6e" }}>{label}</span>
                <span style={{ color: left > 0 ? "#39ff8f" : "#4b5563" }}>{left > 0 ? `${krw(left)} 남음` : "한도 소진"}</span>
              </div>
            ))}
            <button onClick={autoAllocate}
              className="mt-2 w-full rounded py-1.5 text-[12px] font-bold"
              style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
              자동 배분 제안
            </button>
          </div>
        )}

        {/* Allocations */}
        <div className="grid grid-cols-2 gap-2 mb-2">
          {[
            { label: "연금저축", val: pension, set: setPension },
            { label: "IRP",     val: irp,     set: setIrp },
            { label: "ISA",     val: isa,     set: setIsa },
            { label: "일반계좌", val: general, set: setGeneral },
          ].map(({ label, val, set }) => (
            <div key={label}>
              <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>{label}</label>
              <input type="number" value={val} onChange={(e) => set(e.target.value)} onWheel={(e) => e.currentTarget.blur()} className={inp} style={inpStyle} placeholder="만원" />
            </div>
          ))}
        </div>

        {/* Diff indicator */}
        {Number(total) > 0 && (
          <div className="text-[12px] mb-2 flex justify-between rounded-lg px-3 py-2"
            style={{ background: "#111111", border: `1px solid ${Math.abs(diff) < 1000 ? "#1e1e1e" : "#ef444433"}` }}>
            <span style={{ color: "#6e6e6e" }}>배분 합계</span>
            <span style={{ color: Math.abs(diff) < 1000 ? "#39ff8f" : "#ef4444" }}>
              {krw(allocSum)} {Math.abs(diff) >= 1000 ? `(${diff > 0 ? "-" : "+"}${krw(Math.abs(diff))} 차이)` : "✓"}
            </span>
          </div>
        )}

        {/* Portfolio value (optional) */}
        <div className="mb-3">
          <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>현재 포트폴리오 총액 (선택, 만원)</label>
          <input type="number" value={pfValue} onChange={(e) => setPfValue(e.target.value)} onWheel={(e) => e.currentTarget.blur()} className={inp} style={inpStyle} placeholder="실제 평가액 입력 시 목표 추적 정확도 향상" />
        </div>

        <div className="mb-4">
          <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>메모 (선택)</label>
          <input type="text" value={note} onChange={(e) => setNote(e.target.value)} className={inp} style={inpStyle} placeholder="예: 연말 상여 포함" />
        </div>

        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222222", color: "#6e6e6e" }}>취소</button>
          <button onClick={save} disabled={saving || !total}
            className="flex-1 rounded-lg py-2 text-sm font-bold"
            style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
            {saving ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}

// ── LimitBar ───────────────────────────────────────────────────────────────────
function LimitBar({ label, used, limit, color }: { label: string; used: number; limit: number; color: string }) {
  const ratio = limit > 0 ? Math.min(used / limit, 1) : 0;
  return (
    <div>
      <div className="flex justify-between text-[12px] mb-1">
        <span style={{ color: "#a8a8a8" }}>{label}</span>
        <span style={{ color: ratio >= 1 ? "#39ff8f" : "#6b7280" }}>
          {krw(used)} / {krw(limit)}
          {ratio >= 1 && <span className="ml-1 font-bold" style={{ color: "#39ff8f" }}>완납 ✓</span>}
        </span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "#202020" }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${ratio * 100}%`, background: color }} />
      </div>
    </div>
  );
}

// ── Strategy Journal Modal ─────────────────────────────────────────────────────
function StrategyModal({ existing, onSave, onClose }: {
  existing?: any;
  onSave: () => void;
  onClose: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate]            = useState(existing?.date ?? today);
  const [marketContext, setMarket] = useState(existing?.market_context ?? "");
  const [strategyFocus, setFocus]  = useState(existing?.strategy_focus ?? "");
  const [holdings, setHoldings]    = useState(existing?.holdings ?? "");
  const [concerns, setConcerns]    = useState(existing?.concerns ?? "");
  const [saving, setSaving]        = useState(false);
  const [autoLoading, setAutoLoading] = useState(false);

  async function autoFill() {
    setAutoLoading(true);
    try {
      const [usGate, usRegime, krGate, krRegime, usPos, krPos] = await Promise.allSettled([
        fetch("/api/data/market-gate").then(r => r.json()),
        fetch("/api/data/regime").then(r => r.json()),
        fetch("/api/data/kr/market-gate").then(r => r.json()),
        fetch("/api/data/kr/regime").then(r => r.json()),
        fetch("/api/real/US/positions").then(r => r.json()),
        fetch("/api/real/KR/positions").then(r => r.json()),
      ]);

      // 시장 상황 조합
      const usG = usGate.status === "fulfilled" ? usGate.value : {};
      const usR = usRegime.status === "fulfilled" ? usRegime.value : {};
      const krG = krGate.status === "fulfilled" ? krGate.value : {};
      const krR = krRegime.status === "fulfilled" ? krRegime.value : {};

      const usPart = `미국 ${usR.regime ?? "—"} · 게이트 ${usG.gate ?? "—"} · 체제점수 ${usR.weighted_score?.toFixed(2) ?? "—"}`;
      const krPart = `한국 ${krR.regime ?? "—"} · 게이트 ${krG.gate ?? "—"}${krG.reason ? ` (${krG.reason})` : ""}`;
      setMarket(`${usPart}\n${krPart}`);

      // 보유 종목 조합
      const usPositions: any[] = usPos.status === "fulfilled" ? (usPos.value.positions ?? []) : [];
      const krPositions: any[] = krPos.status === "fulfilled" ? (krPos.value.positions ?? []) : [];
      const allPos = [
        ...usPositions.map((p: any) => ({ ...p, flag: "🇺🇸" })),
        ...krPositions.map((p: any) => ({ ...p, flag: "🇰🇷" })),
      ];

      if (allPos.length === 0) {
        setHoldings("보유 종목 없음");
      } else {
        const lines = allPos.map((p: any) => {
          const pct = p.unrealized_pnl_pct != null
            ? ` ${p.unrealized_pnl_pct >= 0 ? "+" : ""}${(p.unrealized_pnl_pct * 100).toFixed(1)}%`
            : "";
          return `${p.flag} ${p.symbol}${pct}`;
        });
        const totalPnl = [...usPositions, ...krPositions].reduce((s: number, p: any) => s + (p.unrealized_pnl ?? 0), 0);
        const totalCost = [...usPositions, ...krPositions].reduce((s: number, p: any) => s + (p.cost_basis ?? 0), 0);
        const totalPct = totalCost > 0 ? (totalPnl / totalCost * 100).toFixed(1) : null;
        setHoldings(`${lines.join(", ")} (총 ${allPos.length}종목${totalPct ? ` · 합산 ${Number(totalPct) >= 0 ? "+" : ""}${totalPct}%` : ""})`);
      }
    } finally {
      setAutoLoading(false);
    }
  }

  async function save() {
    setSaving(true);
    await fetch("/api/workbook/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, market_context: marketContext, strategy_focus: strategyFocus, holdings, concerns }),
    });
    onSave();
    setSaving(false);
  }

  const inp = "w-full rounded-lg px-3 py-2 text-sm text-white outline-none resize-none";
  const inpStyle = { background: "#222222", border: "1px solid #2e2e2e" };
  const Label = ({ children }: { children: string }) => (
    <label className="block text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: "#6e6e6e" }}>{children}</label>
  );

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" style={{ background: "rgba(0,0,0,0.85)" }} onClick={onClose}>
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="rounded-2xl p-5 w-full max-w-lg my-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }} onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-white">전략 일지 기록</h2>
            <button onClick={onClose} style={{ color: "#6e6e6e" }}>✕</button>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Label>날짜</Label>
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                  className="rounded-lg px-3 py-2 text-sm text-white outline-none" style={inpStyle} />
              </div>
              <button onClick={autoFill} disabled={autoLoading}
                className="text-[12px] font-bold px-3 py-1.5 rounded-lg mt-4"
                style={{ background: "#facc1518", color: "#facc15", border: "1px solid #facc1533" }}>
                {autoLoading ? "불러오는 중…" : "⚡ 시장·종목 자동 채우기"}
              </button>
            </div>

            <div>
              <Label>시장 상황 (자동)</Label>
              <textarea rows={2} value={marketContext} onChange={(e) => setMarket(e.target.value)}
                className={inp} style={inpStyle} placeholder="⚡ 자동 채우기를 누르면 현재 체제·게이트 데이터를 불러옵니다." />
            </div>
            <div>
              <Label>보유 종목 (자동)</Label>
              <textarea rows={2} value={holdings} onChange={(e) => setHoldings(e.target.value)}
                className={inp} style={inpStyle} placeholder="⚡ 자동 채우기를 누르면 현재 보유 종목과 손익을 불러옵니다." />
            </div>

            <div className="h-px" style={{ background: "#2e2e2e" }} />

            <div>
              <Label>전략 포커스 (직접 작성)</Label>
              <textarea rows={2} value={strategyFocus} onChange={(e) => setFocus(e.target.value)}
                className={inp} style={inpStyle} placeholder="예: PEG보다 EPS 가속도 우선. AI 섹터 비중 유지. 손절 -7~8% 엄격 적용." />
            </div>
            <div>
              <Label>고민 / 우려 (직접 작성)</Label>
              <textarea rows={2} value={concerns} onChange={(e) => setConcerns(e.target.value)}
                className={inp} style={inpStyle} placeholder="예: AI 섹터 집중도 높음. NVDA 비중 과다 여부 재검토 필요." />
            </div>
          </div>

          <div className="flex gap-2 mt-5">
            <button onClick={onClose} className="flex-1 rounded-lg py-2 text-sm font-bold" style={{ background: "#222222", color: "#6e6e6e" }}>취소</button>
            <button onClick={save} disabled={saving}
              className="flex-1 rounded-lg py-2 text-sm font-bold"
              style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
              {saving ? "저장 중…" : "저장"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function buildClaudeContext(entry: any): string {
  const lines = [
    `=== AlphaDesk 전략 일지 (${entry.date}) ===`,
    entry.market_context  ? `시장 상황: ${entry.market_context}`      : null,
    entry.strategy_focus  ? `전략 포커스: ${entry.strategy_focus}`    : null,
    entry.holdings        ? `보유 종목: ${entry.holdings}`            : null,
    entry.concerns        ? `고민/우려: ${entry.concerns}`            : null,
    "",
    "위 내용을 바탕으로 지금 시장에서 전략의 어느 부분에 더 무게를 둘지 같이 점검해보자.",
  ];
  return lines.filter((l) => l !== null).join("\n");
}

// ── Main Page ──────────────────────────────────────────────────────────────────
type WbTab = "plan" | "monthly" | "strategy";

export default function WorkbookPage() {
  const [tab, setTab] = useState<WbTab>("plan");
  const [profile, setProfile] = useState<any>(null);
  const [entries, setEntries] = useState<any[]>([]);
  const [annualUsage, setAnnualUsage] = useState<Record<string, any>>({});
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showMonthlyModal, setShowMonthlyModal] = useState(false);
  const [editEntry, setEditEntry] = useState<any>(null);
  const [showProjection, setShowProjection] = useState(false);
  const [strategyEntries, setStrategyEntries] = useState<any[]>([]);
  const [showStrategyModal, setShowStrategyModal] = useState(false);
  const [editStrategy, setEditStrategy] = useState<any>(null);
  const [copied, setCopied] = useState<number | null>(null);

  const load = useCallback(async () => {
    const [res, sj] = await Promise.all([
      fetch("/api/workbook/monthly").then((r) => r.json()).catch(() => ({})),
      fetch("/api/workbook/strategy").then((r) => r.json()).catch(() => []),
    ]);
    setProfile(res.profile ?? null);
    setEntries(res.entries ?? []);
    setAnnualUsage(res.annualUsage ?? {});
    setStrategyEntries(Array.isArray(sj) ? sj : []);
    if (!res.profile) setShowProfileModal(true);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function deleteEntry(year: number, month: number) {
    await fetch(`/api/workbook/monthly?year=${year}&month=${month}`, { method: "DELETE" });
    load();
  }

  const now = new Date();
  const currentYear = now.getFullYear();
  const thisYearUsage = annualUsage[currentYear] ?? { pension: 0, irp: 0, isa: 0, general: 0, total: 0 };
  const totalInvested = entries.reduce((s, e) => s + e.total_amount, 0);

  // Projection data
  const projection = profile ? buildProjection(
    profile.current_assets,
    profile.annual_capacity,
    profile.target_amount,
    profile.target_year,
    profile.expected_rate,
    currentYear,
    entries,
  ) : [];

  const latestProjected = projection.find((r) => r.year === profile?.target_year)?.projected ?? 0;
  const progressToTarget = profile ? Math.min(latestProjected / profile.target_amount, 1) : 0;
  const currentProjected = projection.find((r) => r.year === currentYear)?.projected ?? profile?.current_assets ?? 0;
  const currentProgress = profile ? currentProjected / profile.target_amount : 0;

  // Tax benefit estimate
  const taxBenefit = profile
    ? Math.min(profile.pension_limit, 9000000) * 0.165   // 연금+IRP 공제 한도 900만 × 16.5%
    : 0;

  const TABS: { id: WbTab; label: string }[] = [
    { id: "plan",     label: "투자 계획" },
    { id: "monthly",  label: "월별 기록" },
    { id: "strategy", label: "전략 일지" },
  ];

  return (
    <div className="space-y-3 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-base font-bold text-white">투자 워크북</h1>
          <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>
            목표를 설정하고 매달 투자 기록을 쌓아가세요
          </p>
        </div>
        <button onClick={() => setShowProfileModal(true)}
          className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-1.5 rounded-lg"
          style={{ background: "#222222", color: "#a8a8a8", border: "1px solid #2e2e2e" }}>
          <Settings size={12} /> 프로필 수정
        </button>
      </div>

      {!profile ? (
        <div className="rounded-xl p-10 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
          <Target size={28} className="mx-auto mb-2" style={{ color: "#39ff8f" }} />
          <p className="text-sm font-bold text-white mb-1">투자 프로필을 먼저 설정하세요</p>
          <p className="text-[12px] mb-4" style={{ color: "#6e6e6e" }}>나이, 목표금액, 계좌 한도를 입력하면 맞춤 계획이 만들어집니다</p>
          <button onClick={() => setShowProfileModal(true)}
            className="text-sm font-bold px-5 py-2 rounded-xl"
            style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
            시작하기
          </button>
        </div>
      ) : (
        <>
          {/* ── Summary cards ── */}
          <div className="grid grid-cols-4 gap-3">
            {[
              {
                label: "현재 추정 자산",
                value: krw(currentProjected),
                sub: `목표의 ${(currentProgress * 100).toFixed(1)}%`,
                color: "var(--text-primary)",
                icon: <Wallet size={14} />,
              },
              {
                label: "목표 달성 예상",
                value: `${profile.target_year}년`,
                sub: `${profile.target_year - currentYear}년 후 · ${krw(latestProjected)}`,
                color: latestProjected >= profile.target_amount ? "#39ff8f" : "#facc15",
                icon: <Target size={14} />,
              },
              {
                label: "총 누적 투입",
                value: krw(totalInvested),
                sub: `원금 기준`,
                color: "#a8a8a8",
                icon: <TrendingUp size={14} />,
              },
              {
                label: "연간 세액공제",
                value: krw(taxBenefit),
                sub: `IRP+연금저축 공제`,
                color: "#39ff8f",
                icon: <TrendingUp size={14} />,
              },
            ].map(({ label, value, sub, color, icon }) => (
              <div key={label} className="rounded-xl p-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                <div className="flex items-center gap-1.5 mb-2" style={{ color: "#6e6e6e" }}>{icon}<p className="text-[12px] uppercase tracking-widest font-bold" style={{ color: "#6e6e6e" }}>{label}</p></div>
                <p className="text-lg font-black" style={{ color }}>{value}</p>
                <p className="text-[12px] mt-0.5" style={{ color: "#6e6e6e" }}>{sub}</p>
              </div>
            ))}
          </div>

          {/* Progress bar */}
          <div className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
            <div className="flex justify-between text-[12px] mb-2">
              <span style={{ color: "#6e6e6e" }}>목표까지 진행률</span>
              <span className="font-bold" style={{ color: "#facc15" }}>
                {krw(currentProjected)} / {krw(profile.target_amount)}
              </span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: "#202020" }}>
              <div className="h-full rounded-full" style={{ width: `${currentProgress * 100}%`, background: "linear-gradient(90deg,#39ff8f,#facc15)" }} />
            </div>
            <p className="text-[12px] mt-1.5 text-right" style={{ color: "#6e6e6e" }}>
              기대수익률 {(profile.expected_rate * 100).toFixed(0)}% 기준 추정값
            </p>
          </div>

          {/* Tabs */}
          <div className="flex rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e", width: "fit-content" }}>
            {TABS.map(({ id, label }) => (
              <button key={id} onClick={() => setTab(id)}
                className="px-5 py-2 text-[12px] font-semibold transition-colors"
                style={{
                  background: tab === id ? "#facc1518" : "transparent",
                  color: tab === id ? "#facc15" : "#6b7280",
                  borderRight: id === "plan" ? "1px solid #1e1e1e" : undefined,
                }}>
                {label}
              </button>
            ))}
          </div>

          {/* ── Plan tab ── */}
          {tab === "plan" && (
            <div className="space-y-3">
              {/* This year limits */}
              <div className="rounded-xl p-4 space-y-3" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[12px] font-bold text-white">{currentYear}년 계좌별 납입 현황</p>
                  <p className="text-[12px]" style={{ color: "#6e6e6e" }}>세액공제 우선 채우기</p>
                </div>
                <LimitBar label="연금저축 (부부합산)" used={thisYearUsage.pension} limit={profile.pension_limit} color="#39ff8f" />
                <LimitBar label="IRP (부부합산)"     used={thisYearUsage.irp}     limit={profile.irp_limit}     color="#60a5fa" />
                <LimitBar label="ISA"                used={thisYearUsage.isa}     limit={profile.isa_limit}     color="#a78bfa" />
                <div className="pt-1 border-t" style={{ borderColor: "#2e2e2e" }}>
                  <div className="flex justify-between text-[12px]">
                    <span style={{ color: "#6e6e6e" }}>일반계좌 투입</span>
                    <span style={{ color: "#a8a8a8" }}>{krw(thisYearUsage.general)}</span>
                  </div>
                  <div className="flex justify-between text-[12px] mt-0.5">
                    <span style={{ color: "#6e6e6e" }}>올해 총 투입</span>
                    <span className="font-bold text-white">{krw(thisYearUsage.total)}</span>
                  </div>
                </div>
              </div>

              {/* Account allocation guide */}
              <div className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                <p className="text-[12px] font-bold text-white mb-2">연간 {krw(profile.annual_capacity)} 최적 배분 가이드</p>
                <div className="space-y-2">
                  {[
                    { label: "① 연금저축", amount: profile.pension_limit, color: "#39ff8f", desc: `세액공제 ${krw(Math.min(profile.pension_limit, 6000000) * 0.165)} 환급` },
                    { label: "② IRP",     amount: profile.irp_limit,     color: "#60a5fa", desc: `추가 세액공제 ${krw(Math.min(profile.irp_limit, 3000000) * 0.165)} 환급` },
                    { label: "③ ISA",     amount: profile.isa_limit,     color: "#a78bfa", desc: "비과세 200만 + 저율과세 9.9%" },
                    { label: "④ 일반계좌", amount: Math.max(0, profile.annual_capacity - profile.pension_limit - profile.irp_limit - profile.isa_limit), color: "#f97316", desc: "미국 직투 · 양도세 250만 공제" },
                  ].map(({ label, amount, color, desc }) => (
                    amount > 0 && (
                      <div key={label} className="flex items-center gap-3 rounded-lg px-3 py-2.5" style={{ background: "#111111", border: "1px solid #1a1a1a" }}>
                        <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                        <div className="flex-1">
                          <span className="text-[12px] font-bold text-white">{label}</span>
                          <span className="ml-2 text-[12px]" style={{ color: "#6e6e6e" }}>{desc}</span>
                        </div>
                        <span className="text-[12px] font-bold shrink-0" style={{ color }}>{krw(amount)}</span>
                      </div>
                    )
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t flex justify-between text-[12px]" style={{ borderColor: "#2e2e2e" }}>
                  <span style={{ color: "#6e6e6e" }}>연간 세액공제 효과</span>
                  <span className="font-bold" style={{ color: "#39ff8f" }}>+{krw(taxBenefit)} 환급</span>
                </div>
              </div>

              {/* Projection table */}
              <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
                <button
                  onClick={() => setShowProjection((v) => !v)}
                  className="w-full flex items-center justify-between px-4 py-3 text-[12px] font-bold text-white"
                  style={{ background: "#1c1c1c" }}>
                  <span>연도별 자산 성장 시뮬레이션</span>
                  {showProjection ? <ChevronUp size={14} style={{ color: "#6e6e6e" }} /> : <ChevronDown size={14} style={{ color: "#6e6e6e" }} />}
                </button>
                {showProjection && (
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr style={{ background: "#111111", borderTop: "1px solid #2e2e2e" }}>
                        {["연도", "나이", "예상 자산", "목표 달성률", ""].map((h) => (
                          <th key={h} className="px-4 py-2.5 text-left text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {projection.map((row) => {
                        const ratio = row.projected / profile.target_amount;
                        const isTarget = row.year === profile.target_year;
                        const isCurrent = row.year === currentYear;
                        const reached = ratio >= 1;
                        return (
                          <tr key={row.year} style={{
                            borderBottom: "1px solid #151515",
                            background: isTarget ? "#facc1508" : isCurrent ? "#39ff8f05" : "transparent",
                          }}>
                            <td className="px-4 py-2.5 font-bold" style={{ color: isTarget ? "#facc15" : isCurrent ? "#39ff8f" : "#9ca3af" }}>
                              {row.year}{isTarget && " ★"}
                            </td>
                            <td className="px-4 py-2.5" style={{ color: "#6e6e6e" }}>
                              {row.year - profile.birth_year + 1}세
                            </td>
                            <td className="px-4 py-2.5 font-bold" style={{ color: reached ? "#39ff8f" : "#fff" }}>
                              {krw(row.projected)}
                            </td>
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-2">
                                <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: "#202020" }}>
                                  <div className="h-full rounded-full" style={{ width: `${Math.min(ratio * 100, 100)}%`, background: reached ? "#39ff8f" : "#facc15" }} />
                                </div>
                                <span style={{ color: reached ? "#39ff8f" : "#9ca3af" }}>{(ratio * 100).toFixed(0)}%</span>
                              </div>
                            </td>
                            <td className="px-4 py-2.5 text-[12px]" style={{ color: "#4a4a4a" }}>
                              {row.isActual ? "실제" : "예측"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {/* ── Strategy Journal tab ── */}
          {tab === "strategy" && (
            <div className="space-y-3">
              {/* 안내 배너 */}
              <div className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                <p className="text-[12px] font-bold text-white mb-1">2주마다 Claude와 전략 점검하기</p>
                <p className="text-[12px]" style={{ color: "#6e6e6e" }}>
                  아래 기록을 저장하고, 새 대화 시작 시 <span style={{ color: "#facc15" }}>📋 복사</span> 버튼으로 내용을 붙여넣으면 이전 맥락 없이도 바로 깊은 이야기가 가능합니다.
                </p>
              </div>

              <div className="flex justify-end">
                <button onClick={() => { setEditStrategy(null); setShowStrategyModal(true); }}
                  className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-1.5 rounded-lg"
                  style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
                  <Plus size={12} /> 오늘 일지 작성
                </button>
              </div>

              {strategyEntries.length === 0 ? (
                <div className="rounded-xl p-10 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                  <p className="text-sm font-bold text-white mb-1">아직 기록이 없습니다</p>
                  <p className="text-[12px]" style={{ color: "#6e6e6e" }}>첫 전략 일지를 작성해보세요</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {strategyEntries.map((entry, idx) => (
                    <div key={entry.id} className="rounded-xl p-4" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-[12px] font-bold" style={{ color: idx === 0 ? "#39ff8f" : "#a8a8a8" }}>
                          {entry.date} {idx === 0 && <span className="ml-1 text-[11px]" style={{ color: "#39ff8f" }}>최신</span>}
                        </span>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(buildClaudeContext(entry));
                              setCopied(entry.id);
                              setTimeout(() => setCopied(null), 2000);
                            }}
                            className="text-[12px] font-bold px-3 py-1 rounded-lg"
                            style={{ background: copied === entry.id ? "#39ff8f22" : "#222222", color: copied === entry.id ? "#39ff8f" : "#facc15", border: `1px solid ${copied === entry.id ? "#39ff8f44" : "#2e2e2e"}` }}>
                            {copied === entry.id ? "✓ 복사됨" : "📋 복사"}
                          </button>
                          <button onClick={() => { setEditStrategy(entry); setShowStrategyModal(true); }}
                            className="text-[12px] px-2 py-1 rounded" style={{ color: "#6e6e6e", background: "#222222" }}>수정</button>
                          <button onClick={async () => {
                            await fetch(`/api/workbook/strategy?date=${entry.date}`, { method: "DELETE" });
                            load();
                          }} className="p-1 rounded" style={{ color: "#4a4a4a" }}>
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        {[
                          { label: "시장 상황",       val: entry.market_context },
                          { label: "전략 포커스",     val: entry.strategy_focus },
                          { label: "보유 종목",       val: entry.holdings },
                          { label: "고민 / 우려",     val: entry.concerns },
                        ].map(({ label, val }) => val ? (
                          <div key={label} className="rounded-lg p-3" style={{ background: "#111111", border: "1px solid #1a1a1a" }}>
                            <p className="text-[11px] font-bold uppercase tracking-widest mb-1" style={{ color: "#4a4a4a" }}>{label}</p>
                            <p className="text-[12px] leading-relaxed" style={{ color: "#a8a8a8" }}>{val}</p>
                          </div>
                        ) : null)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Monthly tab ── */}
          {tab === "monthly" && (
            <div className="space-y-3">
              <div className="flex justify-end">
                <button onClick={() => { setEditEntry(null); setShowMonthlyModal(true); }}
                  className="flex items-center gap-1.5 text-[12px] font-bold px-3 py-1.5 rounded-lg"
                  style={{ background: "#39ff8f18", color: "#39ff8f", border: "1px solid #39ff8f33" }}>
                  <Plus size={12} /> 이달 투자 입력
                </button>
              </div>

              {entries.length === 0 ? (
                <div className="rounded-xl p-10 text-center" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
                  <p className="text-sm font-bold text-white mb-1">아직 기록이 없습니다</p>
                  <p className="text-[12px]" style={{ color: "#6e6e6e" }}>매달 투자 금액을 입력하면 이곳에 쌓입니다</p>
                </div>
              ) : (
                <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #2e2e2e" }}>
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr style={{ background: "#1c1c1c", borderBottom: "1px solid #2e2e2e" }}>
                        {["년/월", "총 투입", "연금저축", "IRP", "ISA", "일반계좌", "포트폴리오", "메모", ""].map((h) => (
                          <th key={h} className="px-3 py-2.5 text-left text-[12px] font-bold uppercase tracking-widest" style={{ color: "#6e6e6e" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {entries.map((e) => (
                        <tr key={e.id} style={{ borderBottom: "1px solid #151515" }}>
                          <td className="px-3 py-2.5 font-bold text-white">{e.year}.{String(e.month).padStart(2,"0")}</td>
                          <td className="px-3 py-2.5 font-bold" style={{ color: "#facc15" }}>{krw(e.total_amount)}</td>
                          <td className="px-3 py-2.5" style={{ color: "#39ff8f" }}>{e.pension > 0 ? krw(e.pension) : "—"}</td>
                          <td className="px-3 py-2.5" style={{ color: "#60a5fa" }}>{e.irp > 0 ? krw(e.irp) : "—"}</td>
                          <td className="px-3 py-2.5" style={{ color: "#a78bfa" }}>{e.isa > 0 ? krw(e.isa) : "—"}</td>
                          <td className="px-3 py-2.5" style={{ color: "#a8a8a8" }}>{e.general > 0 ? krw(e.general) : "—"}</td>
                          <td className="px-3 py-2.5" style={{ color: e.portfolio_value ? "#fff" : "#374151" }}>
                            {e.portfolio_value ? krw(e.portfolio_value) : "—"}
                          </td>
                          <td className="px-3 py-2.5 text-[12px]" style={{ color: "#6e6e6e" }}>{e.note ?? ""}</td>
                          <td className="px-3 py-2.5">
                            <div className="flex gap-1.5">
                              <button onClick={() => { setEditEntry(e); setShowMonthlyModal(true); }}
                                className="text-[12px] px-2 py-0.5 rounded" style={{ color: "#6e6e6e", background: "#222222" }}>수정</button>
                              <button onClick={() => deleteEntry(e.year, e.month)}
                                className="p-1 rounded" style={{ color: "#4a4a4a" }}>
                                <Trash2 size={12} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr style={{ background: "#111111", borderTop: "1px solid #2e2e2e" }}>
                        <td className="px-3 py-2.5 text-[12px] font-bold" style={{ color: "#6e6e6e" }}>합계</td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: "#facc15" }}>{krw(entries.reduce((s,e)=>s+e.total_amount,0))}</td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: "#39ff8f" }}>{krw(entries.reduce((s,e)=>s+e.pension,0))}</td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: "#60a5fa" }}>{krw(entries.reduce((s,e)=>s+e.irp,0))}</td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: "#a78bfa" }}>{krw(entries.reduce((s,e)=>s+e.isa,0))}</td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: "#a8a8a8" }}>{krw(entries.reduce((s,e)=>s+e.general,0))}</td>
                        <td colSpan={3} />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {showProfileModal && (
        <ProfileModal
          initial={profile}
          onClose={() => setShowProfileModal(false)}
          onSave={() => { setShowProfileModal(false); load(); }}
        />
      )}

      {showMonthlyModal && (
        <MonthlyModal
          profile={profile}
          annualUsage={annualUsage}
          existing={editEntry}
          onClose={() => { setShowMonthlyModal(false); setEditEntry(null); }}
          onSave={() => { setShowMonthlyModal(false); setEditEntry(null); load(); }}
        />
      )}

      {showStrategyModal && (
        <StrategyModal
          existing={editStrategy}
          onClose={() => { setShowStrategyModal(false); setEditStrategy(null); }}
          onSave={() => { setShowStrategyModal(false); setEditStrategy(null); load(); }}
        />
      )}
    </div>
  );
}

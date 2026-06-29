"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Check } from "lucide-react";

interface CheckItem {
  id: string;
  text: string;
  checked: boolean;
  note?: string;
}

interface Checklists {
  strategy: CheckItem[];
  sector: CheckItem[];
}

type Section = "strategy" | "sector";

const SECTION_META: Record<Section, { label: string; desc: string; color: string }> = {
  strategy: {
    label: "투자 전략 체크리스트",
    desc: "종목 진입 전 시장 환경과 전략 조건을 점검합니다.",
    color: "#a78bfa",
  },
  sector: {
    label: "섹터/종목 선택 기준",
    desc: "개별 종목 선택 시 재무·기술 조건을 확인합니다.",
    color: "#39ff8f",
  },
};

function uid() {
  return Math.random().toString(36).slice(2, 9);
}

export default function WorkbookPage() {
  const [data, setData] = useState<Checklists>({ strategy: [], sector: [] });
  const [saving, setSaving] = useState<Section | null>(null);
  const [addingNote, setAddingNote] = useState<string | null>(null); // item id
  const [newTexts, setNewTexts] = useState<Record<Section, string>>({ strategy: "", sector: "" });

  const load = useCallback(async () => {
    const res = await fetch("/api/workbook/checklist").then((r) => r.json()).catch(() => null);
    if (res) setData(res);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function save(section: Section, items: CheckItem[]) {
    setSaving(section);
    await fetch("/api/workbook/checklist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: section, items }),
    });
    setSaving(null);
  }

  function toggle(section: Section, id: string) {
    const items = data[section].map((it) => it.id === id ? { ...it, checked: !it.checked } : it);
    setData((d) => ({ ...d, [section]: items }));
    save(section, items);
  }

  function addItem(section: Section) {
    const text = newTexts[section].trim();
    if (!text) return;
    const items = [...data[section], { id: uid(), text, checked: false }];
    setData((d) => ({ ...d, [section]: items }));
    setNewTexts((n) => ({ ...n, [section]: "" }));
    save(section, items);
  }

  function removeItem(section: Section, id: string) {
    const items = data[section].filter((it) => it.id !== id);
    setData((d) => ({ ...d, [section]: items }));
    save(section, items);
  }

  function updateNote(section: Section, id: string, note: string) {
    const items = data[section].map((it) => it.id === id ? { ...it, note } : it);
    setData((d) => ({ ...d, [section]: items }));
    save(section, items);
  }

  function resetSection(section: Section) {
    const items = data[section].map((it) => ({ ...it, checked: false }));
    setData((d) => ({ ...d, [section]: items }));
    save(section, items);
  }

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-base font-bold text-white">투자 워크북</h1>

      {(["strategy", "sector"] as Section[]).map((section) => {
        const meta = SECTION_META[section];
        const items = data[section];
        const checkedCount = items.filter((it) => it.checked).length;
        const allChecked = items.length > 0 && checkedCount === items.length;

        return (
          <div key={section} className="rounded-2xl overflow-hidden" style={{ background: "#1c1c1c", border: "1px solid #2e2e2e" }}>
            {/* 헤더 */}
            <div className="px-4 pt-4 pb-3" style={{ borderBottom: "1px solid #2e2e2e" }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[13px] font-bold" style={{ color: meta.color }}>{meta.label}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[11px]" style={{ color: allChecked ? meta.color : "#4b5563" }}>
                    {checkedCount}/{items.length}
                  </span>
                  <button onClick={() => resetSection(section)}
                    className="text-[10px] px-2 py-1 rounded-lg"
                    style={{ background: "#2a2a2a", color: "#6b7280" }}>
                    초기화
                  </button>
                </div>
              </div>
              <p className="text-[11px]" style={{ color: "#4b5563" }}>{meta.desc}</p>
              {/* 진행 바 */}
              <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: "#2e2e2e" }}>
                <div className="h-full rounded-full transition-all duration-300"
                  style={{ background: meta.color, width: items.length > 0 ? `${(checkedCount / items.length) * 100}%` : "0%" }} />
              </div>
            </div>

            {/* 체크리스트 항목들 */}
            <div className="divide-y" style={{ borderColor: "#222" }}>
              {items.map((item) => (
                <div key={item.id} className="px-4 py-3">
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => toggle(section, item.id)}
                      className="mt-0.5 shrink-0 w-4 h-4 rounded flex items-center justify-center transition-all"
                      style={{
                        background: item.checked ? `${meta.color}33` : "#2a2a2a",
                        border: `1.5px solid ${item.checked ? meta.color : "#444"}`,
                      }}>
                      {item.checked && <Check size={10} color={meta.color} strokeWidth={3} />}
                    </button>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] leading-snug"
                        style={{ color: item.checked ? "#4b5563" : "#d1d5db", textDecoration: item.checked ? "line-through" : "none" }}>
                        {item.text}
                      </p>
                      {/* 메모 */}
                      {addingNote === item.id ? (
                        <input
                          autoFocus
                          defaultValue={item.note ?? ""}
                          onBlur={(e) => { updateNote(section, item.id, e.target.value); setAddingNote(null); }}
                          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                          className="mt-1 w-full px-2 py-1 rounded text-[11px] outline-none"
                          style={{ background: "#141414", color: "#9ca3af", border: "1px solid #333" }}
                          placeholder="메모 입력 후 Enter"
                        />
                      ) : item.note ? (
                        <p className="mt-0.5 text-[11px] cursor-pointer" style={{ color: "#6b7280" }}
                          onClick={() => setAddingNote(item.id)}>
                          💬 {item.note}
                        </p>
                      ) : (
                        <button onClick={() => setAddingNote(item.id)}
                          className="mt-0.5 text-[10px]" style={{ color: "#3a3a3a" }}>
                          + 메모
                        </button>
                      )}
                    </div>
                    <button onClick={() => removeItem(section, item.id)}
                      className="shrink-0 p-1 rounded"
                      style={{ color: "#3a3a3a" }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                      onMouseLeave={(e) => (e.currentTarget.style.color = "#3a3a3a")}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* 항목 추가 */}
            <div className="px-4 py-3" style={{ borderTop: "1px solid #222" }}>
              <div className="flex gap-2">
                <input
                  value={newTexts[section]}
                  onChange={(e) => setNewTexts((n) => ({ ...n, [section]: e.target.value }))}
                  onKeyDown={(e) => { if (e.key === "Enter") addItem(section); }}
                  placeholder="새 항목 추가"
                  className="flex-1 px-3 py-1.5 rounded-lg text-[12px] outline-none"
                  style={{ background: "#141414", color: "#e5e7eb", border: "1px solid #2e2e2e" }}
                />
                <button onClick={() => addItem(section)}
                  className="px-3 py-1.5 rounded-lg"
                  style={{ background: `${meta.color}18`, color: meta.color, border: `1px solid ${meta.color}33` }}>
                  <Plus size={13} />
                </button>
              </div>
              {saving === section && (
                <p className="text-[10px] mt-1" style={{ color: "#4b5563" }}>저장 중…</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

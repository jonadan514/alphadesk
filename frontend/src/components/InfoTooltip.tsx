"use client";

import { useState, useRef, useEffect, useCallback } from "react";

interface InfoTooltipProps {
  content: string | React.ReactNode;
}

export default function InfoTooltip({ content }: InfoTooltipProps) {
  const [visible, setVisible] = useState(false);
  const [side, setSide] = useState<"right" | "left" | "top">("right");
  const btnRef = useRef<HTMLButtonElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  const calcSide = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const BOX_W = 272;
    const BOX_H = 120; // rough estimate

    if (rect.right + BOX_W + 12 <= vw) {
      setSide("right");
    } else if (rect.left - BOX_W - 12 >= 0) {
      setSide("left");
    } else if (rect.top - BOX_H - 12 >= 0) {
      setSide("top");
    } else {
      setSide("right");
    }
  }, []);

  const show = useCallback(() => { calcSide(); setVisible(true); }, [calcSide]);
  const hide = useCallback(() => setVisible(false), []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        btnRef.current && !btnRef.current.contains(e.target as Node) &&
        boxRef.current && !boxRef.current.contains(e.target as Node)
      ) {
        setVisible(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const boxStyle: React.CSSProperties = {
    position: "absolute",
    zIndex: 9999,
    background: "#1a1a1a",
    border: "1px solid #303030",
    borderRadius: 12,
    padding: "12px 16px",
    width: 288,
    color: "#a1a1aa",
    fontSize: 12,
    lineHeight: 1.65,
    boxShadow: "0 12px 40px rgba(0,0,0,0.8)",
    whiteSpace: "normal",
    pointerEvents: "none",
  };

  const arrowBase: React.CSSProperties = {
    position: "absolute",
    width: 8,
    height: 8,
    background: "#1a1a1a",
    border: "1px solid #303030",
    transform: "rotate(45deg)",
  };

  let posStyle: React.CSSProperties = {};
  let arrowStyle: React.CSSProperties = {};

  if (side === "right") {
    posStyle = { left: "calc(100% + 10px)", top: "50%", transform: "translateY(-50%)" };
    arrowStyle = { ...arrowBase, left: -5, top: "50%", marginTop: -4, borderRight: "none", borderTop: "none" };
  } else if (side === "left") {
    posStyle = { right: "calc(100% + 10px)", top: "50%", transform: "translateY(-50%)" };
    arrowStyle = { ...arrowBase, right: -5, top: "50%", marginTop: -4, borderLeft: "none", borderBottom: "none" };
  } else {
    posStyle = { bottom: "calc(100% + 10px)", left: "50%", transform: "translateX(-50%)" };
    arrowStyle = { ...arrowBase, bottom: -5, left: "50%", marginLeft: -4, borderLeft: "none", borderTop: "none" };
  }

  return (
    <span className="relative inline-flex items-center" style={{ verticalAlign: "middle" }}>
      <button
        ref={btnRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        onClick={() => (visible ? hide() : show())}
        aria-label="도움말"
        className="flex items-center justify-center rounded-full text-[12px] font-bold transition-all shrink-0"
        style={{
          width: 16,
          height: 16,
          background: visible ? "#39ff8f22" : "#222",
          color: visible ? "#39ff8f" : "#71717a",
          border: `1px solid ${visible ? "#39ff8f55" : "#333"}`,
          cursor: "default",
          lineHeight: 1,
        }}
      >
        ?
      </button>

      {visible && (
        <div ref={boxRef} style={{ ...boxStyle, ...posStyle }}>
          <span style={arrowStyle} />
          {content}
        </div>
      )}
    </span>
  );
}

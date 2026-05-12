"use client";

import { createContext, useContext, useState, useEffect } from "react";

type Market = "US" | "KR";

interface MarketContextValue {
  market: Market;
  setMarket: (m: Market) => void;
}

const MarketContext = createContext<MarketContextValue>({
  market: "US",
  setMarket: () => {},
});

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [market, setMarketState] = useState<Market>("US");

  useEffect(() => {
    const saved = localStorage.getItem("alphaDesk_market") as Market | null;
    if (saved === "KR" || saved === "US") setMarketState(saved);
  }, []);

  function setMarket(m: Market) {
    setMarketState(m);
    localStorage.setItem("alphaDesk_market", m);
  }

  return (
    <MarketContext.Provider value={{ market, setMarket }}>
      {children}
    </MarketContext.Provider>
  );
}

export function useMarket() {
  return useContext(MarketContext);
}

import Database from "better-sqlite3";
import path from "path";

const PAPER_DB_PATH =
  process.env.PAPER_DB_PATH ??
  path.resolve(process.cwd(), "../output/paper_trading.db");

export function getPaperDb(): Database.Database {
  const db = new Database(PAPER_DB_PATH, { fileMustExist: false });
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  initSchema(db);
  return db;
}

function initSchema(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS paper_portfolio (
      id      INTEGER PRIMARY KEY,
      market  TEXT    UNIQUE NOT NULL,
      initial_capital REAL NOT NULL DEFAULT 10000000,
      cash    REAL    NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS paper_positions (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      market     TEXT    NOT NULL,
      symbol     TEXT    NOT NULL,
      name       TEXT,
      shares     REAL    NOT NULL,
      avg_price  REAL    NOT NULL,
      stop_loss  REAL    NOT NULL,
      grade      TEXT,
      sector     TEXT,
      bought_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
      UNIQUE(market, symbol)
    );

    CREATE TABLE IF NOT EXISTS paper_trades (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      market          TEXT    NOT NULL,
      symbol          TEXT    NOT NULL,
      name            TEXT,
      action          TEXT    NOT NULL,
      shares          REAL    NOT NULL,
      price           REAL    NOT NULL,
      total_amount    REAL    NOT NULL,
      realized_pnl    REAL,
      realized_pnl_pct REAL,
      note            TEXT,
      traded_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS real_positions (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      market     TEXT    NOT NULL,
      symbol     TEXT    NOT NULL,
      name       TEXT,
      shares     REAL    NOT NULL,
      avg_price  REAL    NOT NULL,
      sector     TEXT,
      note       TEXT,
      added_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
      UNIQUE(market, symbol)
    );

    CREATE TABLE IF NOT EXISTS workbook_profile (
      id          INTEGER PRIMARY KEY CHECK (id = 1),
      birth_year  INTEGER NOT NULL DEFAULT 1988,
      target_year INTEGER NOT NULL DEFAULT 2033,
      target_amount    REAL NOT NULL DEFAULT 1000000000,
      current_assets   REAL NOT NULL DEFAULT 0,
      annual_capacity  REAL NOT NULL DEFAULT 50000000,
      pension_limit    REAL NOT NULL DEFAULT 12000000,
      irp_limit        REAL NOT NULL DEFAULT 6000000,
      isa_limit        REAL NOT NULL DEFAULT 20000000,
      expected_rate    REAL NOT NULL DEFAULT 0.15,
      updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS workbook_monthly (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      year        INTEGER NOT NULL,
      month       INTEGER NOT NULL,
      total_amount REAL NOT NULL,
      pension     REAL NOT NULL DEFAULT 0,
      irp         REAL NOT NULL DEFAULT 0,
      isa         REAL NOT NULL DEFAULT 0,
      general     REAL NOT NULL DEFAULT 0,
      portfolio_value REAL,
      note        TEXT,
      recorded_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
      UNIQUE(year, month)
    );

    CREATE TABLE IF NOT EXISTS real_trades (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      market           TEXT    NOT NULL,
      symbol           TEXT    NOT NULL,
      name             TEXT,
      action           TEXT    NOT NULL,
      shares           REAL    NOT NULL,
      price            REAL    NOT NULL,
      total_amount     REAL    NOT NULL,
      realized_pnl     REAL,
      realized_pnl_pct REAL,
      note             TEXT,
      traded_at        TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS strategy_journal (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      date            TEXT    NOT NULL UNIQUE,
      market_context  TEXT,
      strategy_focus  TEXT,
      holdings        TEXT,
      concerns        TEXT,
      recorded_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
    );
  `);
}

export type Portfolio = {
  market: string;
  initial_capital: number;
  cash: number;
  created_at: string;
  updated_at: string;
};

export type Position = {
  id: number;
  market: string;
  symbol: string;
  name: string | null;
  shares: number;
  avg_price: number;
  stop_loss: number;
  grade: string | null;
  sector: string | null;
  bought_at: string;
};

export type Trade = {
  id: number;
  market: string;
  symbol: string;
  name: string | null;
  action: string;
  shares: number;
  price: number;
  total_amount: number;
  realized_pnl: number | null;
  realized_pnl_pct: number | null;
  note: string | null;
  traded_at: string;
};

export function getPortfolio(market: string): Portfolio | null {
  const db = getPaperDb();
  try {
    return (db.prepare("SELECT * FROM paper_portfolio WHERE market = ?").get(market) as Portfolio) ?? null;
  } finally {
    db.close();
  }
}

export function setupPortfolio(market: string, initial_capital: number): Portfolio {
  const db = getPaperDb();
  try {
    db.prepare(`
      INSERT INTO paper_portfolio (market, initial_capital, cash)
      VALUES (?, ?, ?)
      ON CONFLICT(market) DO UPDATE SET
        initial_capital = excluded.initial_capital,
        cash = excluded.initial_capital,
        updated_at = datetime('now','localtime')
    `).run(market, initial_capital, initial_capital);
    // Clear existing positions and trades
    db.prepare("DELETE FROM paper_positions WHERE market = ?").run(market);
    db.prepare("DELETE FROM paper_trades WHERE market = ?").run(market);
    return db.prepare("SELECT * FROM paper_portfolio WHERE market = ?").get(market) as Portfolio;
  } finally {
    db.close();
  }
}

export function getPositions(market: string): Position[] {
  const db = getPaperDb();
  try {
    return db.prepare("SELECT * FROM paper_positions WHERE market = ? ORDER BY bought_at DESC").all(market) as Position[];
  } finally {
    db.close();
  }
}

export function buyStock(params: {
  market: string;
  symbol: string;
  name?: string;
  shares: number;
  price: number;
  grade?: string;
  sector?: string;
}): { ok: boolean; error?: string } {
  const db = getPaperDb();
  try {
    const pf = db.prepare("SELECT * FROM paper_portfolio WHERE market = ?").get(params.market) as Portfolio | undefined;
    if (!pf) return { ok: false, error: "포트폴리오가 설정되지 않았습니다." };

    const total = params.shares * params.price;
    if (total > pf.cash) return { ok: false, error: `현금 부족: 필요 ${total.toFixed(0)}, 보유 ${pf.cash.toFixed(0)}` };

    const stop_loss = params.price * 0.925; // -7.5% stop loss

    // Upsert position (average down if exists)
    const existing = db.prepare("SELECT * FROM paper_positions WHERE market = ? AND symbol = ?")
      .get(params.market, params.symbol) as Position | undefined;

    if (existing) {
      const newShares = existing.shares + params.shares;
      const newAvgPrice = (existing.shares * existing.avg_price + params.shares * params.price) / newShares;
      const newStopLoss = newAvgPrice * 0.925;
      db.prepare(`
        UPDATE paper_positions SET shares = ?, avg_price = ?, stop_loss = ?
        WHERE market = ? AND symbol = ?
      `).run(newShares, newAvgPrice, newStopLoss, params.market, params.symbol);
    } else {
      db.prepare(`
        INSERT INTO paper_positions (market, symbol, name, shares, avg_price, stop_loss, grade, sector)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run(params.market, params.symbol, params.name ?? null, params.shares, params.price, stop_loss, params.grade ?? null, params.sector ?? null);
    }

    // Deduct cash
    db.prepare("UPDATE paper_portfolio SET cash = cash - ?, updated_at = datetime('now','localtime') WHERE market = ?")
      .run(total, params.market);

    // Record trade
    db.prepare(`
      INSERT INTO paper_trades (market, symbol, name, action, shares, price, total_amount, note)
      VALUES (?, ?, ?, 'BUY', ?, ?, ?, 'manual')
    `).run(params.market, params.symbol, params.name ?? null, params.shares, params.price, total);

    return { ok: true };
  } finally {
    db.close();
  }
}

export function sellStock(params: {
  market: string;
  symbol: string;
  shares: number;
  price: number;
  note?: string;
}): { ok: boolean; error?: string } {
  const db = getPaperDb();
  try {
    const pf = db.prepare("SELECT * FROM paper_portfolio WHERE market = ?").get(params.market) as Portfolio | undefined;
    if (!pf) return { ok: false, error: "포트폴리오가 설정되지 않았습니다." };

    const pos = db.prepare("SELECT * FROM paper_positions WHERE market = ? AND symbol = ?")
      .get(params.market, params.symbol) as Position | undefined;
    if (!pos) return { ok: false, error: "보유하지 않은 종목입니다." };
    if (params.shares > pos.shares) return { ok: false, error: `보유 수량 초과: 보유 ${pos.shares}주` };

    const total = params.shares * params.price;
    const costBasis = params.shares * pos.avg_price;
    const realized_pnl = total - costBasis;
    const realized_pnl_pct = costBasis !== 0 ? realized_pnl / costBasis : 0;

    // Update/remove position
    if (Math.abs(params.shares - pos.shares) < 0.0001) {
      db.prepare("DELETE FROM paper_positions WHERE market = ? AND symbol = ?").run(params.market, params.symbol);
    } else {
      db.prepare("UPDATE paper_positions SET shares = shares - ? WHERE market = ? AND symbol = ?")
        .run(params.shares, params.market, params.symbol);
    }

    // Add cash
    db.prepare("UPDATE paper_portfolio SET cash = cash + ?, updated_at = datetime('now','localtime') WHERE market = ?")
      .run(total, params.market);

    // Record trade
    db.prepare(`
      INSERT INTO paper_trades (market, symbol, name, action, shares, price, total_amount, realized_pnl, realized_pnl_pct, note)
      VALUES (?, ?, ?, 'SELL', ?, ?, ?, ?, ?, ?)
    `).run(params.market, params.symbol, pos.name ?? null, params.shares, params.price, total, realized_pnl, realized_pnl_pct, params.note ?? 'manual');

    return { ok: true };
  } finally {
    db.close();
  }
}

export function getTrades(market: string, limit = 50): Trade[] {
  const db = getPaperDb();
  try {
    return db.prepare("SELECT * FROM paper_trades WHERE market = ? ORDER BY traded_at DESC LIMIT ?")
      .all(market, limit) as Trade[];
  } finally {
    db.close();
  }
}

// ── Real Portfolio ─────────────────────────────────────────────────────────────

export type RealPosition = {
  id: number;
  market: string;
  symbol: string;
  name: string | null;
  shares: number;
  avg_price: number;
  sector: string | null;
  note: string | null;
  added_at: string;
};

export function getRealPositions(market: string): RealPosition[] {
  const db = getPaperDb();
  try {
    return db.prepare("SELECT * FROM real_positions WHERE market = ? ORDER BY added_at ASC")
      .all(market) as RealPosition[];
  } finally {
    db.close();
  }
}

export type RealTrade = {
  id: number;
  market: string;
  symbol: string;
  name: string | null;
  action: string;
  shares: number;
  price: number;
  total_amount: number;
  realized_pnl: number | null;
  realized_pnl_pct: number | null;
  note: string | null;
  traded_at: string;
};

export function upsertRealPosition(params: {
  market: string;
  symbol: string;
  name?: string | null;
  shares: number;
  avg_price: number;
  sector?: string | null;
  note?: string | null;
}): { ok: boolean; error?: string } {
  const db = getPaperDb();
  try {
    const existing = db.prepare("SELECT * FROM real_positions WHERE market = ? AND symbol = ?")
      .get(params.market, params.symbol) as RealPosition | undefined;

    if (existing) {
      const newShares = existing.shares + params.shares;
      const newAvg = (existing.shares * existing.avg_price + params.shares * params.avg_price) / newShares;
      db.prepare(`
        UPDATE real_positions SET shares = ?, avg_price = ?, name = COALESCE(?, name), added_at = datetime('now','localtime')
        WHERE market = ? AND symbol = ?
      `).run(newShares, newAvg, params.name ?? null, params.market, params.symbol);
    } else {
      db.prepare(`
        INSERT INTO real_positions (market, symbol, name, shares, avg_price, sector, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run(params.market, params.symbol, params.name ?? null, params.shares, params.avg_price,
             params.sector ?? null, params.note ?? null);
    }

    const total = params.shares * params.avg_price;
    db.prepare(`
      INSERT INTO real_trades (market, symbol, name, action, shares, price, total_amount, note)
      VALUES (?, ?, ?, 'BUY', ?, ?, ?, ?)
    `).run(params.market, params.symbol, params.name ?? null, params.shares, params.avg_price, total, params.note ?? null);

    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: e.message };
  } finally {
    db.close();
  }
}

export function sellRealPosition(params: {
  market: string;
  symbol: string;
  shares: number;
  sell_price: number;
  note?: string | null;
}): { ok: boolean; error?: string } {
  const db = getPaperDb();
  try {
    const pos = db.prepare("SELECT * FROM real_positions WHERE market = ? AND symbol = ?")
      .get(params.market, params.symbol) as RealPosition | undefined;
    if (!pos) return { ok: false, error: "보유하지 않은 종목입니다." };
    if (params.shares > pos.shares + 0.0001) return { ok: false, error: `보유 수량 초과: 보유 ${pos.shares}주` };

    const total = params.shares * params.sell_price;
    const costBasis = params.shares * pos.avg_price;
    const realized_pnl = total - costBasis;
    const realized_pnl_pct = costBasis !== 0 ? realized_pnl / costBasis : 0;

    if (Math.abs(params.shares - pos.shares) < 0.0001) {
      db.prepare("DELETE FROM real_positions WHERE market = ? AND symbol = ?").run(params.market, params.symbol);
    } else {
      db.prepare("UPDATE real_positions SET shares = shares - ? WHERE market = ? AND symbol = ?")
        .run(params.shares, params.market, params.symbol);
    }

    db.prepare(`
      INSERT INTO real_trades (market, symbol, name, action, shares, price, total_amount, realized_pnl, realized_pnl_pct, note)
      VALUES (?, ?, ?, 'SELL', ?, ?, ?, ?, ?, ?)
    `).run(params.market, params.symbol, pos.name ?? null, params.shares, params.sell_price, total,
           realized_pnl, realized_pnl_pct, params.note ?? null);

    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: e.message };
  } finally {
    db.close();
  }
}

export function deleteRealPosition(market: string, symbol: string): { ok: boolean } {
  const db = getPaperDb();
  try {
    db.prepare("DELETE FROM real_positions WHERE market = ? AND symbol = ?").run(market, symbol);
    return { ok: true };
  } finally {
    db.close();
  }
}

export function getRealTrades(market: string, limit = 200): RealTrade[] {
  const db = getPaperDb();
  try {
    return db.prepare("SELECT * FROM real_trades WHERE market = ? ORDER BY traded_at DESC LIMIT ?")
      .all(market, limit) as RealTrade[];
  } finally {
    db.close();
  }
}

// ── Workbook ───────────────────────────────────────────────────────────────────

export type WorkbookProfile = {
  birth_year: number;
  target_year: number;
  target_amount: number;
  current_assets: number;
  annual_capacity: number;
  pension_limit: number;
  irp_limit: number;
  isa_limit: number;
  expected_rate: number;
  updated_at: string;
};

export type WorkbookMonthly = {
  id: number;
  year: number;
  month: number;
  total_amount: number;
  pension: number;
  irp: number;
  isa: number;
  general: number;
  portfolio_value: number | null;
  note: string | null;
  recorded_at: string;
};

export function getWorkbookProfile(): WorkbookProfile | null {
  const db = getPaperDb();
  try {
    return (db.prepare("SELECT * FROM workbook_profile WHERE id = 1").get() as WorkbookProfile) ?? null;
  } finally {
    db.close();
  }
}

export function saveWorkbookProfile(p: Omit<WorkbookProfile, "updated_at">): void {
  const db = getPaperDb();
  try {
    db.prepare(`
      INSERT INTO workbook_profile (id, birth_year, target_year, target_amount, current_assets,
        annual_capacity, pension_limit, irp_limit, isa_limit, expected_rate)
      VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        birth_year = excluded.birth_year, target_year = excluded.target_year,
        target_amount = excluded.target_amount, current_assets = excluded.current_assets,
        annual_capacity = excluded.annual_capacity, pension_limit = excluded.pension_limit,
        irp_limit = excluded.irp_limit, isa_limit = excluded.isa_limit,
        expected_rate = excluded.expected_rate,
        updated_at = datetime('now','localtime')
    `).run(p.birth_year, p.target_year, p.target_amount, p.current_assets,
           p.annual_capacity, p.pension_limit, p.irp_limit, p.isa_limit, p.expected_rate);
  } finally {
    db.close();
  }
}

export function getWorkbookMonthly(): WorkbookMonthly[] {
  const db = getPaperDb();
  try {
    return db.prepare("SELECT * FROM workbook_monthly ORDER BY year DESC, month DESC")
      .all() as WorkbookMonthly[];
  } finally {
    db.close();
  }
}

export function upsertWorkbookMonthly(entry: Omit<WorkbookMonthly, "id" | "recorded_at">): void {
  const db = getPaperDb();
  try {
    db.prepare(`
      INSERT INTO workbook_monthly (year, month, total_amount, pension, irp, isa, general, portfolio_value, note)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(year, month) DO UPDATE SET
        total_amount = excluded.total_amount, pension = excluded.pension,
        irp = excluded.irp, isa = excluded.isa, general = excluded.general,
        portfolio_value = excluded.portfolio_value, note = excluded.note,
        recorded_at = datetime('now','localtime')
    `).run(entry.year, entry.month, entry.total_amount, entry.pension, entry.irp,
           entry.isa, entry.general, entry.portfolio_value ?? null, entry.note ?? null);
  } finally {
    db.close();
  }
}

export function deleteWorkbookMonthly(year: number, month: number): void {
  const db = getPaperDb();
  try {
    db.prepare("DELETE FROM workbook_monthly WHERE year = ? AND month = ?").run(year, month);
  } finally {
    db.close();
  }
}

// ── Strategy Journal ───────────────────────────────────────────────────────────
export type StrategyJournal = {
  id: number;
  date: string;
  market_context: string | null;
  strategy_focus: string | null;
  holdings: string | null;
  concerns: string | null;
  recorded_at: string;
};

export function getStrategyJournal(): StrategyJournal[] {
  const db = getPaperDb();
  try {
    return db.prepare("SELECT * FROM strategy_journal ORDER BY date DESC").all() as StrategyJournal[];
  } finally {
    db.close();
  }
}

export function upsertStrategyJournal(entry: Omit<StrategyJournal, "id" | "recorded_at">): void {
  const db = getPaperDb();
  try {
    db.prepare(`
      INSERT INTO strategy_journal (date, market_context, strategy_focus, holdings, concerns)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(date) DO UPDATE SET
        market_context = excluded.market_context,
        strategy_focus = excluded.strategy_focus,
        holdings = excluded.holdings,
        concerns = excluded.concerns,
        recorded_at = datetime('now','localtime')
    `).run(entry.date, entry.market_context ?? null, entry.strategy_focus ?? null,
           entry.holdings ?? null, entry.concerns ?? null);
  } finally {
    db.close();
  }
}

export function deleteStrategyJournal(date: string): void {
  const db = getPaperDb();
  try {
    db.prepare("DELETE FROM strategy_journal WHERE date = ?").run(date);
  } finally {
    db.close();
  }
}

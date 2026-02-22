"""SQLite database for user portfolio, tracking list, and price targets. BRVM only."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ._data import fetch_palmares
from .brvm_companies import get_valid_symbols

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "brvm_bot.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist."""
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                buy_price REAL NOT NULL,
                buy_date TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
                UNIQUE(telegram_id, symbol)
            );
            CREATE TABLE IF NOT EXISTS tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
                UNIQUE(telegram_id, symbol)
            );
            CREATE TABLE IF NOT EXISTS target_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                target_price REAL NOT NULL,
                direction TEXT NOT NULL CHECK (direction IN ('above', 'below')),
                notified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            );
            CREATE INDEX IF NOT EXISTS idx_portfolio_telegram ON portfolio(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_tracking_telegram ON tracking(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_targets_telegram ON target_alerts(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_targets_pending ON target_alerts(notified) WHERE notified = 0;
        """)
        conn.commit()
        # Migration: add help_sent_at for new-user welcome (ignore if column exists)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN help_sent_at TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()


def get_or_create_user(telegram_id: int) -> None:
    """Ensure user exists."""
    init_db()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
            (telegram_id,),
        )
        conn.commit()
    finally:
        conn.close()


def has_sent_help(telegram_id: int) -> bool:
    """True if we have already sent the help/welcome message to this user."""
    init_db()
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT help_sent_at FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        return row is not None and row[0] is not None
    finally:
        conn.close()


def mark_help_sent(telegram_id: int) -> None:
    """Mark that we have sent the help message to this user."""
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE users SET help_sent_at = datetime('now') WHERE telegram_id = ?",
            (telegram_id,),
        )
        conn.commit()
    finally:
        conn.close()


# --- Portfolio ---
def portfolio_add(telegram_id: int, symbol: str, buy_price: float, buy_date: str, quantity: float = 1.0) -> dict[str, Any]:
    """Add or update a position. Returns {ok, message, error}."""
    get_or_create_user(telegram_id)
    symbol = (symbol or "").strip().upper()
    if symbol not in get_valid_symbols():
        return {"ok": False, "error": f"{symbol} is not a listed BRVM symbol."}
    try:
        d = date.fromisoformat(buy_date.strip()[:10])
        buy_date_str = d.isoformat()
    except ValueError:
        return {"ok": False, "error": f"Invalid buy_date. Use YYYY-MM-DD."}
    if buy_price <= 0 or quantity <= 0:
        return {"ok": False, "error": "buy_price and quantity must be positive."}
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO portfolio (telegram_id, symbol, buy_price, buy_date, quantity)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id, symbol) DO UPDATE SET
                 buy_price=excluded.buy_price, buy_date=excluded.buy_date, quantity=excluded.quantity""",
            (telegram_id, symbol, buy_price, buy_date_str, quantity),
        )
        conn.commit()
        return {"ok": True, "message": f"Added/updated {symbol}: {quantity} @ {buy_price} F CFA on {buy_date_str}."}
    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def portfolio_list(telegram_id: int) -> list[dict[str, Any]]:
    """List portfolio rows for user."""
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol, buy_price, buy_date, quantity, created_at FROM portfolio WHERE telegram_id = ? ORDER BY symbol",
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def portfolio_remove(telegram_id: int, symbol: str) -> dict[str, Any]:
    """Remove a symbol from portfolio."""
    symbol = (symbol or "").strip().upper()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM portfolio WHERE telegram_id = ? AND symbol = ?", (telegram_id, symbol))
        conn.commit()
        if cur.rowcount:
            return {"ok": True, "message": f"Removed {symbol} from your portfolio."}
        return {"ok": False, "error": f"No position in {symbol} in your portfolio."}
    finally:
        conn.close()


def _current_price(symbol: str) -> float | None:
    """Current price from palmarès for one symbol."""
    stocks = fetch_palmares(period="veille", progression="tout")
    for s in stocks:
        if (s.get("symbol") or "").strip().upper() == symbol:
            return s.get("cours_actuel")
    return None


def portfolio_with_prices(telegram_id: int) -> list[dict[str, Any]]:
    """Portfolio rows with current_price and gain_loss_pct (when current price available)."""
    rows = portfolio_list(telegram_id)
    out = []
    for r in rows:
        sym = r["symbol"]
        current = _current_price(sym)
        buy = r["buy_price"]
        gain_pct = None
        if current is not None and buy and buy > 0:
            gain_pct = round((current - buy) / buy * 100, 2)
        out.append({
            **r,
            "current_price": current,
            "gain_loss_pct": gain_pct,
        })
    return out


def portfolio_summary(telegram_id: int) -> dict[str, Any]:
    """Total cost, total value, overall gain/loss %."""
    rows = portfolio_with_prices(telegram_id)
    total_cost = sum(r["buy_price"] * r["quantity"] for r in rows)
    total_value = 0.0
    for r in rows:
        p = r.get("current_price")
        if p is not None:
            total_value += p * r["quantity"]
        else:
            total_value += r["buy_price"] * r["quantity"]  # fallback to cost
    gain_pct = None
    if total_cost and total_cost > 0:
        gain_pct = round((total_value - total_cost) / total_cost * 100, 2)
    return {
        "total_cost_fcfa": round(total_cost, 2),
        "total_value_fcfa": round(total_value, 2),
        "gain_loss_pct": gain_pct,
        "positions_count": len(rows),
    }


# --- Tracking ---
def tracking_list(telegram_id: int) -> list[dict[str, Any]]:
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol, created_at FROM tracking WHERE telegram_id = ? ORDER BY symbol",
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def tracking_add(telegram_id: int, symbol: str) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if symbol not in get_valid_symbols():
        return {"ok": False, "error": f"{symbol} is not a listed BRVM symbol."}
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO tracking (telegram_id, symbol) VALUES (?, ?)", (telegram_id, symbol))
        conn.commit()
        return {"ok": True, "message": f"Added {symbol} to your tracking list."}
    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def tracking_remove(telegram_id: int, symbol: str) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM tracking WHERE telegram_id = ? AND symbol = ?", (telegram_id, symbol))
        conn.commit()
        if cur.rowcount:
            return {"ok": True, "message": f"Removed {symbol} from tracking."}
        return {"ok": False, "error": f"{symbol} was not in your tracking list."}
    finally:
        conn.close()


# --- Target alerts ---
def target_add(telegram_id: int, symbol: str, target_price: float, direction: str = "above") -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if symbol not in get_valid_symbols():
        return {"ok": False, "error": f"{symbol} is not a listed BRVM symbol."}
    if target_price <= 0:
        return {"ok": False, "error": "Target price must be positive."}
    direction = (direction or "above").strip().lower()
    if direction not in ("above", "below"):
        direction = "above"
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO target_alerts (telegram_id, symbol, target_price, direction) VALUES (?, ?, ?, ?)",
            (telegram_id, symbol, target_price, direction),
        )
        conn.commit()
        return {"ok": True, "message": f"Alert set: notify when {symbol} goes {direction} {target_price} F CFA."}
    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def target_list(telegram_id: int) -> list[dict[str, Any]]:
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT symbol, target_price, direction, notified, created_at FROM target_alerts WHERE telegram_id = ? ORDER BY symbol",
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def target_remove(telegram_id: int, symbol: str) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM target_alerts WHERE telegram_id = ? AND symbol = ?", (telegram_id, symbol))
        conn.commit()
        if cur.rowcount:
            return {"ok": True, "message": f"Removed price alert for {symbol}."}
        return {"ok": False, "error": f"No alert set for {symbol}."}
    finally:
        conn.close()


def get_pending_alerts() -> list[dict[str, Any]]:
    """All target alerts that are not yet notified."""
    init_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, telegram_id, symbol, target_price, direction FROM target_alerts WHERE notified = 0"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_alert_notified(alert_id: int) -> None:
    conn = _get_conn()
    try:
        conn.execute("UPDATE target_alerts SET notified = 1 WHERE id = ?", (alert_id,))
        conn.commit()
    finally:
        conn.close()


def check_targets_and_notify() -> list[tuple[int, str]]:
    """For each pending alert, check current price; if target reached, return (telegram_id, message) and mark notified."""
    alerts = get_pending_alerts()
    to_send: list[tuple[int, str]] = []
    for a in alerts:
        symbol = a["symbol"]
        target = a["target_price"]
        direction = a["direction"]
        current = _current_price(symbol)
        if current is None:
            continue
        triggered = False
        if direction == "above" and current >= target:
            triggered = True
        elif direction == "below" and current <= target:
            triggered = True
        if triggered:
            to_send.append((
                a["telegram_id"],
                f"Alert: {symbol} is now {current} F CFA (target {direction} {target} F CFA).",
            ))
            mark_alert_notified(a["id"])
    return to_send

"""User database: portfolio, tracking list, price targets, daily usage. BRVM only.

Backends:
- SQLite (default): local file at app/data/brvm_bot.db — zero config for dev.
- PostgreSQL: when config.DATABASE_URL is set (production / docker compose).

All public functions keep identical signatures on both backends.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import config
from app.utils._data import fetch_palmares
from app.utils.brvm_companies import get_valid_symbols

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "brvm_bot.db"
BACKEND = "postgres" if getattr(config, "DATABASE_URL", "") else "sqlite"

DB_ERRORS: tuple = (sqlite3.Error,)
if BACKEND == "postgres":
    import psycopg

    DB_ERRORS = (sqlite3.Error, psycopg.Error)


def _get_conn():
    if BACKEND == "postgres":
        from psycopg.rows import dict_row

        return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # The bot process (alert job) and the API process (portfolio tools) both
    # write this DB. WAL + busy_timeout prevent cross-process lock errors.
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
    except sqlite3.Error:
        pass
    conn.row_factory = sqlite3.Row
    return conn


def _sql(stmt: str) -> str:
    """Translate SQLite-flavored SQL to the active backend (placeholder + dialect)."""
    if BACKEND == "sqlite":
        return stmt
    out = stmt.replace("?", "%s")
    out = out.replace("MAX(", "GREATEST(")  # scalar max
    out = out.replace("datetime('now')", "CURRENT_TIMESTAMP")
    if out.lstrip().upper().startswith("INSERT OR IGNORE INTO"):
        out = out.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
        out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return out


def _val0(row) -> Any:
    """First column of a row (sqlite3.Row or psycopg dict_row)."""
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


_DDL_SQLITE = [
    """CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        buy_price REAL NOT NULL,
        buy_date TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
        UNIQUE(telegram_id, symbol)
    )""",
    """CREATE TABLE IF NOT EXISTS tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
        UNIQUE(telegram_id, symbol)
    )""",
    """CREATE TABLE IF NOT EXISTS target_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        target_price REAL NOT NULL,
        direction TEXT NOT NULL CHECK (direction IN ('above', 'below')),
        notified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_telegram ON portfolio(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_tracking_telegram ON tracking(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_targets_telegram ON target_alerts(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_targets_pending ON target_alerts(notified) WHERE notified = 0",
    """CREATE TABLE IF NOT EXISTS usage_daily (
        user_id TEXT NOT NULL,
        day TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, day)
    )""",
]

_DDL_POSTGRES = [
    """CREATE TABLE IF NOT EXISTS users (
        telegram_id BIGINT PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS portfolio (
        id BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL,
        symbol TEXT NOT NULL,
        buy_price DOUBLE PRECISION NOT NULL,
        buy_date TEXT NOT NULL,
        quantity DOUBLE PRECISION NOT NULL DEFAULT 1,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
        UNIQUE(telegram_id, symbol)
    )""",
    """CREATE TABLE IF NOT EXISTS tracking (
        id BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL,
        symbol TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
        UNIQUE(telegram_id, symbol)
    )""",
    """CREATE TABLE IF NOT EXISTS target_alerts (
        id BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL,
        symbol TEXT NOT NULL,
        target_price DOUBLE PRECISION NOT NULL,
        direction TEXT NOT NULL CHECK (direction IN ('above', 'below')),
        notified INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_telegram ON portfolio(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_tracking_telegram ON tracking(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_targets_telegram ON target_alerts(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_targets_pending ON target_alerts(notified) WHERE notified = 0",
    """CREATE TABLE IF NOT EXISTS usage_daily (
        user_id TEXT NOT NULL,
        day TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, day)
    )""",
]


def init_db() -> None:
    """Create tables if they do not exist. Cheap to call repeatedly."""
    conn = _get_conn()
    try:
        if BACKEND == "postgres":
            # One round trip in steady state: skip DDL when schema already exists.
            row = conn.execute("SELECT to_regclass('public.users')").fetchone()
            if row and _val0(row) is not None:
                return
            for stmt in _DDL_POSTGRES:
                conn.execute(stmt)
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS help_sent_at TEXT")
            conn.commit()
            return
        for stmt in _DDL_SQLITE:
            conn.execute(stmt)
        conn.commit()
        # Migration: add help_sent_at for new-user welcome (ignore if column exists)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN help_sent_at TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()


def _today_utc() -> str:
    """Current UTC day (UTC == local time for UEMOA users)."""
    return datetime.now(timezone.utc).date().isoformat()


def get_daily_usage(user_id: str) -> int:
    """Number of requests used today by this user key."""
    init_db()
    conn = _get_conn()
    try:
        row = conn.execute(
            _sql("SELECT count FROM usage_daily WHERE user_id = ? AND day = ?"),
            (str(user_id), _today_utc()),
        ).fetchone()
        return int(_val0(row)) if row else 0
    finally:
        conn.close()


def increment_daily_usage(user_id: str) -> int:
    """Count one more request for today; return the new count. Prunes old days."""
    init_db()
    conn = _get_conn()
    try:
        today = _today_utc()
        row = conn.execute(
            # Table-qualified `usage_daily.count`: bare `count` is ambiguous in
            # Postgres upserts (table vs EXCLUDED); SQLite accepts both forms.
            _sql("""
            INSERT INTO usage_daily (user_id, day, count) VALUES (?, ?, 1)
            ON CONFLICT(user_id, day) DO UPDATE SET count = usage_daily.count + 1
            RETURNING count
            """),
            (str(user_id), today),
        ).fetchone()
        conn.execute(_sql("DELETE FROM usage_daily WHERE day < ?"), (today,))
        conn.commit()
        return int(_val0(row)) if row else 0
    finally:
        conn.close()


def decrement_daily_usage(user_id: str) -> None:
    """Refund one request for today (used when a counted request fails)."""
    init_db()
    conn = _get_conn()
    try:
        conn.execute(
            _sql("UPDATE usage_daily SET count = MAX(count - 1, 0) WHERE user_id = ? AND day = ?"),
            (str(user_id), _today_utc()),
        )
        conn.commit()
    finally:
        conn.close()


def get_or_create_user(telegram_id: int) -> None:
    """Ensure user exists."""
    init_db()
    conn = _get_conn()
    try:
        conn.execute(
            _sql("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)"),
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
            _sql("SELECT help_sent_at FROM users WHERE telegram_id = ?"),
            (telegram_id,),
        ).fetchone()
        return row is not None and _val0(row) is not None
    finally:
        conn.close()


def mark_help_sent(telegram_id: int) -> None:
    """Mark that we have sent the help message to this user."""
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        conn.execute(
            _sql("UPDATE users SET help_sent_at = datetime('now') WHERE telegram_id = ?"),
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
        return {"ok": False, "error": f"{symbol} n'est pas un symbole BRVM coté."}
    try:
        d = date.fromisoformat(buy_date.strip()[:10])
        buy_date_str = d.isoformat()
    except ValueError:
        return {"ok": False, "error": "Date d'achat invalide. Utilisez AAAA-MM-JJ."}
    if buy_price <= 0 or quantity <= 0:
        return {"ok": False, "error": "Le prix d'achat et la quantité doivent être positifs."}
    conn = _get_conn()
    try:
        conn.execute(
            _sql("""INSERT INTO portfolio (telegram_id, symbol, buy_price, buy_date, quantity)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id, symbol) DO UPDATE SET
                 buy_price=excluded.buy_price, buy_date=excluded.buy_date, quantity=excluded.quantity"""),
            (telegram_id, symbol, buy_price, buy_date_str, quantity),
        )
        conn.commit()
        return {"ok": True, "message": f"Ajout/mise à jour : {symbol} : {quantity} @ {buy_price} F CFA le {buy_date_str}."}
    except DB_ERRORS as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def portfolio_list(telegram_id: int) -> list[dict[str, Any]]:
    """List portfolio rows for user."""
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        rows = conn.execute(
            _sql("SELECT symbol, buy_price, buy_date, quantity, created_at FROM portfolio WHERE telegram_id = ? ORDER BY symbol"),
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
        cur = conn.execute(_sql("DELETE FROM portfolio WHERE telegram_id = ? AND symbol = ?"), (telegram_id, symbol))
        conn.commit()
        if cur.rowcount:
            return {"ok": True, "message": f"{symbol} retiré de votre portefeuille."}
        return {"ok": False, "error": f"Aucune position {symbol} dans votre portefeuille."}
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
    if total_cost and total_value > 0:
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
            _sql("SELECT symbol, created_at FROM tracking WHERE telegram_id = ? ORDER BY symbol"),
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def tracking_add(telegram_id: int, symbol: str) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if symbol not in get_valid_symbols():
        return {"ok": False, "error": f"{symbol} n'est pas un symbole BRVM coté."}
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        conn.execute(_sql("INSERT OR IGNORE INTO tracking (telegram_id, symbol) VALUES (?, ?)"), (telegram_id, symbol))
        conn.commit()
        return {"ok": True, "message": f"{symbol} ajouté à votre liste de suivi."}
    except DB_ERRORS as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def tracking_remove(telegram_id: int, symbol: str) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    conn = _get_conn()
    try:
        cur = conn.execute(_sql("DELETE FROM tracking WHERE telegram_id = ? AND symbol = ?"), (telegram_id, symbol))
        conn.commit()
        if cur.rowcount:
            return {"ok": True, "message": f"{symbol} retiré du suivi."}
        return {"ok": False, "error": f"{symbol} n'était pas dans votre liste de suivi."}
    finally:
        conn.close()


# --- Target alerts ---
def target_add(telegram_id: int, symbol: str, target_price: float, direction: str = "above") -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if symbol not in get_valid_symbols():
        return {"ok": False, "error": f"{symbol} n'est pas un symbole BRVM coté."}
    if target_price <= 0:
        return {"ok": False, "error": "Le prix cible doit être positif."}
    direction = (direction or "above").strip().lower()
    if direction not in ("above", "below"):
        direction = "above"
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        conn.execute(
            _sql("INSERT INTO target_alerts (telegram_id, symbol, target_price, direction) VALUES (?, ?, ?, ?)"),
            (telegram_id, symbol, target_price, direction),
        )
        conn.commit()
        dir_fr = "au-dessus" if direction == "above" else "en dessous"
        return {"ok": True, "message": f"Alerte définie : notification quand {symbol} atteint {target_price} F CFA ({dir_fr})."}
    except DB_ERRORS as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def target_list(telegram_id: int) -> list[dict[str, Any]]:
    get_or_create_user(telegram_id)
    conn = _get_conn()
    try:
        rows = conn.execute(
            _sql("SELECT symbol, target_price, direction, notified, created_at FROM target_alerts WHERE telegram_id = ? ORDER BY symbol"),
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def target_remove(telegram_id: int, symbol: str) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    conn = _get_conn()
    try:
        cur = conn.execute(_sql("DELETE FROM target_alerts WHERE telegram_id = ? AND symbol = ?"), (telegram_id, symbol))
        conn.commit()
        if cur.rowcount:
            return {"ok": True, "message": f"Alerte de prix supprimée pour {symbol}."}
        return {"ok": False, "error": f"Aucune alerte définie pour {symbol}."}
    finally:
        conn.close()


def get_pending_alerts() -> list[dict[str, Any]]:
    """All target alerts that are not yet notified."""
    init_db()
    conn = _get_conn()
    try:
        rows = conn.execute(
            _sql("SELECT id, telegram_id, symbol, target_price, direction FROM target_alerts WHERE notified = 0")
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_alert_notified(alert_id: int) -> None:
    conn = _get_conn()
    try:
        conn.execute(_sql("UPDATE target_alerts SET notified = 1 WHERE id = ?"), (alert_id,))
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

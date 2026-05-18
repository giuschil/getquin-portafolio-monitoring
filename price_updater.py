import json
import os
from datetime import datetime
import yfinance as yf

STATE_FILE = os.path.join("output", "portfolio_state.json")


def save_portfolio_state(analysis_data: dict):
    """Salva ticker, quantita' e prezzo acquisto dopo ogni analisi screenshot."""
    assets = analysis_data.get("assets", [])
    state = []
    for a in assets:
        ticker = a.get("ticker", "").strip()
        quantity = a.get("quantity", 0)
        purchase_price = a.get("purchase_price", 0)
        name = a.get("name", "")
        if not ticker or ticker.upper() in ("N/A", "", "CASH"):
            continue
        if quantity <= 0:
            # fallback: derive quantity from position_value / current_price
            pv = a.get("position_value", 0)
            cp = a.get("current_price", 0)
            if cp and cp > 0:
                quantity = round(pv / cp, 6)
        state.append({
            "name": name,
            "ticker": ticker,
            "quantity": quantity,
            "purchase_price": purchase_price,
            "last_screenshot": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    os.makedirs("output", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def load_portfolio_state() -> list:
    if not os.path.exists(STATE_FILE):
        return []
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def update_prices_from_market(initial_value: float) -> dict:
    """
    Scarica i prezzi aggiornati da Yahoo Finance per tutti i ticker salvati.
    Restituisce un dict compatibile con la struttura 'result' della dashboard.
    """
    state = load_portfolio_state()
    if not state:
        return {}

    assets = []
    total_value = 0.0

    for item in state:
        ticker = item["ticker"]
        quantity = item.get("quantity", 0)
        purchase_price = item.get("purchase_price", 0)

        try:
            info = yf.Ticker(ticker)
            hist = info.history(period="1d")
            if hist.empty:
                current_price = 0.0
            else:
                current_price = float(hist["Close"].iloc[-1])
        except Exception:
            current_price = 0.0

        position_value = round(current_price * quantity, 2) if current_price else 0.0
        cost_basis = round(purchase_price * quantity, 2)
        pl_eur = round(position_value - cost_basis, 2)
        pl_pct = round((pl_eur / cost_basis * 100) if cost_basis else 0, 2)
        total_value += position_value

        assets.append({
            "name": item["name"],
            "ticker": ticker,
            "purchase_price": purchase_price,
            "current_price": current_price,
            "quantity": quantity,
            "position_value": position_value,
            "profit_loss_eur": pl_eur,
            "profit_loss_percent": pl_pct,
            "weight_percentage": 0.0,  # ricalcolato sotto
            "sentiment": "N/A",
            "recommendation": "N/A",
            "target_price": 0.0,
            "risk_level": "N/A",
            "news_summary": "Aggiornamento prezzi da mercato, nessuna analisi AI.",
            "investment_advice": "",
        })

    # calcola pesi
    for a in assets:
        a["weight_percentage"] = round((a["position_value"] / total_value * 100) if total_value else 0, 2)

    abs_ret = round(total_value - initial_value, 2)
    pct_ret = round((abs_ret / initial_value * 100) if initial_value else 0, 2)

    return {
        "portfolio_summary": {
            "initial_value": initial_value,
            "current_total_value": round(total_value, 2),
            "absolute_return": abs_ret,
            "percentage_return": pct_ret,
            "risk_profile": "",
            "risk_profile_reason": "",
            "strategy_summary": f"Prezzi aggiornati da Yahoo Finance alle {datetime.now().strftime('%H:%M:%S')}.",
            "rebalancing_actions": [],
        },
        "assets": assets,
    }


def has_saved_state() -> bool:
    return os.path.exists(STATE_FILE)

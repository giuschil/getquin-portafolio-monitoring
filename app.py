import os
import json
import glob
import tempfile
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from ai_engine import analyze_portfolio
from price_updater import save_portfolio_state, update_prices_from_market, has_saved_state

if os.path.exists(".env"):
    load_dotenv(".env")

st.set_page_config(page_title="Portfolio Monitor", layout="wide")
st.title("Portfolio Monitor")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Configurazione")
    initial_value = st.number_input(
        "Valore Iniziale (EUR)",
        value=float(os.getenv("INITIAL_PORTFOLIO_VALUE", "55000")),
        step=500.0,
        format="%.2f",
    )
    start_date = st.text_input("Data Inizio (YYYY-MM-DD)", value=os.getenv("PORTFOLIO_START_DATE", "2025-09-01"))

    st.divider()
    st.subheader("Screenshot portafoglio")

    input_dir = "input"
    png_files = sorted(
        glob.glob(os.path.join(input_dir, "*.png")) + glob.glob(os.path.join(input_dir, "*.jpg")),
        key=os.path.getmtime,
        reverse=True,
    )

    image_path = None
    if png_files:
        selected = st.selectbox("Seleziona screenshot", png_files, format_func=os.path.basename)
        st.image(selected, caption=os.path.basename(selected), use_container_width=True)
        image_path = selected
    else:
        uploaded = st.file_uploader("Carica screenshot", type=["png", "jpg", "jpeg"])
        if uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(uploaded.read())
            tmp.flush()
            image_path = tmp.name
            st.image(image_path, use_container_width=True)

    st.divider()
    run_btn = st.button("Analizza portafoglio", type="primary", use_container_width=True)

    update_btn = False
    if has_saved_state():
        st.caption("Portafoglio salvato disponibile.")
        update_btn = st.button("Aggiorna prezzi da mercato", use_container_width=True,
                               help="Scarica i prezzi aggiornati da Yahoo Finance senza usare lo screenshot")

    if st.button("Svuota cache", use_container_width=True):
        st.session_state.pop("result", None)
        st.rerun()

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
if run_btn:
    if not image_path:
        st.error("Seleziona o carica uno screenshot prima di procedere.")
        st.stop()
    with st.spinner("Analisi in corso con Gemini (potrebbe richiedere qualche minuto)..."):
        try:
            raw = analyze_portfolio(image_path, initial_value=str(int(initial_value)), start_date=start_date)
            raw = raw.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            data = json.loads(raw.strip())
            st.session_state["result"] = data
            st.session_state["analyzed_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            # salva ticker + quantita' per aggiornamenti futuri senza screenshot
            saved = save_portfolio_state(data)
            if saved:
                st.success(f"Portafoglio salvato: {len(saved)} titoli pronti per aggiornamento prezzi.")
        except Exception as e:
            st.error(f"Errore: {e}")
            st.stop()

if update_btn:
    with st.spinner("Scaricamento prezzi da Yahoo Finance..."):
        try:
            data = update_prices_from_market(initial_value)
            if not data:
                st.error("Nessun portafoglio salvato. Esegui prima un'analisi screenshot.")
            else:
                st.session_state["result"] = data
                st.session_state["analyzed_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " (prezzi live)"
                st.rerun()
        except Exception as e:
            st.error(f"Errore aggiornamento prezzi: {e}")

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
if "result" not in st.session_state:
    st.info("Configura i parametri nella barra laterale e premi 'Analizza portafoglio'.")
    st.stop()

data = st.session_state["result"]
analyzed_at = st.session_state.get("analyzed_at", "")
summary = data.get("portfolio_summary", {})
assets = data.get("assets", [])
df = pd.DataFrame(assets)

st.caption(f"Ultimo aggiornamento: {analyzed_at}")

# --- KPI ---
c1, c2, c3, c4, c5 = st.columns(5)
curr = summary.get("current_total_value", 0)
init = summary.get("initial_value", 0)
abs_ret = summary.get("absolute_return", 0)
pct_ret = summary.get("percentage_return", 0)
risk = summary.get("risk_profile", "N/A")
risk_reason = summary.get("risk_profile_reason", "")

c1.metric("Valore Attuale", f"{curr:,.0f} EUR")
c2.metric("Valore Iniziale", f"{init:,.0f} EUR")
c3.metric("Rendimento", f"{abs_ret:+,.0f} EUR", delta=f"{pct_ret:+.2f}%")
c4.metric("Profilo Rischio", risk, help=risk_reason)
if not df.empty and "recommendation" in df.columns:
    buy_count = df["recommendation"].isin(["Buy", "Accumulate"]).sum()
    sell_count = df["recommendation"].isin(["Sell", "Reduce"]).sum()
    c5.metric("Buy / Sell", f"{buy_count} / {sell_count}", help="Asset con raccomandazione Buy+Accumulate vs Sell+Reduce")

st.divider()

# --- Strategy + Rebalancing ---
col_s, col_r = st.columns([3, 2])
with col_s:
    st.subheader("Strategia")
    st.info(summary.get("strategy_summary", "N/A"))
with col_r:
    st.subheader("Azioni di ottimizzazione")
    actions = summary.get("rebalancing_actions", [])
    if actions:
        for i, action in enumerate(actions, 1):
            st.markdown(f"**{i}.** {action}")
    else:
        st.caption("Nessuna azione suggerita.")

st.divider()

# --- Charts ---
if not df.empty:
    col_pie, col_bar = st.columns(2)

    with col_pie:
        st.subheader("Allocazione portafoglio")
        fig_pie = px.pie(
            df, values="position_value", names="name",
            hole=0.42, color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_bar:
        st.subheader("P/L per asset (EUR)")
        df_bar = df[df["name"].str.lower() != "liquidita"].copy() if "name" in df.columns else df.copy()
        df_bar = df_bar.sort_values("profit_loss_eur")
        df_bar["color"] = df_bar["profit_loss_eur"].apply(lambda x: "positivo" if x >= 0 else "negativo")
        fig_bar = px.bar(
            df_bar, x="profit_loss_eur", y="name", orientation="h",
            color="color", color_discrete_map={"positivo": "#2ecc71", "negativo": "#e74c3c"},
        )
        fig_bar.update_layout(
            showlegend=False, yaxis_title="", xaxis_title="P/L (EUR)",
            margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # --- Asset Table ---
    st.subheader("Riepilogo asset")

    _RECO_COLORS = {
        "Buy": "#1a7a1a", "Accumulate": "#4caf50",
        "Hold": "#f0ad4e", "Reduce": "#e67e22", "Sell": "#c0392b",
    }
    _SENT_COLORS = {"Bullish": "#2ecc71", "Bearish": "#e74c3c", "Neutral": "#95a5a6"}

    def _style_reco(val):
        bg = _RECO_COLORS.get(val, "")
        return f"background-color:{bg};color:white;font-weight:bold;border-radius:4px" if bg else ""

    def _style_sent(val):
        color = _SENT_COLORS.get(val, "")
        return f"color:{color};font-weight:bold" if color else ""

    table_cols = ["name", "ticker", "position_value", "profit_loss_eur", "profit_loss_percent",
                  "weight_percentage", "sentiment", "recommendation", "risk_level", "target_price"]
    available = [c for c in table_cols if c in df.columns]

    fmt = {}
    if "position_value" in available:
        fmt["position_value"] = "{:,.2f}"
    if "profit_loss_eur" in available:
        fmt["profit_loss_eur"] = "{:+,.2f}"
    if "profit_loss_percent" in available:
        fmt["profit_loss_percent"] = "{:+.2f}%"
    if "weight_percentage" in available:
        fmt["weight_percentage"] = "{:.1f}%"
    if "target_price" in available:
        fmt["target_price"] = lambda x: f"{x:,.2f}" if x and x != 0 else "N/A"

    styled = (
        df[available]
        .style
        .applymap(_style_reco, subset=[c for c in ["recommendation"] if c in available])
        .applymap(_style_sent, subset=[c for c in ["sentiment"] if c in available])
        .format(fmt, na_rep="N/A")
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()

    # --- Investment Advice ---
    st.subheader("Consigli operativi per asset")

    for _, row in df.iterrows():
        name = row.get("name", "")
        if name.lower() in ["liquidita", "liquidità", "cash", "liquidity"]:
            continue
        ticker = row.get("ticker", "")
        reco = row.get("recommendation", "N/A")
        reco_color = _RECO_COLORS.get(reco, "#555")
        label = f"{name} ({ticker})  —  :{reco}:" if ticker else f"{name}  —  {reco}"

        with st.expander(f"{name}  ({ticker})  —  {reco}", expanded=False):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Sentiment", row.get("sentiment", "N/A"))
            m2.metric("Raccomandazione", reco)
            m3.metric("Rischio", row.get("risk_level", "N/A"))
            tp = row.get("target_price")
            m4.metric("Target Price", f"{tp:,.2f} EUR" if tp and tp != 0 else "N/A")
            st.markdown(f"**Consiglio:** {row.get('investment_advice', 'N/A')}")
            st.caption(f"News: {row.get('news_summary', 'N/A')}")

# ---------------------------------------------------------------------------
# Chatbot Gemini
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Chat con Gemini sul tuo portafoglio")

def _build_system_context(data: dict) -> str:
    if not data:
        return "Non hai ancora analizzato il portafoglio. Rispondi in modo generale su finanza e investimenti."
    return (
        "Sei un consulente finanziario esperto. L'utente ha gia' analizzato il suo portafoglio. "
        "Usa questi dati come contesto per rispondere alle sue domande.\n\n"
        f"DATI PORTAFOGLIO:\n{json.dumps(data, ensure_ascii=False, indent=2)}\n\n"
        "Rispondi sempre in italiano, in modo conciso e operativo. "
        "Non ripetere tutti i dati, usa solo quelli rilevanti per la domanda."
    )

def _chat_with_gemini(messages: list, user_input: str, portfolio_data: dict) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "GEMINI_API_KEY non configurata nel file .env."
    client = genai.Client(api_key=api_key)
    system_ctx = _build_system_context(portfolio_data)
    history = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    history.append(types.Content(role="user", parts=[types.Part(text=user_input)]))
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=system_ctx)])] + history,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return response.text
    except Exception as e:
        return f"Errore Gemini: {e}"

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Chiedi qualcosa sul tuo portafoglio...")
if user_input:
    st.session_state["chat_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner("Gemini sta elaborando..."):
            reply = _chat_with_gemini(
                st.session_state["chat_history"][:-1],
                user_input,
                st.session_state.get("result", {}),
            )
        st.markdown(reply)
    st.session_state["chat_history"].append({"role": "assistant", "content": reply})

if st.session_state["chat_history"]:
    if st.button("Pulisci chat"):
        st.session_state["chat_history"] = []
        st.rerun()

import os
import time
import json
import pandas as pd
import schedule
from datetime import datetime
from dotenv import load_dotenv
from scraper import scrape_getquin
from ai_engine import analyze_portfolio

# Controllo se siamo in un ambiente Jupyter per una visualizzazione migliore
try:
    from IPython.display import display
    IN_JUPYTER = True
except ImportError:
    IN_JUPYTER = False

# Carica le variabili d'ambiente dal file .env
# Se non esiste, prova a caricare da .env.example
if os.path.exists(".env"):
    load_dotenv(".env")
elif os.path.exists(".env.example"):
    load_dotenv(".env.example")
else:
    load_dotenv()

def job():
    print(f"\n--- Inizio monitoraggio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # Leggi i dati iniziali del portafoglio dal file .env (se presenti)
    initial_value = os.getenv("INITIAL_PORTFOLIO_VALUE", "55000")
    start_date = os.getenv("PORTFOLIO_START_DATE", "2025-09-01")
    
    # 1. Estrazione dati
    print("Ricerca screenshot del portafoglio...")
    scrape_result = scrape_getquin()
    
    if scrape_result["status"] == "error":
        print(f"Errore:\n{scrape_result['message']}")
        return
        
    image_path = scrape_result.get("image_path")
    
    # 2. Analisi AI
    print("Analisi del portafoglio con Gemini in corso (potrebbe richiedere un minuto per analizzare tutti i titoli)...")
    try:
        analysis_json = analyze_portfolio(image_path, initial_value=initial_value, start_date=start_date)
        
        # Pulizia stringa JSON se Gemini ha aggiunto markdown
        if analysis_json.startswith("```json"):
            analysis_json = analysis_json[7:]
        if analysis_json.endswith("```"):
            analysis_json = analysis_json[:-3]
            
        data = json.loads(analysis_json.strip())
    except Exception as e:
        print(f"Errore durante l'analisi AI o il parsing JSON:\n{str(e)}")
        # Stampa la risposta grezza per debug
        try:
            print(f"Risposta grezza: {analysis_json}")
        except:
            pass
        return
        
    # 3. Creazione DataFrame e Output
    print("\n" + "="*80)
    print("RIASSUNTO PORTAFOGLIO")
    print("="*80)

    summary = data.get("portfolio_summary", {})
    df_summary = pd.DataFrame([summary])

    drop_cols = ["strategy_summary", "risk_profile_reason", "rebalancing_actions"]
    strategy = df_summary["strategy_summary"].iloc[0] if "strategy_summary" in df_summary.columns else "N/A"
    risk_profile = df_summary["risk_profile"].iloc[0] if "risk_profile" in df_summary.columns else "N/A"
    risk_reason = df_summary["risk_profile_reason"].iloc[0] if "risk_profile_reason" in df_summary.columns else ""
    rebalancing = summary.get("rebalancing_actions", [])

    df_summary_display = df_summary.drop(columns=[c for c in drop_cols if c in df_summary.columns])
    if "percentage_return" in df_summary_display.columns:
        df_summary_display["percentage_return"] = df_summary_display["percentage_return"].apply(
            lambda x: f"{x}%" if pd.notna(x) and str(x).strip() != "" else x)

    if IN_JUPYTER:
        display(df_summary_display)
    else:
        print(df_summary_display.to_markdown(index=False))

    print(f"\nRischio portafoglio: {risk_profile} — {risk_reason}")
    print(f"\nStrategia e Conclusioni:\n{strategy}\n")

    if rebalancing:
        print("Azioni di ottimizzazione consigliate:")
        for i, action in enumerate(rebalancing, 1):
            print(f"  {i}. {action}")

    print("\n" + "="*100)
    print("ANALISI ASSET E CONSIGLI INVESTIMENTO")
    print("="*100)

    assets = data.get("assets", [])
    df_assets = pd.DataFrame(assets)

    if not df_assets.empty:
        df_assets_display = df_assets.copy()

        for col in ["weight_percentage", "profit_loss_percent"]:
            if col in df_assets_display.columns:
                df_assets_display[col] = df_assets_display[col].apply(
                    lambda x: f"{x}%" if pd.notna(x) and str(x).strip() != "" else x)

        overview_cols = ["name", "ticker", "position_value", "profit_loss_eur", "profit_loss_percent",
                         "weight_percentage", "sentiment", "recommendation", "risk_level", "target_price"]
        available_cols = [c for c in overview_cols if c in df_assets_display.columns]

        if IN_JUPYTER:
            display(df_assets_display[available_cols])
        else:
            print(df_assets_display[available_cols].to_markdown(index=False))

        print("\nConsigli operativi per asset:")
        advice_cols = ["name", "sentiment", "recommendation", "investment_advice", "news_summary"]
        available_advice_cols = [c for c in advice_cols if c in df_assets_display.columns]

        if IN_JUPYTER:
            display(df_assets_display[available_advice_cols])
        else:
            print(df_assets_display[available_advice_cols].to_markdown(index=False))
    else:
        print("Nessun asset trovato.")

    print("="*100 + "\n")
    
    # 4. Salva i DataFrame in CSV nella cartella output
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    summary_file = os.path.join(output_dir, f"portfolio_summary_{timestamp}.csv")
    assets_file = os.path.join(output_dir, f"portfolio_assets_{timestamp}.csv")
    
    try:
        df_summary.to_csv(summary_file, index=False, sep=";")
        df_assets.to_csv(assets_file, index=False, sep=";")
        print(f"Dati salvati in formato CSV in:")
        print(f"   - {summary_file}")
        print(f"   - {assets_file}")
    except Exception as e:
        print(f"Errore durante il salvataggio dei file CSV: {e}")
        
    print("\nProcesso completato con successo.")

def main():
    print("Avvio del sistema di Portfolio Monitoring.")
    
    # Esegui subito il job
    job()

if __name__ == "__main__":
    main()

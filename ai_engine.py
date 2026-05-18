import os
import time
from datetime import datetime
from google import genai
from google.genai import types
from PIL import Image

_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash"]

def _call_with_retry(client, model, contents, config, retries=3, backoff=10):
    for attempt in range(retries):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < retries - 1:
                    wait = backoff * (2 ** attempt)
                    print(f"Modello {model} non disponibile, riprovo tra {wait}s (tentativo {attempt+1}/{retries})...")
                    time.sleep(wait)
                else:
                    raise
            else:
                raise

_MAX_IMG_WIDTH = 1024

def _resize_image(img):
    if img.width > _MAX_IMG_WIDTH:
        ratio = _MAX_IMG_WIDTH / img.width
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    return img

def analyze_portfolio(image_path, initial_value="55000", start_date="2025-09-01", watchlist_data=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY mancante nel file .env")

    client = genai.Client(api_key=api_key)
    current_date = datetime.now().strftime('%Y-%m-%d')

    prompt = (
        f"Portfolio screenshot analysis. Date:{current_date} InitialValue:{initial_value}EUR Start:{start_date}\n"
        "\n"
        "COLUMN MAPPING (critical — do not confuse these):\n"
        "- 'Posizione' column = CURRENT MARKET VALUE of the position (position_value). This is shares_held x current_price.\n"
        "- 'Buy in' / 'Prezzo medio' column = AVERAGE PURCHASE PRICE per share (purchase_price). This is NOT the position value.\n"
        "- current_price = current market price per single share (derive from position_value / shares if not shown directly)\n"
        "- quantity = number of shares held (derive from position_value / current_price if not shown directly)\n"
        "\n"
        "Tasks:\n"
        "1. Sum ALL values in the 'Posizione' column (incl. liquidita') → current_total_value. Use ONLY 'Posizione' values, never 'Buy in' values.\n"
        "2. absolute_return=current_total_value-initial_value; percentage_return=absolute_return/initial_value*100\n"
        "3. For each asset extract: name, ticker (Yahoo Finance format), purchase_price (from 'Buy in' column, per share), current_price (per share), quantity (shares held), position_value (from 'Posizione' column), profit_loss_eur, profit_loss_percent, weight%\n"
        "4. Google Search per ogni asset (escludi liquidita'): sentiment + analisi fondamentale + tecnica\n"
        "5. Per ogni asset: recommendation (Buy/Accumulate/Hold/Reduce/Sell), target_price (consensus analisti, null se non disponibile), risk_level (Low/Medium/High), max 20-word news_summary, max 40-word investment_advice\n"
        "6. portfolio_optimization: 3-5 rebalancing_actions concrete (stringhe)\n"
        "7. risk_profile (Conservative/Moderate/Aggressive) + risk_profile_reason (max 30 parole)\n"
        "8. strategy_summary: 2 frasi su stato portafoglio e priorita' di intervento\n"
        "Reply ONLY with valid JSON, no markdown fences:\n"
        f'{{"portfolio_summary":{{"initial_value":{initial_value},"current_total_value":0.0,"absolute_return":0.0,"percentage_return":0.0,"risk_profile":"","risk_profile_reason":"","strategy_summary":"","rebalancing_actions":[]}},'
        '"assets":[{"name":"","ticker":"","purchase_price":0.0,"current_price":0.0,"quantity":0.0,"position_value":0.0,"profit_loss_eur":0.0,"profit_loss_percent":0.0,"weight_percentage":0.0,"sentiment":"Bullish|Bearish|Neutral|N/A","recommendation":"Buy|Accumulate|Hold|Reduce|Sell","target_price":0.0,"risk_level":"Low|Medium|High","news_summary":"","investment_advice":""}]}}'
    )

    print("Caricamento immagine e richiesta a Gemini in corso...")

    try:
        img = _resize_image(Image.open(image_path))
    except Exception as e:
        raise ValueError(f"Impossibile aprire l'immagine {image_path}: {e}")

    config = types.GenerateContentConfig(
        tools=[{"google_search": {}}],
        temperature=0
    )

    last_error = None
    for model in _MODELS:
        try:
            print(f"Uso modello: {model}")
            response = _call_with_retry(client, model, [img, prompt], config)
            return response.text
        except Exception as e:
            print(f"Modello {model} fallito: {e}")
            last_error = e

    raise RuntimeError(f"Tutti i modelli Gemini non disponibili. Ultimo errore: {last_error}")

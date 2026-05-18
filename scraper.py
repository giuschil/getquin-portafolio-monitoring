import os
import glob

def scrape_getquin(max_retries=3):
    """
    Cerca l'ultimo screenshot del portafoglio (file .png, .jpg, .jpeg) nella cartella 'input'.
    """
    input_dir = "input"
    
    # Crea la cartella 'input' se non esiste
    os.makedirs(input_dir, exist_ok=True)
    
    print(f"Cerco lo screenshot più recente del portafoglio nella cartella '{input_dir}'...")
    
    # Cerca tutti i file immagine nella cartella input
    image_files = []
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        image_files.extend(glob.glob(os.path.join(input_dir, ext)))
    
    if not image_files:
        return {
            "status": "error", 
            "message": f"Nessun file immagine (.png, .jpg, .jpeg) trovato nella cartella '{input_dir}'. Salva lo screenshot in questa cartella e riavvia lo script."
        }
    
    # Trova il file più recente in base alla data di modifica/creazione
    latest_file = max(image_files, key=os.path.getmtime)
    print(f"Trovato screenshot più recente: {latest_file}")
    
    return {
        "status": "success", 
        "image_path": latest_file,
        "message": f"Screenshot trovato: {latest_file}"
    }

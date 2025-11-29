import json
import google.generativeai as genai
import time
import os
from google.api_core import exceptions

# --- ASETUKSET ---
GOOGLE_API_KEY = "AIzaSyAJzJP0QTfStnyxwfU2edCkQzn7aMwn-0c"

# SUOSITUS: Käytä 'gemini-1.5-flash'. Se on luotettavin.
# Jos haluat kokeilla onneasi Prolla, vaihda tähän 'gemini-2.0-pro-exp'
MODEL_NAME = 'gemini-2.5-flash' 

INPUT_FILE = "structured_data.json"
OUTPUT_FILE = "ai_analyses.json"

def create_analysis_prompt(ac_type, reports):
    context = ""
    # Flashin konteksti-ikkuna on iso (1M tokenia), joten voimme syöttää paljon dataa.
    # Otetaan max 40 viimeisintä tapausta.
    for r in reports[:40]: 
        context += f"--- RAPORTTI {r['date']} ({r['location_name']}) ---\n"
        context += f"{r['summary']}\n\n"

    return f"""
    Toimit Onnettomuustutkintakeskuksen johtavana turvallisuusanalyytikkona.
    Tehtäväsi on analysoida alla oleva aineisto ja tuottaa siitä ammattimainen yhteenveto.
    
    KOHDERYHMÄ: {ac_type}
    AINEISTO:
    {context}
    
    LAADI ANALYYSI (Markdown-muodossa) SEURAAVALLA RAKENTEELLA:
    
    ### ✈️ Analyysi: {ac_type}
    
    **1. Tilannekuva ja trendit**
    Kuvaile lyhyesti, millainen onnettomuusprofiili tällä ryhmällä on Suomessa.
    
    **2. Tunnistetut juurisyyt ja vaaratekijät**
    Erittele 2-3 yleisintä syytä (esim. "Sääolosuhteiden vaikutus", "Tekniset viat", "Inhimillinen tekijä"). Käytä luettelomerkkejä.
    
    **3. Konkreettinen turvallisuussuositus**
    Anna yksi selkeä toimenpidesuositus, jolla vastaavat tapaukset voitaisiin estää.
    
    Kirjoita suomeksi, selkeällä virkakielellä.
    """

def generate_with_backoff(model, prompt):
    """
    Yrittää luoda sisältöä. Jos kiintiö täyttyy, odottaa pidempään ja yrittää uudelleen.
    """
    retries = 5
    wait_time = 10 # Aloitetaan 10 sekunnista
    
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except exceptions.ResourceExhausted:
            print(f"    ⚠️ Kiintiö täynnä (Yritys {attempt+1}/{retries}). Odotetaan {wait_time}s...")
            time.sleep(wait_time)
            wait_time *= 2 # Tuplataan odotusaika: 10s -> 20s -> 40s...
        except Exception as e:
            print(f"    ❌ Muu virhe: {e}")
            return None
            
    return "Analyysi epäonnistui toistuvien yhteysongelmien vuoksi."

def main():
    if not GOOGLE_API_KEY or "AIza" not in GOOGLE_API_KEY:
        print("VIRHE: API-avain puuttuu!")
        return

    genai.configure(api_key=GOOGLE_API_KEY)
    print(f"Alustetaan malli: {MODEL_NAME}...")
    model = genai.GenerativeModel(MODEL_NAME)

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Virhe: {INPUT_FILE} puuttuu. Aja data_enricher.py ensin.")
        return

    grouped_data = {}
    for entry in data:
        ac = entry['aircraft_type']
        if ac not in grouped_data:
            grouped_data[ac] = []
        grouped_data[ac].append(entry)

    analyses = {}
    # Jos haluat säilyttää vanhat analyysit (esim. jos joku onnistui aiemmin), poista kommentit:
    # if os.path.exists(OUTPUT_FILE):
    #    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
    #        analyses = json.load(f)

    print(f"Aloitetaan analyysi {len(grouped_data)} ryhmälle.\n")

    for i, (ac_type, reports) in enumerate(grouped_data.items()):
        key = f"Suomi_{ac_type}"
        
        # Analysoidaan aina uudestaan varmuuden vuoksi
        if len(reports) > 0:
            print(f"[{i+1}/{len(grouped_data)}] Analysoidaan: {ac_type} ({len(reports)} tapausta)...")
            
            prompt = create_analysis_prompt(ac_type, reports)
            result = generate_with_backoff(model, prompt)
            
            if result:
                analyses[key] = result
                print("    ✅ Valmis.")
            
            # Pieni tauko onnistumisenkin jälkeen
            time.sleep(5) 

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analyses, f, ensure_ascii=False, indent=4)

    print(f"\nVALMIS! Analyysit tallennettu: {OUTPUT_FILE}")
    print("Nyt voit päivittää GitHubin.")

if __name__ == "__main__":
    main()
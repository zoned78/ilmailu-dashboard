import json
import google.generativeai as genai
import time
import os
from google.api_core import exceptions

# --- ASETUKSET ---
try:
    import secrets
    GOOGLE_API_KEY = secrets.GOOGLE_API_KEY
except ImportError:
    print("VIRHE: secrets.py -tiedostoa ei löydy!")
    exit()

MODEL_NAME = 'gemini-2.5-flash' 

INPUT_FILE = "structured_data.json"
OUTPUT_FILE = "ai_analyses.json"

def create_analysis_prompt(ac_type, reports):
    context = ""
    
    # Järjestetään aikajärjestykseen
    reports_sorted = sorted(reports, key=lambda x: x.get('date', '9999'))
    
    for r in reports_sorted: 
        context += f"- {r['date']} | {r['location_name']}: {r['summary'][:300]}\n"

    return f"""
    Toimit riippumattomana ilmailuturvallisuuden data-analyytikkona.
    Tehtäväsi on analysoida alla oleva aineisto ja tuottaa siitä objektiivinen yhteenveto.
    
    TÄRKEÄÄ:
    - Älä esiinny viranomaisena (OTKES).
    - Älä käytä ilmaisuja kuten "OTKES toteaa" tai "Suositamme".
    - Käytä neutraaleja ilmaisuja: "Aineistosta nousee esiin...", "Raporteissa toistuu...", "Yleinen havainto on...".
    
    KOHDERYHMÄ: {ac_type}
    TAPAUSTEN MÄÄRÄ: {len(reports)}
    
    AINEISTO (Aikajärjestyksessä):
    {context}
    
    LAADI ANALYYSI (Markdown-muodossa):
    
    ### ✈️ Data-analyysi: {ac_type} ({len(reports)} tapausta)
    
    **1. Havainnot onnettomuusprofiilista**
    Kuvaile lyhyesti, millaisia onnettomuuksia tässä ryhmässä aineiston perusteella tyypillisesti tapahtuu. Miten tilanne on kehittynyt vuosien varrella?
    
    **2. Aineistosta tunnistetut riskitekijät**
    Erittele 2-3 merkittävintä juurisyytä, jotka toistuvat datassa (esim. "Sääolosuhteet", "Tekniset viat").
    
    **3. Yhteenveto turvallisuushavainnoista**
    Tiivistä yksi keskeinen turvallisuusvinkki, joka raporteista on johdettavissa (esim. "Raportit korostavat huolellisuutta...").
    
    Kirjoita suomeksi, selkeällä ja neutraalilla tyylillä.
    """

def generate_with_backoff(model, prompt):
    retries = 5
    wait_time = 10 
    
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except exceptions.ResourceExhausted:
            print(f"    ⚠️ Kiintiö täynnä (Yritys {attempt+1}/{retries}). Odotetaan {wait_time}s...")
            time.sleep(wait_time)
            wait_time *= 2 
        except Exception as e:
            print(f"    ❌ Muu virhe: {e}")
            return None
            
    return "Analyysi epäonnistui."

def main():
    genai.configure(api_key=GOOGLE_API_KEY)
    print(f"Alustetaan malli: {MODEL_NAME}...")
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        print(f"VIRHE: {e}")
        return

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Virhe: {INPUT_FILE} puuttuu.")
        return

    grouped_data = {}
    for entry in data:
        ac = entry['aircraft_type']
        if ac not in grouped_data:
            grouped_data[ac] = []
        grouped_data[ac].append(entry)

    analyses = {}
    
    print(f"Aloitetaan analyysi {len(grouped_data)} ryhmälle (Neutraali sävy).")

    for i, (ac_type, reports) in enumerate(grouped_data.items()):
        key = f"Suomi_{ac_type}"
        
        if len(reports) > 0:
            print(f"[{i+1}/{len(grouped_data)}] Analysoidaan: {ac_type} ({len(reports)} tapausta)...")
            
            prompt = create_analysis_prompt(ac_type, reports)
            result = generate_with_backoff(model, prompt)
            
            if result:
                analyses[key] = result
                print("    ✅ Valmis.")
            
            time.sleep(5) 

    # Kaikki-yhteenveto
    print(f"\n[{len(grouped_data)+1}] Luodaan yhteenveto KAIKISTA...")
    all_prompt = create_analysis_prompt("Kaikki Suomen onnettomuudet", data)
    all_result = generate_with_backoff(model, all_prompt)
    if all_result:
        analyses["Suomi_Kaikki"] = all_result
        print("    ✅ Yhteenveto valmis.")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analyses, f, ensure_ascii=False, indent=4)

    print(f"\nVALMIS! Analyysit tallennettu: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
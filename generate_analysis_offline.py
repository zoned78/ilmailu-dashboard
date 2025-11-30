import json
import google.generativeai as genai
import time
import os
from google.api_core import exceptions

# --- ASETUKSET ---

# 1. Haetaan avain
try:
    import secrets
    GOOGLE_API_KEY = secrets.GOOGLE_API_KEY
except ImportError:
    print("VIRHE: secrets.py -tiedostoa ei löydy!")
    exit()

# 2. Malli: Käytetään Flashia, koska se pystyy lukemaan valtavan määrän tekstiä kerralla.
# Voit kokeilla 'gemini-2.0-flash-exp' tai 'gemini-1.5-flash'
MODEL_NAME = 'gemini-2.5-flash' 

INPUT_FILE = "structured_data.json"
OUTPUT_FILE = "ai_analyses.json"

def create_analysis_prompt(ac_type, reports):
    context = ""
    
    # --- MUUTOS: EI ENÄÄ RAJOITINTA ---
    # Otetaan KAIKKI raportit, mutta pidetään tiivistelmä napakkana (300 merkkiä per raportti).
    # 500 raporttia * 300 merkkiä = 150 000 merkkiä. 
    # Tämä mahtuu helposti Geminin 1 miljoonan tokenin ikkunaan.
    
    # Järjestetään raportit aikajärjestykseen (vanhin ensin), jotta AI hahmottaa kehityksen
    reports_sorted = sorted(reports, key=lambda x: x.get('date', '0'))
    
    for r in reports_sorted: 
        context += f"- {r['date']} | {r['location_name']}: {r['summary'][:300]}\n"

    return f"""
    Toimit Onnettomuustutkintakeskuksen (OTKES) johtavana turvallisuusanalyytikkona.
    Tehtäväsi on analysoida alla oleva aineisto, joka kattaa vuodet 1996–2025.
    
    KOHDERYHMÄ: {ac_type}
    TAPAUSTEN MÄÄRÄ: {len(reports)}
    
    AINEISTO (Aikajärjestyksessä 1996 -> 2025):
    {context}
    
    LAADI ANALYYSI (Markdown-muodossa) SEURAAVALLA RAKENTEELLA:
    
    ### ✈️ Analyysi: {ac_type} ({len(reports)} tapausta)
    
    **1. Historiallinen kehitys ja trendit**
    Kuvaile, miten onnettomuuksien luonne on muuttunut vuosikymmenten aikana (90-luku vs. nykypäivä). Ovatko tietyt onnettomuustyypit vähentyneet tai lisääntyneet?
    
    **2. Keskeiset juurisyyt (Koko aineisto)**
    Erittele 2-3 merkittävintä syytä, jotka toistuvat aineistossa vuodesta toiseen. Etsi yhdistäviä tekijöitä (esim. "Kaasuttimen jäätyminen harrasteilmailussa" tai "Kommunikaatiokatkokset").
    
    **3. Turvallisuussuositus**
    Anna yksi, koko aineiston perusteella tärkein turvallisuusvinkki tälle ryhmälle.
    
    Kirjoita suomeksi, asiantuntevalla tyylillä. Perusta analyysi vain tähän dataan.
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
    
    print(f"Aloitetaan analyysi {len(grouped_data)} ryhmälle.")
    print("Käsitellään koko historiaa (1996-2025), joten promptit ovat suuria.\n")

    # 1. Analysoidaan konetyyppiryhmät
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

    # 2. Analysoidaan "Kaikki" (MASSIVINEN PROMPTI)
    print(f"\n[{len(grouped_data)+1}] Luodaan yhteenveto KAIKISTA ({len(data)} kpl)...")
    all_prompt = create_analysis_prompt("Kaikki Suomen onnettomuudet", data)
    all_result = generate_with_backoff(model, all_prompt)
    
    if all_result:
        analyses["Suomi_Kaikki"] = all_result
        print("    ✅ Yhteenveto valmis.")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analyses, f, ensure_ascii=False, indent=4)

    print(f"\nVALMIS! Kattavat analyysit tallennettu: {OUTPUT_FILE}")
    print("Päivitä GitHub: git add . -> commit -> push")

if __name__ == "__main__":
    main()
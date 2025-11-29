import json
import re

INPUT_FILE = "otkes_db.json"
OUTPUT_FILE = "structured_data.json"

# --- SÄÄNNÖT (TÄRKEYSJÄRJESTYKSESSÄ) ---
# (Kategoria, [Avainsanat], [Kielletyt sanat samassa yhteydessä])
AIRCRAFT_RULES = [
    ("Laskuvarjohyppy", [r"laskuvarjo", r"hyppy", r"pudotus"], []), 
    ("Harraste/Ultrakevyt", [r"ultrakevyt", r"sonerai", r"harraste", r"experimental", r"liidin", r"extra 300", r"rv-8", r"taitolento"], []),
    ("Cessna", [r"cessna", r"c150", r"c152", r"c172", r"c182", r"c206", r"c560"], []),
    ("Diamond", [r"diamond", r"da40", r"da42", r"da62"], []),
    ("Airbus", [r"airbus", r"a319", r"a320", r"a321", r"a330", r"a350"], []),
    ("Boeing", [r"boeing", r"b737", r"b757", r"b787"], []),
    ("ATR", [r"atr 72", r"atr-72", r"atr 42"], []),
    ("Embraer", [r"embraer", r"emb-120"], []),
    # Helikopteri on tarkka: hylätään jos sana on "lääkärihelikopteri" tms.
    ("Helikopteri", [r"helikopteri", r"eurocopter", r"robinson", r"nh90", r"md500", r"heko", r"ec145"], [r"lääkäri", r"pelastus", r"raja", r"lentoavustaja"]),
]

# Paikat ja koordinaatit
LOCATIONS = {
    "Helsinki-Vantaa": (60.3172, 24.9633),
    "Malmi": (60.2546, 25.0428),
    "Ivalo": (68.6073, 27.4053),
    "Pori": (61.4617, 21.7910),
    "Selänpää": (61.0619, 26.7975),
    "Lahti-Vesivehmaa": (61.1436, 25.6872),
    "Jyväskylä": (62.3994, 25.6783), # Tikkakoski
    "Kemi": (65.7788, 24.5821),
    "Kuusamo": (65.9876, 29.2394),
    "Maarianhamina": (60.1222, 19.8982),
    "Hyvinkää": (60.6544, 24.8311),
    "Joensuu": (62.6629, 29.6075),
    "Muhos": (64.8071, 25.9915),
    "Turku": (60.5141, 22.2628),
    "Tampere": (61.4141, 23.6002),
    "Oulu": (64.9301, 25.3546),
    "Rovaniemi": (66.5648, 25.8304),
    "Vaasa": (63.0507, 21.7622),
    "Räyskälä": (60.7447, 24.1046)
}

# Synonyymit (hakusana -> mihin paikkaan liitetään)
SYNONYMS = {
    "muhoks": "Muhos", 
    "muhos": "Muhos",
    "selänpää": "Selänpää", 
    "hyvinkää": "Hyvinkää",
    "joensuu": "Joensuu", 
    "ahvenanmaa": "Maarianhamina",
    "tikkakosk": "Jyväskylä", 
    "jyväskylä": "Jyväskylä",
    "kemi": "Kemi", 
    "vesivehmaa": "Lahti-Vesivehmaa",
    "efhk": "Helsinki-Vantaa", 
    "helsinki": "Helsinki-Vantaa"
}

def detect_aircraft_smart(title, full_text):
    """Tunnistaa konetyypin, painottaen otsikkoa."""
    # Yhdistetään otsikko ja tekstin alku
    text_to_search = (title + " " + full_text[:3000]).lower()
    
    for category, keywords, exclusions in AIRCRAFT_RULES:
        for kw in keywords:
            # Etsitään avainsanaa
            if re.search(kw, text_to_search):
                # TARKISTUS: Onko kielletty sana (esim. "lääkäri") lähellä?
                is_excluded = False
                for exc in exclusions:
                    # Etsitään kiellettyä sanaa 30 merkin säteellä
                    pattern = f"{exc}.{{0,30}}{kw}|{kw}.{{0,30}}{exc}"
                    if re.search(pattern, text_to_search):
                        is_excluded = True
                        break
                
                if not is_excluded:
                    return category

    return "Muu"

def detect_location_smart(title, full_text):
    """Etsii sijaintia ensisijaisesti otsikosta."""
    title_lower = title.lower()
    
    # 1. Etsitään ensin vain otsikosta (Tämä korjaa Muhos/Helsinki -ongelman)
    for syn, real in SYNONYMS.items():
        if syn in title_lower:
            return real
    
    # 2. Jos ei otsikossa, etsitään tekstin alusta
    start_text = full_text[:600].lower()
    for syn, real in SYNONYMS.items():
        # Varmistetaan sanaraja \b ettei "kemikaali" laukaise Kemiä
        if re.search(r'\b' + syn, start_text):
            if syn == "kemi" and "kemikaali" in start_text: continue
            return real
            
    return "Tuntematon"

def create_smart_link(report_id):
    """Luo täsmähaun OTKESin sivuilta tai Googlesta."""
    # Eristetään koodi (esim L2022-01)
    code_match = re.search(r'[A-Z]\d{4}-\d{2}', report_id)
    
    if code_match:
        code = code_match.group(0)
        return f"https://www.google.com/search?q=site:turvallisuustutkinta.fi+{code}"
    else:
        # Jos koodia ei ole, siivotaan otsikko hakusanoiksi
        clean_title = report_id.replace(".pdf", "").replace(".txt", "")
        # Poistetaan turhat sanat
        clean_title = re.sub(r'Selvitys|Tutkintaselostus', '', clean_title, flags=re.IGNORECASE).strip()
        return f"https://www.google.com/search?q=site:turvallisuustutkinta.fi+{clean_title}"

def main():
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Datatiedostoa ei löydy.")
        return

    enriched_data = []
    
    print("Prosessoidaan dataa (Smart Logic)...")
    
    for entry in data:
        # Skipataan indeksisivut
        if "tutkintaselostukset" in entry['id'].lower() and "otkes" not in entry['id'].lower():
             continue
             
        title_id = entry['id']
        content_text = entry['text']
        
        ac_type = detect_aircraft_smart(title_id, content_text)
        loc_name = detect_location_smart(title_id, content_text)
        
        coords = LOCATIONS.get(loc_name)
        smart_url = create_smart_link(title_id)
        
        # Vuosi
        year_match = re.search(r'20\d{2}', title_id)
        date_str = year_match.group(0) if year_match else "N/A"

        new_entry = {
            "id": title_id,
            "date": date_str,
            "aircraft_type": ac_type,
            "country": "Suomi", 
            "location_name": loc_name,
            "lat": coords[0] if coords else None,
            "lon": coords[1] if coords else None,
            "url": smart_url,
            "summary": content_text[:400].replace('\n', ' ') + "..." 
        }
        enriched_data.append(new_entry)
        
        # Debug-tulostus: Näet heti meneekö oikein
        print(f"  > {title_id[:30]}... -> [{ac_type}] @ {loc_name}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=4)
    
    print(f"\nValmis! {len(enriched_data)} tapausta käsitelty.")

if __name__ == "__main__":
    main()
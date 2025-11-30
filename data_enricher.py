import json
import re
import time
import os
import urllib.parse
import google.generativeai as genai
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from google.api_core import exceptions

# --- ASETUKSET ---
INPUT_FILE = "otkes_db.json"
OUTPUT_FILE = "structured_data.json"
LOCATION_CACHE_FILE = "location_cache.json"
AIRCRAFT_CACHE_FILE = "aircraft_cache.json"

# Haetaan API-avain
try:
    import secrets
    GOOGLE_API_KEY = secrets.GOOGLE_API_KEY
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash-exp') 
except ImportError:
    print("VAROITUS: secrets.py puuttuu tai virheellinen. AI-tunnistus ei toimi.")
    model = None

# --- 1. KONETYYPIT ---
AIRCRAFT_RULES = [
    ("Laskuvarjohyppy", [r"laskuvarjo", r"hyppy", r"pudotus"], []), 
    ("Kuumailmapallo", [r"kuumailmapallo", r"pallo-onnettomuus"], []),
    ("Purjelentokone", [r"purjelentokone", r"moottoripurje", r"liidin", r"ls-4", r"ls-8", r"duo discus", r"dg-\d", r"grob", r"szd", r"ask-\d", r"pik-20"], []),
    ("Cessna", [r"cessna", r"c150", r"c152", r"c172", r"c182", r"c185", r"c206", r"c560", r"citation", r"caravan"], []),
    ("Piper", [r"piper", r"pa-28", r"pa-18", r"pa-32", r"pa-34", r"pa-44", r"seneca", r"arrow", r"cub", r"pawnee"], []),
    ("Beechcraft", [r"beech", r"king air", r"bonanza", r"baron"], []),
    ("Diamond", [r"diamond", r"da40", r"da42", r"da20", r"da62", r"katona"], []),
    ("Cirrus", [r"cirrus", r"sr20", r"sr22"], []),
    ("Airbus", [r"airbus", r"a319", r"a320", r"a321", r"a330", r"a340", r"a350"], []),
    ("Boeing", [r"boeing", r"b737", r"b757", r"b787", r"md-11", r"md-8", r"dc-9", r"hornet"], []), 
    ("ATR", [r"atr 72", r"atr-72", r"atr 42", r"atr-42"], []),
    ("Embraer", [r"embraer", r"emb-120", r"e190", r"e170", r"erj"], []),
    ("Bombardier", [r"bombardier", r"crj", r"challenger", r"global express", r"dash 8", r"q400"], []),
    ("Saab", [r"\bsaab\b", r"sf340", r"\b340\b", r"\b2000\b"], []),
    ("Helikopteri", [r"helikopteri", r"eurocopter", r"robinson", r"r44", r"r22", r"nh90", r"md500", r"heko", r"ec135", r"ec145", r"finnhems", r"bell", r"hughes", r"schweizer", r"enstrom", r"cabri", r"agusta"], [r"lääkäri", r"pelastus", r"raja", r"lentoavustaja"]),
    ("Harraste/Ultrakevyt", [r"ultrakevyt", r"ultra", r"sonerai", r"harraste", r"experimental", r"extra 300", r"rv-8", r"taitolento", r"varjoliito", r"riippuliito", r"trike", r"ikarus", r"eurostar", r"c42", r"breezer", r"dynamic", r"autogyro", r"gyrokopteri", r"zephyr", r"fox", r"bekas"], []),
]

# --- 2. PAIKAT ---
LOCATIONS = {
    "Helsinki-Vantaa": (60.3172, 24.9633),
    "Malmi": (60.2546, 25.0428),
    "Ivalo": (68.6073, 27.4053),
    "Pori": (61.4617, 21.7910),
    "Selänpää": (61.0619, 26.7975),
    "Lahti-Vesivehmaa": (61.1436, 25.6872),
    "Jyväskylä": (62.3994, 25.6783),
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
    "Räyskälä": (60.7447, 24.1046),
    "Kitee": (62.1661, 30.0736),
    "Nummela": (60.3328, 24.2956),
    "Jämijärvi": (61.7778, 22.7178),
    "Kauhava": (63.1272, 23.0514),
    "Seinäjoki": (62.6928, 22.8322),
    "Kruunupyy": (63.7211, 23.1431),
    "Savonlinna": (61.9431, 28.9451),
    "Varkaus": (62.1711, 27.8683),
    "Kuopio": (63.0072, 27.7978),
    "Lappeenranta": (61.0446, 28.1443),
    "Kajaani": (64.2855, 27.6924),
    "Enontekiö": (68.3626, 23.4243),
    "Hollola": (61.0550, 25.4350),
    "Haapajärvi": (63.7490, 25.3210),
    "Mikkeli": (61.6886, 27.2022),
    "Porvoo": (60.3930, 25.6650),
    "Kangasala": (61.4634, 24.0738),
    "Vihti": (60.4167, 24.3167),
    "Sipoo": (60.3773, 25.2732),
    "Espoo": (60.2055, 24.6559),
    "Kittilä": (67.7009, 24.8466),
    "Siilinjärvi": (63.0756, 27.6603),
    "Alavus": (62.5523, 23.6176),
    "Kalajoki": (64.2583, 23.9492),
    "Mäntsälä": (60.6360, 25.3194),
    "Pudasjärvi": (65.3974, 26.9973),
    "Immola": (61.2500, 28.9000),
    "Tahkovuori": (63.2319, 28.0333),
    "Kirkkonummi": (60.1167, 24.4333),
    "Tammisaari": (59.9733, 23.4367),
    "Halli": (61.8567, 24.7878),
    "Utti": (60.8964, 26.9381),
    "Viitasaari": (63.0761, 25.7839),
    "Oulainen": (64.2667, 24.8167),
    "Pälkäne": (61.3333, 24.2667),
    "Kälviä": (63.8667, 23.4500),
    "Hattula": (61.0561, 24.3717),
    "Ikaalinen": (61.7667, 23.0667),
    "Nilsiä": (63.2036, 28.0892),
    "Jaatila": (66.3922, 25.5489)
}

SYNONYMS = {
    "helsin": "Helsinki-Vantaa", "vantaa": "Helsinki-Vantaa", "efhk": "Helsinki-Vantaa",
    "malmi": "Malmi", "efhf": "Malmi",
    "turu": "Turku", "turku": "Turku", "eftu": "Turku",
    "tampere": "Tampere", "pirkkala": "Tampere", "eftp": "Tampere",
    "jyväskylä": "Jyväskylä", "tikkakosk": "Jyväskylä", "efjy": "Jyväskylä",
    "oulu": "Oulu", "efou": "Oulu",
    "rovanieme": "Rovaniemi", "rovaniemi": "Rovaniemi", "efro": "Rovaniemi",
    "kuopio": "Kuopio", "efku": "Kuopio",
    "pori": "Pori", "efpo": "Pori",
    "vaasa": "Vaasa", "efva": "Vaasa",
    "joensuu": "Joensuu", "efjo": "Joensuu",
    "lappeenra": "Lappeenranta", "eflp": "Lappeenranta",
    "kajaani": "Kajaani", "efkj": "Kajaani",
    "ivalo": "Ivalo", "efiv": "Ivalo",
    "kemi": "Kemi", "tornio": "Kemi", "efke": "Kemi",
    "maarianhamina": "Maarianhamina", "ahvenanmaa": "Maarianhamina", "efma": "Maarianhamina",
    "kittilä": "Kittilä", "efkt": "Kittilä",
    "kuusamo": "Kuusamo", "efks": "Kuusamo",
    "sodankylä": "Sodankylä", "efso": "Sodankylä",
    "enontekiö": "Enontekiö", "efet": "Enontekiö",
    "halli": "Halli", "efha": "Halli",
    "utti": "Utti", "utin": "Utti", "efut": "Utti",
    "selänpää": "Selänpää",
    "lahti": "Lahti-Vesivehmaa", "vesivehmaa": "Lahti-Vesivehmaa",
    "räyskälä": "Räyskälä",
    "nummela": "Nummela", "vihti": "Nummela",
    "hyvinkää": "Hyvinkää",
    "jämi": "Jämijärvi",
    "kauhava": "Kauhava",
    "seinäjo": "Seinäjoki",
    "kruunupy": "Kruunupyy", "kokkola": "Kruunupyy",
    "savonlinna": "Savonlinna",
    "varkaus": "Varkaus",
    "hollola": "Hollola",
    "haapajärv": "Haapajärvi", "haapave": "Haapavesi",
    "mikkeli": "Mikkeli",
    "porvoo": "Porvoo",
    "kangasala": "Kangasala",
    "sipoo": "Sipoo", "simsalö": "Sipoo",
    "espoo": "Espoo",
    "siilinjärv": "Siilinjärvi",
    "alavu": "Alavus", "menkijärvi": "Alavus",
    "kalajo": "Kalajoki",
    "mäntsälä": "Mäntsälä",
    "pudasjärv": "Pudasjärvi",
    "ylivieska": "Ylivieska",
    "hanko": "Hanko", "hangon": "Hanko",
    "imatra": "Imatra", "immola": "Imatra",
    "ranua": "Ranua",
    "kiuruve": "Kiuruvesi",
    "orive": "Orivesi",
    "sastamala": "Sastamala", "vammala": "Sastamala",
    "siikajo": "Siikajoki", "ruukki": "Siikajoki",
    "iitti": "Iitti", "vuolenkoski": "Iitti",
    "akaa": "Akaa", "kylmäkoski": "Akaa",
    "uusikaarlepyy": "Uusikaarlepyy",
    "kangasniemi": "Kangasniemi",
    "somero": "Somero", "hirsijärvi": "Somero",
    "kaarina": "Kaarina", "piikkiö": "Kaarina",
    "taipalsaari": "Taipalsaari", "taipalsaare": "Taipalsaari",
    "kolari": "Kolari", "äkäs": "Kolari",
    "naantali": "Naantali", "rymättylä": "Naantali",
    "rääkkylä": "Rääkkylä",
    "utsjoki": "Utsjoki",
    "eura": "Eura",
    "pelkosenniemi": "Pelkosenniemi",
    "huittinen": "Huittinen", "vampula": "Huittinen",
    "valkeakoski": "Valkeakoski", "valkeakoske": "Valkeakoski",
    "inkoo": "Inkoo", "torbacka": "Inkoo",
    "laukaa": "Laukaa", "lievestuore": "Laukaa", "leppäve": "Laukaa",
    "mustasaari": "Mustasaari", "petsmo": "Mustasaari",
    "raasepori": "Raasepori", "bromarv": "Raasepori",
    "rautavaara": "Rautavaara",
    "juuka": "Juuka", "juua": "Juuka",
    "kontiolahti": "Kontiolahti",
    "sysmä": "Sysmä",
    "piikajärvi": "Piikajärvi",
    "urjala": "Urjala",
    "pieksämäki": "Pieksämäki", "naarajärvi": "Pieksämäki",
    "salo": "Salo", "kiikala": "Salo",
    "salla": "Salla", "naruska": "Salla",
    "alastaro": "Alastaro",
    "oripää": "Oripää",
    "jämsä": "Jämsä",
    "hattula": "Hattula",
    "riihimäki": "Riihimäki", "riihimäe": "Riihimäki",
    "pertunmaa": "Pertunmaa",
    "parainen": "Parainen", "paraisi": "Parainen",
    "oulainen": "Oulainen", "oulaisi": "Oulainen",
    "viikki": "Helsinki", "laajasalo": "Helsinki",
    "pyhäselkä": "Joensuu",
    "vehmersalmi": "Kuopio", "tahkovuori": "Kuopio", "tahkovuore": "Tahkovuori", "nilsiä": "Kuopio",
    "teisko": "Tampere",
    "kilpisjärvi": "Enontekiö",
    "närpiö": "Närpiö",
    "valkeala": "Valkeala",
    "kerimäki": "Kerimäki", "kerimäe": "Kerimäki",
    "leppävesi": "Leppävesi",
    "kirkkonummi": "Kirkkonummi", "kirkkonumme": "Kirkkonummi",
    "tammisaari": "Tammisaari", "tammisaare": "Tammisaari",
    "viitasaare": "Viitasaari", "viitasaari": "Viitasaari",
    "jaatila": "Jaatila"
}

geolocator = Nominatim(user_agent="ilmailu_dashboard_project_v29_loose_search")

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def clean_soft_hyphens(text):
    if not text: return ""
    return text.replace('\xad', '').replace('\u00ad', '').strip()

# --- AI-TUNNISTUS (RETRY LOGIC) ---
def identify_aircraft_with_ai(text, cache, report_id):
    if report_id in cache:
        return cache[report_id]
    
    if not model: return "Muu"

    prompt = f"""
    Tehtävä: Tunnista onnettomuudessa osallinen ilma-alustyyppi.
    Teksti: "{text[:800]}"
    
    Palauta VAIN YKSI sana seuraavasta listasta (tai valmistaja):
    - Cessna, Piper, Diamond, Cirrus, Beechcraft
    - Airbus, Boeing, ATR, Embraer, Bombardier, Saab
    - Helikopteri, Kuumailmapallo, Purjelentokone, Laskuvarjohyppy
    - Harraste/Ultrakevyt
    - Muu (jos ei mikään yllä mainituista)
    """
    
    retries = 3
    wait_time = 10
    
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            result = response.text.strip().replace("\n", "").replace(".", "")
            if len(result) > 25: result = "Muu"
            
            print(f"    🤖 AI Tunnisti: {result}")
            cache[report_id] = result
            time.sleep(5) 
            return result
            
        except exceptions.ResourceExhausted:
            print(f"    ⚠️ Kiintiö täynnä. Odotetaan {wait_time}s...")
            time.sleep(wait_time)
            wait_time *= 2 
        except Exception as e:
            print(f"    ⚠️ AI Virhe: {e}")
            return "Muu"
            
    return "Muu"

def detect_aircraft_smart(title, full_text, ai_cache, report_id):
    text_to_search = (clean_soft_hyphens(title) + " " + clean_soft_hyphens(full_text)[:3000]).lower()
    for category, keywords, exclusions in AIRCRAFT_RULES:
        for kw in keywords:
            if re.search(kw, text_to_search):
                is_excluded = False
                for exc in exclusions:
                    pattern = f"{exc}.{{0,30}}{kw}|{kw}.{{0,30}}{exc}"
                    if re.search(pattern, text_to_search):
                        is_excluded = True
                        break
                if not is_excluded:
                    return category
    return identify_aircraft_with_ai(clean_soft_hyphens(title) + " " + clean_soft_hyphens(full_text), ai_cache, report_id)

def clean_finnish_location(word):
    w = clean_soft_hyphens(word).lower()
    if not w: return ""
    for syn, real_loc in SYNONYMS.items():
        if syn == w: return real_loc
    suffixes = [("ssa", ""), ("ssä", ""), ("lla", ""), ("llä", ""), ("lta", ""), ("ltä", ""), ("sta", ""), ("stä", ""), ("n", ""), ("a", ""), ("ä", "")]
    base = w
    for suf, rep in suffixes:
        if w.endswith(suf):
            base = w[:-len(suf)] + rep
            break
    return base.capitalize()

def get_coordinates(place_name, cache):
    if not place_name: return None, None, "Tuntematon"
    clean_name = clean_finnish_location(place_name)
    if clean_name in LOCATIONS:
        loc = LOCATIONS[clean_name]
        return loc[0], loc[1], clean_name
    if clean_name in cache:
        val = cache[clean_name]
        if val: return val[0], val[1], clean_name
        return None, None, "Tuntematon"
    try:
        location = geolocator.geocode(f"{clean_name}, Finland", timeout=10)
        if location:
            coords = (location.latitude, location.longitude)
            cache[clean_name] = coords
            time.sleep(1.1)
            return coords[0], coords[1], clean_name
        else: cache[clean_name] = None
    except: pass
    return None, None, "Tuntematon"

def find_location_in_text(text):
    text = clean_soft_hyphens(text)
    text_lower = text[:1000].lower()
    sorted_keys = sorted(SYNONYMS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if re.search(r'\b' + re.escape(key), text_lower):
            if key == "kemi" and "kemikaali" in text_lower: continue
            return SYNONYMS[key]
    return None

def extract_location_from_title(title):
    clean_title = clean_soft_hyphens(title)
    clean = re.sub(r'^[A-Z0-9/]+[- ]?\w*\s+', '', clean_title)
    clean = re.sub(r'\d{1,2}\.\d{1,2}\.\d{4}.*', '', clean)
    title_lower = clean.lower()
    sorted_keys = sorted(SYNONYMS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if re.search(r'\b' + re.escape(key), title_lower):
            if key == "kemi" and "kemikaali" in title_lower: continue
            return SYNONYMS[key]
    return None

# --- UUSI HAKU: Löysä Google-haku ---
def create_smart_link(report_id):
    clean_id = clean_soft_hyphens(report_id)
    
    # Poistetaan tiedostopäätteet
    clean_title = clean_id.replace(".pdf", "").replace(".txt", "").strip()
    
    # Haku ilman site: -rajoitusta, mutta OTKES-kontekstilla
    query = f"{clean_title} OTKES"
    safe_query = urllib.parse.quote(query)
    
    return f"https://www.google.com/search?q={safe_query}"

def main():
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Datatiedostoa ei löydy.")
        return

    location_cache = load_json(LOCATION_CACHE_FILE)
    aircraft_cache = load_json(AIRCRAFT_CACHE_FILE) 
    enriched_data = []
    processed_roots = set()
    
    print("Prosessoidaan dataa (V29 - Loose Search)...")
    
    for entry in data:
        raw_id = clean_soft_hyphens(entry['id'])
        
        is_valid_code = re.match(r'^[A-Z]\d', raw_id) or re.match(r'^[A-Z][0-9]{3}[- ]', raw_id)
        if not is_valid_code:
            if any(x in raw_id.lower() for x in ["tutkintaselostukset", "otkes", "raideliikenne", "vesiliikenne", "sotilas", "muu"]): 
                continue

        id_root = raw_id.lower().replace(".pdf", "").replace(".txt", "").strip()
        if id_root in processed_roots: continue
        processed_roots.add(id_root)
             
        title_id = raw_id
        content_text = clean_soft_hyphens(entry['text'])
        
        ac_type = detect_aircraft_smart(title_id, content_text, aircraft_cache, raw_id)
        
        extracted_place = extract_location_from_title(title_id)
        lat, lon, final_loc_name = get_coordinates(extracted_place, location_cache)
        if not lat:
            text_place = find_location_in_text(content_text)
            if text_place:
                 lat, lon, final_loc_name = get_coordinates(text_place, location_cache)
        if not final_loc_name: final_loc_name = "Tuntematon"

        year_match = re.search(r'20\d{2}|19\d{2}', title_id)
        date_str = year_match.group(0) if year_match else "N/A"

        new_entry = {
            "id": title_id,
            "date": date_str,
            "aircraft_type": ac_type,
            "country": "Suomi", 
            "location_name": final_loc_name,
            "lat": lat,
            "lon": lon,
            "url": create_smart_link(title_id), # Löysä haku
            "summary": content_text[:300].replace('\n', ' ') + "..." 
        }
        enriched_data.append(new_entry)
        
        source = "AI" if raw_id in aircraft_cache else "Regex"
        print(f"  > {title_id[:25]}... -> [{ac_type}] ({source}) @ {final_loc_name}")

    save_json(location_cache, LOCATION_CACHE_FILE)
    save_json(aircraft_cache, AIRCRAFT_CACHE_FILE) 
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=4)
    
    print(f"\nValmis! {len(enriched_data)} tapausta.")

if __name__ == "__main__":
    main()
import json
import re
import time
import os
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

# --- 1. NOPEAT SÄÄNNÖT ---
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
    "Sodankylä": (67.3951, 26.6074),
    "Ylivieska": (64.0586, 24.7075),
    "Hanko": (59.8231, 22.9700),
    "Imatra": (61.1917, 28.7778),
    "Ranua": (65.9270, 26.5175),
    "Kiuruvesi": (63.6525, 26.6200),
    "Jämsä": (61.8642, 25.1900),
    "Hattula": (61.0561, 24.3717),
    "Riihimäki": (60.7389, 24.7736),
    "Haapavesi": (64.1333, 25.3667),
    "Pertunmaa": (61.5028, 26.4778),
    "Parainen": (60.3000, 22.3000),
    "Kauhajoen lentopaikka": (62.4625, 22.3931),
    "Orivesi": (61.6772, 24.3572),
    "Sastamala": (61.3417, 22.9078),
    "Siikajoki": (64.6667, 25.1000),
    "Iitti": (61.0833, 26.1667),
    "Akaa": (61.1500, 23.6833),
    "Uusikaarlepyy": (63.5222, 22.5306),
    "Kangasniemi": (61.9933, 26.6458),
    "Somero": (60.6333, 23.5167),
    "Kaarina": (60.4239, 22.5178),
    "Taipalsaari": (61.1606, 28.0600),
    "Kolari": (67.3311, 23.7908),
    "Naantali": (60.3761, 21.9428),
    "Rääkkylä": (62.3139, 29.6231),
    "Utsjoki": (69.9086, 27.0269),
    "Eura": (61.1319, 22.1331),
    "Pelkosenniemi": (67.1092, 27.5144),
    "Huittinen": (61.0286, 22.6917),
    "Valkeakoski": (61.2667, 24.0333),
    "Inkoo": (60.0667, 24.0667),
    "Laukaa": (62.4144, 25.9527),
    "Mustasaari": (63.1111, 21.7000),
    "Raasepori": (59.9733, 23.4367),
    "Rautavaara": (63.4947, 28.2982),
    "Juuka": (63.2419, 29.2521),
    "Kontiolahti": (62.7654, 29.8469),
    "Sysmä": (61.5036, 25.6856),
    "Piikajärvi": (61.2467, 22.1972),
    "Urjala": (61.0808, 23.5481),
    "Pieksämäki": (62.3006, 27.1336),
    "Salo": (60.3833, 23.1333),
    "Salla": (66.8312, 28.6626),
    "Alastaro": (60.9551, 22.8583),
    "Oripää": (60.8633, 22.6972),
    "Valkeala": (60.9381, 26.8017), # Kouvola
    "Kerimäki": (61.9167, 29.2833), # Savonlinna
    "Ruukki": (64.6667, 25.1000),
    "Leppävesi": (62.2644, 25.8539),
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

# --- 3. SYNONYYMIT ---
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

geolocator = Nominatim(user_agent="ilmailu_dashboard_project_v25_finalfix")

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
    
    # 1. Regex
    for category, keywords, exclusions in AIRCRAFT_RULES:
        for kw in keywords:
            if re.search(kw, text_to_search):
                is_excluded = False
                for exc in exclusions:
                    if re.search(f"{exc}.{{0,30}}{kw}|{kw}.{{0,30}}{exc}", text_to_search):
                        is_excluded = True; break
                if not is_excluded: return category

    # 2. AI Fallback (Jarrulla)
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

# --- TÄSSÄ KORJAUS: POISTETTU 'TITLE'-PARAMETRI ---
def create_smart_link(report_id):
    clean_id = clean_soft_hyphens(report_id)
    code_match = re.search(r'[A-Z]\d{4}-\d{2}|[A-Z]\d+/\d+[A-Z]', clean_id)
    if code_match:
        return f"https://turvallisuustutkinta.fi/fi/index/tutkintaselostukset/ilmailuonnettomuuksientutkinta/tutkintaselostuksetvuosittain.html"
    clean_title = clean_id.replace(".pdf", "").replace(".txt", "")
    clean_title = re.sub(r'Selvitys|Tutkintaselostus', '', clean_title, flags=re.IGNORECASE).strip()
    return f"https://www.google.com/search?q=site:turvallisuustutkinta.fi+{clean_title}"

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
    
    print("Prosessoidaan dataa (V25 - Fixed Arg)...")
    
    for entry in data:
        raw_id = clean_soft_hyphens(entry['id'])
        
        # Whitelist (salli L/C/D/B-alkuiset)
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
            # KORJATTU KUTSU:
            "url": create_smart_link(title_id),
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
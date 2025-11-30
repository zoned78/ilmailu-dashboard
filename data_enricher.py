import json
import re
import time
import os
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

INPUT_FILE = "otkes_db.json"
OUTPUT_FILE = "structured_data.json"
CACHE_FILE = "location_cache.json"

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

# --- 2. PAIKAT (LAAJA LISTA) ---
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
    "Valkeala": (60.9381, 26.8017),
    "Kerimäki": (61.9167, 29.2833),
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
    "Oulainen": (64.2667, 24.8167)
}

geolocator = Nominatim(user_agent="ilmailu_dashboard_project_v18_fix")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

def clean_soft_hyphens(text):
    if not text: return ""
    return text.replace('\xad', '').replace('\u00ad', '').strip()

def clean_finnish_location(word):
    """Palauttaa sanan perusmuodon."""
    w = clean_soft_hyphens(word).lower()
    if not w: return ""
    
    # 1. Tunnetut poikkeukset
    if "helsinki" in w or "vantaa" in w or "efhk" in w: return "Helsinki-Vantaa"
    if "turku" in w or "turun" in w: return "Turku"
    if "tampere" in w: return "Tampere"
    if "maarianhami" in w or "ahvenanmaa" in w: return "Maarianhamina"
    if "jyväskylä" in w or "tikkakosk" in w: return "Jyväskylä"
    if "rovanieme" in w: return "Rovaniemi"
    if "ivalon" in w: return "Ivalo"
    if "utin" in w: return "Utti"

    # 2. Poistetaan sijapäätteet
    suffixes = [("ssa", ""), ("ssä", ""), ("lla", ""), ("llä", ""), ("lta", ""), ("ltä", ""), ("sta", ""), ("stä", ""), ("n", ""), ("a", ""), ("ä", "")]
    base = w
    for suf, rep in suffixes:
        if w.endswith(suf):
            base = w[:-len(suf)] + rep
            break
            
    # 3. KORJATAAN VARTALOVAIHTELUT
    if base.endswith("mäe"): return base[:-3] + "mäki"
    if base.endswith("järve"): return base[:-5] + "järvi"
    if base.endswith("koske"): return base[:-5] + "koski"
    if base.endswith("lahde"): return base[:-5] + "lahti"
    if base.endswith("saare"): return base[:-5] + "saari"
    if base.endswith("niume"): return base[:-5] + "nummi"
    if base.endswith("numme"): return base[:-5] + "nummi"
    if base.endswith("vede"): return base[:-4] + "vesi"
    if base.endswith("vuore"): return base[:-5] + "vuori"
    if base.endswith("joe"): return base[:-3] + "joki"
    if base.endswith("laise"): return base[:-5] + "lainen"
    if base.endswith("aisi"): return base[:-4] + "ainen"
    
    return base.capitalize()

def get_coordinates(place_name, cache):
    if not place_name: return None, None, "Tuntematon"
    
    clean_name = clean_finnish_location(place_name)
    
    # Tarkistetaan ensin suoraan LOCATIONS-listasta (nopein ja varmin)
    if clean_name in LOCATIONS:
        loc = LOCATIONS[clean_name]
        return loc[0], loc[1], clean_name

    # Cache
    if clean_name in cache:
        val = cache[clean_name]
        if val: return val[0], val[1], clean_name
        return None, None, "Tuntematon"
    
    # Haku
    try:
        location = geolocator.geocode(f"{clean_name}, Finland", timeout=10)
        if location:
            coords = (location.latitude, location.longitude)
            cache[clean_name] = coords
            time.sleep(1.1)
            return coords[0], coords[1], clean_name
        else:
            cache[clean_name] = None
    except: pass
    
    return None, None, "Tuntematon"

def find_location_in_text(text):
    """Etsii paikkaa tekstistä."""
    text = clean_soft_hyphens(text)
    text_lower = text[:1000].lower()
    
    # Käydään läpi kaikki tunnetut paikat
    for place_name in LOCATIONS.keys():
        place_lower = place_name.lower()
        # Etsitään sanan perusmuotoa (tai juurta)
        if place_lower in text_lower:
             # Estetään "kemi" vs "kemikaali"
             if place_lower == "kemi" and "kemikaali" in text_lower: continue
             return place_name

    return None

def extract_location_from_title(title):
    clean_title = clean_soft_hyphens(title)
    # Poistetaan ID
    clean = re.sub(r'^[A-Z0-9/]+[- ]?\w*\s+', '', clean_title)
    clean = re.sub(r'\d{1,2}\.\d{1,2}\.\d{4}.*', '', clean)
    
    # Kokeillaan ensin täsmäosumaa tunnettuihin paikkoihin
    title_lower = clean.lower()
    for place_name in LOCATIONS.keys():
        # Taivutus: "Ivalossa" -> "ivalo" in "ivalossa"
        place_lower = place_name.lower()
        if place_lower in title_lower:
             if place_lower == "kemi" and "kemikaali" in title_lower: continue
             return place_name

    # Jos ei löydy tunnettua, yritetään arvata viimeinen sana
    words = clean.split()
    potential_places = []
    
    skip_words = ["Lento-onnettomuus", "Vaaratilanne", "Lentoturvallisuutta", "Vakava", "Onnettomuus", "Vaurio", "Lentokoneen", "Helikopterin", "Ultrakevyen", "Suuronnettomuuden", "Kahden", "Liikennelentokoneen", "Harrasterakenteisen", "Vesilentokoneen", "Purjelentokoneen", "Moottoripurjelentokoneen", "Matkustajalentokoneen", "Liikesuihkukoneen", "Lentokoneelle", "Kuumailmapallon", "Riippuliito-onnettomuus", "Varjoliito-onnettomuus", "Laskuvarjo-onnettomuus", "Laskuvarjohyppyonnettomuus", "Laskuvarjohyppääjiä", "Koululennolla", "Reittilennolla", "Lennolla", "Ohjaamoon", "Pakkolasku", "Keskeytetty", "Kiitotieltä", "Laskutelineen", "Rullausvaurio", "Yhteentörmäysvaara", "Porrastuksen", "Tutkaporrastusminimin", "Porrastusminimien", "Ilmatilaloukkauksesta", "Päällikön", "Lentoperämiehen", "Lennonjohtoporrastuksen", "Matkustamomiehistön", "Akkujen", "Saksalaisen", "Saksalaiselle", "Norjalaisen", "Turkkilaisen", "Belgialaisen", "Tunisialaisen", "Venäläisen", "Ruotsalaisen", "Kannettavan", "Miehistön", "Ilma-aluksen", "Rullaavan", "Painopisteohjatun", "Ultrakevytlentokoneen", "Moottorivaurio", "Moottorin", "Lentoväylässä", "Lento-osaston", "Lintutörmäys", "Korkeusperäsimen", "Raportointi", "Vaaratilanteet", "Kahdeksan", "Lentäjä", "Matkustaja", "OH-BEX", "OH-LVA", "OH-HTR", "OH-HWA", "OH-PZL", "OH-CIJ", "OH-FAB", "OH-BBL", "OH-HIU", "OH-GSM", "OH-HPT", "OH-XHV", "OH-HCA", "D-ABIB", "M-70", "MIG-21", "DC-9-81n", "ATR", "Cessna", "Tapaus", "Kaapelikatkos", "Vaarantanut", "Lentoasemalla", "Lentopaikalla", "Läheisyydessä", "Edustalla", "Jossa", "Alueella"]
    
    for w in words:
        w_clean = w.strip(".,:;")
        if len(w_clean) > 3 and w_clean[0].isupper() and w_clean not in skip_words:
            if not any(char.isdigit() for char in w_clean):
                potential_places.append(w_clean)
            
    if potential_places: return potential_places[-1]
    return None

def detect_aircraft_smart(title, full_text):
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
    return "Muu"

def create_smart_link(report_id, title):
    clean_id = clean_soft_hyphens(report_id)
    code_match = re.search(r'[A-Z]\d{4}-\d{2}|[A-Z]\d+/\d+[A-Z]', clean_id)
    if code_match:
        return f"https://turvallisuustutkinta.fi/fi/index/tutkintaselostukset/ilmailuonnettomuuksientutkinta/tutkintaselostuksetvuosittain.html"
    clean_title = clean_id.replace(".pdf", "").replace(".txt", "")
    clean_title = re.sub(r'Selvitys|Tutkintaselostus', '', clean_title, flags=re.IGNORECASE).strip()
    return f"https://www.google.com/search?q=site:turvallisuustutkinta.fi+{clean_title}"

def main():
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Datatiedostoa ei löydy.")
        return

    location_cache = load_cache()
    enriched_data = []
    processed_roots = set()
    
    print("Prosessoidaan dataa (V18 - Final)...")
    
    for entry in data:
        raw_id = clean_soft_hyphens(entry['id'])
        if any(x in raw_id.lower() for x in ["tutkintaselostukset", "otkes", "raideliikenne", "vesiliikenne", "sotilas", "muu"]): continue

        id_root = raw_id.lower().replace(".pdf", "").replace(".txt", "").strip()
        if id_root in processed_roots: continue
        processed_roots.add(id_root)
             
        title_id = raw_id
        content_text = clean_soft_hyphens(entry['text'])
        
        ac_type = detect_aircraft_smart(title_id, content_text)
        
        # 1. Otsikkohaku (Tehostettu)
        extracted_place = extract_location_from_title(title_id)
        lat, lon, final_loc_name = get_coordinates(extracted_place, location_cache)
        
        # 2. Tekstihaku (Tehostettu)
        if not lat:
            text_place = find_location_in_text(content_text)
            if text_place:
                 lat, lon, final_loc_name = get_coordinates(text_place, location_cache)
        
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
            "url": create_smart_link(title_id, title_id),
            "summary": content_text[:300].replace('\n', ' ') + "..." 
        }
        enriched_data.append(new_entry)
        
        status = "OK" if lat else "FAIL"
        # print(f"  > {title_id[:25]}... -> [{ac_type}] @ {final_loc_name} ({status})")

    save_cache(location_cache)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=4)
    
    print(f"\nValmis! {len(enriched_data)} tapausta.")

if __name__ == "__main__":
    main()
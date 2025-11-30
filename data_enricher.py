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

geolocator = Nominatim(user_agent="ilmailu_dashboard_project_v10")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

def clean_finnish_location(word):
    w = word.strip().lower()
    if not w: return ""
    
    if "helsinki" in w or "vantaa" in w or "efhk" in w: return "Helsinki-Vantaa"
    if "turku" in w or "turun" in w: return "Turku"
    if "tampere" in w: return "Tampere"
    if "lappeenran" in w: return "Lappeenranta"
    if "maarianhami" in w or "ahvenanmaa" in w: return "Maarianhamina"
    if "jyväskylä" in w or "tikkakosk" in w: return "Jyväskylä"
    if "rovanieme" in w: return "Rovaniemi"
    if "kontiolahde" in w: return "Kontiolahti"
    if "kemi" in w and "kemikaali" not in w: return "Kemi"
    if "seinäjoe" in w: return "Seinäjoki"

    suffixes = [("ssa", ""), ("ssä", ""), ("lla", ""), ("llä", ""), ("lta", ""), ("ltä", ""), ("sta", ""), ("stä", ""), ("n", ""), ("a", ""), ("ä", "")]
    for suf, rep in suffixes:
        if w.endswith(suf):
            return w[:-len(suf)] + rep
    return w.capitalize()

def get_coordinates(place_name, cache):
    if not place_name: return None, None, "Tuntematon"
    
    clean_name = clean_finnish_location(place_name)
    
    if clean_name in cache:
        val = cache[clean_name]
        if val: return val[0], val[1], clean_name
        return None, None, "Tuntematon"
    
    try:
        # print(f"    [GEO] Haetaan: {clean_name}...")
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
    text_lower = text[:1000].lower()
    
    # Tunnetut
    known_places = [
        "helsinki-vantaa", "helsinki", "vantaa", "turku", "tampere", 
        "oulu", "rovaniemi", "kuopio", "jyväskylä", "maarianhamina",
        "pori", "vaasa", "lappeenranta", "kajaani", "joensuu", "kemi", "ivalo",
        "enontekiö", "sodankylä", "kittilä"
    ]
    for place in known_places:
        if re.search(r'\b' + place, text_lower):
            if place == "kemi" and "kemikaali" in text_lower: continue
            return place.capitalize()

    # Yleinen haku
    words = text.split()
    skip_words = [
        "Onnettomuustutkintakeskus", "Suomen", "Helsingin", "Turun", "Tampereen", 
        "Lentokone", "Helikopteri", "Ohjaaja", "Lentäjä", "Matkustaja", "Vuonna",
        "Kello", "Noin", "Tämä", "Kyseessä", "Lisäksi", "Kuitenkin", "Koska", "Kun",
        "Kahdeksan", "Kaksi", "Kolme", "Neljä", "Viisi", "Kuusi", "Seitsemän", "Raportti"
    ]

    candidates = []
    for i, w in enumerate(words[:100]): 
        w_clean = w.strip(".,:;()")
        if len(w_clean) > 3 and w_clean[0].isupper() and w_clean not in skip_words:
            if i > 0 and not words[i-1].endswith("."):
                candidates.append(w_clean)
    
    if candidates: return candidates[0]
    return None

def extract_location_from_title(title):
    clean = re.sub(r'^[A-Z]\d{4}[- ]?\w+\s+', '', title)
    clean = re.sub(r'\d{1,2}\.\d{1,2}\.\d{4}.*', '', clean)
    words = clean.split()
    potential_places = []
    skip_words = [
        "Lento-onnettomuus", "Vaaratilanne", "Lentoturvallisuutta", "Vakava", 
        "Onnettomuus", "Vaurio", "Lentokoneen", "Helikopterin", "Ultrakevyen", 
        "Suuronnettomuuden", "Kahden", "Liikennelentokoneen", "Harrasterakenteisen",
        "Vesilentokoneen", "Purjelentokoneen", "Moottoripurjelentokoneen", "Matkustajalentokoneen",
        "Liikesuihkukoneen", "Lentokoneelle", "Kuumailmapallon", "Riippuliito-onnettomuus",
        "Varjoliito-onnettomuus", "Laskuvarjo-onnettomuus", "Laskuvarjohyppyonnettomuus",
        "Laskuvarjohyppääjiä", "Koululennolla", "Reittilennolla", "Lennolla", "Ohjaamoon",
        "Pakkolasku", "Keskeytetty", "Kiitotieltä", "Laskutelineen", "Rullausvaurio",
        "Yhteentörmäysvaara", "Porrastuksen", "Tutkaporrastusminimin", "Porrastusminimien",
        "Ilmatilaloukkauksesta", "Päällikön", "Lentoperämiehen", "Lennonjohtoporrastuksen",
        "Matkustamomiehistön", "Akkujen", "Saksalaisen", "Saksalaiselle", "Norjalaisen",
        "Turkkilaisen", "Belgialaisen", "Tunisialaisen", "Venäläisen", "Ruotsalaisen",
        "Kannettavan", "Miehistön", "Ilma-aluksen", "Rullaavan", "Painopisteohjatun",
        "Ultrakevytlentokoneen", "Moottorivaurio", "Moottorin", "Lentoväylässä",
        "Lento-osaston", "Lintutörmäys", "Korkeusperäsimen", "Raportointi", "Vaaratilanteet",
        "Kahdeksan", "Lentäjä", "Matkustaja", "OH-BEX", "OH-LVA", "OH-HTR", "OH-HWA",
        "OH-PZL", "OH-CIJ", "OH-FAB", "OH-BBL", "OH-HIU", "OH-GSM", "OH-HPT", "OH-XHV", "OH-HCA",
        "D-ABIB", "M-70", "MIG-21", "DC-9-81n", "ATR", "Cessna"
    ]
    
    for w in words:
        w_clean = w.strip(".,:;")
        if len(w_clean) > 3 and w_clean[0].isupper() and w_clean not in skip_words:
            if not any(char.isdigit() for char in w_clean):
                potential_places.append(w_clean)
            
    if potential_places: return potential_places[-1]
    return None

def detect_aircraft_smart(title, full_text):
    text_to_search = (title + " " + full_text[:3000]).lower()
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
    code_match = re.search(r'[A-Z]\d{4}-\d{2}', report_id)
    if code_match:
        return f"https://turvallisuustutkinta.fi/fi/index/tutkintaselostukset/ilmailuonnettomuuksientutkinta/tutkintaselostuksetvuosittain.html"
    clean_title = report_id.replace(".pdf", "").replace(".txt", "")
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
    
    print("Prosessoidaan dataa (V10 - Full Debug)...")
    
    for entry in data:
        raw_id = entry['id']
        if any(x in raw_id.lower() for x in ["tutkintaselostukset", "otkes", "raideliikenne", "vesiliikenne", "sotilas", "muu"]): continue

        id_root = raw_id.lower().replace(".pdf", "").replace(".txt", "").strip()
        if id_root in processed_roots: continue
        processed_roots.add(id_root)
             
        title_id = entry['id']
        content_text = entry['text']
        
        ac_type = detect_aircraft_smart(title_id, content_text)
        
        # 1. Yritetään otsikosta
        extracted_place = extract_location_from_title(title_id)
        lat, lon, final_loc_name = get_coordinates(extracted_place, location_cache)
        
        # 2. JOS EI LÖYDY (Fallback), etsitään tekstistä
        source = "Otsikko"
        if not lat:
            text_place = find_location_in_text(content_text)
            if text_place:
                 lat, lon, final_loc_name = get_coordinates(text_place, location_cache)
                 source = "Teksti"
        
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
        
        # TULOSTETAAN DEBUG-TIEDOT
        status = "OK" if lat else "FAIL"
        print(f"  > {title_id[:30]}... -> [{ac_type}] @ {final_loc_name} ({status}) - {source}")

    save_cache(location_cache)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=4)
    
    print(f"\nValmis! {len(enriched_data)} tapausta.")

if __name__ == "__main__":
    main()
import json
import re
import os

INPUT_FILE = "otkes_db.json"
OUTPUT_FILE = "structured_data.json"

# --- 1. KONETYYPIT ---
AIRCRAFT_RULES = [
    ("Laskuvarjohyppy", [r"laskuvarjo", r"hyppy", r"pudotus"], []), 
    ("Kuumailmapallo", [r"kuumailmapallo", r"pallo-onnettomuus"], []),
    ("Purjelentokone", [r"purjelentokone", r"moottoripurje", r"liidin", r"ls-4", r"ls-8", r"duo discus", r"dg-\d", r"grob", r"szd-", r"ask-\d", r"pik-20"], []),
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
    # SAAB: Vaaditaan sanaraja (\b) ja case-insensitive
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
    "Kiuruvesi": (63.6525, 26.6200)
}

SYNONYMS = {
    "muhoks": "Muhos", "muhos": "Muhos",
    "selänpää": "Selänpää", 
    "hyvinkää": "Hyvinkää",
    "joensuu": "Joensuu", 
    "ahvenanmaa": "Maarianhamina", "efma": "Maarianhamina",
    "tikkakosk": "Jyväskylä", "jyväskylä": "Jyväskylä", "efjy": "Jyväskylä",
    "kemi": "Kemi", "tornio": "Kemi", "efke": "Kemi",
    "vesivehmaa": "Lahti-Vesivehmaa", "efyl": "Lahti-Vesivehmaa",
    "efhk": "Helsinki-Vantaa", "helsinki": "Helsinki-Vantaa", "vantaa": "Helsinki-Vantaa",
    "malmi": "Malmi", "efhf": "Malmi",
    "räyskälä": "Räyskälä", "efry": "Räyskälä",
    "jämi": "Jämijärvi", "efjm": "Jämijärvi",
    "nummela": "Nummela", "efnu": "Nummela", "vihti": "Nummela",
    "menkijärvi": "Alavus", "efro": "Rovaniemi",
    "efou": "Oulu", "eftu": "Turku", "efsi": "Seinäjoki",
    "eftp": "Tampere", "efpo": "Pori", "efva": "Vaasa", "efut": "Kouvola"
}

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

def detect_location_smart(title, full_text):
    title_lower = title.lower()
    text_start = full_text[:800].lower()

    for keyword, real_loc in SYNONYMS.items():
        pattern = r'\b' + re.escape(keyword)
        if re.search(pattern, title_lower):
            if keyword == "kemi" and "kemikaali" in title_lower: continue
            return real_loc
    
    for loc in LOCATIONS:
        root = loc.split('-')[0].lower()
        pattern = r'\b' + re.escape(root)
        if re.search(pattern, title_lower):
             if root == "kemi" and "kemikaali" in title_lower: continue
             return loc

    for keyword, real_loc in SYNONYMS.items():
        pattern = r'\b' + re.escape(keyword)
        if re.search(pattern, text_start):
            if keyword == "kemi" and "kemikaali" in text_start: continue
            return real_loc

    for loc in LOCATIONS:
        root = loc.split('-')[0].lower()
        pattern = r'\b' + re.escape(root)
        if re.search(pattern, text_start):
            if root == "kemi" and "kemikaali" in text_start: continue
            return loc

    return "Tuntematon"

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

    enriched_data = []
    processed_roots = set() # TÄMÄ ESTÄÄ DUPLIKAATIT
    
    print("Prosessoidaan dataa (v5)...")
    
    for entry in data:
        raw_id = entry['id']
        
        # 1. Poistetaan turhat indeksisivut
        if "tutkintaselostukset" in raw_id.lower() and "otkes" not in raw_id.lower():
             continue
        if "raideliikenne" in raw_id.lower() or "vesiliikenne" in raw_id.lower():
             continue
        if raw_id.lower().startswith("muu") or raw_id.lower().startswith("sotilas"):
             # Nämä ovat usein vain kansioiden nimiä
             continue

        # 2. Duplikaattien tarkistus (Ilman tiedostopäätettä)
        id_root = raw_id.lower().replace(".pdf", "").replace(".txt", "").strip()
        if id_root in processed_roots:
            continue
        processed_roots.add(id_root)
             
        title_id = entry['id']
        content_text = entry['text']
        
        ac_type = detect_aircraft_smart(title_id, content_text)
        loc_name = detect_location_smart(title_id, content_text)
        coords = LOCATIONS.get(loc_name)
        smart_url = create_smart_link(title_id, title_id)
        
        year_match = re.search(r'20\d{2}|19\d{2}', title_id)
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
            "summary": content_text[:300].replace('\n', ' ') + "..." 
        }
        enriched_data.append(new_entry)
        
        print(f"  > {title_id[:25]}... -> [{ac_type}] @ {loc_name}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=4)
    
    print(f"\nValmis! {len(enriched_data)} uniikkia tapausta käsitelty.")

if __name__ == "__main__":
    main()
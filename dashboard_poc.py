import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

# Asetukset
st.set_page_config(page_title="OTKES Analyysi PoC", layout="wide", page_icon="✈️")

# --- DATAN LATAUS ---
@st.cache_data
def load_data():
    try:
        with open("structured_data.json", 'r', encoding='utf-8') as f:
            return pd.DataFrame(json.load(f))
    except Exception as e:
        st.error(f"Virhe datan latauksessa: {e}")
        return pd.DataFrame()

@st.cache_data
def load_analyses():
    try:
        with open("ai_analyses.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

df = load_data()
analyses = load_analyses()

# --- KÄYTTÖLIITTYMÄ ---

# Yläpalkki
st.markdown("""
    <style>
    .main-title {font-size: 3em; color: #0f5499; text-align: center; margin-bottom: 0;}
    .sub-title {font-size: 1.2em; color: #666; text-align: center; margin-top: -10px;}
    div.block-container {padding-top: 2rem;}
    </style>
    <h1 class='main-title'>✈️ Turvallisuustutkintojen analyysia</h1>
    <p class='sub-title'>Analyysi Suomen onnettomuustutkinnoista 2021–2024</p>
    <hr>
""", unsafe_allow_html=True)

# Filtterit
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    # Tässä vaiheessa meillä on vain Suomi, mutta valikko on valmiina tulevaisuutta varten
    countries = ["Suomi"] 
    sel_country = st.selectbox("Valitse valtio", countries)
with col2:
    if not df.empty:
        # Järjestetään aakkosiin, "Kaikki" ensin
        ac_types = ["Kaikki"] + sorted([x for x in df['aircraft_type'].unique() if x != "Kaikki"])
    else:
        ac_types = ["Ei dataa"]
    sel_aircraft = st.selectbox("Valitse ilma-alustyyppi", ac_types)

# Datan suodatus
filtered_df = df.copy()
if sel_aircraft != "Kaikki":
    filtered_df = filtered_df[filtered_df['aircraft_type'] == sel_aircraft]

# --- PÄÄNÄKYMÄ ---

# 1. AI Analyysi -laatikko
st.subheader(f"📊 Analyysi: {sel_aircraft}")

# Haetaan oikea analyysiteksti avaimella "Suomi_Konetyyppi"
analysis_key = f"Suomi_{sel_aircraft}"
analysis_text = analyses.get(analysis_key, "⚠️ Tälle valinnalle ei ole vielä valmista analyysia tietokannassa.")

with st.container():
    st.info(analysis_text, icon="🤖")

# 2. Graafit ja Kartta
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📍 Tapahtumapaikat")
    if not filtered_df.empty:
        # Kartan keskitys: Jos suodatettu dataa, keskitä ekaan. Jos ei, keskitä Suomeen.
        valid_coords = filtered_df.dropna(subset=['lat', 'lon'])
        
        if not valid_coords.empty:
            if sel_aircraft == "Kaikki":
                center = [65.0, 26.0]
                zoom = 5
            else:
                # Keskitetään tapauksiin
                center = [valid_coords.iloc[0]['lat'], valid_coords.iloc[0]['lon']]
                zoom = 6
        else:
            center = [64.5, 26.0]
            zoom = 5
            
        m = folium.Map(location=center, zoom_start=zoom)
        
        for _, row in valid_coords.iterrows():
            # Väri: Jos otsikossa "onnettomuus" -> punainen, muuten sininen
            color = "red" if "onnettomuus" in row['id'].lower() else "blue"
            
            folium.Marker(
                [row['lat'], row['lon']],
                popup=folium.Popup(f"<b>{row['id']}</b><br>{row['date']}", max_width=300),
                tooltip=f"{row['aircraft_type']} - {row['location_name']}",
                icon=folium.Icon(color=color, icon="plane")
            ).add_to(m)
        
        st_folium(m, height=400, use_container_width=True)
    else:
        st.write("Ei näytettäviä kohteita.")

with col_right:
    st.markdown("### 📈 Tilastot")
    if not filtered_df.empty:
        # Esimerkkigraafi: Tapaukset paikkakunnittain
        loc_counts = filtered_df['location_name'].value_counts().head(10)
        
        if not loc_counts.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            loc_counts.plot(kind='barh', ax=ax, color='#0f5499', edgecolor='black')
            ax.set_title("Yleisimmät tapahtumapaikat tässä ryhmässä")
            ax.invert_yaxis() # Suurin ylös
            ax.set_xlabel("Tapausten määrä")
            st.pyplot(fig)
        
        # Vuosijakauma
        year_counts = filtered_df['date'].value_counts().sort_index()
        if not year_counts.empty:
             st.markdown("**Jakauma vuosittain:**")
             st.bar_chart(year_counts)

    else:
        st.write("Ei dataa tilastoihin.")

# 3. Raporttilistaus
st.divider()
st.markdown(f"### 📄 Tutkintaselostukset ({len(filtered_df)} kpl)")

for _, row in filtered_df.iterrows():
    with st.expander(f"{row['date']} | {row['id']}"):
        st.markdown(f"**Tyyppi:** {row['aircraft_type']}")
        st.markdown(f"**Sijainti:** {row['location_name']}")
        st.markdown(f"**Tiivistelmä:** _{row['summary']}_")
        st.markdown(f"[Avaa raportti OTKESin sivuilla]({row['url']})")
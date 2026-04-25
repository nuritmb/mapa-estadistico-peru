"""
Perú 2021 — Resultados Electorales por Distrito
Interactive Streamlit app
"""

import json
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Perú 2021 — Resultados Electorales",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ─── Password gate (Streamlit Cloud deploy) ──────────────────────────────────
# Reads `app_password` from `.streamlit/secrets.toml` (configured via the
# Streamlit Cloud dashboard). If no password is set (local dev), the gate
# is skipped.
def _password_gate():
    expected = None
    try:
        expected = st.secrets.get("app_password")
    except Exception:
        expected = None
    if not expected:
        return  # no password configured → open access (local dev)
    if st.session_state.get("auth_ok"):
        return
    st.title("🗳️ Perú 2021 — Resultados")
    pw = st.text_input("Contraseña", type="password")
    if pw:
        if pw == expected:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()

_password_gate()

# ─── Metadata ─────────────────────────────────────────────────────────────────
CANDIDATES_R1 = {
    "PNP":  ("Ollanta Humala",      "Partido Nacionalista Peruano"),
    "FA":   ("Marco Arana",         "Frente Amplio"),
    "PM":   ("Julio Guzmán",        "Partido Morado"),
    "PPS":  ("Rafael Santos",       "Perú Patria Segura"),
    "VN":   ("George Forsyth",      "Victoria Nacional"),
    "AP":   ("Yonhy Lescano",       "Acción Popular"),
    "AvP":  ("Hernando de Soto",    "Avanza País"),
    "PP":   ("Daniel Urresti",      "Podemos Perú"),
    "JP":   ("Verónika Mendoza",    "Juntos por el Perú"),
    "PPC":  ("Alberto Beingolea",   "Partido Popular Cristiano"),
    "FP":   ("Keiko Fujimori",      "Fuerza Popular"),
    "UPP":  ("José Vega",           "Unión por el Perú"),
    "RP":   ("Rafael López Aliaga", "Renovación Popular"),
    "RUNA": ("Ciro Gálvez",         "Renacimiento Unido Nacional"),
    "SP":   ("Daniel Salaverry",    "Somos Perú"),
    "PL":   ("Pedro Castillo",      "Perú Libre"),
    "DD":   ("Andrés Alcántara",    "Democracia Directa"),
    "APP":  ("César Acuña",         "Alianza para el Progreso"),
}

PARTY_COLORS = {
    "PL":   "#E63946",
    "FP":   "#F4A261",
    "AP":   "#2A9D8F",
    "RP":   "#264653",
    "AvP":  "#9B5DE5",
    "JP":   "#C77DFF",
    "APP":  "#F77F00",
    "PNP":  "#4361EE",
    "FA":   "#3A5A40",
    "PM":   "#8338EC",
    "PPS":  "#FB8500",
    "VN":   "#219EBC",
    "PP":   "#023E8A",
    "PPC":  "#0077B6",
    "UPP":  "#6A4C93",
    "RUNA": "#588157",
    "SP":   "#ADB5BD",
    "DD":   "#CDB4DB",
}

CENSUS_VARS = {
    "pct_pobreza_total":       "Pobreza total (%)",
    "pct_pobreza_extrema":     "Pobreza extrema (%)",
    "idh_2019":                "IDH 2019",
    "pct_rural":               "Área rural (%)",
    "pct_quechua":             "Quechua hablantes (%)",
    "pct_aimara":              "Aimara hablantes (%)",
    "pct_indigenous_total":    "Lengua indígena (%)",
    "pct_castellano":          "Castellano hablantes (%)",
    "pct_sin_nivel":           "Sin nivel educativo (%)",
    "pct_primaria_o_menos":    "Primaria o menos (%)",
    "pct_secundaria":          "Secundaria (%)",
    "pct_superior_cualquiera": "Educación superior (%)",
    "pct_hasta_secundaria":    "Educación: hasta secundaria (%)",
    "pct_superior":            "Educación: superior (%)",
    "altitude":                "Altitud (m.s.n.m.)",
    "pob_densidad_2020":       "Densidad (hab/km²)",
}

LAND_REFORM_VARS = {
    # From the Peru_LR Dataverse dataset (1975-era, Velasco-period reform).
    # See scripts/build_land_reform_distrito.py and the upstream Codebook.
    "landredist_pc":            "Tierra redistribuida (per cápita)",
    "landredist_pcprivate":     "Tierra redistribuida privada (per cápita)",
    "landdist_uncult_pc":       "Tierra no cultivada redistribuida (per cápita)",
    "D_LRSurfaceArea50th":      "Reforma agraria por encima de la mediana (superficie)",
    "LRpercap_calweighted_log": "Reforma agraria per cápita (log, ponderada)",
    "prop_ha_ths":              "Hectáreas redistribuidas (miles)",
}

CONFLICT_VARS = {
    "cvr_deaths":          "Muertes CVR (per cápita)",
    "cvr_events":          "Eventos violentos CVR",
    "cvr_guerr_8088":      "Guerrilla 1980-88",
    "cvr_guerr_8900":      "Guerrilla 1989-00",
    "cvr_state_8088":      "Violencia estatal 1980-88",
    "cvr_state_8900":      "Violencia estatal 1989-00",
    "emergency_zone_1990": "Zona de emergencia 1990",
    "guerrilla_presence":  "Presencia guerrillera",
    "marxist_vote_1980":   "Voto marxista 1980",
    "illiteracy_1972":     "Analfabetismo 1972",
}

# Bivariate choropleth palette (Joshua Stevens pink-blue 3×3)
# Rows = primary variable (electoral), Cols = secondary variable (context)
# [primary_class][secondary_class]  where 0=Low, 1=Mid, 2=High
BIVARIATE_PALETTE = [
    ["#e8e8e8", "#ace4e4", "#5ac8c8"],  # primary Low
    ["#dfb0d6", "#a5add3", "#5698b9"],  # primary Mid
    ["#be64ac", "#8c62aa", "#3b4994"],  # primary High
]
BIVARIATE_CLASS_LABELS = {
    "0_0": "Bajo P · Bajo S", "0_1": "Bajo P · Medio S", "0_2": "Bajo P · Alto S",
    "1_0": "Medio P · Bajo S", "1_1": "Medio P · Medio S", "1_2": "Medio P · Alto S",
    "2_0": "Alto P · Bajo S", "2_1": "Alto P · Medio S", "2_2": "Alto P · Alto S",
}

# ─── i18n ─────────────────────────────────────────────────────────────────────
STRINGS = {
    # Sidebar chrome
    "app_title":            {"es": "🗳️ Perú 2021",                     "en": "🗳️ Peru 2021"},
    "app_subtitle":         {"es": "Elecciones presidenciales",          "en": "Presidential elections"},
    "geo_level":            {"es": "🌎 Nivel geográfico",               "en": "🌎 Geographic level"},
    "unit_label":           {"es": "Unidad de análisis",                 "en": "Unit of analysis"},
    "distrito":             {"es": "Distrito",                           "en": "District"},
    "provincia":            {"es": "Provincia",                          "en": "Province"},
    "departamento":         {"es": "Departamento",                       "en": "Department"},
    "level_help":           {
        "es": ("Elige a qué escala agregar los datos. Votos se suman; porcentajes se recalculan "
               "a partir de las sumas (no promedios, para evitar la paradoja de Simpson). "
               "Variables censales se promedian **ponderando por población**."),
        "en": ("Choose the geographic scale. Votes are summed; percentages are recomputed "
               "from sums (not averages, to avoid Simpson's paradox). "
               "Census variables are **population-weighted** averages."),
    },
    "representation":       {"es": "Representación",                     "en": "Representation"},
    "choropleth":           {"es": "Coropleta",                          "en": "Choropleth"},
    "bubbles":              {"es": "Burbujas (por población)",            "en": "Bubbles (by population)"},
    "repr_help":            {
        "es": ("**Coropleta**: colorea el polígono completo, da igual peso a cada área geográfica.\n\n"
               "**Burbujas**: cada unidad es un círculo cuya área es proporcional a su población total."),
        "en": ("**Choropleth**: colours the full polygon; each area gets equal visual weight.\n\n"
               "**Bubbles**: each unit is a circle whose area is proportional to its total population."),
    },
    "visualization":        {"es": "🗺️ Visualización",                  "en": "🗺️ Visualization"},
    "round":                {"es": "Vuelta",                             "en": "Round"},
    "second_round":         {"es": "Segunda vuelta",                     "en": "Second round"},
    "first_round":          {"es": "Primera vuelta",                     "en": "First round"},
    "color_mode":           {"es": "Modo de color",                      "en": "Color mode"},
    "winner":               {"es": "Ganador",                            "en": "Winner"},
    "vote_pct":             {"es": "Porcentaje de voto",                 "en": "Vote share"},
    "margin":               {"es": "Margen",                             "en": "Margin"},
    "swing":                {"es": "Swing (R1→R2)",                      "en": "Swing (R1→R2)"},
    "mode_help":            {
        "es": ("**Ganador**: qué candidato obtuvo más votos.\n\n"
               "**Porcentaje de voto**: % de votos válidos para un candidato elegido.\n\n"
               "**Margen**: % Castillo − % Fujimori (2ª v.). Positivo = gana Castillo.\n\n"
               "**Swing**: cuántos pp ganó (o perdió) Castillo entre la 1ª y la 2ª vuelta."),
        "en": ("**Winner**: which candidate received the most votes.\n\n"
               "**Vote share**: % of valid votes for a chosen candidate.\n\n"
               "**Margin**: % Castillo − % Fujimori (2nd round). Positive = Castillo wins.\n\n"
               "**Swing**: how many pp Castillo gained (or lost) from 1st to 2nd round."),
    },
    "candidate":            {"es": "Candidato",                          "en": "Candidate"},
    "bivariate_chk":        {"es": "🔬 Comparar con variable de contexto (bivariado)",
                             "en": "🔬 Compare with context variable (bivariate)"},
    "bivariate_help":       {
        "es": ("Muestra dos variables en un solo mapa usando una paleta 3×3. "
               "El eje primario (filas) es tu variable electoral actual. "
               "El eje secundario (columnas) es la variable de contexto que elijas."),
        "en": ("Displays two variables on one map using a 3×3 palette. "
               "The primary axis (rows) is your current electoral variable. "
               "The secondary axis (columns) is the context variable you choose."),
    },
    "context_var":          {"es": "Variable de contexto (secundaria)",  "en": "Context variable (secondary)"},
    "binning":              {"es": "Método de binning",                  "en": "Binning method"},
    "quantiles":            {"es": "Cuantiles (tercios)",                "en": "Quantiles (thirds)"},
    "equal_width":          {"es": "Ancho igual",                        "en": "Equal width"},
    "binning_help":         {
        "es": ("**Cuantiles**: cada clase contiene ≈1/3 de los distritos. Útil para distribuciones sesgadas.\n\n"
               "**Ancho igual**: divide el rango numérico en tres tramos iguales."),
        "en": ("**Quantiles**: each class contains ≈1/3 of units. Good for skewed distributions.\n\n"
               "**Equal width**: divides the numeric range into three equal intervals."),
    },
    "primary_var":          {"es": "Variable primaria",                  "en": "Primary variable"},
    "secondary_var":        {"es": "Variable secundaria",                "en": "Secondary variable"},
    "single_layer":         {"es": "📊 Capa única",                     "en": "📊 Single layer"},
    "dataset":              {"es": "Dataset",                            "en": "Dataset"},
    "none":                 {"es": "Ninguna",                            "en": "None"},
    "census":               {"es": "Censo",                              "en": "Census"},
    "conflict":             {"es": "Conflicto armado",                   "en": "Armed conflict"},
    "land_reform":          {"es": "Reforma agraria",                    "en": "Land reform"},
    "layer_help":           {
        "es": "Alternativa al modo bivariado: muestra SOLO la capa de contexto.",
        "en": "Alternative to bivariate mode: shows ONLY the context layer.",
    },
    "census_var":           {"es": "Variable censal",                    "en": "Census variable"},
    "conflict_var":         {"es": "Variable de conflicto",              "en": "Conflict variable"},
    "lr_var":               {"es": "Variable de reforma agraria",        "en": "Land reform variable"},
    "filter":               {"es": "🔍 Filtrar",                        "en": "🔍 Filter"},
    "department":           {"es": "Departamento",                       "en": "Department"},
    "all":                  {"es": "Todos",                              "en": "All"},
    # Tabs
    "tab_map":              {"es": "🗺️ Mapa",                           "en": "🗺️ Map"},
    "tab_corr":             {"es": "📈 Correlación",                    "en": "📈 Correlation"},
    "tab_data":             {"es": "📋 Datos",                          "en": "📋 Data"},
    # Map tab
    "back_btn":             {"es": "← Volver",                          "en": "← Back"},
    "back_help":            {"es": "Limpiar selección y volver a la vista general",
                             "en": "Clear selection and return to overview"},
    "click_hint":           {"es": "💡 **Haz clic en cualquier {unit}** para ver el detalle.",
                             "en": "💡 **Click any {unit}** to see details."},
    "no_pop_warning":       {"es": "No hay columna `total_pop` disponible; cayendo a coropleta.",
                             "en": "No `total_pop` column available; falling back to choropleth."},
    "bivariate_legend":     {"es": "**Leyenda bivariada**",              "en": "**Bivariate legend**"},
    "no_data":              {"es": "Sin datos",                          "en": "No data"},
    "inherited":            {"es": "Valor heredado (1975)",              "en": "Inherited value (1975)"},
    "imputed_caption":      {
        "es": ("❗ **{n} {unit}** marcados con '!' tienen un valor *heredado*: los datos de "
               "{source} provienen del mapa de distritos de 1975, y este {unit_s} fue creado "
               "después. El valor mostrado es el del distrito-padre de 1975. Es una inferencia "
               "espacial, no una medición directa."),
        "en": ("❗ **{n} {unit}** marked with '!' have an *inherited* value: the {source} data "
               "come from the 1975 district map, and this {unit_s} was created later. "
               "The value shown is that of the 1975 parent district — a spatial inference, "
               "not a direct measurement."),
    },
    "conflict_source":      {"es": "conflicto armado (CVR)",             "en": "armed conflict (CVR)"},
    "lr_source":            {"es": "reforma agraria (Velasco)",          "en": "land reform (Velasco)"},
    # Units (plural / singular)
    "distritos":            {"es": "distritos",       "en": "districts"},
    "provincias":           {"es": "provincias",      "en": "provinces"},
    "departamentos":        {"es": "departamentos",   "en": "departments"},
    "distrito_s":           {"es": "distrito",        "en": "district"},
    "provincia_s":          {"es": "provincia",       "en": "province"},
    "departamento_s":       {"es": "departamento",    "en": "department"},
    # Detail panel
    "province_label":       {"es": "Provincia",       "en": "Province"},
    "department_label":     {"es": "Departamento",    "en": "Department"},
    "castillo_r2":          {"es": "Castillo (2ª vuelta)",  "en": "Castillo (2nd round)"},
    "fujimori_r2":          {"es": "Fujimori (2ª vuelta)",  "en": "Fujimori (2nd round)"},
    "margin_label":         {"es": "Margen",               "en": "Margin"},
    "wins":                 {"es": "gana",                 "en": "wins"},
    "r1_votes":             {"es": "**Primera vuelta — votos por candidato**",
                             "en": "**First round — votes by candidate**"},
    "census_data":          {"es": "📋 Datos del Censo 2017",           "en": "📋 Census data (2017)"},
    "conflict_data":        {"es": "⚔️ Conflicto armado (CVR)",         "en": "⚔️ Armed conflict (CVR)"},
    "lr_data":              {"es": "🌾 Reforma agraria (Velasco)",      "en": "🌾 Land reform (Velasco)"},
    "not_available":        {"es": "No disponible",                      "en": "Not available"},
    # Scatter / correlation tab
    "x_axis":               {"es": "Variable X (contexto)",              "en": "X variable (context)"},
    "y_axis":               {"es": "Variable Y (electoral)",             "en": "Y variable (electoral)"},
    "log_x":                {"es": "Log(X)",                             "en": "Log(X)"},
    "log_y":                {"es": "Log(Y)",                             "en": "Log(Y)"},
    "trim_pct":             {"es": "Recortar extremos (%)",              "en": "Trim extremes (%)"},
    "controls":             {"es": "Controlar por (mantener constante)", "en": "Control for (hold constant)"},
    "pearson":              {"es": "Pearson r",                          "en": "Pearson r"},
    "spearman":             {"es": "Spearman ρ",                         "en": "Spearman ρ"},
    # Data tab
    "data_title":           {"es": "Tabla de datos por {unit}",         "en": "Data table by {unit}"},
    "col_groups":           {"es": "Columnas a mostrar",                 "en": "Columns to display"},
    "search":               {"es": "Buscar por nombre",                  "en": "Search by name"},
    # National summary bar
    "castillo_nacional":    {"es": "Castillo (nacional)",                "en": "Castillo (national)"},
    "fujimori_nacional":    {"es": "Fujimori (nacional)",                "en": "Fujimori (national)"},
    "distritos_castillo":   {"es": "Distritos Castillo",                 "en": "Districts (Castillo)"},
    "distritos_fujimori":   {"es": "Distritos Fujimori",                 "en": "Districts (Fujimori)"},
    "votos_validos_r2":     {"es": "Votos válidos (2ª v.)",              "en": "Valid votes (2nd round)"},
    # Detail panel extras
    "pct_votos":            {"es": "% votos válidos",                    "en": "% valid votes"},
    "voto_pct_col":         {"es": "Voto %",                             "en": "Vote %"},
    "swing_trace":          {"es": "**Swing Castillo (R1→R2):**",        "en": "**Swing (R1→R2):**"},
    "swing_detail":         {
        "es": "era {r1:.1f}% en 1ª vuelta → {r2:.1f}% en 2ª",
        "en": "was {r1:.1f}% in round 1 → {r2:.1f}% in round 2",
    },
    "socioeco_context":     {"es": "**Contexto socioeconómico (Censo 2017)**",
                             "en": "**Socioeconomic context (Census 2017)**"},
    "conflict_panel":       {"es": "**Conflicto armado (CVR)**",         "en": "**Armed conflict (CVR)**"},
    "cvr_deaths_label":     {"es": "Muertes CVR (per cápita)",           "en": "CVR deaths (per capita)"},
    "violent_events":       {"es": "Eventos violentos",                  "en": "Violent events"},
    "emergency_zone":       {"es": "Zona de emergencia 1990",            "en": "Emergency zone 1990"},
    "yes":                  {"es": "Sí",                                 "en": "Yes"},
    "conflict_imputed_cap": {
        "es": ("⚠️ Datos de conflicto imputados espacialmente "
               "(distrito creado después de 1975; {n} distrito(s) padre)"),
        "en": ("⚠️ Conflict data spatially imputed "
               "(district created after 1975; {n} parent district(s))"),
    },
    "provincia_subtitle":   {"es": "Provincia",                          "en": "Province"},
    # Correlation tab
    "corr_title":           {"es": "### Análisis de correlación por {unit}",
                             "en": "### Correlation analysis by {unit}"},
    "corr_few_warning":     {
        "es": ("⚠️ Con n = 25 departamentos, las correlaciones son muy inestables. "
               "Preferí nivel distrito o provincia para análisis estadístico."),
        "en": ("⚠️ With n = 25 departments, correlations are very unstable. "
               "Use district or province level for statistical analysis."),
    },
    "quick_guide_title":    {"es": "📚 ¿Qué significa esto? (guía rápida)",
                             "en": "📚 What does this mean? (quick guide)"},
    "quick_guide_body":     {
        "es": """
**¿Qué es una correlación?**
Un número entre −1 y +1 que resume cuánto se mueven juntas dos variables.
- **+1**: cuando una sube, la otra sube perfectamente.
- **0**: no hay relación lineal / monotónica.
- **−1**: cuando una sube, la otra baja perfectamente.

Para interpretar la magnitud (regla general en ciencias sociales):

| \\|r\\| | Fuerza |
| --- | --- |
| 0.0 – 0.1 | Nula / trivial |
| 0.1 – 0.3 | Débil |
| 0.3 – 0.5 | Moderada |
| 0.5 – 0.7 | Fuerte |
| > 0.7 | Muy fuerte |

**Pearson r** mide la relación **lineal** entre los valores crudos.
Es sensible a los puntos extremos: un solo distrito atípico puede inflarla o deprimirla.

**Spearman ρ** (rho) convierte los valores en **rangos** (1º, 2º, 3º…) y correlaciona los rangos.
Mide si la relación es **monotónica** (siempre sube o siempre baja), sin exigir que sea lineal.
No se deja influir tanto por outliers ni por distribuciones sesgadas.

**Regla práctica**:
- Si Pearson ≈ Spearman → la relación es lineal y "limpia".
- Si difieren mucho (|r − ρ| > 0.1) → hay no-linealidad o outliers influyentes. Confía más en Spearman.

---

**Recortar outliers** (trimming)
Elimina los distritos cuyo valor X o Y esté en los extremos de la distribución.
Un 1% recorta el 1% inferior y el 1% superior de cada variable — aprox 2-4% de los distritos
quedan excluidos del cálculo, porque algunos son extremos en X y otros en Y.

Sirve para **diagnosticar** si la correlación depende de unos pocos puntos extremos
(p.ej., Lima Metropolitana, o distritos amazónicos muy despoblados).
No es una técnica para "limpiar" los datos: los outliers son distritos reales y merecen atención.
Los puntos recortados se muestran en gris como referencia.

**Causalidad**: una correlación alta **no** implica causa-efecto. Pueden co-variar porque ambas
dependen de un tercer factor (p.ej. ruralidad), o por razones históricas no observadas.

---

**Escala logarítmica (log)**
Algunas variables tienen distribuciones muy **sesgadas**: muchos distritos con valores
cercanos a cero y unos pocos con valores muy altos. Por ejemplo:

- **Muertes CVR per cápita**: la gran mayoría de distritos tienen 0 ó casi 0; unos pocos de Ayacucho, Huancavelica y Huánuco tienen valores muy altos.
- **Densidad poblacional**: La Victoria (Lima) con >20.000 hab/km² vs distritos amazónicos con <1.
- **Altitud**: menos sesgada, pero con un rango amplio de 0 a >4.500 m.

En escala lineal, esos pocos valores altos dominan el gráfico y distorsionan a Pearson.
Transformar con **log(x + 1)** comprime los valores grandes y dispersa los pequeños,
mostrando mejor la forma de la relación.

Se usa **log natural** (ln) con un desplazamiento de +1 — conocido como **log1p** — porque
muchas variables contienen ceros y log(0) no está definido. El "+1" resuelve esto.

**Efectos**:
- Pearson r **cambia** (mide linealidad en el nuevo espacio).
- Spearman ρ **no cambia** — es invariante a transformaciones monotónicas como log.
- La nube de puntos suele verse más "redonda" y la tendencia, más clara.
""",
        "en": """
**What is a correlation?**
A number between −1 and +1 that summarises how much two variables move together.
- **+1**: when one rises, the other rises perfectly.
- **0**: no linear / monotonic relationship.
- **−1**: when one rises, the other falls perfectly.

To interpret the magnitude (social-science rule of thumb):

| \\|r\\| | Strength |
| --- | --- |
| 0.0 – 0.1 | None / trivial |
| 0.1 – 0.3 | Weak |
| 0.3 – 0.5 | Moderate |
| 0.5 – 0.7 | Strong |
| > 0.7 | Very strong |

**Pearson r** measures the **linear** relationship between raw values.
It is sensitive to extreme points: a single outlier district can inflate or deflate it.

**Spearman ρ** (rho) converts values to **ranks** (1st, 2nd, 3rd…) and correlates the ranks.
It detects **monotonic** relationships (always rises or always falls) without requiring linearity.
It is less affected by outliers or skewed distributions.

**Practical rule**:
- If Pearson ≈ Spearman → the relationship is linear and "clean".
- If they differ much (|r − ρ| > 0.1) → non-linearity or influential outliers. Trust Spearman more.

---

**Trimming outliers**
Removes districts whose X or Y value falls in the extremes of the distribution.
1% trims the bottom 1% and top 1% of each variable — roughly 2–4% of districts
are excluded, because some are extreme on X and others on Y.

Useful to **diagnose** whether a correlation depends on a few extreme points
(e.g. Metropolitan Lima, or very sparsely populated Amazon districts).
This is not a data-cleaning technique: outliers are real districts and deserve attention.
Trimmed points are shown in grey for transparency.

**Causality**: a high correlation does **not** imply cause and effect. Variables can co-move
because both depend on a third factor (e.g. rurality), or for unobserved historical reasons.

---

**Log scale**
Some variables have very **skewed** distributions: many districts near zero and a few very high.
For example:

- **CVR deaths per capita**: most districts have 0 or near 0; a few in Ayacucho, Huancavelica and Huánuco are very high.
- **Population density**: La Victoria (Lima) with >20,000 pop/km² vs Amazonian districts with <1.
- **Altitude**: less skewed, but spanning 0 to >4,500 m.

On a linear scale, those few high values dominate the chart and distort Pearson.
Transforming with **log(x + 1)** compresses large values and spreads small ones,
revealing the shape of the relationship more clearly.

**Natural log** (ln) with a +1 shift — known as **log1p** — is used because
many variables contain zeros and log(0) is undefined. The "+1" fixes this.

**Effects**:
- Pearson r **changes** (it measures linearity in the new space).
- Spearman ρ **does not change** — it is invariant to monotonic transforms like log.
- The scatter cloud usually looks more "round" and the trend clearer.
""",
    },
    "x_var_label":          {"es": "Variable X (socioeconómica / conflicto / reforma agraria)",
                             "en": "Variable X (socioeconomic / conflict / land reform)"},
    "y_var_label":          {"es": "Variable Y (electoral)",             "en": "Variable Y (electoral)"},
    "color_by_label":       {"es": "Color por",                         "en": "Color by"},
    "winner_r2_opt":        {"es": "Ganador R2",                        "en": "Winner R2"},
    "none_opt":             {"es": "Ninguno",                           "en": "None"},
    "trim_label":           {"es": "Recortar outliers (% en cada cola, ambos ejes)",
                             "en": "Trim outliers (% in each tail, both axes)"},
    "trim_help":            {
        "es": ("Elimina los distritos que estén en los extremos X o Y. "
               "Un valor de 1%, por ejemplo, recorta el 1% inferior y el 1% superior "
               "de cada variable (≈ 2-4% de los distritos). Muestra los recortados "
               "como puntos grises para transparencia."),
        "en": ("Removes districts that fall in the X or Y extremes. "
               "A value of 1%, for example, trims the bottom 1% and top 1% "
               "of each variable (≈ 2–4% of districts). Trimmed points are shown "
               "as grey dots for transparency."),
    },
    "show_ghosts":          {"es": "Mostrar puntos recortados como fantasmas",
                             "en": "Show trimmed points as ghosts"},
    "log_x_label":          {"es": "📐 Escala log en X  —  log(X + 1)",
                             "en": "📐 Log scale for X  —  log(X + 1)"},
    "log_x_help":           {
        "es": ("Transforma X con el logaritmo natural ln(X + 1). "
               "Útil para variables muy sesgadas (muchos ceros + pocos valores grandes), "
               "como muertes CVR per cápita, densidad poblacional o altitud. "
               "El '+1' evita problemas con los ceros."),
        "en": ("Transforms X with the natural logarithm ln(X + 1). "
               "Useful for very skewed variables (many zeros + few large values), "
               "such as CVR deaths per capita, population density, or altitude. "
               "The '+1' avoids issues with zeros."),
    },
    "log_y_label":          {"es": "📐 Escala log en Y  —  log(Y + 1)",
                             "en": "📐 Log scale for Y  —  log(Y + 1)"},
    "log_y_help":           {
        "es": ("Igual que X log, pero aplicado a la variable electoral del eje Y. "
               "Rara vez necesario para porcentajes (ya están en escala acotada), "
               "pero útil si Y es un conteo sesgado."),
        "en": ("Same as X log, but applied to the electoral variable on the Y axis. "
               "Rarely needed for percentages (already on a bounded scale), "
               "but useful if Y is a skewed count."),
    },
    "control_label":        {"es": "🎛️ Controlar por (mantener constante)",
                             "en": "🎛️ Control for (hold constant)"},
    "control_help":         {
        "es": ("Elige una o más variables a **mantener constantes** para aislar el "
               "efecto propio de X sobre Y. Técnicamente: se regresa Y contra los "
               "controles y se guardan los residuos (la parte de Y que los controles "
               "NO explican); se hace lo mismo con X; y se correlaciona residuo-Y "
               "contra residuo-X. El resultado es la **correlación parcial** y su "
               "pendiente coincide con el coeficiente de X en una regresión múltiple "
               "(teorema de Frisch-Waugh-Lovell)."),
        "en": ("Choose one or more variables to **hold constant** to isolate the "
               "own effect of X on Y. Technically: Y is regressed on the controls "
               "and the residuals are saved (the part of Y the controls do NOT explain); "
               "the same is done with X; then residual-Y is correlated with residual-X. "
               "The result is the **partial correlation** and its slope equals the "
               "X coefficient in a multiple regression (Frisch-Waugh-Lovell theorem)."),
    },
    "neg_x_warning":        {
        "es": "⚠️ {n} distrito(s) tienen valores negativos en X y no se pueden transformar con log. Se excluyen del análisis.",
        "en": "⚠️ {n} district(s) have negative X values and cannot be log-transformed. They are excluded.",
    },
    "neg_y_warning":        {
        "es": "⚠️ {n} distrito(s) tienen valores negativos en Y y no se pueden transformar con log. Se excluyen del análisis.",
        "en": "⚠️ {n} district(s) have negative Y values and cannot be log-transformed. They are excluded.",
    },
    "trimmed_trace":        {"es": "Recortados (n={n})",                 "en": "Trimmed (n={n})"},
    "ols_trace":            {"es": "OLS (sobre n={n})",                  "en": "OLS (n={n})"},
    "log_banner_prefix":    {"es": "🔢 **Transformación aplicada:**",    "en": "🔢 **Transformation applied:**"},
    "log_banner":           {
        "es": (" Se usa logaritmo natural con un desplazamiento de +1 "
               "(log1p) para manejar valores de cero. "
               "Pearson r se calcula sobre los valores transformados; "
               "Spearman ρ es **invariante** a transformaciones monotónicas "
               "como log, así que no cambia con este toggle."),
        "en": (" Natural log with a +1 shift (log1p) is used to handle zeros. "
               "Pearson r is computed on the transformed values; "
               "Spearman ρ is **invariant** to monotonic transforms like log, "
               "so it does not change with this toggle."),
    },
    "suffix_log":           {"es": "log",                               "en": "log"},
    "suffix_trim":          {"es": "recortado",                         "en": "trimmed"},
    "corr_strength":        {
        "es": {"none": "sin relación", "weak": "débil", "moderate": "moderada",
               "strong": "fuerte", "very_strong": "muy fuerte",
               "pos": "positiva", "neg": "negativa"},
        "en": {"none": "no relationship", "weak": "weak", "moderate": "moderate",
               "strong": "strong", "very_strong": "very strong",
               "pos": "positive", "neg": "negative"},
    },
    "pearson_label":        {"es": "Pearson r (lineal)",                 "en": "Pearson r (linear)"},
    "spearman_label":       {"es": "Spearman ρ (rangos)",                "en": "Spearman ρ (ranks)"},
    "n_used_label":         {"es": "n (distritos usados)",               "en": "n (units used)"},
    "trimmed_label":        {"es": "Recortados",                        "en": "Trimmed"},
    "n_help":               {"es": "Número de distritos que entran en el cálculo después del recorte.",
                             "en": "Number of units included in the calculation after trimming."},
    "trimmed_help":         {"es": ("Distritos excluidos del cálculo por estar en los extremos (colas) "
                                    "de X o Y. Siguen visibles como puntos grises."),
                             "en": ("Units excluded from the calculation for being in the X or Y extremes. "
                                    "Still visible as grey dots.")},
    "vs_full":              {"es": "vs. completo",                      "en": "vs. full sample"},
    "interpret_corr_tmpl":  {
        "es": "**Interpretación**: la relación entre *{x}* y *{y}* es **{strength}** (Spearman ρ = {rho:+.2f}, n = {n:,}).",
        "en": "**Interpretation**: the relationship between *{x}* and *{y}* is **{strength}** (Spearman ρ = {rho:+.2f}, n = {n:,}).",
    },
    "gap_warning":          {
        "es": ("⚠️ **Pearson y Spearman difieren en {gap:.2f}.** "
               "Esto sugiere **no-linealidad** o **valores extremos con influencia alta**. "
               "En ese caso, confía más en Spearman (que mide relación monotónica sobre rangos) "
               "que en Pearson. Prueba a recortar outliers para ver si Pearson se acerca a Spearman."),
        "en": ("⚠️ **Pearson and Spearman differ by {gap:.2f}.** "
               "This suggests **non-linearity** or **highly influential extreme values**. "
               "Trust Spearman (monotonic rank relationship) over Pearson. "
               "Try trimming outliers to see if Pearson approaches Spearman."),
    },
    "pearson_spearman_ok":  {
        "es": "✓ Pearson y Spearman son similares → la relación es aproximadamente lineal y no está dominada por outliers.",
        "en": "✓ Pearson and Spearman are similar → the relationship is approximately linear and not dominated by outliers.",
    },
    "partial_reg_title":    {"es": "### 🎛️ Regresión parcial (manteniendo controles constantes)",
                             "en": "### 🎛️ Partial regression (controlling for covariates)"},
    "partial_reg_missing":  {
        "es": "La regresión parcial requiere `statsmodels`. Instálalo con `pip install statsmodels` y reinicia la app.",
        "en": "Partial regression requires `statsmodels`. Install with `pip install statsmodels` and restart the app.",
    },
    "residuals_x":          {"es": "Residuos de {x} | controles",       "en": "Residuals of {x} | controls"},
    "residuals_y":          {"es": "Residuos de {y} | controles",       "en": "Residuals of {y} | controls"},
    "av_plot_title":        {"es": "Gráfico de variable añadida — controlando por: {controls}",
                             "en": "Added-variable plot — controlling for: {controls}"},
    "partial_r_label":      {"es": "Correlación parcial (r)",            "en": "Partial correlation (r)"},
    "beta_label":           {"es": "β (pendiente parcial)",              "en": "β (partial slope)"},
    "pval_label":           {"es": "p-value (β = 0?)",                   "en": "p-value (β = 0?)"},
    "vs_raw":               {"es": "vs. bruta",                         "en": "vs. raw"},
    "partial_r_help":       {
        "es": ("Pearson r calculado sobre los **residuos** de X e Y después de "
               "remover la parte explicada por los controles. Mide la asociación "
               "entre X e Y que NO pasa por los controles."),
        "en": ("Pearson r computed on the **residuals** of X and Y after removing "
               "the part explained by the controls. Measures the X–Y association "
               "that does NOT go through the controls."),
    },
    "beta_help":            {
        "es": ("Coeficiente de X en una regresión múltiple Y ~ X + controles. "
               "Unidades: Δ en Y (transformado si aplica log) por cada +1 en X "
               "(transformado). Por Frisch-Waugh-Lovell, es idéntico a la pendiente "
               "de la recta en este gráfico de residuos."),
        "en": ("Coefficient of X in a multiple regression Y ~ X + controls. "
               "Units: Δ in Y (transformed if log applies) per +1 in X (transformed). "
               "By Frisch-Waugh-Lovell, it equals the slope of the line in this residuals plot."),
    },
    "pval_help":            {
        "es": ("Probabilidad de observar |β| igual o mayor si el verdadero coeficiente "
               "es cero, asumiendo los supuestos de OLS. p < 0.05 es el umbral "
               "convencional de 'significativo', pero con n grande todo sale "
               "significativo — mira también la magnitud (β) y la correlación parcial."),
        "en": ("Probability of observing |β| as large or larger if the true coefficient "
               "is zero, under OLS assumptions. p < 0.05 is conventional 'significance', "
               "but with large n everything becomes significant — also check β magnitude and partial r."),
    },
    "n_controls_help":      {
        "es": "Observaciones con valores no-nulos en X, Y y los {k} controles.",
        "en": "Observations with non-null values in X, Y, and the {k} controls.",
    },
    "verdict_vanishes":     {
        "es": ("**La asociación bruta se desvanece al controlar.** "
               "Probablemente los controles explican la mayor parte "
               "de la relación aparente entre X e Y (confusión / confounder)."),
        "en": ("**The raw association vanishes when controlling.** "
               "The controls likely explain most of the apparent relationship "
               "between X and Y (confounding)."),
    },
    "verdict_flips":        {
        "es": ("⚠️ **El signo de la relación se invierte al controlar.** Caso "
               "clásico de paradoja de Simpson: lo que parecía positivo (o "
               "negativo) sin controles cambia de dirección al mantenerlos constantes. "
               "Interpretar con mucho cuidado."),
        "en": ("⚠️ **The sign of the relationship flips when controlling.** "
               "Classic Simpson's paradox: what appeared positive (or negative) "
               "without controls reverses direction when held constant. "
               "Interpret with great care."),
    },
    "verdict_unchanged":    {
        "es": ("La asociación se mantiene prácticamente igual al controlar "
               "→ los controles no son confundidores de esta relación."),
        "en": ("The association remains practically unchanged when controlling "
               "→ the controls are not confounders of this relationship."),
    },
    "verdict_attenuated":   {
        "es": ("La asociación se **atenúa** ({raw:+.2f} → {partial:+.2f}) "
               "pero no desaparece: parte del efecto bruto se explica por "
               "los controles, y parte queda como efecto propio de X."),
        "en": ("The association is **attenuated** ({raw:+.2f} → {partial:+.2f}) "
               "but does not disappear: part of the raw effect is explained by "
               "the controls, and part remains as X's own effect."),
    },
    "verdict_strengthened": {
        "es": ("La asociación se **refuerza** al controlar "
               "({raw:+.2f} → {partial:+.2f}). Los controles estaban "
               "enmascarando una relación más clara (supresión)."),
        "en": ("The association is **strengthened** when controlling "
               "({raw:+.2f} → {partial:+.2f}). The controls were "
               "masking a clearer relationship (suppression)."),
    },
    "interpret_partial_tmpl": {
        "es": ("**Interpretación**: manteniendo constantes *{controls}*, la "
               "correlación parcial entre *{x}* y *{y}* es **{strength}** "
               "(r = {r:+.2f}, β = {beta:+.3f}, p = {p:.3g}).  \n"),
        "en": ("**Interpretation**: holding *{controls}* constant, the "
               "partial correlation between *{x}* and *{y}* is **{strength}** "
               "(r = {r:+.2f}, β = {beta:+.3f}, p = {p:.3g}).  \n"),
    },
    "partial_detail_title": {"es": "ℹ️ ¿Qué es una regresión parcial? (detalle técnico)",
                             "en": "ℹ️ What is a partial regression? (technical detail)"},
    "partial_detail_body":  {
        "es": """
**Pregunta**: "Manteniendo los controles fijos, ¿cuánto mueve X a Y?"

**Método (Frisch-Waugh-Lovell)**:
1. Se regresa Y contra los controles y se obtiene `residuo_Y` = la parte de Y que los controles **no** explican.
2. Se regresa X contra los mismos controles y se obtiene `residuo_X`.
3. Se correlaciona (y regresa) `residuo_Y` contra `residuo_X`.

La pendiente que sale es **idéntica** al coeficiente β de X en una regresión
múltiple `Y ~ X + controles`. Y el gráfico de residuos es el
**"added variable plot"** — muestra la evidencia que tiene la regresión múltiple
para afirmar que X tiene un efecto propio sobre Y.

**Cuidados**:
- Esto **no** es causalidad. Si hay un confundidor que no has incluido, la estimación sigue sesgada.
- Añadir demasiados controles correlacionados con X causa **colinealidad**: los errores estándar crecen y todo pierde significancia.
- Si controlas por un **mediador** (algo en el camino causal X→Z→Y), "bloqueas" el efecto real.
""",
        "en": """
**Question**: "Holding the controls fixed, how much does X move Y?"

**Method (Frisch-Waugh-Lovell)**:
1. Regress Y on the controls and take `residual_Y` = the part of Y the controls do **not** explain.
2. Regress X on the same controls and take `residual_X`.
3. Correlate (and regress) `residual_Y` on `residual_X`.

The resulting slope is **identical** to the β coefficient of X in a
multiple regression `Y ~ X + controls`. The residuals plot is the
**"added variable plot"** — it shows the evidence the multiple regression
has that X has its own effect on Y.

**Cautions**:
- This is **not** causality. If there is an omitted confounder, the estimate is still biased.
- Adding too many controls correlated with X causes **multicollinearity**: standard errors grow and significance vanishes.
- If you control for a **mediator** (something on the causal path X→Z→Y), you block the real effect.
""",
    },
}

# Variable label dicts — bilingual. Call var_labels(dict_name) to get the
# right language version for the current session.
_CENSUS_VARS_EN = {
    "pct_pobreza_total":       "Total poverty (%)",
    "pct_pobreza_extrema":     "Extreme poverty (%)",
    "idh_2019":                "HDI 2019",
    "pct_rural":               "Rural area (%)",
    "pct_quechua":             "Quechua speakers (%)",
    "pct_aimara":              "Aymara speakers (%)",
    "pct_indigenous_total":    "Indigenous language (%)",
    "pct_castellano":          "Spanish speakers (%)",
    "pct_sin_nivel":           "No education (%)",
    "pct_primaria_o_menos":    "Primary or less (%)",
    "pct_secundaria":          "Secondary (%)",
    "pct_superior_cualquiera": "Higher education (%)",
    "pct_hasta_secundaria":    "Up to secondary (%)",
    "pct_superior":            "Higher education (%)",
    "altitude":                "Altitude (m.a.s.l.)",
    "pob_densidad_2020":       "Population density (hab/km²)",
}
_CONFLICT_VARS_EN = {
    "cvr_deaths":          "CVR deaths (per capita)",
    "cvr_events":          "CVR violent events",
    "cvr_guerr_8088":      "Guerrilla 1980–88",
    "cvr_guerr_8900":      "Guerrilla 1989–00",
    "cvr_state_8088":      "State violence 1980–88",
    "cvr_state_8900":      "State violence 1989–00",
    "emergency_zone_1990": "Emergency zone 1990",
    "guerrilla_presence":  "Guerrilla presence",
    "marxist_vote_1980":   "Marxist vote 1980",
    "illiteracy_1972":     "Illiteracy 1972",
}
_LAND_REFORM_VARS_EN = {
    "landredist_pc":            "Land redistributed (per capita)",
    "landredist_pcprivate":     "Private land redistributed (per capita)",
    "landdist_uncult_pc":       "Uncultivated land redistributed (per capita)",
    "D_LRSurfaceArea50th":      "Above-median land reform surface area",
    "LRpercap_calweighted_log": "Land reform per capita (log, calorie-weighted)",
    "prop_ha_ths":              "Hectares redistributed (thousands)",
}


def t(key: str) -> str:
    """Return the UI string for `key` in the current session language."""
    lang = st.session_state.get("lang", "es")
    entry = STRINGS.get(key, {})
    return entry.get(lang, entry.get("es", key))


def _vlabels(es_dict: dict, en_dict: dict) -> dict:
    """Return the right variable-label dict for the current language."""
    if st.session_state.get("lang", "es") == "en":
        return en_dict
    return es_dict


def census_labels() -> dict:    return _vlabels(CENSUS_VARS, _CENSUS_VARS_EN)
def conflict_labels() -> dict:  return _vlabels(CONFLICT_VARS, _CONFLICT_VARS_EN)
def lr_labels() -> dict:        return _vlabels(LAND_REFORM_VARS, _LAND_REFORM_VARS_EN)
def all_context_labels() -> dict:
    return {**census_labels(), **conflict_labels(), **lr_labels()}

_ELECTION_VARS_EN = {
    "r2_pct_castillo":  "Castillo 2nd round (%)",
    "r2_pct_fujimori":  "Fujimori 2nd round (%)",
    "r2_margin":        "Margin Castillo-Fujimori",
    "swing":            "Swing Castillo (R1→R2)",
    "r1_pct_PL":        "Castillo 1st round (%)",
    "r1_pct_FP":        "Fujimori 1st round (%)",
    "r1_pct_AP":        "Lescano 1st round (%)",
    "r1_pct_RP":        "López Aliaga 1st round (%)",
    "r1_pct_AvP":       "H. de Soto 1st round (%)",
    "r1_pct_APP":       "Acuña 1st round (%)",
    "r1_pct_JP":        "V. Mendoza 1st round (%)",
    "r1_winner_pct":    "Winner 1st round (%)",
}
def election_labels() -> dict:  return _vlabels(ELECTION_VARS, _ELECTION_VARS_EN)

# "No data" styling — keep visually distinct from every palette so that a
# district missing a value can't be confused with a low value. Near-black
# reads as "something different is going on here" against any colorscale.
NODATA_COLOR = "#2b2b2b"
NODATA_LABEL = "Sin datos"  # overridden at render time via t("no_data")

# Imputed-data marker: small "!" rendered at the centroid of districts whose
# current value was inherited from a 1975 parent (land reform or CVR conflict
# data). Warns the user that sub-1975 granularity is a spatial inference, not
# a direct measurement.
IMPUTED_MARK = "!"
IMPUTED_COLOR = "#c0392b"  # burnt red — visible on both light & dark colorscales

ELECTION_VARS = {
    "r2_pct_castillo":  "Castillo 2ª vuelta (%)",
    "r2_pct_fujimori":  "Fujimori 2ª vuelta (%)",
    "r2_margin":        "Margen Castillo-Fujimori",
    "swing":            "Swing Castillo (R1→R2)",
    "r1_pct_PL":        "Castillo 1ª vuelta (%)",
    "r1_pct_FP":        "Fujimori 1ª vuelta (%)",
    "r1_pct_AP":        "Lescano 1ª vuelta (%)",
    "r1_pct_RP":        "López Aliaga 1ª vuelta (%)",
    "r1_pct_AvP":       "H. de Soto 1ª vuelta (%)",
    "r1_pct_APP":       "Acuña 1ª vuelta (%)",
    "r1_pct_JP":        "V. Mendoza 1ª vuelta (%)",
    "r1_winner_pct":    "Ganador 1ª vuelta (%)",
}

# ─── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    # GeoJSON  (uses INEI ubigeo codes)
    with open(os.path.join(DATA_DIR, "peru_distritos.geojson"), encoding="utf-8") as f:
        geojson = json.load(f)

    # Census  (ubigeo = INEI,  reniec = RENIEC)
    census = pd.read_csv(
        os.path.join(DATA_DIR, "census_master_distrito.csv"),
        dtype={"ubigeo": str, "reniec": str},
    )
    # Build RENIEC → INEI crosswalk
    census["reniec"] = census["reniec"].str.split(".").str[0].str.zfill(6)
    reniec_to_inei = census.set_index("reniec")["ubigeo"].to_dict()

    # Drop duplicated name cols that we'll get from election data
    drop_cols = [c for c in ["departamento", "provincia", "distrito"] if c in census.columns]
    census = census.drop(columns=drop_cols)

    # Election  (ubigeo = RENIEC) — domestic only
    elec = pd.read_csv(
        os.path.join(DATA_DIR, "election_distrito.csv"),
        dtype={"ubigeo": str},
    )
    elec = elec[elec["ubigeo"].str[:2].astype(int) < 90].copy()
    # Remap RENIEC → INEI so it joins with GeoJSON and census
    elec["ubigeo_reniec"] = elec["ubigeo"]          # keep original for reference
    elec["ubigeo"] = elec["ubigeo"].map(reniec_to_inei).fillna(elec["ubigeo"])

    # R1 winner per district
    r1_pct_cols = [c for c in elec.columns if c.startswith("r1_pct_")]
    elec["r1_winner"] = (
        elec[r1_pct_cols].idxmax(axis=1).str.replace("r1_pct_", "", regex=False)
    )
    elec["r1_winner_pct"] = elec[r1_pct_cols].max(axis=1)
    elec["r1_winner_name"] = elec["r1_winner"].map(
        lambda x: CANDIDATES_R1.get(x, (x,))[0]
    )

    # Swing: Castillo R2% − Castillo R1% (Perú Libre)
    elec["swing"] = elec["r2_pct_castillo"] - elec["r1_pct_PL"]

    # Conflict
    conflict_cols = ["ubigeo", "imputed", "n_parents", "parent_ubigeos"] + list(CONFLICT_VARS.keys())
    conflict = pd.read_csv(
        os.path.join(DATA_DIR, "conflict_distrito.csv"),
        dtype={"ubigeo": str},
    )
    conflict = conflict[[c for c in conflict_cols if c in conflict.columns]]
    # Rename conflict's bookkeeping cols so they don't collide with LR's own
    # `imputed` flag after merge. `imputed` is kept as the legacy alias of
    # `conflict_imputed` so older references (Datos tab) still work.
    conflict = conflict.rename(columns={
        "imputed": "conflict_imputed",
        "n_parents": "conflict_n_parents",
        "parent_ubigeos": "conflict_parent_ubigeos",
    })

    # ── Belt-and-braces guard ─────────────────────────────────────────────────
    # DQ-1 and DQ-4 are now fixed in the source CSV. Keep a lightweight
    # sanity guard so an accidental re-import of a bad CSV doesn't silently
    # corrupt the app (NaN instead of poisoning aggregations).
    census["total_pop"] = pd.to_numeric(census["total_pop"], errors="coerce")
    bad_pop = census["total_pop"] > 2_000_000
    if bad_pop.any():
        census.loc[bad_pop, "total_pop"] = np.nan

    # Land reform (Velasco, 1969-) — 1975-era district list, 1,571 rows.
    # Post-1975 districts simply get NaN (same pattern as conflict, minus the
    # spatial imputation — see TODO for follow-up).
    lr_path = os.path.join(DATA_DIR, "land_reform_distrito.csv")
    if os.path.exists(lr_path):
        lr_keep = ["ubigeo", "imputed", "lr_parent_ubigeo"] + list(LAND_REFORM_VARS.keys())
        lr = pd.read_csv(lr_path, dtype={"ubigeo": str})
        lr = lr[[c for c in lr_keep if c in lr.columns]]
        # Rename LR's `imputed` to `lr_imputed` so it doesn't collide with the
        # conflict flag (now renamed to `conflict_imputed` above).
        lr = lr.rename(columns={"imputed": "lr_imputed"})
    else:
        lr = pd.DataFrame(columns=["ubigeo"])

    # Merge on INEI ubigeo
    df = elec.merge(census, on="ubigeo", how="left")
    df = df.merge(conflict, on="ubigeo", how="left")
    if not lr.empty:
        df = df.merge(lr, on="ubigeo", how="left")

    # Legacy alias: earlier code references `imputed` assuming it means the
    # conflict flag. Keep it as a mirror of `conflict_imputed`.
    if "conflict_imputed" in df.columns:
        df["imputed"] = df["conflict_imputed"]

    # ── Derived: compressed education dichotomy ───────────────────────────────
    # The source columns double-count (pct_primaria_o_menos appears to include
    # pct_sin_nivel), so we can't just add sin_nivel + primaria + secundaria.
    # Instead we define the dichotomy as the complement of "superior":
    #   pct_superior          = pct_superior_cualquiera   (as given)
    #   pct_hasta_secundaria  = 100 − pct_superior        (everything else)
    # This is robust to any overlap in the underlying columns.
    if "pct_superior_cualquiera" in df.columns:
        df["pct_superior"] = pd.to_numeric(df["pct_superior_cualquiera"], errors="coerce")
        df["pct_hasta_secundaria"] = 100.0 - df["pct_superior"]

    # ── Derived: collapsed education dichotomy ────────────────────────────────
    # The source CSV's 4 education columns double-count (sum ≈ 110%) —
    # pct_primaria_o_menos already includes pct_sin_nivel. To get a clean
    # dichotomy, we define:
    #     pct_superior         = pct_superior_cualquiera         (verbatim)
    #     pct_hasta_secundaria = 100 − pct_superior              (complement)
    # They sum to 100 by construction, no double-counting.
    if "pct_superior_cualquiera" in df.columns:
        sup = pd.to_numeric(df["pct_superior_cualquiera"], errors="coerce")
        df["pct_superior"] = sup
        df["pct_hasta_secundaria"] = 100.0 - sup

    # Friendly district label for hover
    df["_label"] = (
        df["DISTRITO"].str.title()
        + " · "
        + df["PROVINCIA"].str.title()
        + " · "
        + df["DEPARTAMENTO"].str.title()
    )

    # Departments list for filter
    depts = sorted(df["DEPARTAMENTO"].dropna().unique().tolist())

    # Build aggregations to province and department levels
    df_prov = aggregate_to_level(df, "provincia")
    df_dep  = aggregate_to_level(df, "departamento")

    # Load the aggregated GeoJSONs
    with open(os.path.join(DATA_DIR, "peru_provincias.geojson"), encoding="utf-8") as f:
        geojson_prov = json.load(f)
    with open(os.path.join(DATA_DIR, "peru_departamentos.geojson"), encoding="utf-8") as f:
        geojson_dep = json.load(f)

    return {
        "distrito":     {"geojson": geojson,      "df": df},
        "provincia":    {"geojson": geojson_prov, "df": df_prov},
        "departamento": {"geojson": geojson_dep,  "df": df_dep},
    }, depts


# ─── Aggregation to higher administrative levels ──────────────────────────────
# Column-handling registry.  The key insight: we can't just groupby().mean() —
# that gives the mathematically wrong answer for percentages (classic Simpson's
# paradox) and ignores the fact that some vars are rates vs. counts.
#
# Rules:
#  • SUM         → vote counts & population counts (additive).
#  • RECOMPUTE   → percentages / margins / winners (derived from summed counts).
#  • POP_WEIGHTED→ rates, densities, geographic coords — weighted by total_pop.
#                   Mathematically: a province's "% pobreza" is
#                   Σ poor_people / Σ total_pop = Σ (rate_i × pop_i) / Σ pop_i,
#                   i.e. the population-weighted mean of the district rates.

_SUM_COLS = (
    # R1 raw vote counts (one per candidate abbr)
    [f"r1_{a}" for a in CANDIDATES_R1]
    + ["VOTOS_VB", "VOTOS_VN", "VOTOS_VI",
       "r1_total_valid", "r1_blank", "r1_null",
       "r2_castillo", "r2_fujimori", "r2_blank", "r2_null", "r2_total_valid",
       "total_pop", "cvr_events", "population_1972_thousands"]
)

_POP_WEIGHTED_COLS = [
    # Census rates / continuous
    "pct_pobreza_total", "pct_pobreza_extrema", "idh_2019",
    "indice_vulnerabilidad_alimentaria",
    "pct_quechua", "pct_aimara", "pct_indigenous_total", "pct_castellano",
    "pct_rural", "pct_urbano",
    "pct_sin_nivel", "pct_primaria_o_menos", "pct_secundaria",
    "pct_superior_cualquiera", "pct_univ_completa",
    "pct_hasta_secundaria", "pct_superior",
    "pct_hasta_secundaria", "pct_superior",
    "altitude", "pob_densidad_2020",
    "latitude", "longitude",
    # Conflict rates
    "cvr_deaths", "cvr_guerr_8088", "cvr_guerr_8900",
    "cvr_state_8088", "cvr_state_8900",
    "emergency_zone_1990", "guerrilla_presence",
    "marxist_vote_1980", "illiteracy_1972",
    # Land reform rates (per cápita / normalized / log — all population-weighted)
    "landredist_pc", "landredist_pcprivate", "landredist_pc_2",
    "landdist_uncult_pc", "D_LRSurfaceArea50th",
    "LRpercap_calweighted_log",
]

# Hectares redistributed is a raw count → SUM, not pop-weighted.
_SUM_COLS_LR = ["prop_ha_ths"]


def _pop_weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    """Population-weighted mean that ignores NaN values (without biasing weights).
    Coerces non-numeric strings (e.g. 'S.I.') to NaN before weighting."""
    v = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce")
    mask = v.notna() & w.notna() & (w > 0)
    if not mask.any():
        return np.nan
    return float(np.average(v[mask], weights=w[mask]))


def aggregate_to_level(df: pd.DataFrame, level: str) -> pd.DataFrame:
    """
    Aggregate a district-level dataframe to 'provincia' or 'departamento' level.
    Returns a new dataframe with the same electoral / census / conflict columns,
    correctly aggregated.  Percentages are ALWAYS recomputed from summed raw
    counts, never averaged.
    """
    if level == "distrito":
        return df

    if level == "provincia":
        key_len, suffix = 4, "00"
    elif level == "departamento":
        key_len, suffix = 2, "0000"
    else:
        raise ValueError(f"Unknown level: {level}")

    work = df.copy()
    work["_key"] = work["ubigeo"].str[:key_len] + suffix

    rows = []
    for key, g in work.groupby("_key"):
        row = {"ubigeo": key}

        # ── Names: depend on level ────────────────────────────────────────────
        if level == "provincia":
            row["DEPARTAMENTO"] = g["DEPARTAMENTO"].iloc[0]
            row["PROVINCIA"]    = g["PROVINCIA"].iloc[0]
            row["DISTRITO"]     = g["PROVINCIA"].iloc[0]   # use province name as unit
        else:  # departamento
            row["DEPARTAMENTO"] = g["DEPARTAMENTO"].iloc[0]
            row["PROVINCIA"]    = ""
            row["DISTRITO"]     = g["DEPARTAMENTO"].iloc[0]

        # ── Additive columns ──────────────────────────────────────────────────
        for col in list(_SUM_COLS) + list(_SUM_COLS_LR):
            if col in g.columns:
                row[col] = float(g[col].fillna(0).sum())

        # ── Population-weighted columns ──────────────────────────────────────
        pop = g.get("total_pop", pd.Series(np.zeros(len(g)), index=g.index))
        for col in _POP_WEIGHTED_COLS:
            if col in g.columns:
                row[col] = _pop_weighted_mean(g[col], pop)

        # ── Imputation flags (conflict + LR): true if ANY child was imputed ──
        for src_col, out_col, n_col in [
            ("conflict_imputed", "conflict_imputed", "conflict_n_parents"),
            ("lr_imputed", "lr_imputed", "lr_n_parents"),
        ]:
            if src_col in g.columns:
                row[out_col] = bool(g[src_col].fillna(False).any())
                row[n_col]   = int(g[src_col].fillna(False).sum())
        # Legacy alias used by the Datos tab — still means "conflict imputed".
        if "conflict_imputed" in g.columns:
            row["imputed"] = row["conflict_imputed"]

        rows.append(row)

    out = pd.DataFrame(rows)

    # ── Recompute derived percentages from summed raw counts ─────────────────
    # R1 percentages
    if "r1_total_valid" in out.columns:
        denom = out["r1_total_valid"].replace(0, np.nan)
        for a in CANDIDATES_R1:
            vcol, pcol = f"r1_{a}", f"r1_pct_{a}"
            if vcol in out.columns:
                out[pcol] = (out[vcol] / denom * 100).fillna(0)

    # R1 winner
    r1_pct_cols = [f"r1_pct_{a}" for a in CANDIDATES_R1 if f"r1_pct_{a}" in out.columns]
    if r1_pct_cols:
        out["r1_winner"] = (
            out[r1_pct_cols].idxmax(axis=1).str.replace("r1_pct_", "", regex=False)
        )
        out["r1_winner_pct"] = out[r1_pct_cols].max(axis=1)
        out["r1_winner_name"] = out["r1_winner"].map(
            lambda x: CANDIDATES_R1.get(x, (x,))[0]
        )

    # R2 percentages, margin, winner
    if "r2_total_valid" in out.columns:
        denom = out["r2_total_valid"].replace(0, np.nan)
        out["r2_pct_castillo"] = (out["r2_castillo"] / denom * 100).fillna(0)
        out["r2_pct_fujimori"] = (out["r2_fujimori"] / denom * 100).fillna(0)
        out["r2_margin"] = out["r2_pct_castillo"] - out["r2_pct_fujimori"]
        out["r2_winner"] = np.where(out["r2_margin"] > 0, "Castillo", "Fujimori")

    # Swing
    if "r2_pct_castillo" in out.columns and "r1_pct_PL" in out.columns:
        out["swing"] = out["r2_pct_castillo"] - out["r1_pct_PL"]

    # ── Hover label ──────────────────────────────────────────────────────────
    if level == "provincia":
        out["_label"] = (
            out["PROVINCIA"].str.title() + " · " + out["DEPARTAMENTO"].str.title()
        )
    else:
        out["_label"] = out["DEPARTAMENTO"].str.title()

    return out


# ─── Bivariate helpers ────────────────────────────────────────────────────────
def compute_bivariate_classes(df: pd.DataFrame, primary_col: str, secondary_col: str,
                              binning: str = "quantile"):
    """
    Return (df_with_class, color_map, edges).
      df_with_class: df copy with column _bv_class ('p_s' strings).
      color_map: {class_str → hex color}.
      edges: dict {"primary": (lo_edge, hi_edge), "secondary": (lo_edge, hi_edge)}
             — the numeric cutoffs separating Low/Mid/High bins, so the UI can
             show the user *exactly* what those labels mean.
    """
    out = df.copy()
    p_vals = pd.to_numeric(out[primary_col], errors="coerce")
    s_vals = pd.to_numeric(out[secondary_col], errors="coerce")

    def _bin_and_edges(vals, mode):
        """Return (bin_labels 0/1/2, (lo_edge, hi_edge))."""
        if mode == "quantile":
            # qcut on ranks for robust terciles even with ties
            try:
                bins = pd.qcut(vals.rank(method="first"),
                               q=3, labels=[0, 1, 2])
                lo_edge = float(np.nanpercentile(vals, 100 / 3))
                hi_edge = float(np.nanpercentile(vals, 200 / 3))
                return bins, (lo_edge, hi_edge)
            except ValueError:
                mode = "equal_width"
        # equal_width fallback OR user-chosen
        vmin, vmax = float(np.nanmin(vals)), float(np.nanmax(vals))
        lo_edge = vmin + (vmax - vmin) / 3
        hi_edge = vmin + 2 * (vmax - vmin) / 3
        bins = pd.cut(vals, bins=[-np.inf, lo_edge, hi_edge, np.inf],
                      labels=[0, 1, 2], include_lowest=True)
        return bins, (lo_edge, hi_edge)

    p_bin, p_edges = _bin_and_edges(p_vals, binning)
    s_bin, s_edges = _bin_and_edges(s_vals, binning)

    valid = p_bin.notna() & s_bin.notna()
    out["_bv_class"] = np.where(
        valid,
        p_bin.astype("object").astype(str) + "_" + s_bin.astype("object").astype(str),
        "nan",
    )

    color_map = {"nan": NODATA_COLOR}
    for i in range(3):
        for j in range(3):
            color_map[f"{i}_{j}"] = BIVARIATE_PALETTE[i][j]

    edges = {"primary": p_edges, "secondary": s_edges}
    return out, color_map, edges


def _format_edge(v: float) -> str:
    """Pretty-print a numeric cutoff with sensible precision."""
    if pd.isna(v):
        return "—"
    av = abs(v)
    if av >= 1000:
        return f"{v:,.0f}"
    if av >= 100:
        return f"{v:.0f}"
    if av >= 10:
        return f"{v:.1f}"
    if av >= 1:
        return f"{v:.2f}"
    return f"{v:.3f}"


def build_bivariate_legend(primary_label: str, secondary_label: str,
                           edges: dict | None = None):
    """
    Return a small Plotly figure of the 3×3 swatch legend with axis labels.
    If `edges` is supplied, the tick labels show the numeric cutoffs so that
    "Bajo / Medio / Alto" stops being mysterious.
    """
    fig = go.Figure()
    # i = row index (primary, 0=Low … 2=High, displayed bottom → top)
    # j = col index (secondary, 0=Low … 2=High, displayed left → right)
    for i in range(3):
        for j in range(3):
            fig.add_shape(
                type="rect",
                x0=j - 0.48, x1=j + 0.48,
                y0=i - 0.48, y1=i + 0.48,
                fillcolor=BIVARIATE_PALETTE[i][j],
                line=dict(color="white", width=2),
                layer="below",
            )
    # Invisible scatter so the axes render with correct range
    fig.add_trace(go.Scatter(
        x=[0, 1, 2, 0, 1, 2, 0, 1, 2],
        y=[0, 0, 0, 1, 1, 1, 2, 2, 2],
        mode="markers",
        marker=dict(size=1, color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Build tick labels. If edges given, fold them into the Low / Mid / High
    # labels so the swatches have numeric meaning.
    if edges:
        p_lo, p_hi = edges["primary"]
        s_lo, s_hi = edges["secondary"]
        y_ticks = [
            f"<{_format_edge(p_lo)}",
            f"{_format_edge(p_lo)}–{_format_edge(p_hi)}",
            f"≥{_format_edge(p_hi)}",
        ]
        x_ticks = [
            f"<{_format_edge(s_lo)}",
            f"{_format_edge(s_lo)}–{_format_edge(s_hi)}",
            f"≥{_format_edge(s_hi)}",
        ]
        bottom_margin = 70
    else:
        x_ticks = y_ticks = ["Bajo", "Medio", "Alto"]
        bottom_margin = 50

    fig.update_layout(
        width=260, height=260,
        margin=dict(l=5, r=5, t=10, b=bottom_margin),
        xaxis=dict(
            tickmode="array", tickvals=[0, 1, 2],
            ticktext=x_ticks,
            tickfont=dict(size=9),
            title=dict(text=f"{secondary_label} →", font=dict(size=10)),
            showgrid=False, zeroline=False, fixedrange=True,
            range=[-0.6, 2.6],
        ),
        yaxis=dict(
            tickmode="array", tickvals=[0, 1, 2],
            ticktext=y_ticks,
            tickfont=dict(size=9),
            title=dict(text=f"↑ {primary_label}", font=dict(size=10)),
            showgrid=False, zeroline=False, fixedrange=True,
            range=[-0.6, 2.6],
            scaleanchor="x", scaleratio=1,
        ),
        plot_bgcolor="white",
    )
    return fig


# ─── Map builder ──────────────────────────────────────────────────────────────
def _imputed_flag_for_var(col: str) -> str | None:
    """Return the column that flags whether `col`'s value was imputed for a
    given row, or None if `col` is a directly-measured variable."""
    if col in CONFLICT_VARS:
        return "conflict_imputed"
    if col in LAND_REFORM_VARS:
        return "lr_imputed"
    return None


def build_map(geojson, df, color_col, color_label,
              colorscale="RdBu_r", range_color=None,
              categorical=False, color_map=None,
              center=None, zoom=4.2, hover_extra=None,
              imputed_mask=None):
    """Return a Plotly choropleth_mapbox figure."""

    if center is None:
        center = {"lat": -9.19, "lon": -75.0}

    hover_data = {"ubigeo": False, "_label": False}
    if hover_extra:
        hover_data.update(hover_extra)

    # Split missing vs valid. For categorical layers the bivariate classifier
    # uses the string "nan" as a sentinel; for continuous ones missing means
    # NaN in the numeric column. Either way we want the missing rows drawn in
    # a visually distinct color so they can't be mistaken for "low value".
    if categorical:
        missing_mask = df[color_col].astype("object").isin(["nan", "NaN", None]) \
                       | df[color_col].isna()
    else:
        missing_mask = pd.to_numeric(df[color_col], errors="coerce").isna()
    df_valid = df[~missing_mask]
    df_missing = df[missing_mask]

    common = dict(
        geojson=geojson,
        locations="ubigeo",
        featureidkey="properties.UBIGEO",
        mapbox_style="carto-positron",
        center=center,
        zoom=zoom,
        opacity=0.78,
        hover_name="_label",
        hover_data=hover_data,
    )

    if categorical:
        # Drop the 'nan' sentinel from the color map so it doesn't appear as a
        # duplicate legend item — the overlay trace below handles it.
        cm = {k: v for k, v in (color_map or {}).items() if k != "nan"}
        fig = px.choropleth_mapbox(
            df_valid, color=color_col,
            color_discrete_map=cm,
            **common,
        )
    else:
        fig = px.choropleth_mapbox(
            df_valid, color=color_col,
            color_continuous_scale=colorscale,
            range_color=range_color,
            labels={color_col: color_label},
            **common,
        )
        fig.update_coloraxes(
            colorbar=dict(title=color_label, thickness=14, len=0.55, x=1.01)
        )

    # Overlay the "no data" districts in a distinct color. Use a categorical
    # Choroplethmapbox with a single class so it shows up in the legend.
    if len(df_missing) > 0:
        fig.add_trace(go.Choroplethmapbox(
            geojson=geojson,
            locations=df_missing["ubigeo"],
            featureidkey="properties.UBIGEO",
            z=[0] * len(df_missing),
            colorscale=[[0, NODATA_COLOR], [1, NODATA_COLOR]],
            showscale=False,
            marker=dict(
                opacity=0.78,
                line=dict(color="rgba(80,80,80,0.55)", width=0.25),
            ),
            hovertext=df_missing["_label"],
            hovertemplate="<b>%{hovertext}</b><br>" + t("no_data") + "<extra></extra>",
            name=t("no_data"),
            showlegend=True,
            legendgroup="nodata",
        ))

    # Thinner district boundary lines (default is ~1px, too heavy at national zoom)
    fig.update_traces(
        marker_line_width=0.25, marker_line_color="rgba(80,80,80,0.55)",
        selector=dict(type="choroplethmapbox"),
    )

    # Imputed-value marker overlay: "!" at the centroid of each imputed row.
    # Needs `latitude`/`longitude` in df (present for distrito/provincia/dept
    # levels). Silently skips if they're missing.
    if imputed_mask is not None and "latitude" in df.columns and "longitude" in df.columns:
        m = df[imputed_mask.fillna(False).astype(bool) if hasattr(imputed_mask, "fillna") else imputed_mask]
        m = m.dropna(subset=["latitude", "longitude"])
        if len(m):
            fig.add_trace(go.Scattermapbox(
                lat=m["latitude"], lon=m["longitude"],
                mode="text",
                text=[IMPUTED_MARK] * len(m),
                textfont=dict(size=14, color=IMPUTED_COLOR, family="Arial Black"),
                hoverinfo="skip",
                name=t("inherited"),
                showlegend=True,
            ))

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=590,
        legend=dict(
            yanchor="top", y=0.99, xanchor="left", x=0.01,
            bgcolor="rgba(255,255,255,0.82)",
            bordercolor="#ccc", borderwidth=1,
        ),
        clickmode="event+select",
    )
    return fig


# ─── Population-weighted (Dorling-style) bubble map ───────────────────────────
# Rationale: choropleths of Peru are visually dominated by vast, near-empty
# Amazon districts; a bubble map sized by total_pop flips that — each unit
# becomes a circle whose area is proportional to its population, so Lima
# Metropolitana (where most voters actually are) finally looks like it matters.
# This is a "non-contiguous / Dorling-ish" cartogram: we keep the geographic
# centroid (population-weighted at aggregated levels) instead of displacing
# circles to avoid overlap, because the overlap IS the information.

def build_bubble_map(df, color_col, color_label,
                     colorscale="RdBu_r", range_color=None,
                     categorical=False, color_map=None,
                     center=None, zoom=4.2,
                     size_col="total_pop",
                     size_range=(3, 55),
                     imputed_mask=None):
    """
    Return a Plotly Scattermapbox figure where each row is a circle sized by
    `size_col` (default total_pop) and colored by `color_col`.

    Area ∝ population (we map √pop to the marker size so that rendered area,
    not radius, is linear in population).
    """
    if center is None:
        center = {"lat": -9.19, "lon": -75.0}

    # Separate districts with geography+population but *no* value for the
    # coloring variable — they get rendered as distinct "Sin datos" bubbles
    # so they can't be visually confused with low-value ones.
    geo_pop = ["latitude", "longitude", size_col]
    has_geo = df.dropna(subset=geo_pop).copy()
    has_geo = has_geo[has_geo[size_col] > 0]

    if categorical:
        color_missing = has_geo[color_col].astype("object").isin(
            ["nan", "NaN", None]
        ) | has_geo[color_col].isna()
    else:
        color_missing = pd.to_numeric(has_geo[color_col], errors="coerce").isna()

    # Size scaling: sqrt(pop) so AREA is ∝ pop, then min-max into size_range.
    # Compute on the *combined* set so that missing-value bubbles share the
    # same scale as valid ones (a small "sin datos" district shouldn't look
    # bigger than a small valued one just because of the subset it's in).
    smin, smax = size_range
    if len(has_geo):
        sqrt_pop_all = np.sqrt(has_geo[size_col].astype(float))
        s_lo, s_hi = float(sqrt_pop_all.min()), float(sqrt_pop_all.max())
        if s_hi > s_lo:
            has_geo["_size"] = smin + (sqrt_pop_all - s_lo) / (s_hi - s_lo) * (smax - smin)
        else:
            has_geo["_size"] = (smin + smax) / 2.0

    work = has_geo[~color_missing].copy()
    missing = has_geo[color_missing].copy()

    fig = go.Figure()

    if categorical:
        cmap = color_map or {}
        # Stable sort so largest bubbles render at the bottom (under smaller ones)
        work = work.sort_values("_size", ascending=False)
        for cat, grp in work.groupby(color_col, sort=False):
            fig.add_trace(go.Scattermapbox(
                lat=grp["latitude"], lon=grp["longitude"],
                mode="markers",
                marker=dict(
                    size=grp["_size"],
                    sizemode="diameter",
                    color=cmap.get(cat, "#888"),
                    opacity=0.70,
                ),
                name=str(cat),
                text=grp["_label"],
                customdata=np.stack([grp["ubigeo"], grp[size_col]], axis=-1),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    f"{color_label}: {cat}<br>"
                    "Población: %{customdata[1]:,.0f}<extra></extra>"
                ),
            ))
    else:
        cmin = range_color[0] if range_color else float(work[color_col].min())
        cmax = range_color[1] if range_color else float(work[color_col].max())
        work = work.sort_values("_size", ascending=False)
        fig.add_trace(go.Scattermapbox(
            lat=work["latitude"], lon=work["longitude"],
            mode="markers",
            marker=dict(
                size=work["_size"],
                sizemode="diameter",
                color=work[color_col],
                colorscale=colorscale,
                cmin=cmin, cmax=cmax,
                opacity=0.75,
                colorbar=dict(title=color_label, thickness=14, len=0.55, x=1.01),
            ),
            text=work["_label"],
            customdata=np.stack([work["ubigeo"], work[size_col], work[color_col]], axis=-1),
            hovertemplate=(
                "<b>%{text}</b><br>"
                f"{color_label}: %{{customdata[2]:.2f}}<br>"
                "Población: %{customdata[1]:,.0f}<extra></extra>"
            ),
            showlegend=False,
        ))

    # "Sin datos" bubbles for rows that have geography+pop but no color value.
    if len(missing) > 0:
        missing = missing.sort_values("_size", ascending=False)
        fig.add_trace(go.Scattermapbox(
            lat=missing["latitude"], lon=missing["longitude"],
            mode="markers",
            marker=dict(
                size=missing["_size"],
                sizemode="diameter",
                color=NODATA_COLOR,
                opacity=0.55,
            ),
            name=t("no_data"),
            text=missing["_label"],
            customdata=np.stack([missing["ubigeo"], missing[size_col]], axis=-1),
            hovertemplate=(
                "<b>%{text}</b><br>"
                + t("no_data") + "<br>"
                "Población: %{customdata[1]:,.0f}<extra></extra>"
            ),
            showlegend=True,
        ))

    # Imputed-value markers: "!" at centroid of each imputed row.
    if imputed_mask is not None and len(has_geo):
        imp = has_geo[imputed_mask.reindex(has_geo.index).fillna(False).astype(bool)] \
            if hasattr(imputed_mask, "reindex") else has_geo[imputed_mask]
        if len(imp):
            fig.add_trace(go.Scattermapbox(
                lat=imp["latitude"], lon=imp["longitude"],
                mode="text",
                text=[IMPUTED_MARK] * len(imp),
                textfont=dict(size=14, color=IMPUTED_COLOR, family="Arial Black"),
                hoverinfo="skip",
                name=t("inherited"),
                showlegend=True,
            ))

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_center=center,
        mapbox_zoom=zoom,
        margin=dict(l=0, r=0, t=0, b=0),
        height=590,
        legend=dict(
            yanchor="top", y=0.99, xanchor="left", x=0.01,
            bgcolor="rgba(255,255,255,0.82)",
            bordercolor="#ccc", borderwidth=1,
        ),
        clickmode="event+select",
    )
    return fig


# ─── District detail panel ────────────────────────────────────────────────────
def show_district_detail(row: pd.Series, level_key: str = "distrito",
                         on_clear_key: str = "map_key_counter"):
    """Render a detail panel for a clicked unit (district / province / department).

    The "← Volver al mapa" button clears the selection by bumping
    ``st.session_state[on_clear_key]`` — the map chart's `key` includes this
    counter, so bumping it remounts the chart fresh (Plotly's selection state
    is bound to the widget key, so the only reliable way to clear it is to
    remount)."""
    if level_key == "distrito":
        title = row["DISTRITO"].title()
        subtitle = f"{row['PROVINCIA'].title()} · {row['DEPARTAMENTO'].title()}"
        icon = "📍"
    elif level_key == "provincia":
        title = row["PROVINCIA"].title()
        subtitle = f"{t('provincia_subtitle')} · {row['DEPARTAMENTO'].title()}"
        icon = "🏙️"
    else:  # departamento
        title = row["DEPARTAMENTO"].title()
        subtitle = t("department_label")
        icon = "🗺️"

    # Header row: back button on the left, title on the right
    hdr_back, hdr_title = st.columns([1, 5])
    with hdr_back:
        if st.button(t("back_btn"), key=f"clear_selection_{level_key}",
                     help=t("back_help"),
                     use_container_width=True):
            st.session_state[on_clear_key] = st.session_state.get(on_clear_key, 0) + 1
            st.rerun()
    with hdr_title:
        st.markdown(
            f"### {icon} {title}<br><small>{subtitle}</small>",
            unsafe_allow_html=True,
        )
    st.divider()

    # ── 2nd round ──
    col1, col2, col3 = st.columns(3)
    col1.metric(t("castillo_r2"), f"{row['r2_pct_castillo']:.1f}%")
    col2.metric(t("fujimori_r2"), f"{row['r2_pct_fujimori']:.1f}%")
    margin = row["r2_margin"]
    winner = "Castillo" if margin > 0 else "Fujimori"
    col3.metric(t("margin_label"), f"{abs(margin):.1f} pp", delta=f"{winner} {t('wins')}", delta_color="off")

    # ── 1st round bar ──
    st.markdown(t("r1_votes"))
    _vcol = t("voto_pct_col")
    _ccol = t("candidato")
    r1_data = []
    for abbr, (name, party) in CANDIDATES_R1.items():
        col = f"r1_pct_{abbr}"
        if col in row.index and not pd.isna(row[col]):
            r1_data.append({_ccol: f"{name} ({abbr})", _vcol: row[col], "abbr": abbr})
    r1_df = pd.DataFrame(r1_data).sort_values(_vcol, ascending=True)
    bar_colors = [PARTY_COLORS.get(r["abbr"], "#888") for _, r in r1_df.iterrows()]
    fig_bar = go.Figure(go.Bar(
        x=r1_df[_vcol], y=r1_df[_ccol],
        orientation="h",
        marker_color=bar_colors,
        text=r1_df[_vcol].map(lambda v: f"{v:.1f}%"),
        textposition="outside",
    ))
    fig_bar.update_layout(
        height=420, margin=dict(l=0, r=40, t=0, b=0),
        xaxis_title=t("pct_votos"),
        showlegend=False,
        plot_bgcolor="white",
        xaxis=dict(range=[0, r1_df[_vcol].max() * 1.2]),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── Swing ──
    swing_val = row.get("swing", np.nan)
    if not pd.isna(swing_val):
        direction = "📈" if swing_val >= 0 else "📉"
        _swing_detail = t("swing_detail").format(r1=row['r1_pct_PL'], r2=row['r2_pct_castillo'])
        st.markdown(
            f"{t('swing_trace')} {direction} `{swing_val:+.1f} pp`  "
            f"*({_swing_detail})*"
        )

    # ── Census ──
    st.markdown(t("socioeco_context"))
    _cl = census_labels()
    census_items = [
        (_cl.get("pct_pobreza_total", "Pobreza total"), "pct_pobreza_total", "%"),
        (_cl.get("pct_pobreza_extrema", "Pobreza extrema"), "pct_pobreza_extrema", "%"),
        (_cl.get("idh_2019", "IDH 2019"), "idh_2019", ""),
        (_cl.get("pct_rural", "Área rural"), "pct_rural", "%"),
        (_cl.get("pct_indigenous_total", "Lengua indígena"), "pct_indigenous_total", "%"),
        (_cl.get("altitude", "Altitud"), "altitude", " m"),
    ]
    cols = st.columns(3)
    for i, (label, col, unit) in enumerate(census_items):
        val = row.get(col, np.nan)
        if not pd.isna(val):
            cols[i % 3].metric(label, f"{val:.1f}{unit}")

    # ── Conflict ──
    if not pd.isna(row.get("cvr_deaths", np.nan)):
        st.markdown(t("conflict_panel"))
        c1, c2, c3 = st.columns(3)
        c1.metric(t("cvr_deaths_label"), f"{row['cvr_deaths']:.4f}")
        c2.metric(t("violent_events"), f"{row['cvr_events']:.1f}")
        c3.metric(t("emergency_zone"), t("yes") if row.get("emergency_zone_1990", 0) == 1 else "No")
        if row.get("imputed", False):
            st.caption(t("conflict_imputed_cap").format(n=int(row.get("n_parents", 1))))


# ─── Scatter / correlation tab ────────────────────────────────────────────────
def show_scatter(df, level_key: str = "distrito"):
    _unit_plural = t(level_key + "s") if level_key != "departamento" else t("departamentos")
    st.markdown(t("corr_title").format(unit=_unit_plural))
    if level_key == "departamento":
        st.caption(t("corr_few_warning"))

    with st.expander(t("quick_guide_title"), expanded=False):
        st.markdown(t("quick_guide_body"))

    all_x = all_context_labels()
    all_y = election_labels()

    c1, c2, c3 = st.columns([2, 2, 1])
    x_key = c1.selectbox(t("x_var_label"),
                          options=list(all_x.keys()),
                          format_func=lambda k: all_x[k],
                          key="scatter_x")
    y_key = c2.selectbox(t("y_var_label"),
                          options=list(all_y.keys()),
                          format_func=lambda k: all_y[k],
                          key="scatter_y")
    _color_opts = [t("departamento"), t("winner_r2_opt"), t("none_opt")]
    color_by = c3.selectbox(t("color_by_label"), _color_opts, key="scatter_color")

    # ── Robustness controls ───────────────────────────────────────────────────
    c4, c5 = st.columns([2, 2])
    trim_pct = c4.select_slider(
        t("trim_label"),
        options=[0.0, 0.5, 1.0, 2.5, 5.0, 10.0],
        value=0.0,
        help=t("trim_help"),
        key="scatter_trim",
    )
    show_outliers = c5.checkbox(t("show_ghosts"), value=True, key="scatter_ghost")

    # ── Log-scale toggles ─────────────────────────────────────────────────────
    c6, c7 = st.columns([2, 2])
    log_x = c6.checkbox(t("log_x_label"), value=False, key="scatter_log_x", help=t("log_x_help"))
    log_y = c7.checkbox(t("log_y_label"), value=False, key="scatter_log_y", help=t("log_y_help"))

    # ── Controls for partial / conditional regression ─────────────────────────
    # Frisch-Waugh-Lovell: regressing Y on X + Z₁ + Z₂ + … and reporting the
    # coefficient on X is *identical* to:
    #   (1) regressing Y on Z and taking residuals rY
    #   (2) regressing X on Z and taking residuals rX
    #   (3) regressing rY on rX — the slope = β_X in the full model.
    # That residuals-vs-residuals scatter is the "added variable plot" and it
    # shows the relationship between X and Y with the controls held constant.
    control_options = {k: v for k, v in all_x.items() if k != x_key}
    control_keys = st.multiselect(
        t("control_label"),
        options=list(control_options.keys()),
        format_func=lambda k: control_options[k],
        default=[],
        key="scatter_controls",
        help=t("control_help"),
    )

    # Prepare full data — include control columns so we can residualize.
    needed = [x_key, y_key, "DEPARTAMENTO", "r2_winner", "_label"] + control_keys
    needed = list(dict.fromkeys(needed))  # dedupe, preserve order
    full = df[needed].copy()
    # Coerce controls to numeric (census cols may contain 'S.I.' strings)
    for ck in control_keys:
        full[ck] = pd.to_numeric(full[ck], errors="coerce")
    full = full.dropna(subset=[x_key, y_key] + control_keys).copy()

    # Apply log1p transformation if toggled
    # We use np.log1p (natural log of 1+x) to handle zeros gracefully.
    # Negative values can't be log-transformed; drop them with a warning.
    x_col, y_col = x_key, y_key
    x_label = all_x.get(x_key, x_key)
    y_label = all_y.get(y_key, y_key)
    log_notes = []

    if log_x:
        n_neg_x = int((full[x_key] < 0).sum())
        if n_neg_x > 0:
            st.warning(t("neg_x_warning").format(n=n_neg_x))
            full = full[full[x_key] >= 0].copy()
        full["_x_log"] = np.log1p(full[x_key])
        x_col = "_x_log"
        x_label = f"log({all_x.get(x_key, x_key)} + 1)"
        log_notes.append(f"X: ln({all_x.get(x_key, x_key)} + 1)")

    if log_y:
        n_neg_y = int((full[y_key] < 0).sum())
        if n_neg_y > 0:
            st.warning(t("neg_y_warning").format(n=n_neg_y))
            full = full[full[y_key] >= 0].copy()
        full["_y_log"] = np.log1p(full[y_key])
        y_col = "_y_log"
        y_label = f"log({all_y.get(y_key, y_key)} + 1)"
        log_notes.append(f"Y: ln({all_y.get(y_key, y_key)} + 1)")

    # Compute trim mask — applied on the (possibly log-transformed) values
    if trim_pct > 0:
        lo, hi = trim_pct, 100 - trim_pct
        x_lo, x_hi = np.percentile(full[x_col], [lo, hi])
        y_lo, y_hi = np.percentile(full[y_col], [lo, hi])
        keep = (
            (full[x_col] >= x_lo) & (full[x_col] <= x_hi)
            & (full[y_col] >= y_lo) & (full[y_col] <= y_hi)
        )
    else:
        keep = pd.Series(True, index=full.index)

    kept = full[keep]
    dropped = full[~keep]

    color_col = None
    color_map = None
    if color_by == t("departamento"):
        color_col = "DEPARTAMENTO"
    elif color_by == t("winner_r2_opt"):
        color_col = "r2_winner"
        color_map = {"Castillo": PARTY_COLORS["PL"], "Fujimori": PARTY_COLORS["FP"]}

    # Build figure: ghost outliers as grey underlay, then kept points
    fig = go.Figure()
    if show_outliers and len(dropped) > 0:
        fig.add_trace(go.Scatter(
            x=dropped[x_col], y=dropped[y_col],
            mode="markers",
            marker=dict(color="#cccccc", size=6, opacity=0.5,
                        line=dict(width=0)),
            name=t("trimmed_trace").format(n=len(dropped)),
            hovertext=dropped["_label"],
            hoverinfo="text+x+y",
        ))

    # Kept points — use px to get consistent coloring behavior
    kept_fig = px.scatter(
        kept, x=x_col, y=y_col,
        color=color_col, color_discrete_map=color_map,
        hover_name="_label",
        opacity=0.72,
    )
    for tr in kept_fig.data:
        fig.add_trace(tr)

    # OLS trend line on kept (log-transformed if applicable) data
    if len(kept) > 2:
        xv = kept[x_col].values
        yv = kept[y_col].values
        slope, intercept = np.polyfit(xv, yv, 1)
        x_line = np.array([xv.min(), xv.max()])
        y_line = slope * x_line + intercept
        fig.add_trace(go.Scatter(
            x=x_line, y=y_line,
            mode="lines",
            line=dict(color="#333", width=2, dash="solid"),
            name=t("ols_trace").format(n=len(kept)),
            hoverinfo="skip",
        ))

    fig.update_layout(
        height=500, plot_bgcolor="white",
        xaxis=dict(title=x_label,
                   showgrid=True, gridcolor="#eee"),
        yaxis=dict(title=y_label,
                   showgrid=True, gridcolor="#eee"),
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99,
                    bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#ccc", borderwidth=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Banner noting which transformation(s) are in effect ───────────────────
    if log_notes:
        st.info(
            t("log_banner_prefix") + " " + " · ".join(log_notes) + "." + t("log_banner"),
            icon="📐",
        )

    # ── Correlation statistics ────────────────────────────────────────────────
    if len(kept) > 2:
        from scipy import stats as _sst
        # Compute Pearson on whatever columns we're plotting (log-transformed if toggled)
        pearson_r = kept[x_col].corr(kept[y_col])
        spearman_rho, _ = _sst.spearmanr(kept[x_col], kept[y_col])
        # Reference values on the full sample (still in the same transform space)
        pearson_full = full[x_col].corr(full[y_col])
        spearman_full, _ = _sst.spearmanr(full[x_col], full[y_col])

        # Descriptive interpretations of the r value
        def interpret_corr(v):
            a = abs(v)
            _s = STRINGS["corr_strength"].get(st.session_state.get("lang", "es"),
                                              STRINGS["corr_strength"]["es"])
            if a < 0.1:   return _s["none"]
            sign = _s["pos"] if v > 0 else _s["neg"]
            if a < 0.3:   strength = _s["weak"]
            elif a < 0.5: strength = _s["moderate"]
            elif a < 0.7: strength = _s["strong"]
            else:         strength = _s["very_strong"]
            _and = " y " if st.session_state.get("lang", "es") == "es" else " and "
            return f"{strength}{_and}{sign}"

        # Label suffixes reflecting which transformations are active
        pearson_suffix_parts = []
        if log_x or log_y:
            pearson_suffix_parts.append(t("suffix_log"))
        if trim_pct > 0:
            pearson_suffix_parts.append(t("suffix_trim"))
        pearson_suffix = f" — {', '.join(pearson_suffix_parts)}" if pearson_suffix_parts else ""
        spearman_suffix = f" — {t('suffix_trim')}" if trim_pct > 0 else ""

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            t("pearson_label") + pearson_suffix,
            f"{pearson_r:+.3f}",
            delta=f"{pearson_r - pearson_full:+.3f} {t('vs_full')}" if trim_pct > 0 else None,
            delta_color="off",
            help=t("partial_r_help"),
        )
        m2.metric(
            t("spearman_label") + spearman_suffix,
            f"{spearman_rho:+.3f}",
            delta=f"{spearman_rho - spearman_full:+.3f} {t('vs_full')}" if trim_pct > 0 else None,
            delta_color="off",
            help=t("beta_help"),
        )
        m3.metric(
            t("n_used_label"), f"{len(kept):,}",
            help=t("n_help"),
        )
        m4.metric(
            t("trimmed_label"),
            f"{len(dropped):,}",
            delta=(f"{len(dropped)/len(full)*100:.1f}%" if trim_pct > 0 else None),
            delta_color="off",
            help=t("trimmed_help"),
        )

        # Plain-language sentences — Spearman is invariant to log, so we describe
        # the relationship in the original variable space regardless.
        st.markdown(
            t("interpret_corr_tmpl").format(
                x=all_x.get(x_key, x_key), y=all_y.get(y_key, y_key),
                strength=interpret_corr(spearman_rho),
                rho=spearman_rho, n=len(kept),
            )
        )

        # Interpretive notes on Pearson vs Spearman gap
        gap = abs(pearson_r - spearman_rho)
        if gap > 0.1:
            st.warning(t("gap_warning").format(gap=gap))
        else:
            st.caption(t("pearson_spearman_ok"))

    # ── Partial / conditional regression (Frisch-Waugh-Lovell) ────────────────
    if control_keys and len(kept) > len(control_keys) + 2:
        st.divider()
        st.markdown(t("partial_reg_title"))

        try:
            import statsmodels.api as sm
        except ImportError:
            st.error(t("partial_reg_missing"))
            return

        # Build arrays; kept already reflects trim + log transforms on X/Y
        # Controls stay in their natural scale (user can add more X-log toggles later)
        Z = kept[control_keys].astype(float).values
        y_arr = kept[y_col].astype(float).values
        x_arr = kept[x_col].astype(float).values

        # 1) Residualize Y on controls (+ intercept) → ry
        Z_design = sm.add_constant(Z, has_constant="add")
        ry = sm.OLS(y_arr, Z_design).fit().resid
        # 2) Residualize X on controls → rx
        rx = sm.OLS(x_arr, Z_design).fit().resid
        # 3) OLS of ry on rx (no intercept needed — residuals are mean-zero)
        r_design = sm.add_constant(rx, has_constant="add")
        partial_fit = sm.OLS(ry, r_design).fit()
        beta = float(partial_fit.params[1])
        se   = float(partial_fit.bse[1])
        pval = float(partial_fit.pvalues[1])
        partial_r = float(np.corrcoef(rx, ry)[0, 1])

        # Baseline raw correlation we're comparing to
        raw_r = float(np.corrcoef(x_arr, y_arr)[0, 1])

        # ── Added-variable plot: rx vs ry with OLS line ──────────────────────
        ctrl_labels = ", ".join(all_x[c] for c in control_keys)
        av_fig = go.Figure()
        av_fig.add_trace(go.Scatter(
            x=rx, y=ry,
            mode="markers",
            marker=dict(size=6, opacity=0.55, color="#5698b9",
                        line=dict(width=0)),
            text=kept["_label"].values,
            hovertemplate="<b>%{text}</b><br>resX=%{x:.3f}<br>resY=%{y:.3f}<extra></extra>",
            name=f"n={len(kept)}",
        ))
        xl = np.array([rx.min(), rx.max()])
        av_fig.add_trace(go.Scatter(
            x=xl, y=partial_fit.params[0] + beta * xl,
            mode="lines",
            line=dict(color="#333", width=2),
            name=f"β = {beta:+.3f}",
            hoverinfo="skip",
        ))
        av_fig.update_layout(
            height=420, plot_bgcolor="white",
            xaxis=dict(title=t("residuals_x").format(x=x_label),
                       showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#bbb"),
            yaxis=dict(title=t("residuals_y").format(y=y_label),
                       showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#bbb"),
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99,
                        bgcolor="rgba(255,255,255,0.85)",
                        bordercolor="#ccc", borderwidth=1),
            title=dict(
                text=t("av_plot_title").format(controls=ctrl_labels),
                font=dict(size=13), x=0.01, xanchor="left",
            ),
        )
        st.plotly_chart(av_fig, use_container_width=True)

        # ── Metrics ──────────────────────────────────────────────────────────
        p1, p2, p3, p4 = st.columns(4)
        p1.metric(
            t("partial_r_label"),
            f"{partial_r:+.3f}",
            delta=f"{partial_r - raw_r:+.3f} {t('vs_raw')}",
            delta_color="off",
            help=t("partial_r_help"),
        )
        p2.metric(
            t("beta_label"),
            f"{beta:+.3f}",
            help=t("beta_help"),
        )
        p3.metric(
            t("pval_label"),
            f"{pval:.3g}",
            help=t("pval_help"),
        )
        p4.metric(
            "n",
            f"{len(kept):,}",
            help=t("n_controls_help").format(k=len(control_keys)),
        )

        # ── Plain-language interpretation ────────────────────────────────────
        # Qualitative change: did the relationship get weaker, stronger, or flip sign?
        if abs(partial_r) < 0.05 and abs(raw_r) > 0.15:
            verdict = t("verdict_vanishes")
        elif np.sign(partial_r) != np.sign(raw_r) and abs(partial_r) > 0.1:
            verdict = t("verdict_flips")
        elif abs(partial_r) >= 0.9 * abs(raw_r):
            verdict = t("verdict_unchanged")
        elif abs(partial_r) < abs(raw_r):
            verdict = t("verdict_attenuated").format(raw=raw_r, partial=partial_r)
        else:
            verdict = t("verdict_strengthened").format(raw=raw_r, partial=partial_r)

        st.markdown(
            t("interpret_partial_tmpl").format(
                controls=ctrl_labels,
                x=all_x.get(x_key, x_key),
                y=all_y.get(y_key, y_key),
                strength=interpret_corr(partial_r),
                r=partial_r, beta=beta, p=pval,
            )
            + verdict
        )

        with st.expander(t("partial_detail_title")):
            st.markdown(t("partial_detail_body"))


# ─── National summary bar ─────────────────────────────────────────────────────
def show_national_totals(df):
    """One row of headline stats."""
    total_valid = df["r2_total_valid"].sum()
    cast_votes = df["r2_castillo"].sum()
    fuji_votes = df["r2_fujimori"].sum()
    cast_pct = cast_votes / total_valid * 100
    fuji_pct = fuji_votes / total_valid * 100
    cast_distr = (df["r2_winner"] == "Castillo").sum()
    fuji_distr = (df["r2_winner"] == "Fujimori").sum()

    cols = st.columns(6)
    cols[0].metric(t("castillo_nacional"), f"{cast_pct:.2f}%")
    cols[1].metric(t("fujimori_nacional"), f"{fuji_pct:.2f}%")
    cols[2].metric(t("margin_label"), f"{cast_pct - fuji_pct:.2f} pp")
    cols[3].metric(t("distritos_castillo"), f"{cast_distr:,}")
    cols[4].metric(t("distritos_fujimori"), f"{fuji_distr:,}")
    cols[5].metric(t("votos_validos_r2"), f"{total_valid:,.0f}")


# ─── Main app ─────────────────────────────────────────────────────────────────
# Zoom defaults per level — departments are large, districts small
_LEVEL_ZOOM_NATIONAL = {"distrito": 4.2, "provincia": 4.4, "departamento": 4.6}
_LEVEL_ZOOM_FILTERED = {"distrito": 6.5, "provincia": 6.5, "departamento": 6.0}
_LEVEL_LABEL = {"distrito": "Distrito", "provincia": "Provincia", "departamento": "Departamento"}


def main():
    levels, depts = load_data()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        # Language toggle — top of sidebar, affects everything below
        lang_col, _ = st.columns([1, 2])
        with lang_col:
            lang_en = st.toggle("🇬🇧 English", key="lang_toggle")
        st.session_state["lang"] = "en" if lang_en else "es"

        st.title(t("app_title"))
        st.caption(t("app_subtitle"))

        st.divider()
        st.subheader(t("geo_level"))
        level = st.radio(
            t("unit_label"),
            [t("distrito"), t("provincia"), t("departamento")],
            horizontal=True,
            key="level",
            help=t("level_help"),
        )
        level_key = {
            t("distrito"):     "distrito",
            t("provincia"):    "provincia",
            t("departamento"): "departamento",
        }[level]

        # Pull the right df and geojson for this level
        geojson = levels[level_key]["geojson"]
        df = levels[level_key]["df"]

        representation = st.radio(
            t("representation"),
            [t("choropleth"), t("bubbles")],
            horizontal=True,
            key="representation",
            help=t("repr_help"),
        )

        st.divider()
        st.subheader(t("visualization"))

        vuelta = st.radio(t("round"), [t("second_round"), t("first_round")],
                          horizontal=True, key="vuelta")
        is_r2 = vuelta == t("second_round")

        mode_opts = (
            [t("winner"), t("vote_pct"), t("margin"), t("swing")]
            if is_r2
            else [t("winner"), t("vote_pct")]
        )
        mode = st.selectbox(t("color_mode"), mode_opts, key="mode", help=t("mode_help"))
        # Normalise mode back to a stable internal key regardless of language
        _mode_to_key = {
            t("winner"): "winner", t("vote_pct"): "vote_pct",
            t("margin"): "margin", t("swing"): "swing",
        }
        mode_key = _mode_to_key.get(mode, mode)

        cand_abbr = None
        if mode_key == "vote_pct":
            if is_r2:
                cand_r2 = st.radio(t("candidate"), ["Castillo", "Fujimori"], horizontal=True)
                cand_abbr = "castillo" if cand_r2 == "Castillo" else "fujimori"
            else:
                cand_options = {abbr: f"{name} ({abbr})" for abbr, (name, _) in CANDIDATES_R1.items()}
                cand_abbr = st.selectbox(
                    t("candidate"),
                    options=list(cand_options.keys()),
                    format_func=lambda k: cand_options[k],
                    index=list(cand_options.keys()).index("PL"),
                    key="cand_r1",
                )

        # Bivariate mode
        bivariate_on = st.checkbox(t("bivariate_chk"), help=t("bivariate_help"), key="bivariate_on")
        bivariate_sec_col = None
        bivariate_sec_label = None
        if bivariate_on:
            _all_ctx = all_context_labels()
            bivariate_sec_col = st.selectbox(
                t("context_var"),
                options=list(_all_ctx.keys()),
                format_func=lambda k: _all_ctx[k],
                key="bv_sec",
            )
            bivariate_sec_label = _all_ctx[bivariate_sec_col]

            bivariate_binning_label = st.radio(
                t("binning"),
                [t("quantiles"), t("equal_width")],
                horizontal=True, key="bv_binning",
                help=t("binning_help"),
            )
            bivariate_binning = (
                "quantile" if bivariate_binning_label == t("quantiles") else "equal_width"
            )

            if is_r2:
                if mode_key == "vote_pct":
                    primary_preview = (
                        "Castillo 2ª v. (%)" if cand_abbr == "castillo"
                        else "Fujimori 2ª v. (%)"
                    )
                elif mode_key == "swing":
                    primary_preview = "Swing Castillo (pp)"
                else:
                    primary_preview = "Margen Castillo − Fujimori (pp)"
            else:
                if mode_key == "vote_pct":
                    primary_preview = f"{CANDIDATES_R1[cand_abbr][0]} 1ª v. (%)"
                else:
                    primary_preview = "% del ganador (1ª v.)"

            st.info(
                f"**{t('primary_var')}** (filas de la paleta):  \n{primary_preview}  \n\n"
                f"**{t('secondary_var')}** (columnas):  \n{bivariate_sec_label}",
                icon="🎯",
            )

        st.divider()
        st.subheader(t("single_layer"))
        layer_type = st.radio(
            t("dataset"),
            [t("none"), t("census"), t("conflict"), t("land_reform")],
            key="layer_type",
            help=t("layer_help"),
        )
        overlay_col = None
        overlay_label = None
        _cl = census_labels(); _cfl = conflict_labels(); _lrl = lr_labels()
        if layer_type == t("census"):
            overlay_col = st.selectbox(t("census_var"),
                                       options=list(_cl.keys()),
                                       format_func=lambda k: _cl[k],
                                       key="census_var")
            overlay_label = _cl[overlay_col]
        elif layer_type == t("conflict"):
            overlay_col = st.selectbox(t("conflict_var"),
                                       options=list(_cfl.keys()),
                                       format_func=lambda k: _cfl[k],
                                       key="conflict_var")
            overlay_label = _cfl[overlay_col]
        elif layer_type == t("land_reform"):
            overlay_col = st.selectbox(t("lr_var"),
                                       options=list(_lrl.keys()),
                                       format_func=lambda k: _lrl[k],
                                       key="lr_var")
            overlay_label = _lrl[overlay_col]

        st.divider()
        st.subheader(t("filter"))
        _all_label = t("all")
        dept_filter = st.selectbox(t("department"), [_all_label] + depts, key="dept")

    # ── Filter dataframe ───────────────────────────────────────────────────────
    plot_df = df.copy()
    center = {"lat": -9.19, "lon": -75.0}
    zoom = _LEVEL_ZOOM_NATIONAL[level_key]

    if dept_filter != t("all"):
        plot_df = plot_df[plot_df["DEPARTAMENTO"] == dept_filter]
        if "latitude" in plot_df.columns and plot_df["latitude"].notna().any():
            center = {
                "lat": float(plot_df["latitude"].mean()),
                "lon": float(plot_df["longitude"].mean()),
            }
        zoom = _LEVEL_ZOOM_FILTERED[level_key]

    # ── Determine color column & colorscale ───────────────────────────────────
    bivariate_primary_col = None
    bivariate_primary_label = None

    if bivariate_on and bivariate_sec_col:
        # Pick primary electoral column based on current mode
        if is_r2:
            if mode_key == "vote_pct":
                bivariate_primary_col = f"r2_pct_{cand_abbr}"
                bivariate_primary_label = (
                    "Castillo 2ª v. (%)" if cand_abbr == "castillo"
                    else "Fujimori 2ª v. (%)"
                )
            elif mode_key == "swing":
                bivariate_primary_col = "swing"
                bivariate_primary_label = "Swing Castillo (pp)"
            else:
                bivariate_primary_col = "r2_margin"
                bivariate_primary_label = "Margen Castillo−Fujimori"
        else:
            if mode_key == "vote_pct":
                bivariate_primary_col = f"r1_pct_{cand_abbr}"
                bivariate_primary_label = f"{CANDIDATES_R1[cand_abbr][0]} 1ª v. (%)"
            else:
                bivariate_primary_col = "r1_winner_pct"
                bivariate_primary_label = "% voto del ganador (1ª v.)"

        plot_df, bv_color_map, bv_edges = compute_bivariate_classes(
            plot_df, bivariate_primary_col, bivariate_sec_col,
            binning=bivariate_binning,
        )
        color_col = "_bv_class"
        color_label = "Clase bivariada"
        categorical = True
        color_map = bv_color_map
        colorscale = None
        range_color = None
        map_title = f"Bivariado: {bivariate_primary_label} × {bivariate_sec_label}"

    elif overlay_col:
        color_col = overlay_col
        color_label = overlay_label
        colorscale = "YlOrRd"
        range_color = None
        categorical = False
        color_map = None
        map_title = f"{t('single_layer')}: {overlay_label}"

    elif is_r2:
        if mode_key == "winner":
            color_col = "r2_winner"
            color_map = {"Castillo": PARTY_COLORS["PL"], "Fujimori": PARTY_COLORS["FP"]}
            categorical = True
            color_label = t("winner")
            colorscale = None
            range_color = None
            map_title = f"{t('winner')} — {t('second_round')}"

        elif mode_key == "vote_pct":
            color_col = f"r2_pct_{cand_abbr}"
            name = "Castillo" if cand_abbr == "castillo" else "Fujimori"
            color_label = f"{name} (%)"
            colorscale = "Reds" if cand_abbr == "castillo" else "Oranges"
            range_color = [0, 100]
            categorical = False
            color_map = None
            map_title = f"{t('vote_pct')} — {name} ({t('second_round')})"

        elif mode_key == "margin":
            color_col = "r2_margin"
            color_label = f"{t('margin')} (pp)"
            abs_max = float(plot_df["r2_margin"].abs().quantile(0.98))
            colorscale = [
                [0.0, PARTY_COLORS["FP"]],
                [0.5, "#f5f5f5"],
                [1.0, PARTY_COLORS["PL"]],
            ]
            range_color = [-abs_max, abs_max]
            categorical = False
            color_map = None
            map_title = f"{t('margin')} Castillo − Fujimori ({t('second_round')})"

        elif mode_key == "swing":
            color_col = "swing"
            color_label = f"{t('swing')} (pp)"
            abs_max = float(plot_df["swing"].abs().quantile(0.98))
            colorscale = [
                [0.0, "#b5179e"],
                [0.5, "#f5f5f5"],
                [1.0, PARTY_COLORS["PL"]],
            ]
            range_color = [-abs_max, abs_max]
            categorical = False
            color_map = None
            map_title = f"{t('swing')} Castillo (R1→R2)"

    else:  # R1
        if mode_key == "winner":
            color_col = "r1_winner"
            categorical = True
            color_map = {abbr: PARTY_COLORS.get(abbr, "#888") for abbr in df["r1_winner"].unique()}
            color_label = t("winner")
            colorscale = None
            range_color = None
            map_title = f"{t('winner')} — {t('first_round')}"

        elif mode_key == "vote_pct":
            color_col = f"r1_pct_{cand_abbr}"
            name = CANDIDATES_R1[cand_abbr][0]
            color_label = f"{name} (%)"
            colorscale = "Reds" if cand_abbr == "PL" else "Blues"
            range_color = [0, plot_df[color_col].quantile(0.99)]
            categorical = False
            color_map = None
            map_title = f"{t('vote_pct')} — {name} ({t('first_round')})"

    # Hover extras
    if bivariate_on and bivariate_sec_col:
        hover_extra = {
            bivariate_primary_col: ":.2f",
            bivariate_sec_col: ":.2f",
            "_bv_class": False,
        }
    elif is_r2 and not overlay_col:
        hover_extra = {
            "r2_pct_castillo": ":.1f",
            "r2_pct_fujimori": ":.1f",
            "r2_margin": ":.1f",
        }
    elif not is_r2 and not overlay_col:
        hover_extra = {
            "r1_winner_name": True,
            "r1_winner_pct": ":.1f",
        }
    else:
        hover_extra = {color_col: ":.2f"}

    # ── Pseudo-tabs (persist across reruns via session_state) ─────────────────
    # Streamlit's native `st.tabs` doesn't remember the active tab when the
    # script reruns — and every widget interaction triggers a rerun. So typing
    # in the Datos search or toggling a checkbox there snaps the user back to
    # Mapa. Work around it by using a keyed radio as the navigator: the key
    # binds it to session_state, so the selection survives reruns.
    TAB_LABELS = [t("tab_map"), t("tab_corr"), t("tab_data")]
    active_view = st.radio(
        "Vista",
        TAB_LABELS,
        horizontal=True,
        label_visibility="collapsed",
        key="active_view",
    )
    st.markdown(
        # Thin visual divider under the nav so it reads as a tab strip.
        "<div style='border-bottom:1px solid #e6e6e6; margin:-6px 0 8px 0;'></div>",
        unsafe_allow_html=True,
    )

    # ══ MAP TAB ═══════════════════════════════════════════════════════════════
    if active_view == t("tab_map"):
        # Headline stats strip
        show_national_totals(df)
        unit_plural = {"distrito": t("distritos"), "provincia": t("provincias"),
                       "departamento": t("departamentos")}[level_key]
        repr_tag = t("bubbles") if representation == t("bubbles") else t("choropleth")
        st.caption(
            f"{'📊 ' + map_title}  ·  {len(plot_df):,} {unit_plural}  ·  {repr_tag}"
            + (f"  ·  filtrado: **{dept_filter}**" if dept_filter != t("all") else "")
        )
        st.divider()

        # Imputed-value mask: true where the currently-displayed variable was
        # spatially imputed from a 1975 parent district (LR / conflict only).
        _imp_flag = _imputed_flag_for_var(color_col)
        imputed_mask = None
        if _imp_flag and _imp_flag in plot_df.columns:
            imputed_mask = plot_df[_imp_flag].fillna(False).astype(bool)

        # Build & display map — branch by representation
        if representation == t("bubbles"):
            if "total_pop" not in plot_df.columns or plot_df["total_pop"].notna().sum() == 0:
                st.warning(
                    "No hay columna `total_pop` disponible; cayendo a coropleta.",
                    icon="⚠️",
                )
                fig = build_map(
                    geojson=geojson, df=plot_df,
                    color_col=color_col, color_label=color_label,
                    colorscale=colorscale, range_color=range_color,
                    categorical=categorical, color_map=color_map,
                    center=center, zoom=zoom, hover_extra=hover_extra,
                    imputed_mask=imputed_mask,
                )
            else:
                fig = build_bubble_map(
                    df=plot_df,
                    color_col=color_col,
                    color_label=color_label,
                    colorscale=colorscale,
                    range_color=range_color,
                    categorical=categorical,
                    color_map=color_map,
                    center=center,
                    zoom=zoom,
                    imputed_mask=imputed_mask,
                )
        else:
            fig = build_map(
                geojson=geojson,
                df=plot_df,
                color_col=color_col,
                color_label=color_label,
                colorscale=colorscale,
                range_color=range_color,
                categorical=categorical,
                color_map=color_map,
                center=center,
                zoom=zoom,
                hover_extra=hover_extra,
                imputed_mask=imputed_mask,
            )

        # Imputation legend (caption under the map title) — shown only when
        # the user is looking at a variable whose values are (partially)
        # inherited from a 1975 parent district.
        if imputed_mask is not None and imputed_mask.any():
            n_imp = int(imputed_mask.sum())
            source_name = (t("conflict_source") if color_col in CONFLICT_VARS
                           else t("lr_source"))
            unit = {"distrito": t("distritos"), "provincia": t("provincias"),
                    "departamento": t("departamentos")}[level_key]
            unit_s = {"distrito": t("distrito_s"), "provincia": t("provincia_s"),
                      "departamento": t("departamento_s")}[level_key]
            st.caption(
                t("imputed_caption").format(
                    n=n_imp, unit=unit, source=source_name, unit_s=unit_s
                )
            )


        if bivariate_on and bivariate_sec_col:
            map_col, legend_col = st.columns([4, 1])
            with map_col:
                event = st.plotly_chart(
                    fig, use_container_width=True,
                    key=f"main_map_{st.session_state.get('map_key_counter', 0)}",
                    on_select="rerun",
                    selection_mode="points",
                )
            with legend_col:
                st.markdown(t("bivariate_legend"))
                leg_fig = build_bivariate_legend(
                    bivariate_primary_label, bivariate_sec_label,
                    edges=bv_edges,
                )
                st.plotly_chart(leg_fig, use_container_width=True,
                                config={"displayModeBar": False})

                # Explicit threshold caption
                p_lo, p_hi = bv_edges["primary"]
                s_lo, s_hi = bv_edges["secondary"]
                binning_tag = (
                    "cuantiles (≈1/3 de los distritos en cada clase)"
                    if bivariate_binning == "quantile"
                    else "ancho igual en el rango numérico"
                )
                st.caption(
                    f"**Umbrales ({binning_tag}):**  \n"
                    f"• *{bivariate_primary_label}* — "
                    f"Bajo < {_format_edge(p_lo)} · "
                    f"Medio {_format_edge(p_lo)}–{_format_edge(p_hi)} · "
                    f"Alto ≥ {_format_edge(p_hi)}  \n"
                    f"• *{bivariate_sec_label}* — "
                    f"Bajo < {_format_edge(s_lo)} · "
                    f"Medio {_format_edge(s_lo)}–{_format_edge(s_hi)} · "
                    f"Alto ≥ {_format_edge(s_hi)}  \n\n"
                    "Los distritos con ambos valores altos aparecen en la esquina "
                    "superior-derecha del mapa (azul oscuro); con ambos bajos, en la "
                    "inferior-izquierda (gris claro)."
                )
        else:
            event = st.plotly_chart(
                fig, use_container_width=True,
                key=f"main_map_{st.session_state.get('map_key_counter', 0)}",
                on_select="rerun",
                selection_mode="points",
            )

        # ── Click detail panel ────────────────────────────────────────────────
        selected_ubigeo = None
        if event and hasattr(event, "selection") and event.selection:
            pts = event.selection.get("points", [])
            if pts:
                # Choropleth: `location`. Bubble: `customdata` (first element = ubigeo).
                selected_ubigeo = pts[0].get("location")
                if not selected_ubigeo:
                    cd = pts[0].get("customdata")
                    if cd:
                        # customdata may be a list/tuple/ndarray
                        selected_ubigeo = cd[0] if hasattr(cd, "__getitem__") else None

        if selected_ubigeo:
            match = df[df["ubigeo"] == selected_ubigeo]
            if not match.empty:
                st.divider()
                show_district_detail(match.iloc[0], level_key=level_key)
        else:
            click_unit = {"distrito": t("distrito_s"), "provincia": t("provincia_s"),
                          "departamento": t("departamento_s")}[level_key]
            st.info(
                t("click_hint").format(unit=click_unit),
                icon="🖱️",
            )

    # ══ SCATTER TAB ═══════════════════════════════════════════════════════════
    elif active_view == t("tab_corr"):
        show_scatter(df, level_key=level_key)

    # ══ DATA TAB ══════════════════════════════════════════════════════════════
    elif active_view == t("tab_data"):
        unit_plural_data = {"distrito": t("distrito_s"), "provincia": t("provincia_s"),
                            "departamento": t("departamento_s")}[level_key]
        st.markdown(f"### {t('data_title').format(unit=unit_plural_data)}")

        # Column selector
        _g_r2  = {"es": "Electoral 2ª vuelta", "en": "Electoral 2nd round"}[t("lang") if "lang" in STRINGS else "es"]
        _g_r1  = {"es": "Electoral 1ª vuelta", "en": "Electoral 1st round"}[st.session_state.get("lang","es")]
        _g_cen = {"es": "Censo",               "en": "Census"}[st.session_state.get("lang","es")]
        _g_con = {"es": "Conflicto",           "en": "Conflict"}[st.session_state.get("lang","es")]

        col_groups = st.multiselect(
            t("col_groups"),
            [_g_r2, _g_r1, _g_cen, _g_con],
            default=[_g_r2],
        )

        show_cols = ["ubigeo", "DEPARTAMENTO", "PROVINCIA", "DISTRITO"]
        if _g_r2 in col_groups:
            show_cols += ["r2_pct_castillo", "r2_pct_fujimori", "r2_margin", "r2_winner", "swing"]
        if _g_r1 in col_groups:
            show_cols += [f"r1_pct_{a}" for a in CANDIDATES_R1] + ["r1_winner", "r1_winner_pct"]
        if _g_cen in col_groups:
            show_cols += [c for c in CENSUS_VARS if c in df.columns]
        if _g_con in col_groups:
            show_cols += [c for c in CONFLICT_VARS if c in df.columns] + ["imputed"]

        show_cols = [c for c in show_cols if c in plot_df.columns]  # safety check
        show_cols = list(dict.fromkeys(show_cols))  # deduplicate, preserve order

        table_df = plot_df[show_cols].copy()

        # Search
        search = st.text_input(t("search"), placeholder="ej. Ayacucho", key="search")
        if search:
            mask = table_df["DISTRITO"].str.contains(search, case=False, na=False)
            table_df = table_df[mask]

        st.dataframe(
            table_df.reset_index(drop=True),
            use_container_width=True,
            height=500,
            column_config={
                "ubigeo": st.column_config.TextColumn("UBIGEO", width="small"),
                "r2_pct_castillo": st.column_config.NumberColumn("Castillo %", format="%.1f"),
                "r2_pct_fujimori": st.column_config.NumberColumn("Fujimori %", format="%.1f"),
                "r2_margin":       st.column_config.NumberColumn("Margen", format="%.1f"),
                "r2_winner":       st.column_config.TextColumn("Ganador"),
                "swing":           st.column_config.NumberColumn("Swing", format="%+.1f"),
                "imputed":         st.column_config.CheckboxColumn("Imputado"),
            },
        )

        csv = table_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar CSV", csv,
                           file_name=f"peru2021_{level_key}s.csv", mime="text/csv")


if __name__ == "__main__":
    main()

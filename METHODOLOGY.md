# Mapa Estadístico Perú — Methodology & Data Provenance

Last updated: 2026-06-04  
For future agents: read this before touching any data pipeline or app code.

---

## 1. Repo structure

```
app.py                        Main Streamlit app (~2500 lines)
data/                         All CSVs and GeoJSONs loaded at runtime
scripts/                      Reproducible build scripts (run once to regenerate data)
METHODOLOGY.md                This file
TODO.md                       Feature backlog with done/pending status
requirements.txt              Python dependencies
```

---

## 2. Geographic identifiers (critical — read carefully)

Peru has **two parallel ubigeo systems**:

| System | Used by | Format | Example |
|--------|---------|--------|---------|
| **INEI** | Census, official statistics, GeoJSONs | 6-digit numeric | `150101` = Lima district |
| **RENIEC** | Electoral rolls, ONPE | 6-digit numeric | Different codes for Lima/Callao sub-divisions |

They diverge most severely in **Lima Metropolitana and Callao**, where RENIEC created sub-district codes that don't exist in the INEI system. The two systems are fully compatible in the other 23 departments.

**Rule**: the GeoJSON (`peru_distritos.geojson`) uses **INEI codes**. All merges go through INEI ubigeo. The 2021 election CSV originally uses RENIEC codes and is remapped to INEI via `census_master_distrito.csv`'s `reniec` column during `load_data()`.

---

## 3. Data files

### 3a. GeoJSON boundaries

| File | Source | Districts | Vintage |
|------|--------|-----------|---------|
| `data/peru_distritos.geojson` | INEI via SDOT WFS `geoportal:v_distritos_2023` | 1,891 | 2023 |
| `data/peru_provincias.geojson` | Pre-aggregated from district layer | 196 | 2023 |
| `data/peru_departamentos.geojson` | Pre-aggregated from district layer | 25 | 2023 |
| `data/peru_distritos_2017_backup.geojson` | Original app source | 1,874 | ~2017 |

The 2023 GeoJSON is a strict superset of the 2017 one (+17 districts). Downloaded via:
```
https://geosdot.servicios.gob.pe/geoserver/wfs?service=WFS&version=2.0.0
  &request=GetFeature&typeName=geoportal:v_distritos_2023&outputFormat=application/json
```
Simplified with `tolerance=0.005` degrees (geopandas). Properties uppercased to match app expectations (`UBIGEO`, `NOMBDEP`, `NOMBPROV`, `NOMBDIST`, `CAPITAL`).

ñ/accents are fixed post-download via `scripts/fix_enye_encoding.py` (uses `ubigeos-peru` pip package as canonical name source).

### 3b. Census data

`data/census_master_distrito.csv` — INEI Censos 2017, district level.

Key columns: `ubigeo` (INEI), `reniec` (RENIEC code), `departamento`, `provincia`, `distrito`, `total_pop`, `pct_pobreza_total`, `pct_pobreza_extrema`, `idh_2019`, `pct_rural`, `pct_quechua`, `pct_aimara`, `pct_indigenous_total`, `altitude`, `pob_densidad_2020`, `latitude`, `longitude`, and education variables.

**Known DQ issues (resolved)**:
- `total_pop` for Purus (250401) was 29M — corrected to 5,692 in source CSV
- 12 density rows were recomputed as `total_pop / superficie`
- IDH values use INEI district methodology (national avg ~0.43), NOT the PNUD global methodology (Peru national 0.777). Values are correct as published.

### 3c. 2021 election data

`data/election_distrito.csv` — district-level results for all 18 R1 candidates + R2 (Castillo vs Fujimori).

Source: originally provided as a pre-processed CSV (provenance: ONPE official results processed by a third party). Uses **RENIEC ubigeo codes** — remapped to INEI in `load_data()`.

Key columns: `r1_{ABBR}` (raw R1 votes), `r1_pct_{ABBR}` (% of valid), `r2_castillo`, `r2_fujimori`, `r2_pct_castillo`, `r2_pct_fujimori`, `r2_margin`, `r2_winner`.

`swing` is derived at runtime: `r2_pct_castillo − r1_pct_PL`.

2021 R1 party abbreviations:
```
PNP=Humala, FA=Arana, PM=Guzmán, PPS=Santos, VN=Forsyth, AP=Lescano,
AvP=De Soto, PP=Urresti, JP=Mendoza, PPC=Beingolea, FP=Fujimori,
UPP=Vega, RP=López Aliaga, RUNA=Gálvez, SP=Salaverry, PL=Castillo,
DD=Alcántara, APP=Acuña
```

### 3d. 2026 election data (R1 only)

`data/election_2026_r1_distrito.csv` — first-round results, April 12 2026, 100% of actas.

Built by `scripts/build_election_2026_r1_distrito.py`. Source: `oscarzamora/onpeescraper` (GitHub) — mesa-level scrape of ONPE's official results portal, 92,766 mesas, 0 pending.

Uses **INEI ubigeo codes** (no RENIEC remapping needed).

Key columns: `r1_{ABBR}` (raw votes), `r1_pct_{ABBR}` (% of valid), `r1_total_valid`, `r1_blank`, `r1_null`, `r1_winner`.

Verified national totals: FP 17.18%, JxP 12.03%, RP 11.90%.

2026 R1 party abbreviations (main):
```
FP=Fujimori, JxP=Sánchez, RP=López Aliaga, APP=Acuña,
AN=Boluarte (Nicanor), Obras=Belmont, PBG=Forsyth
```

**Coverage caveat**: 1,109 of 2,089 election districts overlap the INEI GeoJSON. The remaining ~980 districts use RENIEC sub-codes for Lima/Callao and have no polygon. This is a known structural issue, not a data error.

### 3e. Conflict data

`data/conflict_distrito.csv` — CVR (Comisión de la Verdad y Reconciliación) armed conflict data, 1980–2000.

Key columns: `cvr_deaths` (per capita), `cvr_events`, `emergency_zone_1990`, `guerrilla_presence`, `cvr_guerr_8088`, `cvr_state_8088`, etc.

Post-1975 districts have spatially-imputed values (see `imputed` / `conflict_imputed` flag). Imputation assigns the parent 1975 district's value when a current district was carved out after 1975.

### 3f. Land reform data

`data/land_reform_distrito.csv` — Velasco land reform (1969–), hectares redistributed.

Source: Dataverse `Peru_LR.dta`. Built by `scripts/build_land_reform_distrito.py`.

Coverage: 1,571 direct + 135 spatially-imputed = 1,706 / 1,874 (91%). The ~168 missing districts fall inside 1975 polygons that have no row in the LR source.

Imputation uses point-in-polygon against `districts_1975_remake.shp` — see `scripts/impute_land_reform_coverage.py`.

Key columns: `landredist_pc`, `landredist_pcprivate`, `landdist_uncult_pc`, `D_LRSurfaceArea50th`, `LRpercap_calweighted_log`, `prop_ha_ths`.

---

## 4. Aggregation methodology

`aggregate_to_level(df, level)` in `app.py` aggregates district→province or district→department.

**Three aggregation rules** — never simple averaging:

| Type | Applied to | Rationale |
|------|-----------|-----------|
| **SUM** | Raw vote counts, `total_pop`, `cvr_events` | Additive quantities |
| **RECOMPUTE** | All percentages, margins, winners | Avoids Simpson's paradox — always divide summed numerator by summed denominator |
| **POP-WEIGHTED MEAN** | Rates (poverty %, IDH, altitude, etc.) | Province % poor = Σ(district_poor_people) / Σ(district_pop) |

Land-reform hectares (`prop_ha_ths`) use SUM (additive count, not rate).

---

## 5. i18n (bilingual ES/EN)

All UI strings go through `t(key)` which reads `st.session_state["lang"]` (set by a sidebar toggle). The `STRINGS` dict (top of `app.py`) holds `{"es": ..., "en": ...}` pairs.

Variable label dicts have bilingual versions: `CENSUS_VARS` / `_CENSUS_VARS_EN`, etc. Use `census_labels()`, `conflict_labels()`, `lr_labels()`, `all_context_labels()`, `election_labels()` — never access the raw dicts directly in UI code.

---

## 6. Build scripts (run order for full rebuild)

```bash
# 1. Fix name encoding in all data files (run after any CSV/GeoJSON change)
python scripts/fix_enye_encoding.py

# 2. Build land reform district CSV from Dataverse .dta
python scripts/build_land_reform_distrito.py

# 3. Impute land reform for post-1975 districts
python scripts/impute_land_reform_coverage.py

# 4. Audit census data quality
python scripts/audit_census.py   # → data/audit_report.csv

# 5. Build province/department GeoJSONs from district GeoJSON
python scripts/build_aggregated_geojsons.py

# 6. Build 2026 R1 election CSV from ONPE scraper
python scripts/build_election_2026_r1_distrito.py
```

---

## 7. Known open issues

- **Lima/Callao RENIEC codes**: ~980 of 2,089 2026 election districts use RENIEC sub-codes not present in the INEI GeoJSON. A RENIEC→INEI crosswalk for Lima/Callao would recover these.
- **New 2026 domestic districts** (~15 genuinely new districts created between 2021 and 2026): no 2021 election data. Imputation via point-in-polygon against the 2021 district layer would assign each new district's results to its parent.
- **2026 R2 data**: second round is June 7 2026. Once ONPE publishes results, run `build_election_2026_r1_distrito.py` variant for R2 and extend the app.
- **Province/dept GeoJSONs**: still use 2017-era aggregation. Rebuilding from the 2023 district layer would pick up the 17 new districts.

---

## 8. Deployment

Streamlit Community Cloud, repo: `nuritmb/mapa-estadistico-peru`.  
Password-gated via `st.secrets["app_password"]` (set in Streamlit Cloud dashboard, not in repo).  
Push to `main` → auto-deploys.  
GitHub auth: use `gh auth login` (browser-based OAuth), then `git push origin main`.

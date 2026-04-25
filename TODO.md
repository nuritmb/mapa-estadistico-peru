# Peru 2021 app — backlog

Prioritized fixes / features. Work through one-by-one.

## Done

- [x] **#11** Land-reform (Velasco, 1969-) layer added as a new context dataset. Extracted from `/Users/carrere/Documents/programar/dataverse_files/Peru_LR.dta` via `scripts/build_land_reform_distrito.py` → `data/land_reform_distrito.csv`. Six variables exposed (`landredist_pc`, `landredist_pcprivate`, `landdist_uncult_pc`, `D_LRSurfaceArea50th`, `LRpercap_calweighted_log`, `prop_ha_ths`). Available in the single-layer overlay ("Capa única → Reforma agraria"), the scatter X dropdown, and the bivariate secondary dropdown. Per-capita cols aggregate as pop-weighted mean; hectares redistributed sum additively.

## Pending

- [x] **#13** Districts with missing values render in near-black (`NODATA_COLOR = #2b2b2b`) with a "Sin datos" legend entry, distinct from any continuous colorscale, categorical palette, or bivariate 3×3 swatch. Works on all four render paths: single-layer choropleth (continuous + categorical), bivariate choropleth (NaN on either axis → "nan" class), and bubble map. Implemented by splitting each df into valid/missing subsets in `build_map` / `build_bubble_map` and overlaying a dedicated Choroplethmapbox / Scattermapbox trace for the missing rows.

- [x] **#12** Added "← Volver" button at the top-left of the detail panel (in `show_district_detail`). Clicking it bumps `st.session_state["map_key_counter"]`, which is appended to the plotly map's `key` — Streamlit's plotly_chart binds selection state to the widget key, so incrementing the counter remounts the chart clean and the detail panel disappears on the next rerun.

- [x] **#14** Imputed districts now flagged on the map when an LR or conflict variable is active: a small red "!" rendered at the centroid of each imputed row (Scattermapbox text trace), plus a legend entry "Valor heredado (1975)" and a caption explaining that the value comes from the 1975 parent polygon. Works at distrito / provincia / departamento levels — aggregated units show the "!" when *any* of their child districts was imputed. Required splitting the single `imputed` column into `conflict_imputed` and `lr_imputed` at load time + mirroring the aggregation for both.

## Pending DQ / coverage for #11

- [x] **#11a** Coverage extended via point-in-polygon imputation (`scripts/impute_land_reform_coverage.py`): match current district representative points against `districts_1975_remake.shp` (reprojected to EPSG:24892), with `sjoin_nearest` fallback for the 1 centroid that falls outside any 1975 polygon. Also fixed a data bug in `build_land_reform_distrito.py`: the .dta's `ubigeo` column has 96 garbage rows with values 1..12 — switched to `ubi12`, the clean 6-digit INEI column. Final coverage: **1,571 direct + 135 imputed = 1,706 / 1,874** (91%). The remaining ~168 current districts fall inside 1975 polygons that have no row in the LR source at all (not fixable without a different source). Imputed rows carry `imputed=True` and `lr_parent_ubigeo`.


- [x] **#1** Clarify bivariate caveat — show primary variable explicitly in sidebar instead of a warning.
- [x] **#4** Thinner district boundary lines.
- [x] **#5** Inline explanations of trimming, Pearson r, Spearman ρ (in Correlation tab's "¿Qué significa esto?" expander).
- [x] **#6** Log-transform toggle (log1p) for skewed X/Y with clear labeling that log is being used.
- [x] **#3** Province-level and department-level aggregation views (level selector in sidebar, aggregated GeoJSONs, population-weighted census, recomputed percentages).
- [x] **#2** Population-weighted (Dorling-style) bubble map — "Representación" toggle in sidebar: each unit is a circle with *area* ∝ total_pop, colored by the current variable. Works at all three levels and in bivariate mode. Click-to-detail works via `customdata[0]` = ubigeo.
- [x] **#8** Compressed education dichotomy — added `pct_superior` and `pct_hasta_secundaria` (= 100 − pct_superior) as derived census variables. They show up in all dropdowns (scatter X, bivariate secondary, overlay). Using `100 − pct_superior` instead of summing the four base columns, because the source columns double-count (sum ≈ 110% — `pct_primaria_o_menos` already includes `pct_sin_nivel`).

## Data-quality issues (source CSVs)

Audit tooling lives at `scripts/audit_census.py`; it writes a flagged-row report to `data/audit_report.csv`. Rerun after any source edit.


- [x] **DQ-1** Fixed in source CSV: Purus (250401) `total_pop` corrected to 5,692; `pob_densidad_2020` recomputed as pop/superficie. Runtime patch (`_POP_KNOWN_FIXES`) removed from `app.py`; only a lightweight belt-and-braces guard (NaN anything > 2M) remains.

- [x] **DQ-4** Fixed in source CSV: 12 broken density rows recomputed as `total_pop / superficie`. Runtime `_DENSITY_KNOWN_BAD` NaN-patch removed from `app.py`. Vintage mismatch (2017 pop vs 2020 density label) is a documentation issue, not a bug — left as-is.

- [x] **DQ-3** Audited against INEI Censos 2017 tomes. Values are correct. Tarapoto (36.8%) and Iquitos (33.6%) are genuine high-education urban centers — consistent with census tables (Tarapoto: 26,762 superior-educated out of 59,837 pop 14+, ~33–45% depending on denominator). The high rates reflect real urban-academic concentrations, not data errors.

- [x] **DQ-5** Audited. The CSV uses INEI's district-level IDH methodology (Peru-specific, national avg ~0.43), not the PNUD global methodology (Peru national 0.777). Values are internally consistent: Iñapari's high IDH (0.680) is driven by income from Brazil border trade, not education. No fix needed.

- [x] **DQ-6** Fixed via `scripts/fix_enye_encoding.py` using the canonical INEI names bundled with the `ubigeos-peru` pip package. Rewrote name columns (by ubigeo lookup) in `census_master_distrito.csv`, `election_distrito.csv`, `land_reform_distrito.csv`, and all three geojsons. Only overwrote values whose accent-stripped form matched the canonical, so legitimate post-package district names are left alone. Total: ~3.5k fixes across 6 files. "Iñapari", "Cañete", "Concepción", "La Convención" etc. now render correctly.

- [x] **DQ-2** Audited against INEI Mapa de Pobreza 2018 official annexes (Anexos.xlsx). Both values are exact CI midpoints from the official source. Iñapari 2.15% confirmed (ranks ~1,854/1,874 — least poor in Peru due to interoceanic highway border trade with Brazil). Callería 6.23% confirmed (low poverty for Ucayali's urban capital). No fix needed.

## Pending

### New (added this session)

- [x] **#7** Datos tab no longer loses focus. Replaced `st.tabs` with a persistent `st.radio(horizontal=True, key="active_view")` navigator + conditional rendering, so the active view survives reruns triggered by widget interactions inside any tab.

- [x] **#9** Partial / conditional regression in the Correlación tab: multiselect "Controlar por (mantener constante)", then Frisch-Waugh-Lovell residualization (statsmodels OLS) produces an added-variable plot plus partial r, β, SE, p-value, and a plain-language "did it attenuate / reinforce / flip sign?" interpretation.

- [x] **#10** Bivariate legend now shows explicit numeric thresholds on both axes (tick labels "<12.3", "12.3–34.8", "≥34.8") + a threshold caption below listing the cutoffs with the variable label. Added a "Método de binning" radio in the sidebar: **cuantiles** (terciles, adaptive) vs **ancho igual** (equal-width in numeric range).

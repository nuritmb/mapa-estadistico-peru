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


- [ ] **DQ-1** `data/census_master_distrito.csv` — Purus (ubigeo **250401**) has `total_pop = 29,381,884` (≈ Peru's national population pasted into one cell). Real 2017 census value is ~5,692. Currently patched in `app.py :: load_data()` via `_POP_KNOWN_FIXES` + a `> 2,000,000` guard. **Fix the source CSV and remove the patch.**

- [ ] **DQ-4** Population density (`pob_densidad_2020`). **Audited** — two findings:
    - **Vintage mismatch (not a bug, but worth documenting).** The column is a 2020 INEI projection while `total_pop` is the 2017 census. Recomputing density as `total_pop / superficie` systematically underestimates by ~20% (median ratio 1.20) because it uses 3-year-old population. Should rename the column to `pob_densidad_2020_proj` or add a `total_pop_2020_proj` column so density is reproducible.
    - **12 genuinely broken rows.** Ratios of CSV density to 2017-recomputed density outside `[0.5, 10]`. Patched at runtime in `app.py` via `_DENSITY_KNOWN_BAD` (values NaN'd). Ground-truth fix needed in the source CSV:
      `150716` Lima·San Antonio (48× too high), `050614` Ayacucho·Saisa, `180302` Moquegua·El Algarrobal, `211105` Puno·San Miguel, `090310` Huancavelica·San Antonio de Antaparco, `040115` Arequipa·Quequeña, `010108` Amazonas·Huancas, `210310` Puno·Usicayos, `211002` Puno·Ananea, `210405` Puno·Pisacoma, `190206` Pasco·Santa Ana de Tusi, `151002` Lima·Alis.

- [ ] **DQ-3** Jungle "education superior" rates look inflated vs. what's plausible. Several Amazonian capitals beat Lima's median (19.6% `pct_superior_cualquiera`):
    - Tarapoto (220901) **36.8%**, Chachapoyas (010101) **36.2%**, Iquitos (160101) **33.6%**, Morales (220910) **33.0%**, Tambopata / Puerto Maldonado (170101) **27.3%**, Callería (250101) **25.6%**.
  Regional capitals with universities can plausibly exceed *average* Lima districts, but beating the *median* of the richest region is suspicious. Likely causes: (a) urban nucleus counted but the depopulated rural ring dropped, (b) denominator issue (non-response coded as "superior"), or (c) "Educación superior" including short technical courses that Lima districts exclude. Worth auditing against INEI's Cédula del Censo 2017.
  Note: this also touches DQ-2 — Callería shows up in both lists (low poverty + high superior-ed rate) which could either be a real Pucallpa-urban nucleus story or a consistent source error.

- [ ] **DQ-5** IDH looks inflated for the same jungle districts that tripped DQ-2 / DQ-3:
    - **Iñapari** (170301): `idh_2019 = 0.680` → rank **72 / 1874**, top 4% nationally. Implausible for a 2,400-person Amazon border town; typical Amazonian districts sit around 0.30–0.45. National IDH is 0.777 as reference.
    - **Callería** (250101): `idh_2019 = 0.563` → rank **304 / 1874**, top 16%.
  Both consistent with a pattern of "urban-nucleus data compiled, rural periphery dropped" (also seen in DQ-2 poverty and DQ-3 education). Cross-check with PNUD's raw district-level IDH table.

- [x] **DQ-6** Fixed via `scripts/fix_enye_encoding.py` using the canonical INEI names bundled with the `ubigeos-peru` pip package. Rewrote name columns (by ubigeo lookup) in `census_master_distrito.csv`, `election_distrito.csv`, `land_reform_distrito.csv`, and all three geojsons. Only overwrote values whose accent-stripped form matched the canonical, so legitimate post-package district names are left alone. Total: ~3.5k fixes across 6 files. "Iñapari", "Cañete", "Concepción", "La Convención" etc. now render correctly.

- [ ] **DQ-2** Poverty data looks suspicious for at least two districts — worth auditing against INEI / ENAHO:
    - **Iñapari** (Tahuamanu, Madre de Dios, ubigeo ~170301): poverty rates look off vs. what you'd expect for a border frontier town with forestry / brazil-nut income.
    - **Callería** (Coronel Portillo, Ucayali, ubigeo ~250101): the provincial capital of Pucallpa; current poverty figures look too high/low given it's the main urban center of the region.
  Suggested check: cross-reference with INEI's [Mapa de Pobreza Distrital 2018](https://www.inei.gob.pe/) and with IDH (which is already in the dataset) — if `pct_pobreza_total` is extreme but `idh_2019` is mid-range, that's a flag. Could be a RENIEC↔INEI ubigeo-crosswalk mismatch (these two districts have been reorganized historically).

## Pending

### New (added this session)

- [x] **#7** Datos tab no longer loses focus. Replaced `st.tabs` with a persistent `st.radio(horizontal=True, key="active_view")` navigator + conditional rendering, so the active view survives reruns triggered by widget interactions inside any tab.

- [x] **#9** Partial / conditional regression in the Correlación tab: multiselect "Controlar por (mantener constante)", then Frisch-Waugh-Lovell residualization (statsmodels OLS) produces an added-variable plot plus partial r, β, SE, p-value, and a plain-language "did it attenuate / reinforce / flip sign?" interpretation.

- [x] **#10** Bivariate legend now shows explicit numeric thresholds on both axes (tick labels "<12.3", "12.3–34.8", "≥34.8") + a threshold caption below listing the cutoffs with the variable label. Added a "Método de binning" radio in the sidebar: **cuantiles** (terciles, adaptive) vs **ancho igual** (equal-width in numeric range).

"""
Build election_2026_r1_distrito.csv — first-round results by district.

Source: oscarzamora/onpeescraper (GitHub)
  - output/mesas_data.txt  : one row per mesa, with ubigeo + vote totals
  - output/votos.txt       : one row per (mesa, party), with vote count
  - output/agrupaciones.txt: party_id → party name

The scraper reached 100% of mesas (92,766 / 92,766, 0 pending).

Output columns (mirrors election_distrito.csv structure):
  ubigeo, DEPARTAMENTO, PROVINCIA, DISTRITO,
  r1_<ABBR> (raw votes per party),
  r1_total_valid, r1_blank, r1_null,
  r1_pct_<ABBR> (% of valid votes),
  r1_winner  (party abbr of top candidate)

Run:
    python scripts/build_election_2026_r1_distrito.py
"""

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_URL = "https://raw.githubusercontent.com/oscarzamora/onpeescraper/main/output"

# Party IDs → short abbreviation (only presidential parties worth keeping)
# Full list: agrupaciones.txt  |  we keep all 38 + blank/null already in mesas_data
PARTY_ABBR = {
    1:  "APP",   # Alianza para el Progreso  (César Acuña)
    2:  "AN",    # Ahora Nación
    3:  "AEV",   # Alianza Electoral Venceremos
    4:  "PM4",   # Perú Moderno
    5:  "FE",    # Fe en el Perú
    6:  "FREPAP",# Frente Popular Agrícola
    7:  "AvP",   # Avanza País
    8:  "FP",    # Fuerza Popular  (Keiko Fujimori) ★
    9:  "FyL",   # Fuerza y Libertad
    10: "JxP",   # Juntos por el Perú  (Roberto Sánchez) ★
    11: "LP",    # Libertad Popular
    12: "APRA",  # Partido Aprista Peruano
    13: "CPP",   # Ciudadanos por el Perú
    14: "Obras", # Partido Cívico Obras
    15: "PTE",   # Trabajadores y Emprendedores
    16: "PBG",   # Partido del Buen Gobierno
    17: "PDU",   # Partido Demócrata Unido Perú
    18: "PDV",   # Partido Demócrata Verde
    19: "PDF",   # Partido Democrático Federal
    20: "SP20",  # Somos Perú
    21: "FE21",  # Frente de la Esperanza 2021
    22: "Morado",# Partido Morado
    23: "PxT",   # País para Todos
    24: "PPP",   # Partido Patriótico del Perú
    25: "CoopP", # Cooperación Popular
    26: "PID",   # Integridad Democrática
    27: "PL",    # Perú Libre
    28: "PPA",   # Perú Acción
    29: "PP1",   # Perú Primero
    30: "PRIN",  # Prin
    31: "SICREO",# Sicreo
    32: "Podemos",# Podemos Perú
    33: "PLG",   # Primero la Gente
    34: "PRG",   # Progresemos
    35: "RP",    # Renovación Popular  (Rafael López Aliaga) ★
    36: "SAP",   # Salvemos al Perú
    37: "UCD",   # Un Camino Diferente
    38: "UN",    # Unidad Nacional
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def fetch_tsv(filename: str) -> pd.DataFrame:
    url = f"{BASE_URL}/{filename}"
    print(f"  Downloading {url} …", end=" ", flush=True)
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), sep="\t", dtype=str, low_memory=False)
    print(f"{len(df):,} rows")
    return df

# ── Download raw files ─────────────────────────────────────────────────────────
print("=== Downloading source files ===")
mesas = fetch_tsv("mesas_data.txt")
votos = fetch_tsv("votos.txt")

# ── Parse types ───────────────────────────────────────────────────────────────
mesas["ubigeo"] = mesas["ubigeo"].str.zfill(6)
mesas["votos_validos"] = pd.to_numeric(mesas["votos_validos"], errors="coerce").fillna(0)
mesas["blancos"]       = pd.to_numeric(mesas["blancos"],       errors="coerce").fillna(0)
mesas["nulos"]         = pd.to_numeric(mesas["nulos"],         errors="coerce").fillna(0)

votos.columns = votos.columns.str.strip()
print("votos columns:", list(votos.columns))

# Normalise column names — the file may use partido_id / agrupacion_id / id
id_col   = next(c for c in votos.columns if "id" in c.lower() or "partido" in c.lower())
vote_col = next(c for c in votos.columns if "voto" in c.lower() or "votos" in c.lower() or "count" in c.lower())
mesa_col = next(c for c in votos.columns if "mesa" in c.lower() or "codigo" in c.lower())

print(f"  Using columns: mesa='{mesa_col}'  party='{id_col}'  votes='{vote_col}'")

votos[id_col]   = pd.to_numeric(votos[id_col],   errors="coerce")
votos[vote_col] = pd.to_numeric(votos[vote_col], errors="coerce").fillna(0)

# Keep only real party votes (drop blank/null/impugnados IDs 80-82 — already in mesas_data)
votos_parties = votos[votos[id_col].notna() & (votos[id_col] < 80)].copy()

# ── Join: attach ubigeo to each vote row ─────────────────────────────────────
print("=== Joining votos → mesas ===")
mesa_ubigeo = mesas[["codigo_mesa", "ubigeo"]].drop_duplicates()
votos_geo = votos_parties.merge(
    mesa_ubigeo,
    left_on=mesa_col,
    right_on="codigo_mesa",
    how="left",
)
missing = votos_geo["ubigeo"].isna().sum()
if missing:
    print(f"  WARNING: {missing:,} vote rows have no matching mesa — dropped")
votos_geo = votos_geo.dropna(subset=["ubigeo"])

# ── Aggregate by district × party ─────────────────────────────────────────────
print("=== Aggregating by district ===")
agg = (
    votos_geo
    .groupby(["ubigeo", id_col])[vote_col]
    .sum()
    .reset_index()
)
# Map party_id → abbreviation
agg["abbr"] = agg[id_col].map(PARTY_ABBR).fillna(agg[id_col].astype(int).astype(str))

# Pivot: rows = ubigeo, cols = party abbr
pivot = (
    agg
    .pivot_table(index="ubigeo", columns="abbr", values=vote_col, aggfunc="sum", fill_value=0)
    .reset_index()
)
pivot.columns.name = None
# Add r1_ prefix
pivot.columns = ["ubigeo"] + [f"r1_{c}" for c in pivot.columns if c != "ubigeo"]

# ── Merge district-level totals (valid, blank, null) ─────────────────────────
dist_totals = (
    mesas
    .groupby("ubigeo")[["votos_validos", "blancos", "nulos"]]
    .sum()
    .reset_index()
    .rename(columns={
        "votos_validos": "r1_total_valid",
        "blancos":       "r1_blank",
        "nulos":         "r1_null",
    })
)
out = pivot.merge(dist_totals, on="ubigeo", how="left")

# ── Compute percentages ───────────────────────────────────────────────────────
party_cols = [c for c in out.columns if c.startswith("r1_") and c not in
              ("r1_total_valid", "r1_blank", "r1_null")]

for col in party_cols:
    abbr = col[3:]   # strip "r1_"
    pct_col = f"r1_pct_{abbr}"
    out[pct_col] = (out[col] / out["r1_total_valid"].replace(0, np.nan) * 100).round(4)

# ── Winner per district ───────────────────────────────────────────────────────
# Only consider real candidate columns (exclude totals)
cand_cols = party_cols
out["r1_winner"] = out[cand_cols].idxmax(axis=1).str.replace("r1_", "", regex=False)

# ── Attach place names via existing ubigeo lookup ─────────────────────────────
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

geo_src = DATA / "census_master_distrito.csv"
if geo_src.exists():
    geo = pd.read_csv(geo_src, dtype={"ubigeo": str},
                      usecols=["ubigeo", "departamento", "provincia", "distrito"])
    geo["ubigeo"] = geo["ubigeo"].str.zfill(6)
    geo = geo.rename(columns={"departamento": "DEPARTAMENTO",
                               "provincia":    "PROVINCIA",
                               "distrito":     "DISTRITO"})
    out = geo.merge(out, on="ubigeo", how="right")
    n_matched = out["DISTRITO"].notna().sum()
    print(f"  Census matched {n_matched:,} / {len(out):,} districts")
else:
    print(f"  WARNING: {geo_src} not found — no place names from census")

# Fill remaining names from ubigeos_peru package
try:
    import json as _json
    import ubigeos_peru as _up
    _pkg = Path(_up.__file__).parent / "resources"
    _dist_names = _json.loads((_pkg / "distritos.json").read_text())["inei"]
    _prov_names = _json.loads((_pkg / "provincias.json").read_text())["inei"]
    _dep_names  = _json.loads((_pkg / "departamentos.json").read_text())["inei"]

    def _fill(row):
        if pd.notna(row.get("DISTRITO")):
            return row
        ubi = str(row["ubigeo"]).zfill(6)
        row["DISTRITO"]     = _dist_names.get(ubi, np.nan)
        row["PROVINCIA"]    = _prov_names.get(ubi[:4], np.nan)
        row["DEPARTAMENTO"] = _dep_names.get(ubi[:2], np.nan)
        return row

    before = out["DISTRITO"].notna().sum()
    out = out.apply(_fill, axis=1)
    after = out["DISTRITO"].notna().sum()
    print(f"  ubigeos_peru filled {after - before:,} more → {after:,} total with names")
except Exception as e:
    print(f"  ubigeos_peru fallback skipped: {e}")

# ── Save ──────────────────────────────────────────────────────────────────────
out["ubigeo"] = out["ubigeo"].str.zfill(6)
out = out.sort_values("ubigeo").reset_index(drop=True)

out_path = DATA / "election_2026_r1_distrito.csv"
out.to_csv(out_path, index=False)
print(f"\n✓ Saved {len(out):,} districts → {out_path}")

# Quick summary
print("\n=== National totals (sanity check) ===")
for abbr in ["FP", "JxP", "RP", "APP"]:
    col = f"r1_{abbr}"
    if col in out.columns:
        votes = out[col].sum()
        total = out["r1_total_valid"].sum()
        print(f"  {abbr:8s}: {votes:>10,.0f}  ({votes/total*100:.2f}%)")
print(f"  {'Total':8s}: {out['r1_total_valid'].sum():>10,.0f}")
print(f"  Winners: {out['r1_winner'].value_counts().to_dict()}")

"""
Extract district-level land-reform (Velasco, 1969–) variables from the
Peru_LR Dataverse dataset and write a clean CSV to data/.

Source: /Users/carrere/Documents/programar/dataverse_files/Peru_LR.dta
  Codebook: /Users/carrere/Documents/programar/dataverse_files/Codebook for Peru_LR.pdf
  Readme:   /Users/carrere/Documents/programar/dataverse_files/Readme.txt
  Replication .do: /Users/carrere/Documents/programar/dataverse_files/Peru_LR.do

Notes on ubigeo coverage:
  The Peru_LR dataset uses the 1975-era district list (1,571 districts).
  Peru now has 1,874 districts in our GeoJSON. ~419 districts were created
  after 1975 by splitting older ones — for those we currently emit no row.
  Ideally we'd spatially impute from parent, same pattern used for conflict
  data (there's an `imputed` flag there). Left as a TODO.

Variables kept (see Codebook for definitions):
  landredist_pc        — land redistributed per capita (normalized 0-1)
  landredist_pcprivate — fraction of redistributed land that was private
  landredist_pc_2      — alternate normalization used in robustness checks
  landdist_uncult_pc   — uncultivated land redistributed, per capita
  D_LRSurfaceArea50th  — binary dummy: above-median LR surface area
  LRpercap_calweighted_log — log(LR per capita · calorie weighting)
  prop_ha_ths          — hectares redistributed, in thousands (raw count)

Run:
    python scripts/build_land_reform_distrito.py
"""

import os
import sys
from pathlib import Path

import pandas as pd

SRC = Path("/Users/carrere/Documents/programar/dataverse_files/Peru_LR.dta")
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "land_reform_distrito.csv"

LR_COLS = [
    "landredist_pc",
    "landredist_pcprivate",
    "landredist_pc_2",
    "landdist_uncult_pc",
    "D_LRSurfaceArea50th",
    "LRpercap_calweighted_log",
    "prop_ha_ths",
]


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found", file=sys.stderr)
        return 1

    df = pd.read_stata(SRC, convert_categoricals=False)

    # Use `ubi12`, not `ubigeo`: the .dta's `ubigeo` column has ~96 garbage
    # rows with values 1..12 (likely a broken import). `ubi12` is the clean
    # 6-digit INEI ubigeo (range 10101..250401).
    df["ubigeo"] = df["ubi12"].astype("Int64").astype(str).str.zfill(6)

    keep = ["ubigeo", "department", "provincia", "distrito"] + LR_COLS
    keep = [c for c in keep if c in df.columns]
    out = df[keep].copy()

    # Drop rows with an all-NaN LR vector (shouldn't happen but be safe)
    lr_present = [c for c in LR_COLS if c in out.columns]
    out = out.dropna(subset=lr_present, how="all")

    # Mark as NOT imputed — reserving the `imputed` flag for future spatial
    # propagation to post-1975 districts (same convention as conflict CSV).
    out["imputed"] = False

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    print(f"Wrote {len(out)} rows × {len(out.columns)} cols → {OUT.relative_to(HERE.parent)}")
    print("\nColumn summary:")
    print(out[lr_present].describe().T[["count", "mean", "std", "min", "50%", "max"]])

    return 0


if __name__ == "__main__":
    sys.exit(main())

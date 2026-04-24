"""
Extend data/land_reform_distrito.csv to cover post-1975 districts via
point-in-polygon spatial imputation.

Problem
-------
The Peru_LR Dataverse dataset is from 1975 (1,571 districts). Peru now has
1,874 districts — the ~300 that don't match were created after 1975 by
splitting an older district. Without imputation, those get NaN on every
land-reform variable, leaving holes in the map.

Fix
---
For each current district that's missing, find the 1975 district whose
polygon contains its centroid, carry the LR values down, and mark
`lr_imputed = True` plus `lr_parent_ubigeo`. Same pattern the conflict
dataset already uses.

Inputs
------
- data/land_reform_distrito.csv           (base, from build_land_reform_distrito.py)
- data/peru_distritos.geojson             (current 1,874 districts, INEI ubigeos)
- ../dataverse_files/districts_1975_remake.shp  (1975 district polygons with DI93 ubigeos)

Output
------
- data/land_reform_distrito.csv           (overwritten, now with coverage ≈ 1,874)

Run:
    python scripts/impute_land_reform_coverage.py
"""

import json
import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

BASE_CSV = DATA / "land_reform_distrito.csv"
CURRENT_GEOJSON = DATA / "peru_distritos.geojson"
SHP_1975 = Path("/Users/carrere/Documents/programar/dataverse_files/districts_1975_remake.shp")

LR_NUMERIC_COLS = [
    "landredist_pc", "landredist_pcprivate", "landredist_pc_2",
    "landdist_uncult_pc", "D_LRSurfaceArea50th",
    "LRpercap_calweighted_log", "prop_ha_ths",
]


def main() -> int:
    for p in (BASE_CSV, CURRENT_GEOJSON, SHP_1975):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 1

    # ── Load ─────────────────────────────────────────────────────────────────
    base = pd.read_csv(BASE_CSV, dtype={"ubigeo": str})
    have_ubigeos = set(base["ubigeo"])
    print(f"Base coverage: {len(base)} districts")

    current = gpd.read_file(CURRENT_GEOJSON)
    # The geojson property is UBIGEO (uppercase); make sure it's string.
    current["UBIGEO"] = current["UBIGEO"].astype(str).str.zfill(6)
    print(f"Current geojson: {len(current)} districts")

    old = gpd.read_file(SHP_1975)
    old["DI93"] = old["DI93"].astype(str).str.zfill(6)
    print(f"1975 polygons: {len(old)} total, {old['DI93'].isin(have_ubigeos).sum()} have LR data")

    # Reproject both to a projected CRS (EPSG:24892 = PSAD56 / Peru central zone)
    # for accurate centroids and distances. Falls back to EPSG:32718 if needed.
    try:
        projected = "EPSG:24892"
        current = current.to_crs(projected)
        old = old.to_crs(projected)
    except Exception:
        projected = "EPSG:32718"
        current = current.to_crs(projected)
        old = old.to_crs(projected)
    print(f"Reprojected to {projected}")

    # ── Identify which current districts need imputation ─────────────────────
    current["_needs"] = ~current["UBIGEO"].isin(have_ubigeos)
    todo = current[current["_needs"]].copy()
    print(f"Missing from LR: {len(todo)} districts → imputing")

    if len(todo) == 0:
        print("Nothing to do.")
        return 0

    # Use representative_point (guaranteed to fall inside the polygon unlike
    # centroid, which can sit outside for concave shapes like coastal districts).
    todo["geometry"] = todo.geometry.representative_point()

    # STEP 1: match each current centroid against ALL 1975 polygons (not just
    # those with LR data). This gives us the true 1975 parent polygon.
    joined = gpd.sjoin(
        todo[["UBIGEO", "geometry"]],
        old[["DI93", "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns="index_right", errors="ignore")

    # STEP 2: for centroids that didn't land inside any 1975 polygon (modern
    # districts in new-territory extensions, e.g. some Amazon frontier cases),
    # fall back to the nearest 1975 polygon.
    missing_parent = joined["DI93"].isna()
    n_missing = int(missing_parent.sum())
    if n_missing:
        print(f"  {n_missing} centroids outside any 1975 polygon — using nearest as parent")
        fallback = gpd.sjoin_nearest(
            todo.loc[missing_parent.values, ["UBIGEO", "geometry"]],
            old[["DI93", "geometry"]],
            how="left",
            distance_col="_dist_m",
        ).drop(columns="index_right", errors="ignore")
        joined.loc[missing_parent.values, "DI93"] = fallback["DI93"].values

    joined = joined.drop_duplicates(subset=["UBIGEO"], keep="first")

    # STEP 3: how many resolved parents actually have LR data?
    resolved = joined["DI93"].isin(have_ubigeos).sum()
    print(f"  Parents with LR data: {resolved} / {len(joined)}")

    # ── Build imputed rows ───────────────────────────────────────────────────
    parent_by_child = joined.set_index("UBIGEO")["DI93"].to_dict()
    base_indexed = base.set_index("ubigeo")

    rows = []
    for child_ubigeo, parent_ubigeo in parent_by_child.items():
        if parent_ubigeo is None or (isinstance(parent_ubigeo, float) and pd.isna(parent_ubigeo)):
            continue
        if parent_ubigeo not in base_indexed.index:
            continue
        src = base_indexed.loc[parent_ubigeo]
        # Carry name columns from current geojson, not from the parent — the
        # user should see the current district's name in hover labels.
        cur_row = current[current["UBIGEO"] == child_ubigeo].iloc[0]
        new = {
            "ubigeo": child_ubigeo,
            "department": str(cur_row.get("DEPARTAMEN") or cur_row.get("NOMBDEP") or ""),
            "provincia":  str(cur_row.get("PROVINCIA") or cur_row.get("NOMBPROV") or ""),
            "distrito":   str(cur_row.get("DISTRITO")  or cur_row.get("NOMBDIST") or ""),
            "imputed": True,
            "lr_parent_ubigeo": parent_ubigeo,
        }
        for col in LR_NUMERIC_COLS:
            if col in base.columns:
                new[col] = src[col]
        rows.append(new)

    imputed = pd.DataFrame(rows)
    print(f"  Imputed rows built: {len(imputed)}")

    # ── Merge with base and write ───────────────────────────────────────────
    # Ensure base has the new bookkeeping columns for consistent schema.
    if "lr_parent_ubigeo" not in base.columns:
        base["lr_parent_ubigeo"] = base["ubigeo"]  # "parent is self" for direct rows
    if "imputed" not in base.columns:
        base["imputed"] = False

    out = pd.concat([base, imputed], ignore_index=True, sort=False)
    out = out.drop_duplicates(subset=["ubigeo"], keep="first")
    out.to_csv(BASE_CSV, index=False)

    n_final = len(out)
    n_imputed = int(out["imputed"].fillna(False).astype(bool).sum())
    print()
    print(f"→ Wrote {n_final} districts total ({n_imputed} imputed, {n_final - n_imputed} direct)")
    print(f"  File: {BASE_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

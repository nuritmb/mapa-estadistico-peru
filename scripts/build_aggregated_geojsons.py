"""
Build province- and department-level GeoJSONs by dissolving the district GeoJSON.

Run once; outputs are written to data/peru_provincias.geojson and
data/peru_departamentos.geojson.

UBIGEO convention after dissolve:
  district     = 6 digits  (e.g. 050401)
  province     = first 4 + '00'   (e.g. 050400)
  departamento = first 2 + '0000' (e.g. 050000)
"""

import os
import geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

src = gpd.read_file(os.path.join(DATA_DIR, "peru_distritos.geojson"))
print(f"Loaded {len(src)} district polygons")

# Repair invalid geometries (self-intersections etc.) — common in real GIS data
n_invalid = (~src.geometry.is_valid).sum()
if n_invalid:
    print(f"  → repairing {n_invalid} invalid geometries with make_valid()")
    src["geometry"] = src.geometry.make_valid()

# Keys for aggregation
src["PROV_UBIGEO"] = src["UBIGEO"].str[:4] + "00"
src["DEP_UBIGEO"]  = src["UBIGEO"].str[:2] + "0000"

# ── Province ──────────────────────────────────────────────────────────────────
print("Dissolving to provinces ...")
prov_names = (
    src.groupby("PROV_UBIGEO")
       .agg(NOMBDEP=("NOMBDEP", "first"),
            NOMBPROV=("NOMBPROV", "first"))
       .reset_index()
)
prov_gdf = src.dissolve(by="PROV_UBIGEO")[["geometry"]].reset_index()
prov_gdf = prov_gdf.merge(prov_names, on="PROV_UBIGEO")
prov_gdf = prov_gdf.rename(columns={"PROV_UBIGEO": "UBIGEO"})
prov_gdf = prov_gdf[["UBIGEO", "NOMBDEP", "NOMBPROV", "geometry"]]

out_prov = os.path.join(DATA_DIR, "peru_provincias.geojson")
if os.path.exists(out_prov):
    os.remove(out_prov)
prov_gdf.to_file(out_prov, driver="GeoJSON")
print(f"→ {len(prov_gdf)} provinces written to {out_prov}")

# ── Department ────────────────────────────────────────────────────────────────
print("Dissolving to departments ...")
dep_names = (
    src.groupby("DEP_UBIGEO")
       .agg(NOMBDEP=("NOMBDEP", "first"))
       .reset_index()
)
dep_gdf = src.dissolve(by="DEP_UBIGEO")[["geometry"]].reset_index()
dep_gdf = dep_gdf.merge(dep_names, on="DEP_UBIGEO")
dep_gdf = dep_gdf.rename(columns={"DEP_UBIGEO": "UBIGEO"})
dep_gdf = dep_gdf[["UBIGEO", "NOMBDEP", "geometry"]]

out_dep = os.path.join(DATA_DIR, "peru_departamentos.geojson")
if os.path.exists(out_dep):
    os.remove(out_dep)
dep_gdf.to_file(out_dep, driver="GeoJSON")
print(f"→ {len(dep_gdf)} departments written to {out_dep}")

print("\nDone.")

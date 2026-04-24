"""
Fix missing ñ / accents in place names across every data file.

Problem
-------
Most of the source CSVs and GeoJSONs dropped ñ and tildes at some ingest step
(DQ-6 in TODO.md). "IÑAPARI" became "INAPARI", "CAÑETE" became "CANETE", etc.
This breaks hover labels, detail-panel titles, and the Datos-tab search.

Approach
--------
Use the `ubigeos_peru` pip package as the canonical source (it bundles INEI's
official ubigeo → name list with proper UTF-8). For each data file we rewrite
the name columns by ubigeo lookup, keeping the file's existing CASE convention
(UPPERCASE or Title) but restoring ñ / á / é / í / ó / ú from the canonical
name.

Districts not present in the package (~42 post-package vintages) are left
untouched. Every fix is logged.

Run:
    python scripts/fix_enye_encoding.py
"""

import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

try:
    import ubigeos_peru  # type: ignore
except ImportError:
    print("ERROR: `pip install ubigeos-peru` first", file=sys.stderr)
    sys.exit(1)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

PKG_RES = Path(ubigeos_peru.__file__).parent / "resources"
_dist = json.loads((PKG_RES / "distritos.json").read_text())["inei"]
_prov = json.loads((PKG_RES / "provincias.json").read_text())["inei"]
_dep  = json.loads((PKG_RES / "departamentos.json").read_text())["inei"]

# ubigeo → canonical name (mixed case, with accents)
CANON_DIST = {k.zfill(6): v for k, v in _dist.items()}
CANON_PROV = {k.zfill(4): v for k, v in _prov.items()}
CANON_DEP  = {k.zfill(2): v for k, v in _dep.items()}


def _strip_accents(s: str) -> str:
    """Remove accents for equality comparison (but leave ñ alone)."""
    if not isinstance(s, str):
        return s
    # Normalise, strip combining marks, but preserve ñ/Ñ by substituting first
    s2 = s.replace("ñ", "\u0001").replace("Ñ", "\u0002")
    s2 = "".join(c for c in unicodedata.normalize("NFD", s2)
                 if unicodedata.category(c) != "Mn")
    return s2.replace("\u0001", "ñ").replace("\u0002", "Ñ")


def _match_case(template: str, canonical: str) -> str:
    """Return `canonical` cased like `template` (UPPER / Title / lower)."""
    if template is None or not isinstance(template, str):
        return canonical
    if template.isupper():
        return canonical.upper()
    if template.islower():
        return canonical.lower()
    return canonical  # Title or mixed — keep package default


def _fix_name(ubigeo: str, template: str, level: str) -> tuple[str, bool]:
    """Return (fixed_name, changed_bool). level in {'dist','prov','dep'}."""
    if level == "dist":
        canon = CANON_DIST.get(str(ubigeo).zfill(6))
    elif level == "prov":
        canon = CANON_PROV.get(str(ubigeo).zfill(6)[:4])
    else:
        canon = CANON_DEP.get(str(ubigeo).zfill(6)[:2])
    if canon is None:
        return template, False
    fixed = _match_case(template, canon)
    if fixed == template:
        return template, False
    # Only call it a "fix" if the ASCII-stripped forms match (else we might be
    # overwriting a legitimately different spelling — e.g. post-package district)
    if _strip_accents(fixed).upper() != _strip_accents(str(template)).upper():
        return template, False
    return fixed, True


def fix_csv(path: Path, col_map: dict[str, str]) -> dict:
    """Fix named columns in a CSV. col_map: {column_name: 'dist'|'prov'|'dep'}."""
    df = pd.read_csv(path, dtype={"ubigeo": str})
    df["ubigeo"] = df["ubigeo"].astype(str).str.zfill(6)
    counts = {}
    for col, level in col_map.items():
        if col not in df.columns:
            continue
        n = 0
        new_vals = []
        for ubi, val in zip(df["ubigeo"], df[col]):
            fixed, changed = _fix_name(ubi, val, level)
            if changed:
                n += 1
            new_vals.append(fixed)
        df[col] = new_vals
        counts[col] = n
    df.to_csv(path, index=False)
    return counts


def fix_geojson(path: Path, prop_map: dict[str, str]) -> dict:
    """Fix named properties in a GeoJSON. prop_map: {prop_name: level}."""
    gj = json.loads(path.read_text())
    counts = {k: 0 for k in prop_map}
    for feat in gj["features"]:
        props = feat["properties"]
        ubi = str(props.get("UBIGEO", "")).zfill(6)
        for prop, level in prop_map.items():
            if prop not in props:
                continue
            fixed, changed = _fix_name(ubi, props[prop], level)
            if changed:
                counts[prop] += 1
            props[prop] = fixed
        # Also fix CAPITAL (it's usually the district name) if present
        if "CAPITAL" in props and "NOMBDIST" in prop_map:
            fixed, changed = _fix_name(ubi, props["CAPITAL"], "dist")
            if changed:
                counts.setdefault("CAPITAL", 0)
                counts["CAPITAL"] += 1
            props["CAPITAL"] = fixed
    path.write_text(json.dumps(gj, ensure_ascii=False))
    return counts


def main() -> int:
    jobs = [
        # CSVs
        (fix_csv, DATA / "census_master_distrito.csv",
         {"departamento": "dep", "provincia": "prov", "distrito": "dist"}),
        (fix_csv, DATA / "election_distrito.csv",
         {"DEPARTAMENTO": "dep", "PROVINCIA": "prov", "DISTRITO": "dist"}),
        (fix_csv, DATA / "land_reform_distrito.csv",
         {"department": "dep", "provincia": "prov", "distrito": "dist"}),
        # GeoJSONs
        (fix_geojson, DATA / "peru_distritos.geojson",
         {"NOMBDEP": "dep", "NOMBPROV": "prov", "NOMBDIST": "dist"}),
        (fix_geojson, DATA / "peru_provincias.geojson",
         {"NOMBDEP": "dep", "NOMBPROV": "prov"}),
        (fix_geojson, DATA / "peru_departamentos.geojson",
         {"NOMBDEP": "dep"}),
    ]

    for fn, path, m in jobs:
        if not path.exists():
            print(f"  skip (missing): {path.name}")
            continue
        counts = fn(path, m)
        total = sum(counts.values())
        print(f"  {path.name:35s}  {total:4d} fixes  {counts}")

    print("\nDone. Re-run the app; hover labels and the Datos-tab search should"
          " now find names like 'Iñapari' and 'Cañete'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

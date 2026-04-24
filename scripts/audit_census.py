"""
Audit script for data/census_master_distrito.csv.

Flags rows that trip any of the quality checks tracked in TODO.md under
the "Data-quality issues" section:

  DQ-1: total_pop > 2,000,000 (no real Peruvian district is that large —
        San Juan de Lurigancho, the largest, is ~1.04M). Purus (250401) has
        29,381,884 in the current file — national pop pasted into one cell.

  DQ-4: pob_densidad_2020 sanity check. NOTE: the column is a 2020 INEI
        projection while total_pop is the 2017 census, so a ~10-25% gap
        between pob_densidad_2020 and (total_pop / superficie) is *expected*
        and not a bug. We only flag rows that look genuinely broken:
          • density ≤ 0 or NaN when pop and area are present
          • density > 10x the 2017-recomputed value (population didn't 10x
            in 3 years for any real district)
          • density inherited from a DQ-1 pop bug (handled via the fixed
            pop check)

  DQ-3: pct_superior_cualquiera high outliers in jungle regions — anything
        > 25% outside Lima/Arequipa/Callao gets flagged.

  DQ-2: Poverty ↔ IDH inconsistency. The two should be strongly negatively
        correlated. We fit a simple linear trend pct_pobreza ~ idh_2019
        over all districts, standardise the residuals, and flag any row
        whose |residual z-score| > 3.

Outputs:
  - data/audit_report.csv  (one row per flagged district, with the check
    columns that tripped)
  - A summary table printed to stdout.

Run once from the repo root:
    python scripts/audit_census.py
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
SRC = DATA_DIR / "census_master_distrito.csv"
OUT = DATA_DIR / "audit_report.csv"

# ── Known fix table (same as the runtime patch in app.py) ─────────────────────
POP_KNOWN_FIXES = {"250401": 5692}  # Purus — real 2017 value

# Districts where a high pct_superior_cualquiera is plausible (big urban cores)
URBAN_CORES = {"LIMA", "CALLAO", "AREQUIPA"}


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found", file=sys.stderr)
        return 1

    df = pd.read_csv(SRC, dtype={"ubigeo": str, "reniec": str})
    n0 = len(df)

    # Coerce numeric columns (some have 'S.I.' strings)
    numeric_cols = [
        "latitude", "longitude", "altitude", "superficie", "total_pop",
        "pob_densidad_2020", "pct_pobreza_total", "pct_pobreza_extrema",
        "idh_2019", "indice_vulnerabilidad_alimentaria",
        "pct_superior_cualquiera",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    flags = pd.DataFrame(
        {
            "ubigeo": df["ubigeo"],
            "departamento": df["departamento"],
            "provincia": df["provincia"],
            "distrito": df["distrito"],
        }
    )

    # ── DQ-1: implausibly large total_pop ────────────────────────────────────
    pop_threshold = 2_000_000  # SJL, the largest district, is ~1.04M
    flags["DQ1_bad_total_pop"] = df["total_pop"] > pop_threshold
    flags["total_pop_raw"] = df["total_pop"]

    # Build a "corrected" total_pop column: apply the known fix table, and
    # NaN-out anything still > threshold. This mirrors the app's runtime patch
    # so density and other downstream checks can use the clean value.
    df["_pop_fixed"] = df["total_pop"].copy()
    for ubi, real in POP_KNOWN_FIXES.items():
        df.loc[df["ubigeo"] == ubi, "_pop_fixed"] = real
    df.loc[df["_pop_fixed"] > pop_threshold, "_pop_fixed"] = np.nan

    # ── DQ-4: density ↔ (total_pop / superficie) consistency ─────────────────
    # Recompute density both ways and flag rows where the CSV's value differs
    # from the recomputation by > 5%.
    df["_density_from_raw_pop"]   = df["total_pop"]  / df["superficie"]
    df["_density_from_fixed_pop"] = df["_pop_fixed"] / df["superficie"]

    def _pct_diff(a: pd.Series, b: pd.Series) -> pd.Series:
        """Safe symmetric-ish percent diff."""
        denom = np.maximum(np.abs(a), np.abs(b))
        return np.where(denom > 0, np.abs(a - b) / denom, 0.0)

    flags["pob_densidad_2020"]       = df["pob_densidad_2020"]
    flags["recomputed_density_raw"]  = df["_density_from_raw_pop"]
    flags["recomputed_density_fixed"] = df["_density_from_fixed_pop"]

    with np.errstate(invalid="ignore", divide="ignore"):
        # Ratio of CSV density to recomputed-from-2017-pop density.
        # A healthy 2020 projection sits in roughly [0.9, 1.5] × 2017 density;
        # anything outside [0.5, 10] is almost certainly a bug.
        density_ratio = df["pob_densidad_2020"] / df["_density_from_fixed_pop"]
    has_inputs = (
        df["superficie"].notna()
        & df["_pop_fixed"].notna()
        & df["pob_densidad_2020"].notna()
    )
    density_broken = (
        (df["pob_densidad_2020"] <= 0)
        | (density_ratio > 10)
        | (density_ratio < 0.5)
    )
    flags["DQ4_density_broken"] = (
        has_inputs & density_broken & (~flags["DQ1_bad_total_pop"])
    )
    flags["density_ratio_csv_over_2017"] = np.where(has_inputs, density_ratio, np.nan)

    # ── DQ-3: high pct_superior_cualquiera outside urban cores ───────────────
    ed_threshold = 25.0
    is_urban_core = df["departamento"].isin(URBAN_CORES)
    flags["pct_superior_cualquiera"] = df["pct_superior_cualquiera"]
    flags["DQ3_education_outlier"] = (
        (df["pct_superior_cualquiera"] > ed_threshold) & (~is_urban_core)
    )

    # ── DQ-2: pobreza ↔ IDH residuals ────────────────────────────────────────
    # Fit pobreza ~ idh on rows that have both; flag |z| > 3.
    pov = df["pct_pobreza_total"]
    idh = df["idh_2019"]
    mask = pov.notna() & idh.notna()
    if mask.sum() >= 20:
        slope, intercept = np.polyfit(idh[mask], pov[mask], 1)
        pred = intercept + slope * idh
        resid = pov - pred
        resid_std = resid[mask].std()
        z = (resid / resid_std) if resid_std > 0 else resid * np.nan
        flags["pct_pobreza_total"] = pov
        flags["idh_2019"] = idh
        flags["pobreza_idh_resid_z"] = z
        flags["DQ2_pobreza_idh_outlier"] = mask & (z.abs() > 3)
        print(f"  pobreza ~ idh fit:  slope={slope:+.2f}  intercept={intercept:+.2f}  "
              f"residual σ={resid_std:.2f}  (n={int(mask.sum())})")
    else:
        flags["DQ2_pobreza_idh_outlier"] = False

    # ── Compile & export flagged rows ────────────────────────────────────────
    flag_cols = [c for c in flags.columns if c.startswith("DQ")]
    any_flag = flags[flag_cols].any(axis=1)
    flagged = flags[any_flag].copy()
    # Reorder: identity, then booleans, then the numeric detail columns
    id_cols   = ["ubigeo", "departamento", "provincia", "distrito"]
    detail    = [c for c in flagged.columns if c not in id_cols + flag_cols]
    flagged   = flagged[id_cols + flag_cols + detail]

    flagged.to_csv(OUT, index=False)
    print()
    print(f"Audited {n0} districts from {SRC.name}")
    print(f"Flagged {len(flagged):4d} total  →  {OUT.relative_to(HERE.parent)}")
    print()
    print("  Breakdown by check:")
    for c in flag_cols:
        print(f"    {c:32s} {int(flags[c].fillna(False).sum()):4d}")

    # Show a preview of the worst offenders per check
    def _preview(df_, mask_col, sort_col, n=5):
        sub = df_[df_[mask_col].fillna(False)]
        if sub.empty:
            return
        sub = sub.sort_values(sort_col, ascending=False, key=lambda s: s.abs())
        print(f"\n  Top {min(n, len(sub))} {mask_col}:")
        # Narrow view: keep labels + the salient metric column
        cols = ["ubigeo", "departamento", "distrito", sort_col]
        for _, r in sub.head(n).iterrows():
            print("    " + "  ".join(
                (f"{r[c]:<12}" if isinstance(r[c], str) else f"{r[c]:>12.3f}")
                for c in cols
            ))

    _preview(flags, "DQ1_bad_total_pop",      "total_pop_raw")
    _preview(flags, "DQ4_density_broken",     "density_ratio_csv_over_2017")
    _preview(flags, "DQ3_education_outlier",  "pct_superior_cualquiera")
    _preview(flags, "DQ2_pobreza_idh_outlier", "pobreza_idh_resid_z")

    return 0


if __name__ == "__main__":
    sys.exit(main())

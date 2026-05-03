"""
generate_india_prices.py
========================
Generates a synthetic 1,000-row dataset of Indian residential real estate
for Gurgaon, Bangalore, and Kolkata with realistic market pricing.

Calibration anchor (verified against example):
  Gurgaon | OverallQual=8 | 2000 sqft | YearBuilt=2018
  → ~2.51 Cr INR → ~$302,000 USD  (user target: 2.5 Cr → $300k)

Exchange rate: 1 USD = 83 INR
Run:
    python generate_india_prices.py
Output:
    india_house_prices.csv
"""

import numpy as np
import pandas as pd

# ── Config ───────────────────────────────────────────────────────────────────
SEED        = 42
N           = 1000
INR_TO_USD  = 83

rng = np.random.default_rng(SEED)

# ── 1. Location ───────────────────────────────────────────────────────────────
# 40 / 40 / 20 split — Kolkata is a smaller market in this dataset
locations = rng.choice(
    ["Gurgaon", "Bangalore", "Kolkata"],
    size=N,
    p=[0.40, 0.40, 0.20],
)

# ── 2. YearBuilt ──────────────────────────────────────────────────────────────
# Heavily weighted toward the post-2000 tech-boom era
_years = np.arange(1960, 2025)
_weights = np.select(
    [_years < 1980, _years < 1990, _years < 2000, _years < 2010, _years < 2020],
    [0.3,           0.8,           1.5,           4.0,           5.5],
    default=6.0,
)
year_built = rng.choice(_years, size=N, p=_weights / _weights.sum())

# ── 3. OverallQual ────────────────────────────────────────────────────────────
# Distribution peaks around 5–7.  Newer builds get a small quality nudge
# because modern construction standards in Indian cities have improved.
_qual_base   = rng.normal(6.0, 1.5, N)
_year_nudge  = (year_built - 1990) * 0.008   # +0.24 for a 2020 build vs 1990
overall_qual = np.clip(
    np.round(_qual_base + _year_nudge).astype(int), 1, 10
)

# ── 4. GrLivArea ─────────────────────────────────────────────────────────────
# City-level means reflect apartment/villa mix typical of each market.
# Premium properties (qual ≥ 8) tend to be larger — luxury tier.
_AREA_PARAMS = {
    "Gurgaon":   {"mu": 1850, "sigma": 520},   # DLF villas, high-rise sectors
    "Bangalore": {"mu": 1500, "sigma": 460},   # Whitefield / Koramangala flats
    "Kolkata":   {"mu": 1200, "sigma": 390},   # New Town / Salt Lake apartments
}
grlivarea = np.zeros(N, dtype=int)
for i, loc in enumerate(locations):
    p = _AREA_PARAMS[loc]
    luxury_bonus = max(0, int(overall_qual[i]) - 7) * 180  # bigger for qual 8-10
    raw = rng.normal(p["mu"] + luxury_bonus, p["sigma"])
    grlivarea[i] = int(np.clip(raw, 600, 5000))

# ── 5. TotalBsmtSF ────────────────────────────────────────────────────────────
# Basements are rare in Gurgaon/Bangalore (waterlogging, construction norms).
# ~8% of units have a small utility basement (parking podium / stilt area).
_has_basement = rng.random(N) < 0.08
total_bsmt_sf = np.where(
    _has_basement,
    rng.integers(150, 550, size=N),
    0,
).astype(int)

# ── 6. SalePrice ──────────────────────────────────────────────────────────────
#
# Formula:
#   price_per_sqft_INR = city_base × quality_mult × year_factor × noise
#   SalePrice_INR      = price_per_sqft × (GrLivArea + 0.5 × TotalBsmtSF)
#   SalePrice_USD      = SalePrice_INR / 83
#
# City base price per sqft (INR) — represents a "mid-quality, mid-age" unit
# in a representative micro-market for each city:
#   Gurgaon   : DLF/Sohna Rd corridor   ~8,000 INR/sqft
#   Bangalore : Whitefield/ITPL belt     ~6,500 INR/sqft
#   Kolkata   : New Town / Salt Lake     ~5,000 INR/sqft
#
_CITY_BASE = {"Gurgaon": 8_000, "Bangalore": 6_500, "Kolkata": 5_000}

# Non-linear quality multiplier: poor finish → 0.30×, ultra-luxury → 2.00×
_QUAL_MULT = {
    1: 0.30, 2: 0.45, 3: 0.60, 4: 0.75,  5: 0.90,
    6: 1.05, 7: 1.20, 8: 1.40, 9: 1.65, 10: 2.00,
}

def _year_factor(yr: int) -> float:
    """Newer construction commands a premium; ageing stock depreciates."""
    if yr < 1980: return 0.60
    if yr < 1990: return 0.75
    if yr < 2000: return 0.88
    if yr < 2010: return 1.00
    if yr < 2020: return 1.12
    return 1.25           # 2020-2024: RERA-era new launches trade at a premium

sale_prices = np.zeros(N, dtype=int)
for i in range(N):
    city    = locations[i]
    qual    = int(overall_qual[i])
    yr      = int(year_built[i])
    area    = int(grlivarea[i]) + int(total_bsmt_sf[i]) * 0.5

    ppsf    = _CITY_BASE[city] * _QUAL_MULT[qual] * _year_factor(yr)

    # ±8% log-normal noise models micro-location variance (floor, view, builder)
    noise   = float(np.clip(rng.lognormal(0.0, 0.08), 0.82, 1.25))

    price_inr = ppsf * area * noise
    price_usd = int(np.clip(price_inr / INR_TO_USD, 8_000, 2_000_000))
    sale_prices[i] = price_usd

# ── Assemble DataFrame ────────────────────────────────────────────────────────
df = pd.DataFrame({
    "OverallQual":  overall_qual,
    "GrLivArea":    grlivarea,
    "TotalBsmtSF":  total_bsmt_sf,
    "YearBuilt":    year_built,
    "Location":     locations,
    "SalePrice":    sale_prices,
})

# ── Sanity-check prints ───────────────────────────────────────────────────────
def _cr(usd: float) -> str:
    return f"{usd * INR_TO_USD / 1e7:.2f} Cr INR"

print("=" * 56)
print(" India House Price Dataset — Sanity Checks")
print("=" * 56)

print("\n[ Shape ]")
print(f"  Rows: {len(df):,}   Columns: {df.shape[1]}")

print("\n[ Location split ]")
for loc, cnt in df["Location"].value_counts().items():
    print(f"  {loc:<12} {cnt:>4} rows  ({cnt/N*100:.0f}%)")

print("\n[ YearBuilt distribution ]")
print(f"  Pre-2000 : {(df['YearBuilt'] < 2000).sum():>4} rows")
print(f"  2000–2009: {((df['YearBuilt'] >= 2000) & (df['YearBuilt'] < 2010)).sum():>4} rows")
print(f"  2010–2019: {((df['YearBuilt'] >= 2010) & (df['YearBuilt'] < 2020)).sum():>4} rows")
print(f"  2020+    : {(df['YearBuilt'] >= 2020).sum():>4} rows")

print("\n[ Basement ]")
print(f"  No basement : {(df['TotalBsmtSF'] == 0).sum():>4} rows")
print(f"  Has basement: {(df['TotalBsmtSF'] > 0).sum():>4} rows")

print("\n[ Median SalePrice by city ]")
medians = df.groupby("Location")["SalePrice"].median()
for loc, usd in medians.items():
    print(f"  {loc:<12}  ${usd:>10,.0f}  ({_cr(usd)})")

print("\n[ Overall SalePrice range ]")
print(f"  Min  ${df['SalePrice'].min():>10,.0f}  ({_cr(df['SalePrice'].min())})")
print(f"  Mean ${df['SalePrice'].mean():>10,.0f}  ({_cr(df['SalePrice'].mean())})")
print(f"  Max  ${df['SalePrice'].max():>10,.0f}  ({_cr(df['SalePrice'].max())})")

print("\n[ Calibration check - Gurgaon qual=8 2000sqft 2018 -> target ~$302k ]")
_mask = (
    (df["Location"] == "Gurgaon") &
    (df["OverallQual"] == 8) &
    (df["GrLivArea"].between(1950, 2050)) &
    (df["YearBuilt"].between(2015, 2021))
)
_sub = df[_mask]["SalePrice"]
if len(_sub):
    print(f"  Matched {len(_sub)} rows — median ${_sub.median():,.0f}  ({_cr(_sub.median())})")
else:
    print("  (No exact matches — check a nearby band manually)")

print("\n[ Pearson correlations with SalePrice ]")
_corr = df[["OverallQual", "GrLivArea", "TotalBsmtSF", "YearBuilt", "SalePrice"]].corr()
for col in ["OverallQual", "GrLivArea", "TotalBsmtSF", "YearBuilt"]:
    print(f"  {col:<14}  r = {_corr.loc[col, 'SalePrice']:+.3f}")

# ── Save ──────────────────────────────────────────────────────────────────────
output_path = "india_house_prices.csv"
df.to_csv(output_path, index=False)
print(f"\nSaved -> {output_path}  ({len(df):,} rows x {df.shape[1]} cols)")

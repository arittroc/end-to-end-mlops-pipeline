"""
generate_data.py
================
Generates a synthetic 1,000-row dataset of Indian residential real estate
for Gurgaon, Bangalore, and Kolkata with realistic market pricing.

Output:
    data/indian_housing.csv
"""

import os

import numpy as np
import pandas as pd

# ── Config ───────────────────────────────────────────────────────────────────
SEED        = 42
N           = 1000
INR_TO_USD  = 83

rng = np.random.default_rng(SEED)

# ── 1. Location ───────────────────────────────────────────────────────────────
locations = rng.choice(
    ["Gurgaon", "Bangalore", "Kolkata"],
    size=N,
    p=[0.40, 0.40, 0.20],
)

# ── 2. YearBuilt ──────────────────────────────────────────────────────────────
_years = np.arange(1960, 2025)
_weights = np.select(
    [_years < 1980, _years < 1990, _years < 2000, _years < 2010, _years < 2020],
    [0.3,           0.8,           1.5,           4.0,           5.5],
    default=6.0,
)
year_built = rng.choice(_years, size=N, p=_weights / _weights.sum())

# ── 3. OverallQual ────────────────────────────────────────────────────────────
_qual_base  = rng.normal(6.0, 1.5, N)
_year_nudge = (year_built - 1990) * 0.008
overall_qual = np.clip(
    np.round(_qual_base + _year_nudge).astype(int), 1, 10
)

# ── 4. GrLivArea ─────────────────────────────────────────────────────────────
_AREA_PARAMS = {
    "Gurgaon":   {"mu": 1850, "sigma": 520},
    "Bangalore": {"mu": 1500, "sigma": 460},
    "Kolkata":   {"mu": 1200, "sigma": 390},
}
grlivarea = np.zeros(N, dtype=int)
for i, loc in enumerate(locations):
    p = _AREA_PARAMS[loc]
    luxury_bonus = max(0, int(overall_qual[i]) - 7) * 180
    raw = rng.normal(p["mu"] + luxury_bonus, p["sigma"])
    grlivarea[i] = int(np.clip(raw, 600, 5000))

# ── 5. TotalBsmtSF ────────────────────────────────────────────────────────────
_has_basement = rng.random(N) < 0.08
total_bsmt_sf = np.where(
    _has_basement,
    rng.integers(150, 550, size=N),
    0,
).astype(int)

# ── 6. SalePrice ──────────────────────────────────────────────────────────────
_CITY_BASE = {"Gurgaon": 8_000, "Bangalore": 6_500, "Kolkata": 5_000}

_QUAL_MULT = {
    1: 0.30, 2: 0.45, 3: 0.60, 4: 0.75,  5: 0.90,
    6: 1.05, 7: 1.20, 8: 1.40, 9: 1.65, 10: 2.00,
}

def _year_factor(yr: int) -> float:
    if yr < 1980: return 0.60
    if yr < 1990: return 0.75
    if yr < 2000: return 0.88
    if yr < 2010: return 1.00
    if yr < 2020: return 1.12
    return 1.25

sale_prices = np.zeros(N, dtype=int)
for i in range(N):
    city  = locations[i]
    qual  = int(overall_qual[i])
    yr    = int(year_built[i])
    area  = int(grlivarea[i]) + int(total_bsmt_sf[i]) * 0.5

    ppsf  = _CITY_BASE[city] * _QUAL_MULT[qual] * _year_factor(yr)
    noise = float(np.clip(rng.lognormal(0.0, 0.08), 0.82, 1.25))

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

# ── Save ──────────────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
output_path = "data/indian_housing.csv"
df.to_csv(output_path, index=False)
print(f"Saved -> {output_path}  ({len(df):,} rows x {df.shape[1]} cols)")
print(f"Median SalePrice by city:")
for loc, usd in df.groupby("Location")["SalePrice"].median().items():
    print(f"  {loc:<12}  ${usd:>10,.0f}")

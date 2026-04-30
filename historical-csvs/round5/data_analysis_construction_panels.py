import os

os.chdir(r"C:\Users\oscar\OneDrive\Python\IntaraTradingAlgorithm\historical-csvs\round5")

import pandas as pd
import numpy as np

# LOAD FILES

files = [
    "prices_round_5_day_2.csv",
    "prices_round_5_day_3.csv",
    "prices_round_5_day_4.csv"
]


df = pd.concat(
    [pd.read_csv(f, sep=";") for f in files],
    ignore_index=True
)

# =========================
# MID + SPREAD MATRICES
# =========================

mid = df.pivot_table(
    index=["day", "timestamp"],
    columns="product",
    values="mid_price"
)

bid = df.pivot_table(
    index=["day", "timestamp"],
    columns="product",
    values="bid_price_1"
)

ask = df.pivot_table(
    index=["day", "timestamp"],
    columns="product",
    values="ask_price_1"
)

spread = ask - bid

# =========================
# PANEL PRODUCTS
# =========================

panels = [
    "PANEL_1X2",
    "PANEL_2X2",
    "PANEL_1X4",
    "PANEL_2X4",
    "PANEL_4X4",
]

print("\n=== PANEL SPREADS ===")

for p in panels:
    print()
    print(p)
    print("mean spread:", spread[p].mean())
    print("median spread:", spread[p].median())
    print("max spread:", spread[p].max())

# =========================
# STRUCTURAL RELATIONSHIP TESTS
# =========================

tests = {}

tests["2 * PANEL_1X2 - PANEL_2X2"] = (
    2 * mid["PANEL_1X2"]
    - mid["PANEL_2X2"]
)

tests["2 * PANEL_2X2 - PANEL_2X4"] = (
    2 * mid["PANEL_2X2"]
    - mid["PANEL_2X4"]
)

tests["2 * PANEL_1X4 - PANEL_2X4"] = (
    2 * mid["PANEL_1X4"]
    - mid["PANEL_2X4"]
)

tests["2 * PANEL_2X4 - PANEL_4X4"] = (
    2 * mid["PANEL_2X4"]
    - mid["PANEL_4X4"]
)

tests["4 * PANEL_1X2 - PANEL_2X4"] = (
    4 * mid["PANEL_1X2"]
    - mid["PANEL_2X4"]
)

tests["4 * PANEL_2X2 - PANEL_4X4"] = (
    4 * mid["PANEL_2X2"]
    - mid["PANEL_4X4"]
)

print("\n=== PANEL RELATIONSHIP TESTS ===")

for name in tests:
    s = tests[name].dropna()

    print()
    print(name)
    print("mean:", round(s.mean(), 3))
    print("std:", round(s.std(), 3))
    print("min:", round(s.min(), 3))
    print("max:", round(s.max(), 3))
    print("range:", round(s.max() - s.min(), 3))

# =========================
# PAIR RELATIONSHIPS
# =========================

print("\n=== PANEL PAIR SPREADS ===")

for i in range(len(panels)):
    for j in range(i + 1, len(panels)):
        a = panels[i]
        b = panels[j]

        pair_spread = mid[a] - mid[b]

        print()
        print(a, "minus", b)
        print("corr:", round(mid[a].corr(mid[b]), 4))
        print("spread mean:", round(pair_spread.mean(), 3))
        print("spread std:", round(pair_spread.std(), 3))
        print("spread min:", round(pair_spread.min(), 3))
        print("spread max:", round(pair_spread.max(), 3))

# =========================
# NEXT-STEP MEAN REVERSION TESTS
# =========================

print("\n=== PANEL MEAN REVERSION TESTS ===")

for name in tests:
    error = tests[name].dropna()
    future_change = error.shift(-1) - error

    corr = error.corr(future_change)

    print()
    print(name)
    print("corr(error, next error change):", round(corr, 4))

    for threshold in [10, 20, 30, 50, 100]:
        mask = error.abs() > threshold

        if mask.sum() == 0:
            continue

        reversion = -np.sign(error[mask]) * future_change[mask]

        print(
            "threshold",
            threshold,
            "| count:",
            int(mask.sum()),
            "| avg reversion:",
            round(reversion.mean(), 3),
            "| win rate:",
            round((reversion > 0).mean(), 3)
        )
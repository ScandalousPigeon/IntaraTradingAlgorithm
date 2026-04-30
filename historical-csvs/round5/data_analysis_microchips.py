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

# =========================================
# MID + SPREAD MATRICES
# =========================================

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

# =========================================
# MICROCHIPS
# =========================================

chips = [
    "MICROCHIP_CIRCLE",
    "MICROCHIP_OVAL",
    "MICROCHIP_SQUARE",
    "MICROCHIP_RECTANGLE",
    "MICROCHIP_TRIANGLE",
]

# =========================================
# SPREADS
# =========================================

print("\n=== MICROCHIP SPREADS ===")

for p in chips:

    print()
    print(p)

    print("mean spread:", round(spread[p].mean(), 3))
    print("median spread:", round(spread[p].median(), 3))
    print("max spread:", round(spread[p].max(), 3))

# =========================================
# CORRELATIONS
# =========================================

print("\n=== MICROCHIP CORRELATIONS ===")

print(
    mid[chips].corr().round(4)
)

# =========================================
# PAIR SPREAD ANALYSIS
# =========================================

print("\n=== MICROCHIP PAIR ANALYSIS ===")

results = []

for i in range(len(chips)):

    for j in range(i + 1, len(chips)):

        a = chips[i]
        b = chips[j]

        pair_spread = (
            mid[a] - mid[b]
        )

        future_change = (
            pair_spread.shift(-1)
            - pair_spread
        )

        mean_rev = pair_spread.corr(
            future_change
        )

        z = (
            pair_spread
            - pair_spread.mean()
        ) / pair_spread.std()

        big = z.abs() > 2

        if big.sum() > 0:

            reversion = (
                -np.sign(pair_spread[big])
                * future_change[big]
            )

            avg_reversion = reversion.mean()

            win_rate = (
                reversion > 0
            ).mean()

        else:

            avg_reversion = np.nan
            win_rate = np.nan

        results.append({

            "pair": f"{a} vs {b}",

            "corr": mid[a].corr(mid[b]),

            "spread_std": pair_spread.std(),

            "spread_mean": pair_spread.mean(),

            "mean_reversion_corr": mean_rev,

            "avg_reversion_after_z2":
                avg_reversion,

            "win_rate_after_z2":
                win_rate,

            "spread_a":
                spread[a].mean(),

            "spread_b":
                spread[b].mean(),
        })

results = pd.DataFrame(results)

results = results.sort_values(
    "mean_reversion_corr"
)

print(
    results.round(4)
)

# =========================================
# BEST PAIRS ONLY
# =========================================

print("\n=== MOST NEGATIVE MEAN REVERSION ===")

best = results.sort_values(
    "mean_reversion_corr"
).head(5)

print(best.round(4))

# =========================================
# LEAD LAG
# =========================================

print("\n=== LEAD LAG TESTS ===")

for i in range(len(chips)):

    for j in range(len(chips)):

        if i == j:
            continue

        a = chips[i]
        b = chips[j]

        ret_a = mid[a].diff()
        ret_b = mid[b].diff()

        corr = ret_a.shift(1).corr(ret_b)

        print()
        print(a, "->", b)

        print(
            "lag1 corr:",
            round(corr, 4)
        )

spread_ot = (
    mid["MICROCHIP_OVAL"]
    - mid["MICROCHIP_TRIANGLE"]
)

z = (
    spread_ot
    - spread_ot.mean()
) / spread_ot.std()

future_change = (
    spread_ot.shift(-1)
    - spread_ot
)

print(
    "mean reversion corr:",
    spread_ot.corr(future_change)
)

print()

for threshold in [1, 1.5, 2, 2.5, 3]:

    mask = z.abs() > threshold

    reversion = (
        -np.sign(spread_ot[mask])
        * future_change[mask]
    )

    print()
    print("threshold", threshold)

    print("count:", mask.sum())

    print(
        "avg reversion:",
        reversion.mean()
    )

    print(
        "win rate:",
        (reversion > 0).mean()
    )

import pandas as pd
import numpy as np

# =====================================
# VISORS
# =====================================

visors = [
    "UV_VISOR_YELLOW",
    "UV_VISOR_AMBER",
    "UV_VISOR_ORANGE",
    "UV_VISOR_RED",
    "UV_VISOR_MAGENTA",
]

# =====================================
# RETURNS
# =====================================

ret = mid[visors].diff()

# =====================================
# MOMENTUM TABLE
# =====================================

print("\n=== RETURN CORRELATIONS ===")

print(ret.corr().round(4))

# =====================================
# LEAD-LAG
# =====================================

print("\n=== LEAD LAG ===")

for i in range(len(visors)):

    for j in range(len(visors)):

        if i == j:
            continue

        a = visors[i]
        b = visors[j]

        corr = ret[a].shift(1).corr(ret[b])

        print()
        print(a, "->", b)

        print(round(corr, 5))

# =====================================
# DISPERSION
# =====================================

dispersion = (
    mid[visors].max(axis=1)
    - mid[visors].min(axis=1)
)

future_change = (
    dispersion.shift(-1)
    - dispersion
)

print("\n=== DISPERSION MR ===")

print(
    dispersion.corr(future_change)
)

# =====================================
# LEADER CONTINUATION
# =====================================

print("\n=== LEADER FOLLOW-THROUGH ===")

for v in visors:

    signal = ret[v] > ret[v].std() * 2

    future = ret.shift(-1)

    print()
    print(v)

    for other in visors:

        if other == v:
            continue

        print(
            other,
            future[other][signal].mean()
        )


df = pd.concat(
    [pd.read_csv(f, sep=";") for f in files],
    ignore_index=True
)

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
# SINGLE PRODUCT ANALYSIS
# =========================

products = mid.columns.tolist()

rows = []

for p in products:

    price = mid[p].dropna()
    ret = price.diff()

    future_ret = ret.shift(-1)

    product_spread = spread[p]

    # short-term reversal / momentum
    corr_1 = ret.corr(future_ret)

    # large move continuation / reversal
    ret_std = ret.std()

    big_up = ret > 2 * ret_std
    big_down = ret < -2 * ret_std

    after_big_up = future_ret[big_up].mean()
    after_big_down = future_ret[big_down].mean()

    # mean reversion after price deviation from rolling mean
    rolling_fair = price.rolling(100).mean()
    deviation = price - rolling_fair
    future_price_change = price.shift(-1) - price

    dev_corr = deviation.corr(future_price_change)

    rows.append({
        "product": p,
        "mean_spread": product_spread.mean(),
        "median_spread": product_spread.median(),
        "price_std": price.std(),
        "ret_std": ret_std,
        "ret_autocorr_1": corr_1,
        "after_big_up": after_big_up,
        "after_big_down": after_big_down,
        "rolling_dev_corr": dev_corr,
        "big_up_count": big_up.sum(),
        "big_down_count": big_down.sum(),
    })

results = pd.DataFrame(rows)

# =========================
# SORTED OUTPUTS
# =========================

print("\n=== MOST MOMENTUM-LIKE PRODUCTS ===")
print(
    results.sort_values("ret_autocorr_1", ascending=False)
    .head(20)
    .round(4)
)

print("\n=== MOST MEAN-REVERTING PRODUCTS ===")
print(
    results.sort_values("ret_autocorr_1", ascending=True)
    .head(20)
    .round(4)
)

print("\n=== BEST ROLLING FAIR MEAN REVERSION ===")
print(
    results.sort_values("rolling_dev_corr", ascending=True)
    .head(20)
    .round(4)
)

print("\n=== BIG UP REVERSAL CANDIDATES ===")
print(
    results.sort_values("after_big_up", ascending=True)
    .head(20)
    .round(4)
)

print("\n=== BIG DOWN REVERSAL CANDIDATES ===")
print(
    results.sort_values("after_big_down", ascending=False)
    .head(20)
    .round(4)
)


products = [
    "ROBOT_DISHES",
    "ROBOT_IRONING",
]

for p in products:

    print("\n====================")
    print(p)
    print("====================")

    price = mid[p]

    ret = price.diff()

    future_ret = ret.shift(-1)

    ret_std = ret.std()

    for threshold in [1, 1.5, 2, 2.5, 3]:

        big_up = ret > threshold * ret_std

        big_down = ret < -threshold * ret_std

        up_reversal = (
            -future_ret[big_up]
        )

        down_reversal = (
            future_ret[big_down]
        )

        print()
        print("threshold", threshold)

        print("UP count:", big_up.sum())

        if big_up.sum() > 0:

            print(
                "UP avg reversal:",
                up_reversal.mean()
            )

            print(
                "UP win rate:",
                (up_reversal > 0).mean()
            )

        print()

        print("DOWN count:", big_down.sum())

        if big_down.sum() > 0:

            print(
                "DOWN avg reversal:",
                down_reversal.mean()
            )

            print(
                "DOWN win rate:",
                (down_reversal > 0).mean()
            )

    print()
    print("spread:", spread[p].mean())

p = "ROBOT_DISHES"

price = mid[p]

ret = price.diff()

future_ret = ret.shift(-1)

ret_std = ret.std()

big_up = ret > 2 * ret_std

up_reversal = -future_ret[big_up]

print(up_reversal.describe())

print()

print(up_reversal.sort_values().head(20))

print()

print(up_reversal.sort_values().tail(20))

p = "ROBOT_DISHES"

price = mid[p]
ret = price.diff()

print(ret.value_counts().head(30))

big = ret.abs() >= 90

print("big jumps:", big.sum())

print(mid[p][big].head(30))
print(ret[big].head(30))

future_ret = ret.shift(-1)

print("after big jumps:")
print(future_ret[big].value_counts().head(20))

print("avg after +big jump:", future_ret[ret >= 90].mean())
print("avg after -big jump:", future_ret[ret <= -90].mean())
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

dfs = []

for f in files:
    dfs.append(pd.read_csv(f, sep=";"))

df = pd.concat(dfs)

print(df.columns)

# build mid matrix

mid = df.pivot_table(
    index=["day", "timestamp"],
    columns="product",
    values="mid_price"
)

print(mid.columns.tolist())

fair_xl = (
    50000
    - mid["PEBBLES_XS"]
    - mid["PEBBLES_S"]
    - mid["PEBBLES_M"]
    - mid["PEBBLES_L"]
)

error = mid["PEBBLES_XL"] - fair_xl

print(error.mean())
print(error.std())



spread = df.pivot_table(
    index=["day", "timestamp"],
    columns="product",
    values="ask_price_1"
) - df.pivot_table(
    index=["day", "timestamp"],
    columns="product",
    values="bid_price_1"
)

print("XL spread mean:")
print(spread["PEBBLES_XL"].mean())

print()

print("XS spread mean:")
print(spread["PEBBLES_XS"].mean())

print()

z = (error - error.mean()) / error.std()

print("abs(z) > 2")
print(np.sum(np.abs(z) > 2))

print()

print("abs(z) > 3")
print(np.sum(np.abs(z) > 3))

print()

print("max abs z")
print(np.max(np.abs(z)))



fair_xl = (
    50000
    - mid["PEBBLES_XS"]
    - mid["PEBBLES_S"]
    - mid["PEBBLES_M"]
    - mid["PEBBLES_L"]
)

fair_ret = fair_xl.diff()
xl_ret = mid["PEBBLES_XL"].diff()

for lag in range(1, 6):

    corr = fair_ret.shift(lag).corr(xl_ret)

    print(
        "fair leads XL by",
        lag,
        "->",
        corr
    )

z = (error - error.mean()) / error.std()

future_change = error.shift(-1) - error

corr = z.corr(future_change)

print(corr)


large = z.abs() > 2

print(
    (
        future_change[large]
    ).mean()
)

for threshold in [1, 2, 3]:

    mask = z.abs() > threshold

    reversion = (
        -np.sign(z[mask]) * future_change[mask]
    )

    print(threshold)
    print(reversion.mean())
    print()


error_change = error.diff()

print(error_change.value_counts().head(20))

print(error.head(30))

fair_xl = (
    50000
    - mid["PEBBLES_XS"]
    - mid["PEBBLES_S"]
    - mid["PEBBLES_M"]
    - mid["PEBBLES_L"]
)

error = mid["PEBBLES_XL"] - fair_xl

big = error.abs() > 10

cols = [
    "PEBBLES_XS",
    "PEBBLES_S",
    "PEBBLES_M",
    "PEBBLES_L",
    "PEBBLES_XL",
]

for c in cols:

    change = mid[c].diff()

    print()
    print(c)

    print(
        change[big].value_counts().head(10)
    )


fair_xl = (
    50000
    - mid["PEBBLES_XS"]
    - mid["PEBBLES_S"]
    - mid["PEBBLES_M"]
    - mid["PEBBLES_L"]
)

error = mid["PEBBLES_XL"] - fair_xl

z = (error - error.mean()) / error.std()

future_error = error.shift(-1)

for threshold in [2, 3, 4]:

    pnl = []

    for i in range(len(z) - 1):

        if z.iloc[i] > threshold:

            # short error
            pnl.append(
                error.iloc[i] - future_error.iloc[i]
            )

        elif z.iloc[i] < -threshold:

            # long error
            pnl.append(
                future_error.iloc[i] - error.iloc[i]
            )

    print()
    print("threshold", threshold)

    if len(pnl) > 0:

        pnl = np.array(pnl)

        print("trades:", len(pnl))
        print("avg pnl:", pnl.mean())
        print("median pnl:", np.median(pnl))
        print("win rate:", np.mean(pnl > 0))


big = error.abs() > 10

print(big.sum())

print()

print(error[big].head(50))

times = error[big].index

for t in list(times[:20]):

    print()
    print(t)

    print(
        mid.loc[t, [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL",
        ]]
    )



# =========================================
# LEAD/LAG TESTS
# =========================================

fair_ret = fair_xl.diff()
xl_ret = mid["PEBBLES_XL"].diff()

for lag in range(1, 6):
    print("fair leads XL by", lag, "->", fair_ret.shift(lag).corr(xl_ret))

for lag in range(1, 6):
    print("XL leads fair by", lag, "->", xl_ret.shift(lag).corr(fair_ret))


# =========================================
# MEAN REVERSION TEST
# =========================================

z = (error - error.mean()) / error.std()

future_change = error.shift(-1) - error

print(z.corr(future_change))


# =========================================
# REVERSION SIZE BY THRESHOLD
# =========================================

for threshold in [1, 2, 3]:

    mask = z.abs() > threshold

    reversion = (
        -np.sign(z[mask]) * future_change[mask]
    )

    print(threshold)
    print(reversion.mean())
    print(mask.sum())
    print()


# =========================================
# SIMPLE STRATEGY TEST
# =========================================

future_error = error.shift(-1)

for threshold in [2, 3, 4]:

    pnl = []

    for i in range(len(z) - 1):

        if z.iloc[i] > threshold:

            pnl.append(
                error.iloc[i] - future_error.iloc[i]
            )

        elif z.iloc[i] < -threshold:

            pnl.append(
                future_error.iloc[i] - error.iloc[i]
            )

    print()
    print("threshold", threshold)

    if len(pnl) > 0:

        pnl = np.array(pnl)

        print("trades:", len(pnl))
        print("avg pnl:", pnl.mean())
        print("median pnl:", np.median(pnl))
        print("win rate:", np.mean(pnl > 0))


# =========================================
# ERROR JUMP DISTRIBUTION
# =========================================

print(error.diff().value_counts().head(20))

print(error.head(30))


# =========================================
# LARGE ERROR EVENTS
# =========================================

big = error.abs() > 10

print(big.sum())

print()

print(error[big].head(50))


# =========================================
# PRINT PRICES DURING BIG EVENTS
# =========================================

times = error[big].index

for t in list(times[:20]):

    print()
    print(t)

    print(
        mid.loc[t, [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL",
        ]]
    )


# =========================================
# WHICH PRODUCTS MOVE DURING BIG EVENTS
# =========================================

cols = [
    "PEBBLES_XS",
    "PEBBLES_S",
    "PEBBLES_M",
    "PEBBLES_L",
    "PEBBLES_XL",
]

for c in cols:

    change = mid[c].diff()

    print()
    print(c)

    print(
        change[big].value_counts().head(10)
    )


# =========================================
# DOES XL MOVE NEXT STEP?
# =========================================

future_xl_move = (
    mid["PEBBLES_XL"].shift(-1)
    - mid["PEBBLES_XL"]
)

signal = error.abs() > 10

print(future_xl_move[signal].describe())


# =========================================
# DIRECTIONAL XL MOVE
# =========================================

signal_pos = error > 10

print(
    "future XL move when error > 10:"
)

print(
    future_xl_move[signal_pos].mean()
)

signal_neg = error < -10

print(
    "future XL move when error < -10:"
)

print(
    future_xl_move[signal_neg].mean()
)


# =========================================
# DOES FAIR MOVE OR XL MOVE?
# =========================================

future_fair_move = (
    fair_xl.shift(-1)
    - fair_xl
)

print(
    "future fair move:"
)

print(
    future_fair_move[signal].mean()
)

print(
    "future XL move:"
)

print(
    future_xl_move[signal].mean()
)

# =========================================
# SIMPLE PASSIVE XL BACKTEST
# =========================================

z = (error - error.mean()) / error.std()

xl_mid = mid["PEBBLES_XL"]

xl_spread = spread["PEBBLES_XL"]

position = 0

entry_price = None

pnl = []

trades = 0

THRESHOLD = 3

for i in range(len(z) - 1):

    current_z = z.iloc[i]

    current_mid = xl_mid.iloc[i]

    next_mid = xl_mid.iloc[i + 1]

    current_spread = xl_spread.iloc[i]

    if np.isnan(current_z):
        continue

    # =====================================
    # ENTER SHORT
    # =====================================

    if position == 0 and current_z > THRESHOLD:

        # assume passive sell fill
        entry_price = current_mid + current_spread / 2

        position = -1

        trades += 1

    # =====================================
    # ENTER LONG
    # =====================================

    elif position == 0 and current_z < -THRESHOLD:

        # assume passive buy fill
        entry_price = current_mid - current_spread / 2

        position = 1

        trades += 1

    # =====================================
    # EXIT LONG
    # =====================================

    elif position == 1 and current_z >= 0:

        # assume passive sell fill
        exit_price = current_mid + current_spread / 2

        pnl.append(
            exit_price - entry_price
        )

        position = 0

    # =====================================
    # EXIT SHORT
    # =====================================

    elif position == -1 and current_z <= 0:

        # assume passive buy fill
        exit_price = current_mid - current_spread / 2

        pnl.append(
            entry_price - exit_price
        )

        position = 0


# =========================================
# RESULTS
# =========================================

pnl = np.array(pnl)

print("trades:", trades)

print("closed trades:", len(pnl))

if len(pnl) > 0:

    print("total pnl:", pnl.sum())

    print("avg pnl:", pnl.mean())

    print("median pnl:", np.median(pnl))

    print("win rate:", np.mean(pnl > 0))

    print("sharpe-ish:", pnl.mean() / pnl.std())


for THRESHOLD in [2, 3, 4, 5, 6]:

    position = 0
    entry_price = None
    pnl = []

    for i in range(len(z) - 1):

        current_z = z.iloc[i]

        if np.isnan(current_z):
            continue

        current_mid = xl_mid.iloc[i]
        current_spread = xl_spread.iloc[i]

        if position == 0 and current_z > THRESHOLD:

            entry_price = current_mid + current_spread / 2
            position = -1

        elif position == 0 and current_z < -THRESHOLD:

            entry_price = current_mid - current_spread / 2
            position = 1

        elif position == 1 and current_z >= 0:

            exit_price = current_mid + current_spread / 2

            pnl.append(exit_price - entry_price)

            position = 0

        elif position == -1 and current_z <= 0:

            exit_price = current_mid - current_spread / 2

            pnl.append(entry_price - exit_price)

            position = 0

    pnl = np.array(pnl)

    print()
    print("threshold", THRESHOLD)

    if len(pnl) > 0:

        print("trades", len(pnl))
        print("total pnl", pnl.sum())
        print("avg", pnl.mean())
        print("win rate", np.mean(pnl > 0))
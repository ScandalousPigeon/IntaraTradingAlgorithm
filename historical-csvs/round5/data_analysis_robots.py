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
# ROBOTS
# =========================

robots = [
    "ROBOT_VACUUMING",
    "ROBOT_MOPPING",
    "ROBOT_DISHES",
    "ROBOT_LAUNDRY",
    "ROBOT_IRONING",
]

# =========================
# BASIC STATS
# =========================

print("\n=== ROBOT BASIC STATS ===")

for p in robots:
    price = mid[p]
    ret = price.diff()

    print("\n", p)
    print("mean price:", round(price.mean(), 2))
    print("price std:", round(price.std(), 2))
    print("mean spread:", round(spread[p].mean(), 2))
    print("median spread:", round(spread[p].median(), 2))
    print("ret std:", round(ret.std(), 2))
    print("ret autocorr 1:", round(ret.corr(ret.shift(-1)), 4))

# =========================
# RETURN CORRELATIONS
# =========================

print("\n=== ROBOT RETURN CORRELATIONS ===")
print(mid[robots].diff().corr().round(4))

print("\n=== ROBOT PRICE CORRELATIONS ===")
print(mid[robots].corr().round(4))

# =========================
# INDIVIDUAL JUMP ANALYSIS
# =========================

print("\n=== ROBOT JUMP ANALYSIS ===")

for p in robots:
    price = mid[p]
    ret = price.diff()

    print("\n==============================")
    print(p)
    print("==============================")

    print("\nMost common moves:")
    print(ret.value_counts().head(25))

    for jump in [20, 40, 60, 80, 90, 100]:

        big_up = ret >= jump
        big_down = ret <= -jump

        if big_up.sum() == 0 and big_down.sum() == 0:
            continue

        print("\nJump threshold:", jump)

        print("up jumps:", int(big_up.sum()))
        print("down jumps:", int(big_down.sum()))

        future_ret = ret.shift(-1)

        if big_up.sum() > 0:
            print("next move after up jump:", round(future_ret[big_up].mean(), 3))
            print("up jump reversal win rate:", round((-future_ret[big_up] > 0).mean(), 3))

        if big_down.sum() > 0:
            print("next move after down jump:", round(future_ret[big_down].mean(), 3))
            print("down jump reversal win rate:", round((future_ret[big_down] > 0).mean(), 3))

# =========================
# MULTI-HORIZON JUMP FOLLOW-THROUGH
# =========================

print("\n=== ROBOT MULTI-HORIZON JUMP EFFECTS ===")

for p in robots:
    price = mid[p]
    ret = price.diff()

    print("\n==============================")
    print(p)
    print("==============================")

    for jump in [40, 80, 100]:

        big_up = ret >= jump
        big_down = ret <= -jump

        if big_up.sum() == 0 and big_down.sum() == 0:
            continue

        print("\nJump threshold:", jump)

        for horizon in [1, 2, 5, 10, 20, 50]:

            future_change = price.shift(-horizon) - price

            print("horizon", horizon)

            if big_up.sum() > 0:
                print("  after up:", round(future_change[big_up].mean(), 3))

            if big_down.sum() > 0:
                print("  after down:", round(future_change[big_down].mean(), 3))

# =========================
# ROLLING FAIR MEAN REVERSION
# =========================

print("\n=== ROBOT ROLLING MEAN REVERSION ===")

for p in robots:
    price = mid[p]

    print("\n", p)

    for window in [20, 50, 100, 200]:

        fair = price.rolling(window).mean()
        deviation = price - fair
        future_change = price.shift(-1) - price

        corr = deviation.corr(future_change)

        print(
            "window",
            window,
            "corr:",
            round(corr, 4)
        )

# =========================
# SIMPLE STRATEGY BACKTESTS
# =========================

print("\n=== SIMPLE ROBOT STRATEGY TESTS ===")

for p in robots:
    price = mid[p]
    ret = price.diff()
    product_spread = spread[p].mean()

    print("\n==============================")
    print(p)
    print("spread:", round(product_spread, 2))
    print("==============================")

    # ---- Jump reversal strategy ----
    for jump in [20, 40, 60, 80, 100]:

        pnl = []

        for i in range(len(price) - 1):

            move = ret.iloc[i]

            if np.isnan(move):
                continue

            if move >= jump:
                # short after up jump, close next tick
                pnl.append(price.iloc[i] - price.iloc[i + 1] - product_spread)

            elif move <= -jump:
                # buy after down jump, close next tick
                pnl.append(price.iloc[i + 1] - price.iloc[i] - product_spread)

        if len(pnl) > 0:
            pnl = np.array(pnl)

            print()
            print("Jump reversal threshold:", jump)
            print("trades:", len(pnl))
            print("total pnl:", round(pnl.sum(), 2))
            print("avg pnl:", round(pnl.mean(), 3))
            print("win rate:", round((pnl > 0).mean(), 3))

    # ---- Jump momentum strategy ----
    for jump in [20, 40, 60, 80, 100]:

        pnl = []

        for i in range(len(price) - 1):

            move = ret.iloc[i]

            if np.isnan(move):
                continue

            if move >= jump:
                # buy after up jump, close next tick
                pnl.append(price.iloc[i + 1] - price.iloc[i] - product_spread)

            elif move <= -jump:
                # short after down jump, close next tick
                pnl.append(price.iloc[i] - price.iloc[i + 1] - product_spread)

        if len(pnl) > 0:
            pnl = np.array(pnl)

            print()
            print("Jump momentum threshold:", jump)
            print("trades:", len(pnl))
            print("total pnl:", round(pnl.sum(), 2))
            print("avg pnl:", round(pnl.mean(), 3))
            print("win rate:", round((pnl > 0).mean(), 3))
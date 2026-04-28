import os
import pandas as pd
import numpy as np

# =========================
# SET WORKING DIRECTORY
# =========================

os.chdir(r"C:\Users\oscar\OneDrive\Python\IntaraTradingAlgorithm\historical-csvs\round4")

print("Current WD:", os.getcwd())

print("\nFiles in directory:")
print(os.listdir())

# =====================================
# LOAD DATA
# =====================================

day1 = pd.read_csv("trades_round_4_day_1.csv", sep=";")
day2 = pd.read_csv("trades_round_4_day_2.csv", sep=";")
day3 = pd.read_csv("trades_round_4_day_3.csv", sep=";")

# =====================================
# ADD DAY COLUMN
# =====================================

day1["day"] = 1
day2["day"] = 2
day3["day"] = 3

# =====================================
# MERGE
# =====================================

df = pd.concat(
    [day1, day2, day3],
    ignore_index=True
)

# =====================================
# FILTER PRODUCT
# =====================================

product = "VEV_500"

df = df[
    df["symbol"] == product
].copy()

# =====================================
# SORT
# =====================================

df = df.sort_values(
    ["day", "timestamp"]
).reset_index(drop=True)

# =====================================
# FUTURE RETURNS
# =====================================

LOOKAHEAD = 50

# IMPORTANT:
# only shift within same day

df["future_price"] = (
    df.groupby("day")["price"]
    .shift(-LOOKAHEAD)
)

df["future_return"] = (
    df["future_price"]
    - df["price"]
)

# =====================================
# REMOVE NAN ROWS
# =====================================

df = df.dropna(subset=["future_return"])

# =====================================
# BUYER ANALYSIS
# =====================================

buyer_stats = (
    df.groupby("buyer")
    .agg(
        avg_future_return=("future_return", "mean"),
        num_trades=("future_return", "count"),
        std_future_return=("future_return", "std"),
        avg_quantity=("quantity", "mean")
    )
)

buyer_stats = buyer_stats[
    buyer_stats["num_trades"] >= 30
]

buyer_stats["t_stat"] = (
    buyer_stats["avg_future_return"]
    /
    (
        buyer_stats["std_future_return"]
        /
        np.sqrt(buyer_stats["num_trades"])
    )
)

buyer_stats = buyer_stats.sort_values(
    "t_stat",
    ascending=False
)

print("\n====================")
print("BEST BUYERS")
print("====================")

print(buyer_stats)

# =====================================
# SELLER ANALYSIS
# =====================================

seller_stats = (
    df.groupby("seller")
    .agg(
        avg_future_return=("future_return", "mean"),
        num_trades=("future_return", "count"),
        std_future_return=("future_return", "std"),
        avg_quantity=("quantity", "mean")
    )
)

seller_stats = seller_stats[
    seller_stats["num_trades"] >= 50
]

seller_stats["t_stat"] = (
    seller_stats["avg_future_return"]
    /
    (
        seller_stats["std_future_return"]
        /
        np.sqrt(seller_stats["num_trades"])
    )
)

seller_stats = seller_stats.sort_values(
    "t_stat"
)

print("\n====================")
print("BEST SELLERS")
print("====================")

print(seller_stats)
"""
summary = []

for LOOKAHEAD in [10, 20, 50, 100, 200]:
    temp = df.copy()
    temp["future_price"] = temp.groupby("day")["price"].shift(-LOOKAHEAD)
    temp["future_return"] = temp["future_price"] - temp["price"]
    temp = temp.dropna(subset=["future_return"])

    for trader in ["Mark 14", "Mark 38"]:
        buys = temp[temp["buyer"] == trader]["future_return"]
        sells = temp[temp["seller"] == trader]["future_return"]

        summary.append({
            "lookahead": LOOKAHEAD,
            "trader": trader,
            "buy_mean": buys.mean(),
            "sell_mean": sells.mean(),
            "buy_count": buys.count(),
            "sell_count": sells.count(),
        })

summary_df = pd.DataFrame(summary)
print(summary_df)

events = []

for i, row in df.iterrows():

    signal = None

    if row["buyer"] == "Mark 14":
        signal = "M14_BUY"
    elif row["seller"] == "Mark 14":
        signal = "M14_SELL"
    elif row["buyer"] == "Mark 38":
        signal = "M38_BUY"
    elif row["seller"] == "Mark 38":
        signal = "M38_SELL"

    if signal is not None:
        event = {
            "day": row["day"],
            "timestamp": row["timestamp"],
            "signal": signal,
            "price_0": row["price"],
        }

        for h in [1, 5, 10, 20, 50, 100]:
            future = df[
                (df["day"] == row["day"]) &
                (df.index == i + h)
            ]

            if len(future) > 0:
                event[f"move_{h}"] = future["price"].iloc[0] - row["price"]

        events.append(event)

events = pd.DataFrame(events)

print(events.groupby("signal")[
    ["move_1", "move_5", "move_10", "move_20", "move_50", "move_100"]
].mean())
"""
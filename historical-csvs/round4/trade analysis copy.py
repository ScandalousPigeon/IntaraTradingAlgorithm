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

product = "VELVETFRUIT_EXTRACT"

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
    buyer_stats["num_trades"] >= 50
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
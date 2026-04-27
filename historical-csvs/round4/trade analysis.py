import os
import pandas as pd

# =========================
# SET WORKING DIRECTORY
# =========================

os.chdir(r"C:\Users\oscar\OneDrive\Python\IntaraTradingAlgorithm\historical-csvs\round4")

print("Current WD:", os.getcwd())

print("\nFiles in directory:")
print(os.listdir())

# =========================
# LOAD CSV
# =========================

trades = pd.read_csv(
    "trades_round_4_day_1.csv",
    sep=";"
)

# =========================
# VIEW DATA
# =========================

print("\nColumns:")
print(trades.columns)

print("\nFirst rows:")
print(trades.head())

import pandas as pd
import numpy as np

# =====================================
# LOAD DATA
# =====================================

trades = pd.read_csv(
    "trades_round_4_day_1.csv",
    sep=";"
)

# =====================================
# SEE PRODUCTS
# =====================================

print(trades["symbol"].unique())

# =====================================
# PICK PRODUCT
# =====================================

product = "VELVETFRUIT_EXTRACT"

df = trades[
    trades["symbol"] == product
].copy()

# =====================================
# SORT
# =====================================

df = df.sort_values("timestamp")

# =====================================
# FUTURE RETURNS
# =====================================

LOOKAHEAD = 20

df["future_price"] = df["price"].shift(-LOOKAHEAD)

df["future_return"] = (
    df["future_price"] - df["price"]
)

# =====================================
# BUYER ANALYSIS
# =====================================

buyer_stats = (
    df.groupby("buyer")
    .agg(
        avg_future_return=("future_return", "mean"),
        num_trades=("future_return", "count"),
        std_future_return=("future_return", "std")
    )
)

buyer_stats = buyer_stats[
    buyer_stats["num_trades"] > 20
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
    "avg_future_return",
    ascending=False
)

print("\nBEST BUYERS")
print(buyer_stats.head(20))

# =====================================
# SELLER ANALYSIS
# =====================================

seller_stats = (
    df.groupby("seller")
    .agg(
        avg_future_return=("future_return", "mean"),
        num_trades=("future_return", "count"),
        std_future_return=("future_return", "std")
    )
)

seller_stats = seller_stats[
    seller_stats["num_trades"] > 20
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
    "avg_future_return"
)

print("\nBEST SELLERS")
print(seller_stats.head(20))
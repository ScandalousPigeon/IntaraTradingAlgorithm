# Hydrogel Executable Event Study + Microstructure-Aware Signal Testing
import os
import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

os.chdir(r"C:\Users\oscar\OneDrive\Python\IntaraTradingAlgorithm\historical-csvs\round4")
PRODUCT = "HYDROGEL_PACK"
SIGNAL_TRADER = "Mark 14"

HORIZONS = [1, 2, 3, 5, 10, 20]

PRICE_FILES = [
    "prices_round_4_day_1.csv",
    "prices_round_4_day_2.csv",
    "prices_round_4_day_3.csv",
]

TRADE_FILES = [
    "trades_round_4_day_1.csv",
    "trades_round_4_day_2.csv",
    "trades_round_4_day_3.csv",
]

DATA_DIR = "."

# ============================================================
# LOADERS
# ============================================================


def load_prices(path):
    df = pd.read_csv(path, sep=";")

    df = df[df["product"] == PRODUCT].copy()

    numeric_cols = [
        "timestamp",
        "bid_price_1",
        "ask_price_1",
        "mid_price",
    ]

    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.sort_values("timestamp")
    df = df.reset_index(drop=True)

    return df



def load_trades(path):
    df = pd.read_csv(path, sep=";")

    df = df[df["symbol"] == PRODUCT].copy()

    numeric_cols = ["timestamp", "price", "quantity"]

    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.sort_values("timestamp")
    df = df.reset_index(drop=True)

    return df


# ============================================================
# LOAD ALL DAYS
# ============================================================

all_prices = []
all_trades = []

for pf, tf in zip(PRICE_FILES, TRADE_FILES):
    prices = load_prices(Path(DATA_DIR) / pf)
    trades = load_trades(Path(DATA_DIR) / tf)

    day = int(prices["day"].iloc[0])

    prices["day"] = day
    trades["day"] = day

    all_prices.append(prices)
    all_trades.append(trades)

prices = pd.concat(all_prices, ignore_index=True)
trades = pd.concat(all_trades, ignore_index=True)

# ============================================================
# MARK 14 BUY SIGNALS
# ============================================================

signals = trades[
    (trades["buyer"] == SIGNAL_TRADER)
].copy()

print("=" * 60)
print("SIGNAL COUNT")
print("=" * 60)
print(len(signals))

# ============================================================
# EXECUTABLE EVENT STUDY
# ============================================================

results = []

for idx, signal in signals.iterrows():

    day = signal["day"]
    ts = signal["timestamp"]

    day_prices = prices[prices["day"] == day].copy()
    day_prices = day_prices.sort_values("timestamp")
    day_prices = day_prices.reset_index(drop=True)

    # --------------------------------------------------------
    # IMPORTANT:
    # We only react AFTER seeing the trade.
    #
    # So we enter using the NEXT available orderbook snapshot.
    # --------------------------------------------------------

    future_rows = day_prices[
        day_prices["timestamp"] > ts
    ]

    if len(future_rows) == 0:
        continue

    entry_row = future_rows.iloc[0]

    entry_ask = entry_row["ask_price_1"]
    entry_bid = entry_row["bid_price_1"]
    entry_mid = entry_row["mid_price"]

    entry_idx = entry_row.name

    for horizon in HORIZONS:

        exit_idx = entry_idx + horizon

        if exit_idx >= len(day_prices):
            continue

        exit_row = day_prices.iloc[exit_idx]

        exit_bid = exit_row["bid_price_1"]
        exit_mid = exit_row["mid_price"]

        # ====================================================
        # EXECUTABLE PNL
        # Buy at ask
        # Sell at bid
        # ====================================================

        executable_pnl = exit_bid - entry_ask

        # Mid-only reference
        mid_pnl = exit_mid - entry_mid

        results.append({
            "day": day,
            "signal_ts": ts,
            "horizon": horizon,
            "entry_ask": entry_ask,
            "exit_bid": exit_bid,
            "executable_pnl": executable_pnl,
            "mid_pnl": mid_pnl,
        })

results = pd.DataFrame(results)

# ============================================================
# SUMMARY
# ============================================================

summary = (
    results
    .groupby("horizon")
    .agg(
        avg_exec_pnl=("executable_pnl", "mean"),
        median_exec_pnl=("executable_pnl", "median"),
        win_rate=("executable_pnl", lambda x: (x > 0).mean()),
        avg_mid_pnl=("mid_pnl", "mean"),
        count=("executable_pnl", "count"),
    )
    .reset_index()
)

print("\n")
print("=" * 60)
print("EXECUTABLE EVENT STUDY")
print("=" * 60)

print(summary)

# ============================================================
# CONDITIONAL ANALYSIS
# ============================================================

print("\n")
print("=" * 60)
print("BEST HORIZON")
print("=" * 60)

best = summary.sort_values("avg_exec_pnl", ascending=False).iloc[0]
print(best)

# ============================================================
# MICROSTRUCTURE INTERPRETATION
# ============================================================

print("\n")
print("=" * 60)
print("INTERPRETATION")
print("=" * 60)

"""
If executable pnl > 0:
    aggressive crossing may work.

If mid pnl > 0 but executable pnl <= 0:
    signal exists but spread kills profitability.
    Better approach:
        - skew quotes upward
        - avoid selling immediately after Mark 14 buys
        - raise bids slightly
        - raise asks more aggressively

If executable pnl strongly positive at short horizons:
    immediate informed-flow reaction likely exists.
"""

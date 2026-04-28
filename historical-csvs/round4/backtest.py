import pandas as pd
import numpy as np
import os

os.chdir(r"C:\Users\oscar\OneDrive\Python\IntaraTradingAlgorithm\historical-csvs\round4")


# =========================
# LOAD + MERGE DATA
# =========================

day1 = pd.read_csv("trades_round_4_day_1.csv", sep=";")
day2 = pd.read_csv("trades_round_4_day_2.csv", sep=";")
day3 = pd.read_csv("trades_round_4_day_3.csv", sep=";")

day1["day"] = 1
day2["day"] = 2
day3["day"] = 3

trades = pd.concat([day1, day2, day3], ignore_index=True)

# =========================
# FILTER HYDROGEL
# =========================

product = "HYDROGEL_PACK"

df = trades[trades["symbol"] == product].copy()
df = df.sort_values(["day", "timestamp"]).reset_index(drop=True)

print("Hydrogel trades:", len(df))
print(df.head())

# =========================
# EVENT STUDY: MARK 14 BUY
# =========================

horizons = [1, 5, 10, 20, 50, 100]

events = []

for i, row in df.iterrows():

    if row["buyer"] == "Mark 14":

        event = {
            "day": row["day"],
            "timestamp": row["timestamp"],
            "signal": "M14_BUY",
            "entry_price": row["price"],
            "quantity": row["quantity"]
        }

        for h in horizons:

            future_index = i + h

            if future_index < len(df) and df.loc[future_index, "day"] == row["day"]:

                event[f"exit_price_{h}"] = df.loc[future_index, "price"]
                event[f"pnl_{h}"] = df.loc[future_index, "price"] - row["price"]

            else:

                event[f"exit_price_{h}"] = np.nan
                event[f"pnl_{h}"] = np.nan

        events.append(event)

events = pd.DataFrame(events)

print("\n====================")
print("MARK 14 BUY EVENT STUDY")
print("====================")

print(events[[f"pnl_{h}" for h in horizons]].mean())

# =========================
# SIMPLE STRATEGY BACKTEST
# Buy after Mark 14 buys, hold for fixed number of trades
# =========================

def backtest_mark14_buy(df, hold_period=100, trade_size=20):
    
    pnl = 0
    results = []
    in_trade = False
    exit_index = None

    i = 0

    while i < len(df):

        row = df.loc[i]

        # exit existing trade first
        if in_trade and i >= exit_index:
            exit_price = row["price"]

            trade_pnl = (exit_price - entry_price) * trade_size
            pnl += trade_pnl

            results.append({
                "day": entry_day,
                "entry_timestamp": entry_timestamp,
                "exit_timestamp": row["timestamp"],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "hold_period": hold_period,
                "trade_size": trade_size,
                "trade_pnl": trade_pnl,
                "cumulative_pnl": pnl
            })

            in_trade = False

        # enter only if not already in a trade
        if not in_trade and row["buyer"] == "Mark 14":

            entry_day = row["day"]
            entry_timestamp = row["timestamp"]
            entry_price = row["price"]

            # find exit index within same day
            potential_exit = i + hold_period

            if potential_exit < len(df) and df.loc[potential_exit, "day"] == entry_day:
                exit_index = potential_exit
                in_trade = True

        i += 1

    return pd.DataFrame(results)

# =========================
# TEST DIFFERENT HOLD PERIODS
# =========================

summary = []

for hold in [1, 5, 10, 20, 50, 100]:

    bt = backtest_mark14_buy(
        df,
        hold_period=hold,
        trade_size=20
    )

    summary.append({
        "hold_period": hold,
        "num_trades": len(bt),
        "total_pnl": bt["trade_pnl"].sum(),
        "avg_pnl_per_trade": bt["trade_pnl"].mean(),
        "win_rate": (bt["trade_pnl"] > 0).mean(),
        "max_drawdown": (bt["cumulative_pnl"].cummax() - bt["cumulative_pnl"]).max()
    })

summary = pd.DataFrame(summary)

print("\n====================")
print("BACKTEST SUMMARY")
print("====================")

print(summary)

# =========================
# VIEW BEST HOLD PERIOD
# =========================

best_hold = summary.sort_values("total_pnl", ascending=False).iloc[0]["hold_period"]

print("\nBest hold period:", best_hold)

best_bt = backtest_mark14_buy(
    df,
    hold_period=int(best_hold),
    trade_size=20
)

print("\nBest backtest trades:")
print(best_bt.head())

# Optional plot
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 5))
plt.plot(best_bt["cumulative_pnl"])
plt.title(f"Mark 14 Buy Strategy PnL | Hold = {int(best_hold)} trades")
plt.xlabel("Trade number")
plt.ylabel("Cumulative PnL")
plt.grid(True)
plt.show()
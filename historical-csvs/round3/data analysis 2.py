import pandas as pd
import matplotlib.pyplot as plt

# =========================
# LOAD DATA
# =========================

df = pd.read_csv("trades_round_3_day_0.csv", sep=";")

print("========== HEAD ==========")
print(df.head())

print("\n========== INFO ==========")
print(df.info())

print("\n========== PRODUCTS ==========")
print(df["symbol"].value_counts())


# =========================
# SUMMARY STATISTICS
# =========================

summary = df.groupby("symbol").apply(
    lambda x: pd.Series({
        "trades": len(x),
        "total_volume": x["quantity"].sum(),
        "avg_price": x["price"].mean(),
        "vwap": (x["price"] * x["quantity"]).sum() / x["quantity"].sum(),
        "min_price": x["price"].min(),
        "max_price": x["price"].max(),
        "last_price": x.sort_values("timestamp")["price"].iloc[-1]
    })
)

print("\n========== SUMMARY ==========")
print(summary)


# =========================
# PRICE OVER TIME
# =========================

for product in df["symbol"].unique():

    temp = df[df["symbol"] == product]

    plt.figure(figsize=(10, 5))

    plt.plot(temp["timestamp"], temp["price"])

    plt.xlabel("Timestamp")
    plt.ylabel("Price")
    plt.title(f"{product} Price Over Time")

    plt.grid(True)

    plt.show()


# =========================
# VOLUME OVER TIME
# =========================

for product in df["symbol"].unique():

    temp = df[df["symbol"] == product]

    volume_by_time = temp.groupby("timestamp")["quantity"].sum()

    plt.figure(figsize=(10, 5))

    plt.plot(volume_by_time.index, volume_by_time.values)

    plt.xlabel("Timestamp")
    plt.ylabel("Volume")

    plt.title(f"{product} Volume Over Time")

    plt.grid(True)

    plt.show()


# =========================
# OPTION COMPARISON
# =========================

vev = df[df["symbol"].str.startswith("VEV")]

if len(vev) > 0:

    plt.figure(figsize=(12, 6))

    for product in vev["symbol"].unique():

        temp = vev[vev["symbol"] == product]

        plt.plot(
            temp["timestamp"],
            temp["price"],
            label=product
        )

    plt.xlabel("Timestamp")
    plt.ylabel("Price")

    plt.title("VEV Products Comparison")

    plt.legend()

    plt.grid(True)

    plt.show()
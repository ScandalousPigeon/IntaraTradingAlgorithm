import pandas as pd
import matplotlib.pyplot as plt
import os

os.chdir(r"C:\Users\oscar\OneDrive\Python\IntaraTradingAlgorithm\historical-csvs\round5")


# =====================
# LOAD + CONCAT DATA
# =====================

files = [
    "prices_round_5_day_2.csv",
    "prices_round_5_day_3.csv",
    "prices_round_5_day_4.csv",
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

# =====================================
# RETURNS
# =====================================

ret = mid.diff()

products = ret.columns.tolist()

# =====================================
# LEAD LAG SEARCH
# =====================================

results = []

# horizons to test
lags = [1, 2, 5, 10]

for lag in lags:

    for leader in products:

        leader_ret = ret[leader]

        for follower in products:

            if leader == follower:
                continue

            follower_ret = ret[follower]

            corr = (
                leader_ret.shift(lag)
                .corr(follower_ret)
            )

            results.append({

                "lag": lag,

                "leader": leader,

                "follower": follower,

                "corr": corr,

            })

results = pd.DataFrame(results)

# =====================================
# STRONGEST POSITIVE
# =====================================

print("\n=== STRONGEST POSITIVE LEAD-LAG ===")

print(
    results
    .sort_values("corr", ascending=False)
    .head(50)
    .round(5)
)

# =====================================
# STRONGEST NEGATIVE
# =====================================

print("\n=== STRONGEST NEGATIVE LEAD-LAG ===")

print(
    results
    .sort_values("corr", ascending=True)
    .head(50)
    .round(5)
)

# =====================================
# FILTER POSSIBLY REAL SIGNALS
# =====================================

# change threshold if needed

strong = results[
    results["corr"].abs() > 0.03
]

print("\n=== POSSIBLE SIGNALS ===")

print(
    strong
    .sort_values(
        "corr",
        ascending=False
    )
    .round(5)
)

# =====================================
# OPTIONAL:
# TEST DIRECTIONAL FOLLOW-THROUGH
# =====================================

print("\n=== EVENT FOLLOW TESTS ===")

top = (
    results
    .reindex(
        results["corr"]
        .abs()
        .sort_values(ascending=False)
        .index
    )
    .head(10)
)

for _, row in top.iterrows():

    lag = row["lag"]

    leader = row["leader"]

    follower = row["follower"]

    print("\n====================")
    print(
        leader,
        "->",
        follower,
        "lag",
        lag
    )
    print("====================")

    leader_ret = ret[leader]

    follower_future = ret[follower]

    threshold = (
        2 * leader_ret.std()
    )

    big_up = (
        leader_ret.shift(lag)
        > threshold
    )

    big_down = (
        leader_ret.shift(lag)
        < -threshold
    )

    print(
        "after leader big up:",
        follower_future[big_up].mean()
    )

    print(
        "after leader big down:",
        follower_future[big_down].mean()
    )

    print(
        "count up:",
        big_up.sum()
    )

    print(
        "count down:",
        big_down.sum()
    )
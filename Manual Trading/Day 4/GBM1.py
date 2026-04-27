import numpy as np
import pandas as pd

# =========================================================
# Challenge parameters
# =========================================================

TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY

S0 = 50.0
SIGMA = 2.51
CONTRACT_SIZE = 3000

N_SIMS = 10000000
SEED = None ##42 for debugging


def weeks_to_years(weeks: float) -> float:
    return (weeks * 5) / TRADING_DAYS_PER_YEAR


def steps_for_weeks(weeks: float) -> int:
    return int(round(weeks * 5 * STEPS_PER_DAY))


# =========================================================
# Simulate GBM paths
# =========================================================

def simulate_gbm_paths(S0, sigma, weeks, n_sims, seed=None):
    rng = np.random.default_rng(seed)

    n_steps = steps_for_weeks(weeks)
    dt = 1 / STEPS_PER_YEAR

    # zero risk-neutral drift GBM:
    # dS/S = sigma dW
    # discrete exact update:
    # S_{t+dt} = S_t * exp((-0.5 sigma^2)dt + sigma sqrt(dt) Z)

    z = rng.standard_normal((n_sims, n_steps))

    log_returns = (
        -0.5 * sigma**2 * dt
        + sigma * np.sqrt(dt) * z
    )

    log_paths = np.cumsum(log_returns, axis=1)

    paths = S0 * np.exp(log_paths)

    # include starting price at t=0
    paths = np.column_stack([np.full(n_sims, S0), paths])

    return paths


paths_3w = simulate_gbm_paths(S0, SIGMA, weeks=3, n_sims=N_SIMS, seed=SEED)
paths_2w = paths_3w[:, :steps_for_weeks(2) + 1]

S_2w = paths_3w[:, steps_for_weeks(2)]
S_3w = paths_3w[:, steps_for_weeks(3)]


# =========================================================
# Payoff functions
# =========================================================

def call_payoff(S, K):
    return np.maximum(S - K, 0)


def put_payoff(S, K):
    return np.maximum(K - S, 0)


def binary_put_payoff(S_T, K, payout):
    return np.where(S_T < K, payout, 0)


def knockout_put_payoff(paths, K, barrier):
    """
    Knock-out put:
    behaves like put unless underlying ever falls below barrier before expiry.
    Discrete monitoring only.
    """
    S_T = paths[:, -1]

    knocked_out = np.any(paths <= barrier, axis=1)

    return np.where(
        knocked_out,
        0,
        put_payoff(S_T, K)
    )


def chooser_payoff(paths, K, choose_step):
    """
    Chooser:
    at choose_step, choose call if S_choose >= K,
    else choose put. Then payoff is based on final S_T.
    """
    S_choose = paths[:, choose_step]
    S_T = paths[:, -1]

    call = call_payoff(S_T, K)
    put = put_payoff(S_T, K)

    return np.where(S_choose >= K, call, put)


# =========================================================
# Products
# =========================================================

products = [
    # vanillas, mostly for checking
    {"name": "AC_50_P",   "kind": "put", "K": 50, "weeks": 3, "bid": 12.00, "ask": 12.05, "volume": 50},
    {"name": "AC_50_C",   "kind": "call", "K": 50, "weeks": 3, "bid": 12.00, "ask": 12.05, "volume": 50},
    {"name": "AC_35_P",   "kind": "put", "K": 35, "weeks": 3, "bid": 4.33, "ask": 4.35, "volume": 50},
    {"name": "AC_40_P",   "kind": "put", "K": 40, "weeks": 3, "bid": 6.50, "ask": 6.55, "volume": 50},
    {"name": "AC_45_P",   "kind": "put", "K": 45, "weeks": 3, "bid": 9.05, "ask": 9.10, "volume": 50},
    {"name": "AC_60_C",   "kind": "call", "K": 60, "weeks": 3, "bid": 8.80, "ask": 8.85, "volume": 50},

    {"name": "AC_50_P_2", "kind": "put", "K": 50, "weeks": 2, "bid": 9.70, "ask": 9.75, "volume": 50},
    {"name": "AC_50_C_2", "kind": "call", "K": 50, "weeks": 2, "bid": 9.70, "ask": 9.75, "volume": 50},

    # exotics
    {"name": "AC_50_CO", "kind": "chooser", "K": 50, "weeks": 3, "choose_weeks": 2, "bid": 22.20, "ask": 22.30, "volume": 50},
    {"name": "AC_40_BP", "kind": "binary_put", "K": 40, "payout": 10, "weeks": 3, "bid": 5.00, "ask": 5.10, "volume": 50},
    {"name": "AC_45_KO", "kind": "knockout_put", "K": 45, "barrier": 35, "weeks": 3, "bid": 0.15, "ask": 0.175, "volume": 500},
]


# =========================================================
# Price products
# =========================================================

def get_paths_for_weeks(weeks):
    if weeks == 3:
        return paths_3w
    elif weeks == 2:
        return paths_2w
    else:
        return simulate_gbm_paths(S0, SIGMA, weeks, N_SIMS, SEED)


def monte_carlo_fair_value(product):
    paths = get_paths_for_weeks(product["weeks"])
    S_T = paths[:, -1]

    kind = product["kind"]
    K = product["K"]

    if kind == "call":
        payoff = call_payoff(S_T, K)

    elif kind == "put":
        payoff = put_payoff(S_T, K)

    elif kind == "binary_put":
        payoff = binary_put_payoff(S_T, K, product["payout"])

    elif kind == "knockout_put":
        payoff = knockout_put_payoff(paths, K, product["barrier"])

    elif kind == "chooser":
        choose_step = steps_for_weeks(product["choose_weeks"])
        payoff = chooser_payoff(paths, K, choose_step)

    else:
        raise ValueError(f"Unknown kind: {kind}")

    return payoff.mean(), payoff.std(ddof=1)


rows = []

for p in products:
    fair, payoff_std = monte_carlo_fair_value(p)

    buy_edge = fair - p["ask"]
    sell_edge = p["bid"] - fair

    if buy_edge > 0 and buy_edge >= sell_edge:
        action = "BUY"
        edge = buy_edge
    elif sell_edge > 0:
        action = "SELL"
        edge = sell_edge
    else:
        action = "PASS"
        edge = 0

    expected_pnl = edge * p["volume"] * CONTRACT_SIZE

    rows.append({
        "product": p["name"],
        "kind": p["kind"],
        "fair": fair,
        "bid": p["bid"],
        "ask": p["ask"],
        "mid": (p["bid"] + p["ask"]) / 2,
        "buy_edge": buy_edge,
        "sell_edge": sell_edge,
        "action": action,
        "volume": p["volume"],
        "expected_pnl": expected_pnl,
        "payoff_std": payoff_std,
    })


df = pd.DataFrame(rows)
df = df.sort_values("expected_pnl", ascending=False)

# =========================================================
# Pretty print
# =========================================================

print("\n" + "=" * 120)
print(
    f"{'PRODUCT':<12}"
    f"{'TYPE':<15}"
    f"{'FAIR':>10}"
    f"{'BID':>10}"
    f"{'ASK':>10}"
    f"{'MID':>10}"
    f"{'BUY_EDGE':>12}"
    f"{'SELL_EDGE':>12}"
    f"{'ACTION':>10}"
    f"{'EXP_PNL':>15}"
)
print("=" * 120)

for _, row in df.iterrows():

    print(
        f"{row['product']:<12}"
        f"{row['kind']:<15}"
        f"{row['fair']:>10.4f}"
        f"{row['bid']:>10.4f}"
        f"{row['ask']:>10.4f}"
        f"{row['mid']:>10.4f}"
        f"{row['buy_edge']:>12.4f}"
        f"{row['sell_edge']:>12.4f}"
        f"{row['action']:>10}"
        f"{row['expected_pnl']:>15,.0f}"
    )

print("=" * 120)
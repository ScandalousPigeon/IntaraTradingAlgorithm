import math
from dataclasses import dataclass

# -----------------------------
# Parameters from challenge
# -----------------------------

TRADING_DAYS_PER_YEAR = 252
SIGMA = 2.51          # 251% annualized volatility
R = 0.0               # zero risk-neutral drift / rate assumption
S0 = 50.0             # AETHER_CRYSTAL current mid price approx


def weeks_to_years(weeks: float) -> float:
    return (weeks * 5) / TRADING_DAYS_PER_YEAR


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def black_scholes_price(S, K, T, sigma, option_type, r=0.0):
    """
    European Black-Scholes option price.
    option_type = "C" or "P"
    """
    if T <= 0:
        if option_type == "C":
            return max(S - K, 0)
        else:
            return max(K - S, 0)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "C":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)

    elif option_type == "P":
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

    else:
        raise ValueError("option_type must be 'C' or 'P'")


@dataclass
class Option:
    name: str
    option_type: str
    strike: float
    weeks: float
    bid: float
    ask: float
    max_volume: int


options = [
    Option("AC_50_P",   "P", 50, 3, 12.00, 12.05, 50),
    Option("AC_50_C",   "C", 50, 3, 12.00, 12.05, 50),
    Option("AC_35_P",   "P", 35, 3, 4.33, 4.35, 50),
    Option("AC_40_P",   "P", 40, 3, 6.50, 6.55, 50),
    Option("AC_45_P",   "P", 45, 3, 9.05, 9.10, 50),
    Option("AC_60_C",   "C", 60, 3, 8.80, 8.85, 50),
    Option("AC_50_P_2", "P", 50, 2, 9.70, 9.75, 50),
    Option("AC_50_C_2", "C", 50, 2, 9.70, 9.75, 50),
]


CONTRACT_SIZE = 3000


print(f"S0 = {S0}")
print(f"Vol = {SIGMA:.2%}")
print()

results = []

for opt in options:
    T = weeks_to_years(opt.weeks)
    fair = black_scholes_price(
        S=S0,
        K=opt.strike,
        T=T,
        sigma=SIGMA,
        option_type=opt.option_type,
        r=R
    )

    buy_edge = fair - opt.ask      # positive means buy
    sell_edge = opt.bid - fair     # positive means sell

    if buy_edge > sell_edge and buy_edge > 0:
        action = "BUY"
        edge = buy_edge
        entry = opt.ask
    elif sell_edge > buy_edge and sell_edge > 0:
        action = "SELL"
        edge = sell_edge
        entry = opt.bid
    else:
        action = "PASS"
        edge = max(buy_edge, sell_edge)
        entry = None

    expected_pnl = edge * opt.max_volume * CONTRACT_SIZE if action != "PASS" else 0

    results.append({
        "name": opt.name,
        "type": opt.option_type,
        "K": opt.strike,
        "weeks": opt.weeks,
        "fair": fair,
        "bid": opt.bid,
        "ask": opt.ask,
        "buy_edge": buy_edge,
        "sell_edge": sell_edge,
        "action": action,
        "edge": edge,
        "expected_pnl_max_volume": expected_pnl,
    })


# Sort by strongest expected PnL
results = sorted(results, key=lambda x: x["expected_pnl_max_volume"], reverse=True)

for r in results:
    print(
        f"{r['name']:10s} | "
        f"Fair: {r['fair']:7.4f} | "
        f"Bid: {r['bid']:6.3f} | Ask: {r['ask']:6.3f} | "
        f"Buy edge: {r['buy_edge']:7.4f} | "
        f"Sell edge: {r['sell_edge']:7.4f} | "
        f"{r['action']:4s} | "
        f"Exp PnL: {r['expected_pnl_max_volume']:,.0f}"
    )
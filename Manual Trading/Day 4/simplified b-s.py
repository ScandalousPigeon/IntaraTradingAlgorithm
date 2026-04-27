import math
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


print ("Black Scholes Price for $50 call")
print(black_scholes_price(50, 50, 15/252, 2.51, "C"))
print ("Black Scholes Price for $50 put")
print(black_scholes_price(50, 50, 15/252, 2.51, "P"))

print ("Black Scholes Price for $35 put")
print(black_scholes_price(50, 35, 15/252, 2.51, "P"))
print ("Black Scholes Price for $40 put")
print(black_scholes_price(50, 40, 15/252, 2.51, "P"))
print("Black_scholes price for $45 put")
print(black_scholes_price(50, 45, 15/252, 2.51, "P"))

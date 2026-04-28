import math
import numpy as np
from scipy.stats import norm
from prettytable import PrettyTable

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def black_scholes_call(S, K, T, r, sigma):
    if T <= 0:
        return max(S - K, 0)
    if sigma <= 0:
        return max(S - K, 0)
        
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)

def black_scholes_put(S, K, T, r, sigma):
    call = black_scholes_call(S, K, T, r, sigma)
    return call - S + K * math.exp(-r * T)

def chooser_option_value(S, K, T_total, T_choice, r, sigma):
    if T_total <= 0:
        return max(S - K, K - S)
        
    call_value = black_scholes_call(S, K, T_total - T_choice, r, sigma)
    put_value = black_scholes_put(S, K, T_total - T_choice, r, sigma)
    
    straddle_value = call_value + put_value
    max_call_put = max(call_value, put_value)
    
    return straddle_value - max_call_put * math.exp(-r * T_choice)

def binary_put_value(S, K, T, r, sigma, B):
    d2 = (math.log(S / K) + (r - 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return B * math.exp(-r * T) * norm_cdf(-d2)

def knock_out_put_value(S, K, T, r, sigma, H):
    put_value = black_scholes_put(S, K, T, r, sigma)
    d3 = (math.log(S / H) + (r - 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return put_value - (S - H) * math.exp((r - sigma**2 / 2) * T) * norm_cdf(d3)

# Example usage
S0 = 100  # Current spot price of Aether Crystal
r = 0.02  # Risk-free rate
sigma = 2.51  # Volatility of Aether Crystal
T_2w = 2/52  # 2 weeks to expiry in years
T_3w = 3/52  # 3 weeks to expiry in years
K = 100  # Strike price
H = 90  # Barrier price for knock-out put

call_2w_price = black_scholes_call(S0, K, T_2w, r, sigma)
put_2w_price = black_scholes_put(S0, K, T_2w, r, sigma)
call_3w_price = black_scholes_call(S0, K, T_3w, r, sigma)
put_3w_price = black_scholes_put(S0, K, T_3w, r, sigma)
chooser_price = chooser_option_value(S0, K, T_3w, T_2w, r, sigma)
binary_put_price = binary_put_value(S0, K, T_3w, r, sigma, 10)
knock_out_put_price = knock_out_put_value(S0, K, T_3w, r, sigma, H)

# Create a PrettyTable to display the results
table = PrettyTable()
table

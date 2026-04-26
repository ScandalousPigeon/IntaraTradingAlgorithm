from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math

class Trader:

    def norm_cdf(self, x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def bs_call(self, S, K, T, sigma):
        if T <= 0:
            return max(S - K, 0)

        if sigma <= 0:
            return max(S - K, 0)

        d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        return S * self.norm_cdf(d1) - K * self.norm_cdf(d2)

    def implied_vol(self, price, S, K, T):
        intrinsic = max(S - K, 0)

        if price <= intrinsic:
            return None

        low = 0.001
        high = 3.0

        for _ in range(40):
            mid = (low + high) / 2
            model_price = self.bs_call(S, K, T, mid)

            if model_price > price:
                high = mid
            else:
                low = mid

        return (low + high) / 2

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        underlying = "VELVETFRUIT_EXTRACT"
        option = "VEV_5200"
        strike = 5200

        if underlying not in state.order_depths or option not in state.order_depths:
            return result, 0, json.dumps(data)

        under_depth = state.order_depths[underlying]
        opt_depth = state.order_depths[option]

        if not under_depth.buy_orders or not under_depth.sell_orders:
            return result, 0, json.dumps(data)

        if not opt_depth.buy_orders or not opt_depth.sell_orders:
            return result, 0, json.dumps(data)

        under_bid = max(under_depth.buy_orders.keys())
        under_ask = min(under_depth.sell_orders.keys())
        S = (under_bid + under_ask) / 2

        opt_bid = max(opt_depth.buy_orders.keys())
        opt_ask = min(opt_depth.sell_orders.keys())
        opt_mid = (opt_bid + opt_ask) / 2

        opt_bid_volume = opt_depth.buy_orders[opt_bid]
        opt_ask_volume = -opt_depth.sell_orders[opt_ask]

        T = 5 / 365

        market_iv = self.implied_vol(opt_mid, S, strike, T)

        if market_iv is None:
            return result, 0, json.dumps(data)

        # =====================
        # PARAMETERS
        # =====================

        LIMIT = 300
        ORDER_SIZE = 5

        ALPHA_IV = 0.005
        IV_EDGE = 0.01

        PRICE_EDGE = 1

        WARMUP_TIME = 5000

        # =====================
        # IV EMA
        # =====================

        if "iv_5200" not in data:
            data["iv_5200"] = market_iv
        else:
            data["iv_5200"] = (
                ALPHA_IV * market_iv
                + (1 - ALPHA_IV) * data["iv_5200"]
            )

        fair_iv = data["iv_5200"]

        # Warmup: learn fair IV but don't trade yet
        if state.timestamp < WARMUP_TIME:
            return result, 0, json.dumps(data)

        model_price = self.bs_call(S, strike, T, fair_iv)

        position = state.position.get(option, 0)

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        orders: List[Order] = []

        # Buy option if market IV is low / option is cheap
        if (
            market_iv < fair_iv - IV_EDGE
            and opt_ask < model_price - PRICE_EDGE
            and buy_room > 0
        ):
            qty = min(ORDER_SIZE, opt_ask_volume, buy_room)

            if qty > 0:
                orders.append(Order(option, opt_ask, qty))

        # Sell option if market IV is high / option is expensive
        if (
            market_iv > fair_iv + IV_EDGE
            and opt_bid > model_price + PRICE_EDGE
            and sell_room > 0
        ):
            qty = min(ORDER_SIZE, opt_bid_volume, sell_room)

            if qty > 0:
                orders.append(Order(option, opt_bid, -qty))

        result[option] = orders

        return result, 0, json.dumps(data)
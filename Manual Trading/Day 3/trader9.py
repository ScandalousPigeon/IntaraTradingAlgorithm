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

        for _ in range(35):
            mid = (low + high) / 2
            model = self.bs_call(S, K, T, mid)

            if model > price:
                high = mid
            else:
                low = mid

        return (low + high) / 2

    def smooth_iv(self, K, ivs):
        """
        Local smile smoother.
        Fair IV = weighted average of nearby strikes, excluding itself.
        Nearby strikes matter more than far strikes.
        """

        numerator = 0
        denominator = 0

        for K2, iv in ivs.items():

            if K2 == K:
                continue

            distance = abs(K - K2)

            if distance > 500:
                continue

            weight = 1 / (1 + distance / 100)

            numerator += weight * iv
            denominator += weight

        if denominator == 0:
            return None

        return numerator / denominator

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        underlying = "VELVETFRUIT_EXTRACT"

        strikes = [
            5000, 5100, 5200, 5300, 5400, 5500
        ]

        if underlying not in state.order_depths:
            return result, 0, json.dumps(data)

        under_depth = state.order_depths[underlying]

        if not under_depth.buy_orders or not under_depth.sell_orders:
            return result, 0, json.dumps(data)

        under_bid = max(under_depth.buy_orders.keys())
        under_ask = min(under_depth.sell_orders.keys())

        S = (under_bid + under_ask) / 2

        T = 5 / 365

        # =====================
        # PARAMETERS
        # =====================

        LIMIT = 300
        ORDER_SIZE = 15

        VOL_EDGE = 0.03
        PRICE_EDGE = 1

        WARMUP_TIME = 5000

        # =====================
        # COMPUTE CURRENT IVS
        # =====================

        current_ivs = {}

        for K in strikes:

            product = f"VEV_{K}"

            if product not in state.order_depths:
                continue

            depth = state.order_depths[product]

            if not depth.buy_orders or not depth.sell_orders:
                continue

            bid = max(depth.buy_orders.keys())
            ask = min(depth.sell_orders.keys())

            mid_price = (bid + ask) / 2

            iv = self.implied_vol(mid_price, S, K, T)

            if iv is not None:
                current_ivs[K] = iv

        if len(current_ivs) < 3:
            return result, 0, json.dumps(data)

        # =====================
        # SMOOTH IVs OVER TIME
        # =====================

        ALPHA_IV = 0.02

        if "smoothed_ivs" not in data:
            data["smoothed_ivs"] = {}

        for K, iv in current_ivs.items():

            key = str(K)

            if key not in data["smoothed_ivs"]:
                data["smoothed_ivs"][key] = iv
            else:
                data["smoothed_ivs"][key] = (
                    ALPHA_IV * iv
                    + (1 - ALPHA_IV) * data["smoothed_ivs"][key]
                )

        smoothed_ivs = {
            int(K): iv
            for K, iv in data["smoothed_ivs"].items()
            if int(K) in current_ivs
        }

        # Warmup: learn smile but do not trade yet
        if state.timestamp < WARMUP_TIME:
            return result, 0, json.dumps(data)

        # =====================
        # TRADE DEVIATIONS FROM SMILE
        # =====================

        for K in strikes:

            product = f"VEV_{K}"

            if product not in state.order_depths:
                continue

            if K not in current_ivs:
                continue

            fair_iv = self.smooth_iv(K, smoothed_ivs)

            if fair_iv is None:
                continue

            market_iv = current_ivs[K]

            depth = state.order_depths[product]

            if not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())

            best_bid_volume = depth.buy_orders[best_bid]
            best_ask_volume = -depth.sell_orders[best_ask]

            model_price = self.bs_call(S, K, T, fair_iv)

            position = state.position.get(product, 0)

            buy_room = LIMIT - position
            sell_room = LIMIT + position

            orders: List[Order] = []

            # Cheap IV: buy voucher
            if (
                market_iv < fair_iv - VOL_EDGE
                and best_ask < model_price - PRICE_EDGE
                and buy_room > 0
            ):
                qty = min(ORDER_SIZE, best_ask_volume, buy_room)

                if qty > 0:
                    orders.append(Order(product, best_ask, qty))

            # Expensive IV: sell voucher
            if (
                market_iv > fair_iv + VOL_EDGE
                and best_bid > model_price + PRICE_EDGE
                and sell_room > 0
            ):
                qty = min(ORDER_SIZE, best_bid_volume, sell_room)

                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))

            result[product] = orders

        return result, 0, json.dumps(data)
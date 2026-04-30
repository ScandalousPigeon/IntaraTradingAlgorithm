from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:
    PRODUCT = "SLEEP_POD_SUEDE"
    LIMIT = 10

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_sleep_pod_suede(state, result, data)

        return result, 0, json.dumps(data)

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def trade_sleep_pod_suede(self, state: TradingState, result: dict, data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        prefix = "suede_"

        if prefix + "fair" not in data:
            data[prefix + "fair"] = mid
            data[prefix + "fast"] = mid
            data[prefix + "slow"] = mid
            data[prefix + "absret"] = 5.0
            data[prefix + "last_mid"] = mid

        fair = float(data[prefix + "fair"])
        fast = float(data[prefix + "fast"])
        slow = float(data[prefix + "slow"])
        absret = float(data[prefix + "absret"])
        last_mid = float(data[prefix + "last_mid"])

        # Tuned for SLEEP_POD_SUEDE.
        FAIR_ALPHA = 0.040
        FAST_ALPHA = 0.090
        SLOW_ALPHA = 0.008

        TREND_WEIGHT = 0.45
        MAX_TREND_SKEW = 22

        IMBALANCE_WEIGHT = 2.0
        INVENTORY_SKEW = 1.25

        BASE_TAKE_EDGE = 7
        BASE_PASSIVE_EDGE = 3

        TAKE_SIZE = 3
        PASSIVE_SIZE = 2

        # Moving fair value.
        fair = fair + FAIR_ALPHA * (mid - fair)
        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        ret = abs(mid - last_mid)
        absret = 0.90 * absret + 0.10 * ret

        trend = fast - slow

        total_volume = bid_volume + ask_volume
        if total_volume > 0:
            imbalance = (bid_volume - ask_volume) / total_volume
        else:
            imbalance = 0

        trend_skew = self.clamp(TREND_WEIGHT * trend, -MAX_TREND_SKEW, MAX_TREND_SKEW)
        imbalance_skew = IMBALANCE_WEIGHT * imbalance

        adjusted_fair = fair + trend_skew + imbalance_skew - INVENTORY_SKEW * position

        take_edge = BASE_TAKE_EDGE + self.clamp(absret - 6, 0, 4)
        passive_edge = BASE_PASSIVE_EDGE + self.clamp(absret - 8, 0, 2) * 0.5

        can_buy = self.LIMIT - position
        can_sell = self.LIMIT + position

        # Aggressive buy if ask is clearly cheap.
        if can_buy > 0 and best_ask <= adjusted_fair - take_edge:
            qty = min(can_buy, ask_volume, TAKE_SIZE)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                position += qty
                can_buy -= qty
                can_sell += qty

        # Aggressive sell if bid is clearly expensive.
        if can_sell > 0 and best_bid >= adjusted_fair + take_edge:
            qty = min(can_sell, bid_volume, TAKE_SIZE)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                position -= qty
                can_sell -= qty
                can_buy += qty

        # Recalculate after possible aggressive trades.
        adjusted_fair = fair + trend_skew + imbalance_skew - INVENTORY_SKEW * position

        # Passive buy quote.
        if can_buy > 0:
            buy_limit = math.floor(adjusted_fair - passive_edge)
            buy_price = min(best_bid + 1, best_ask - 1, buy_limit)

            if buy_price >= best_bid - 1:
                qty = min(can_buy, PASSIVE_SIZE)
                orders.append(Order(product, int(buy_price), qty))

        # Passive sell quote.
        if can_sell > 0:
            sell_limit = math.ceil(adjusted_fair + passive_edge)
            sell_price = max(best_ask - 1, best_bid + 1, sell_limit)

            if sell_price <= best_ask + 1:
                qty = min(can_sell, PASSIVE_SIZE)
                orders.append(Order(product, int(sell_price), -qty))

        data[prefix + "fair"] = fair
        data[prefix + "fast"] = fast
        data[prefix + "slow"] = slow
        data[prefix + "absret"] = absret
        data[prefix + "last_mid"] = mid
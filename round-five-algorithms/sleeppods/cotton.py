from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_sleep_pod_cotton(state, result, data)

        return result, 0, json.dumps(data)

    def trade_sleep_pod_cotton(self, state: TradingState, result: dict, data: dict) -> None:
        product = "SLEEP_POD_COTTON"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        LIMIT = 10

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        key = "sleep_pod_cotton"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "absret": 8,
                "prev_mid": mid,
            }

        hist = data[key]

        prev_mid = hist.get("prev_mid", mid)
        ret = mid - prev_mid

        # Adaptive fair value.
        # Cotton moves a lot, so do NOT anchor it to 10000.
        hist["fast"] = 0.18 * mid + 0.82 * hist["fast"]
        hist["slow"] = 0.035 * mid + 0.965 * hist["slow"]
        hist["absret"] = 0.06 * abs(ret) + 0.94 * hist["absret"]
        hist["prev_mid"] = mid

        fast = hist["fast"]
        slow = hist["slow"]
        absret = hist["absret"]

        # Top-of-book imbalance.
        # Positive imbalance means stronger bid side.
        if best_bid_volume + best_ask_volume > 0:
            imbalance = (best_bid_volume - best_ask_volume) / (best_bid_volume + best_ask_volume)
        else:
            imbalance = 0

        trend = fast - slow

        # Inventory skew is important because position limit is small.
        fair = fast
        fair += 0.12 * trend
        fair += 8.0 * imbalance
        fair -= 1.9 * position

        # Clamp fair so the bot does not chase too hard.
        max_fair_distance = max(10, 2.2 * absret)
        fair = max(mid - max_fair_distance, min(mid + max_fair_distance, fair))

        # Dynamic edges.
        passive_edge = 2
        take_edge = max(7, int(spread * 0.65))

        # =========================
        # 1. Emergency inventory unwind
        # =========================

        if position >= 8:
            sell_qty = min(2, LIMIT + position, best_bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
                position -= sell_qty

        elif position <= -8:
            buy_qty = min(2, LIMIT - position, best_ask_volume)
            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))
                position += buy_qty

        # =========================
        # 2. Active mispricing trades
        # =========================

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # Buy only when ask is clearly cheap versus adaptive fair.
        if buy_capacity > 0 and best_ask <= fair - take_edge:
            buy_qty = min(2, buy_capacity, best_ask_volume)
            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))
                position += buy_qty

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # Sell only when bid is clearly rich versus adaptive fair.
        if sell_capacity > 0 and best_bid >= fair + take_edge:
            sell_qty = min(2, sell_capacity, best_bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
                position -= sell_qty

        # =========================
        # 3. Passive market making
        # =========================

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # When long, reduce buying. When short, reduce selling.
        buy_size = 2
        sell_size = 2

        if position > 4:
            buy_size = 1
            sell_size = 3

        if position < -4:
            buy_size = 3
            sell_size = 1

        if position >= 7:
            buy_size = 0

        if position <= -7:
            sell_size = 0

        # Passive bid.
        if buy_capacity > 0 and buy_size > 0:
            bid_price = int(math.floor(fair - passive_edge))

            # Usually improve the bid by 1, but never cross the ask.
            bid_price = min(bid_price, best_bid + 1)
            bid_price = min(bid_price, best_ask - 1)

            # Avoid posting absurdly far away.
            bid_price = max(bid_price, best_bid - 3)

            buy_qty = min(buy_size, buy_capacity)

            if buy_qty > 0 and bid_price < best_ask:
                orders.append(Order(product, bid_price, buy_qty))

        # Passive ask.
        if sell_capacity > 0 and sell_size > 0:
            ask_price = int(math.ceil(fair + passive_edge))

            # Usually improve the ask by 1, but never cross the bid.
            ask_price = max(ask_price, best_ask - 1)
            ask_price = max(ask_price, best_bid + 1)

            # Avoid posting absurdly far away.
            ask_price = min(ask_price, best_ask + 3)

            sell_qty = min(sell_size, sell_capacity)

            if sell_qty > 0 and ask_price > best_bid:
                orders.append(Order(product, ask_price, -sell_qty))

        result[product] = orders
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_uv_visor_yellow(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_yellow(self, state: TradingState, result: dict, data: dict) -> None:
        product = "UV_VISOR_YELLOW"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        LIMIT = 10
        ORDER_SIZE = 2

        FAST_ALPHA = 0.01
        SLOW_ALPHA = 0.002

        ENTER_TREND = 25
        EXIT_TREND = 5

        key = "uv_yellow_trend"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "ticks": 0,
                "mode": 0,
            }

        d = data[key]
        d["ticks"] += 1

        d["fast"] = FAST_ALPHA * mid + (1 - FAST_ALPHA) * d["fast"]
        d["slow"] = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * d["slow"]

        trend = d["fast"] - d["slow"]
        mode = d["mode"]

        if d["ticks"] < 100:
            data[key] = d
            return

        # mode 1 = long, mode -1 = short, mode 0 = flat
        if mode == 0:
            if trend > ENTER_TREND:
                mode = 1
            elif trend < -ENTER_TREND:
                mode = -1

        elif mode == 1:
            if trend < EXIT_TREND:
                mode = 0

        elif mode == -1:
            if trend > -EXIT_TREND:
                mode = 0

        d["mode"] = mode
        data[key] = d

        if mode == 1:
            target = LIMIT
        elif mode == -1:
            target = -LIMIT
        else:
            target = 0

        diff = target - position

        if diff > 0:
            qty = min(diff, ORDER_SIZE, best_ask_volume)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        elif diff < 0:
            qty = min(-diff, ORDER_SIZE, best_bid_volume)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
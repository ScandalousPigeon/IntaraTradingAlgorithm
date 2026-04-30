from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "PANEL_4X4"
    LIMIT = 10

    FAST_ALPHA = 2 / (100 + 1)
    SLOW_ALPHA = 2 / (800 + 1)

    ENTRY = 8.0
    EXIT = 3.0

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except:
            data = {}

        self.trade_panel_4x4(state, result, data)

        return result, 0, json.dumps(data)

    def trade_panel_4x4(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        pdata = data.setdefault(product, {})

        if "fast" not in pdata:
            pdata["fast"] = mid
            pdata["slow"] = mid
            pdata["target"] = 0
            pdata["count"] = 0
            return

        pdata["count"] += 1

        fast = pdata["fast"]
        slow = pdata["slow"]

        fast = fast + self.FAST_ALPHA * (mid - fast)
        slow = slow + self.SLOW_ALPHA * (mid - slow)

        pdata["fast"] = fast
        pdata["slow"] = slow

        signal = fast - slow
        old_target = int(pdata.get("target", 0))

        target = old_target

        if signal > self.ENTRY:
            target = self.LIMIT
        elif signal < -self.ENTRY:
            target = -self.LIMIT
        elif abs(signal) < self.EXIT:
            target = 0

        pdata["target"] = target

        current_pos = state.position.get(product, 0)
        desired_change = target - current_pos

        orders: List[Order] = []

        # Buy aggressively up to target
        if desired_change > 0:
            remaining = desired_change

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if remaining <= 0:
                    break

                ask_volume = -order_depth.sell_orders[ask_price]
                buy_qty = min(remaining, ask_volume)

                if buy_qty > 0:
                    orders.append(Order(product, ask_price, buy_qty))
                    remaining -= buy_qty

        # Sell aggressively down to target
        elif desired_change < 0:
            remaining = -desired_change

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if remaining <= 0:
                    break

                bid_volume = order_depth.buy_orders[bid_price]
                sell_qty = min(remaining, bid_volume)

                if sell_qty > 0:
                    orders.append(Order(product, bid_price, -sell_qty))
                    remaining -= sell_qty

        result[product] = orders
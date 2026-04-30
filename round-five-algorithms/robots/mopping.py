from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "ROBOT_MOPPING"
    LIMIT = 10

    # Rolling breakout settings
    WINDOW = 200
    BREAKOUT_BUFFER = 20

    # Avoid trading if book is weird/wide
    MAX_SPREAD = 12

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_robot_mopping(state, result, data)

        return result, 0, json.dumps(data, separators=(",", ":"))

    def trade_robot_mopping(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
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
        ask_volume = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        hist_key = "robot_mopping_hist"
        target_key = "robot_mopping_target"

        history = data.get(hist_key, [])
        target = int(data.get(target_key, 0))

        # Use previous rolling range, not including the current mid.
        if len(history) >= self.WINDOW:
            recent = history[-self.WINDOW:]
            rolling_high = max(recent)
            rolling_low = min(recent)

            # Trend-following breakout.
            if mid > rolling_high + self.BREAKOUT_BUFFER:
                target = self.LIMIT
            elif mid < rolling_low - self.BREAKOUT_BUFFER:
                target = -self.LIMIT
            # Otherwise keep previous target. This is intentional:
            # ROBOT_MOPPING often trends for a long time.

        else:
            target = 0

        # Store current mid after signal calculation.
        history.append(mid)
        if len(history) > self.WINDOW:
            history = history[-self.WINDOW:]

        data[hist_key] = history
        data[target_key] = target

        # Do not enter/flip on ugly books.
        if spread > self.MAX_SPREAD:
            return

        # Move towards target position.
        if target > position:
            qty = min(target - position, self.LIMIT - position, ask_volume)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        elif target < position:
            qty = min(position - target, self.LIMIT + position, bid_volume)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
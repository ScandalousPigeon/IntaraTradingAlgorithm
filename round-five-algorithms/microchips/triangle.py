from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    PRODUCT = "MICROCHIP_TRIANGLE"
    LIMIT = 10

    # Slow adaptive fair value
    EMA_SPAN = 3000
    ALPHA = 2 / (EMA_SPAN + 1)

    # Mean-reversion bands
    ENTRY_BAND = 300      # enter when price is very far from EMA
    EXIT_BAND = 20        # exit when price comes back near EMA

    # Minimum edge required when adding to a position
    MIN_TAKE_EDGE = 25

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        # Reset at the start of a new day/simulation
        if state.timestamp == 0:
            data["triangle"] = {}

        self.trade_microchip_triangle(state, result, data)

        return result, 0, json.dumps(data)

    def trade_microchip_triangle(self, state: TradingState, result: Dict[str, List[Order]], data: dict):
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        tri_data = data.get("triangle", {})

        if "ema" not in tri_data:
            ema = mid
        else:
            ema = tri_data["ema"]
            ema = ema + self.ALPHA * (mid - ema)

        side = tri_data.get("side", 0)

        # Positive deviation means price is below EMA, so we want to buy.
        deviation = ema - mid

        # Hysteresis state machine
        if side == 0:
            if deviation > self.ENTRY_BAND:
                side = 1
            elif deviation < -self.ENTRY_BAND:
                side = -1

        elif side == 1:
            # Long because price was cheap.
            # Exit when it reverts, or flip if it overshoots high.
            if deviation < -self.ENTRY_BAND:
                side = -1
            elif deviation < self.EXIT_BAND:
                side = 0

        elif side == -1:
            # Short because price was expensive.
            # Exit when it reverts, or flip if it overshoots low.
            if deviation > self.ENTRY_BAND:
                side = 1
            elif deviation > -self.EXIT_BAND:
                side = 0

        tri_data["ema"] = ema
        tri_data["side"] = side
        data["triangle"] = tri_data

        target_position = side * self.LIMIT
        target_position = max(-self.LIMIT, min(self.LIMIT, target_position))

        delta = target_position - position

        orders: List[Order] = []

        # Buy towards target
        if delta > 0:
            remaining = min(delta, self.LIMIT - position)

            # If closing a short, close aggressively.
            # If opening/increasing long, only buy with enough edge versus EMA.
            closing_short = position < 0
            max_buy_price = 10**9 if closing_short else math.floor(ema - self.MIN_TAKE_EDGE)

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if remaining <= 0:
                    break

                if ask_price > max_buy_price:
                    continue

                available = -order_depth.sell_orders[ask_price]
                quantity = min(remaining, available)

                if quantity > 0:
                    orders.append(Order(product, ask_price, quantity))
                    remaining -= quantity

        # Sell towards target
        elif delta < 0:
            remaining = min(-delta, self.LIMIT + position)

            # If closing a long, close aggressively.
            # If opening/increasing short, only sell with enough edge versus EMA.
            closing_long = position > 0
            min_sell_price = -10**9 if closing_long else math.ceil(ema + self.MIN_TAKE_EDGE)

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if remaining <= 0:
                    break

                if bid_price < min_sell_price:
                    continue

                available = order_depth.buy_orders[bid_price]
                quantity = min(remaining, available)

                if quantity > 0:
                    orders.append(Order(product, bid_price, -quantity))
                    remaining -= quantity

        result[product] = orders
from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "GALAXY_SOUNDS_SOLAR_WINDS"

    LIMIT = 10

    # Trend-following EMAs.
    # Solar Winds tends to move in chunky directional waves,
    # so this version only trades when the fast trend separates strongly.
    FAST_ALPHA = 0.20
    SLOW_ALPHA = 0.01

    # Higher = fewer trades, safer.
    # Lower to 120 if this is still too inactive.
    ENTRY_SIGNAL = 150

    # Max amount to cross per tick.
    MAX_STEP = 5

    # Avoid weird/wide books.
    MAX_SPREAD = 18

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_solar_winds(state, result, data)

        return result, 0, json.dumps(data)

    def trade_solar_winds(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        if best_bid >= best_ask:
            return

        spread = best_ask - best_bid

        if spread > self.MAX_SPREAD:
            return

        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        memory = data.get(product, {})

        fast = memory.get("fast", mid)
        slow = memory.get("slow", mid)

        # Update EMAs using current mid.
        fast = self.FAST_ALPHA * mid + (1 - self.FAST_ALPHA) * fast
        slow = self.SLOW_ALPHA * mid + (1 - self.SLOW_ALPHA) * slow

        signal = fast - slow

        memory["fast"] = fast
        memory["slow"] = slow
        memory["signal"] = signal
        data[product] = memory

        buy_capacity = self.LIMIT - position
        sell_capacity = self.LIMIT + position

        best_ask_volume = abs(order_depth.sell_orders[best_ask])
        best_bid_volume = abs(order_depth.buy_orders[best_bid])

        # =========================
        # AGGRESSIVE TREND FOLLOWING
        # =========================
        #
        # If fast EMA is far above slow EMA, momentum is up:
        # buy at the ask.
        #
        # If fast EMA is far below slow EMA, momentum is down:
        # sell at the bid.
        #
        # This crosses the spread, so it should actually produce fills.

        if signal > self.ENTRY_SIGNAL and buy_capacity > 0:
            qty = min(self.MAX_STEP, buy_capacity, best_ask_volume)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        elif signal < -self.ENTRY_SIGNAL and sell_capacity > 0:
            qty = min(self.MAX_STEP, sell_capacity, best_bid_volume)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
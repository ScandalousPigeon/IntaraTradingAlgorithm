from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        product = "GALAXY_SOUNDS_SOLAR_FLAMES"

        if product in state.order_depths:
            result[product] = self.trade_low_turnover_momentum(
                product,
                state.order_depths[product],
                state.position.get(product, 0),
                data
            )

        return result, 0, json.dumps(data)

    def trade_low_turnover_momentum(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> List[Order]:

        orders = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        LIMIT = 10

        FAST_ALPHA = 0.008
        SLOW_ALPHA = 0.0015

        ENTRY_THRESHOLD = 12
        EXIT_THRESHOLD = 4

        TRADE_SIZE = 2

        fast_key = product + "_fast"
        slow_key = product + "_slow"

        if fast_key not in data:
            data[fast_key] = mid

        if slow_key not in data:
            data[slow_key] = mid

        fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * data[fast_key]
        slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * data[slow_key]

        data[fast_key] = fast
        data[slow_key] = slow

        signal = fast - slow

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # Strong uptrend: build/hold long
        if signal > ENTRY_THRESHOLD and buy_room > 0:
            qty = min(TRADE_SIZE, best_ask_volume, buy_room)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        # Strong downtrend: build/hold short
        elif signal < -ENTRY_THRESHOLD and sell_room > 0:
            qty = min(TRADE_SIZE, best_bid_volume, sell_room)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        # Trend gone: flatten, but slowly
        elif abs(signal) < EXIT_THRESHOLD:

            if position > 0:
                qty = min(TRADE_SIZE, best_bid_volume, abs(position))

                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))

            elif position < 0:
                qty = min(TRADE_SIZE, best_ask_volume, abs(position))

                if qty > 0:
                    orders.append(Order(product, best_ask, qty))

        return orders
from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        self.trade_oxygen_shake_garlic(state, result)

        return result, 0, state.traderData or ""

    def trade_oxygen_shake_garlic(self, state: TradingState, result: Dict[str, List[Order]]) -> None:
        product = "OXYGEN_SHAKE_GARLIC"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.sell_orders or not order_depth.buy_orders:
            return

        position = state.position.get(product, 0)

        best_ask = min(order_depth.sell_orders.keys())
        best_ask_volume = -order_depth.sell_orders[best_ask]

        best_bid = max(order_depth.buy_orders.keys())
        best_bid_volume = order_depth.buy_orders[best_bid]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        orders: List[Order] = []

        # Garlic has shown strong upward drift across the data.
        # The main edge is simply being long, not overtrading.
        target_position = LIMIT

        # Buy aggressively up to +10.
        if position < target_position:
            buy_qty = min(target_position - position, best_ask_volume)

            # Avoid buying if the book is extremely wide or broken.
            # Normal spread is around 14-16, so 25 is still generous.
            if buy_qty > 0 and spread <= 25:
                orders.append(Order(product, best_ask, buy_qty))

        # If somehow we become too long, flatten back to the limit.
        if position > LIMIT:
            sell_qty = min(position - LIMIT, best_bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        result[product] = orders
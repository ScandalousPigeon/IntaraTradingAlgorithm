from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_panel_1x4(state, result, data)

        return result, 0, json.dumps(data)

    def trade_panel_1x4(self, state: TradingState, result: dict, data: dict) -> None:
        product = "PANEL_1X4"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        LIMIT = 10

        # Signal parameters
        ENTRY_IMBALANCE = 0.30
        MAX_SPREAD = 10

        position = state.position.get(product, 0)

        bid_prices = sorted(order_depth.buy_orders.keys(), reverse=True)
        ask_prices = sorted(order_depth.sell_orders.keys())

        best_bid = bid_prices[0]
        best_ask = ask_prices[0]

        spread = best_ask - best_bid

        if spread > MAX_SPREAD:
            result[product] = orders
            return

        # Use first two levels of the book.
        bid_volume = 0
        ask_volume = 0

        for price in bid_prices[:2]:
            bid_volume += order_depth.buy_orders[price]

        for price in ask_prices[:2]:
            ask_volume += -order_depth.sell_orders[price]

        if bid_volume + ask_volume == 0:
            result[product] = orders
            return

        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

        # Core idea:
        # If bids are much heavier than asks, price tends to rise.
        # If asks are much heavier than bids, price tends to fall.
        #
        # Do NOT flatten when the signal disappears.
        # Hold until the opposite signal appears, because constantly exiting
        # pays the spread too often.
        target_position = position

        if imbalance > ENTRY_IMBALANCE:
            target_position = LIMIT

        elif imbalance < -ENTRY_IMBALANCE:
            target_position = -LIMIT

        # Move toward target position.
        if target_position > position:
            buy_qty = target_position - position

            best_ask_volume = -order_depth.sell_orders[best_ask]
            buy_qty = min(buy_qty, best_ask_volume)

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif target_position < position:
            sell_qty = position - target_position

            best_bid_volume = order_depth.buy_orders[best_bid]
            sell_qty = min(sell_qty, best_bid_volume)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        result[product] = orders
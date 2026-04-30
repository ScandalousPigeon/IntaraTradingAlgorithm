from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_dark_matter(state, result)

        return result, 0, json.dumps(data)

    def trade_dark_matter(self, state: TradingState, result: dict) -> None:
        product = "GALAXY_SOUNDS_DARK_MATTER"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]
        orders: List[Order] = []

        LIMIT = 10
        position = state.position.get(product, 0)
        timestamp = state.timestamp

        # =========================
        # DARK MATTER SEASONALITY
        # =========================
        #
        # Historical pattern:
        # - early part of day tends to drift down
        # - later part tends to recover upward
        #
        # So we:
        # - short early
        # - flatten during transition
        # - go long later

        if timestamp < 325000:
            target_position = -LIMIT
        elif timestamp < 375000:
            target_position = 0
        else:
            target_position = LIMIT

        # =========================
        # MOVE TOWARDS TARGET
        # =========================

        diff = target_position - position

        # Need to buy
        if diff > 0 and order_depth.sell_orders:
            buy_qty = diff

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if buy_qty <= 0:
                    break

                ask_volume = abs(order_depth.sell_orders[ask_price])
                quantity = min(buy_qty, ask_volume)

                if quantity > 0:
                    orders.append(Order(product, ask_price, quantity))
                    buy_qty -= quantity

        # Need to sell
        elif diff < 0 and order_depth.buy_orders:
            sell_qty = -diff

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if sell_qty <= 0:
                    break

                bid_volume = abs(order_depth.buy_orders[bid_price])
                quantity = min(sell_qty, bid_volume)

                if quantity > 0:
                    orders.append(Order(product, bid_price, -quantity))
                    sell_qty -= quantity

        result[product] = orders
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

        self.trade_uv_visor_orange(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_orange(self, state: TradingState, result: dict, data: dict) -> None:
        product = "UV_VISOR_ORANGE"

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

        # =========================
        # PARAMETERS
        # =========================

        LIMIT = 10

        # Lower alpha than 0.30 so fair doesn't chase mid too hard
        ALPHA = 0.08

        EDGE = 10
        ORDER_SIZE = 2

        TAKE_EDGE = 20
        TAKE_SIZE = 2

        INVENTORY_SKEW = 1.5

        key = "uv_orange"

        if key not in data or state.timestamp == 0:
            data[key] = {
                "fair": mid,
                "last_mid": mid,
                "last_timestamp": state.timestamp,
            }

        fair = data[key]["fair"]

        fair = fair + ALPHA * (mid - fair)

        skewed_fair = fair - INVENTORY_SKEW * position

        # =========================
        # AGGRESSIVE BUY
        # =========================
        # Buy when ask is sufficiently cheap versus fair

        if best_ask <= skewed_fair - TAKE_EDGE and position < LIMIT:

            buy_qty = min(
                TAKE_SIZE,
                LIMIT - position,
                best_ask_volume
            )

            if buy_qty > 0:
                orders.append(
                    Order(
                        product,
                        best_ask,
                        buy_qty
                    )
                )

                position += buy_qty

        # =========================
        # AGGRESSIVE SELL
        # =========================
        # Sell when bid is sufficiently rich versus fair

        if best_bid >= skewed_fair + TAKE_EDGE and position > -LIMIT:

            sell_qty = min(
                TAKE_SIZE,
                LIMIT + position,
                best_bid_volume
            )

            if sell_qty > 0:
                orders.append(
                    Order(
                        product,
                        best_bid,
                        -sell_qty
                    )
                )

                position -= sell_qty

        # =========================
        # INVENTORY EXIT / DE-RISK
        # =========================
        # If long and price is no longer cheap, sell some.
        # If short and price is no longer rich, buy some.

        if position > 0 and best_bid >= skewed_fair - EDGE:

            sell_qty = min(
                ORDER_SIZE,
                position,
                best_bid_volume
            )

            if sell_qty > 0:
                orders.append(
                    Order(
                        product,
                        best_bid,
                        -sell_qty
                    )
                )

                position -= sell_qty

        elif position < 0 and best_ask <= skewed_fair + EDGE:

            buy_qty = min(
                ORDER_SIZE,
                -position,
                best_ask_volume
            )

            if buy_qty > 0:
                orders.append(
                    Order(
                        product,
                        best_ask,
                        buy_qty
                    )
                )

                position += buy_qty

        data[key]["fair"] = fair
        data[key]["last_mid"] = mid
        data[key]["last_timestamp"] = state.timestamp

        result[product] = orders
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        # -------------------------
        # HYDROGEL_PACK only
        # -------------------------

        product = "HYDROGEL_PACK"
        orders: List[Order] = []

        if product in state.order_depths:

            order_depth: OrderDepth = state.order_depths[product]

            if order_depth.buy_orders and order_depth.sell_orders:

                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())

                mid = (best_bid + best_ask) / 2

                # Parameters
                LIMIT = 200
                BASE_FAIR = 9990

                ALPHA = 0.015
                ANCHOR_WEIGHT = 0.02

                EDGE = 6
                ORDER_SIZE = 16
                INVENTORY_SKEW = 0.03

                # Historical momentum only
                MOMENTUM_EMA_ALPHA = 0.20
                MOMENTUM_SKEW = 0.03

                # -------------------------
                # Fair value
                # -------------------------

                if "hydrogel_fair" not in data:
                    data["hydrogel_fair"] = BASE_FAIR
                else:
                    data["hydrogel_fair"] = (
                        ALPHA * mid
                        + (1 - ALPHA) * data["hydrogel_fair"]
                    )

                fair = data["hydrogel_fair"]

                # Weak pull to long-run centre
                fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
                data["hydrogel_fair"] = fair

                # -------------------------
                # Historical momentum
                # -------------------------

                if "hydrogel_last_mid" not in data:
                    data["hydrogel_last_mid"] = mid

                momentum = mid - data["hydrogel_last_mid"]
                data["hydrogel_last_mid"] = mid

                if "hydrogel_momentum_ema" not in data:
                    data["hydrogel_momentum_ema"] = momentum
                else:
                    data["hydrogel_momentum_ema"] = (
                        MOMENTUM_EMA_ALPHA * momentum
                        + (1 - MOMENTUM_EMA_ALPHA) * data["hydrogel_momentum_ema"]
                    )

                momentum_ema = data["hydrogel_momentum_ema"]

                # Blend current and historical momentum
                momentum_signal = 0.5 * momentum + 0.5 * momentum_ema

                # -------------------------
                # Position
                # -------------------------

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                # Original inventory skew + small momentum adjustment
                adjusted_fair = (
                    fair
                    - INVENTORY_SKEW * position
                    + MOMENTUM_SKEW * momentum_signal
                )

                # -------------------------
                # Passive market-making quotes
                # -------------------------

                bid_price = int(round(adjusted_fair - EDGE))
                ask_price = int(round(adjusted_fair + EDGE))

                # Avoid crossing too much
                bid_price = min(bid_price, best_bid + 1)
                ask_price = max(ask_price, best_ask - 1)

                if buy_room > 0:
                    buy_qty = min(ORDER_SIZE, buy_room)
                    orders.append(Order(product, bid_price, buy_qty))

                if sell_room > 0:
                    sell_qty = min(ORDER_SIZE, sell_room)
                    orders.append(Order(product, ask_price, -sell_qty))

        result[product] = orders

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData
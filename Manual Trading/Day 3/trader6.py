from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        product = "HYDROGEL_PACK"
        orders: List[Order] = []

        if product in state.order_depths:

            order_depth: OrderDepth = state.order_depths[product]

            if order_depth.buy_orders and order_depth.sell_orders:

                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())

                mid = (best_bid + best_ask) / 2

                LIMIT = 200
                BASE_FAIR = 10000

                ALPHA = 0.01
                ANCHOR_WEIGHT = 0.02

                EDGE = 10
                ORDER_SIZE = 14
                INVENTORY_SKEW = 0.03
                TREND_SKEW = 0.03

                if "hydrogel_fair" not in data:
                    data["hydrogel_fair"] = BASE_FAIR
                else:
                    data["hydrogel_fair"] = (
                        ALPHA * mid
                        + (1 - ALPHA) * data["hydrogel_fair"]
                    )

                fair = data["hydrogel_fair"]

                fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
                data["hydrogel_fair"] = fair

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                trend = mid - fair

                adjusted_fair = (
                    fair
                    + TREND_SKEW * trend
                    - INVENTORY_SKEW * position
                )

                bid_price = int(round(adjusted_fair - EDGE))
                ask_price = int(round(adjusted_fair + EDGE))

                # Stay passive: do not cross the current book
                bid_price = min(bid_price, best_bid)
                ask_price = max(ask_price, best_ask)

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
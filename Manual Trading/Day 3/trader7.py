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
                ALPHA = 0.03

                BASE_EDGE = 5
                VOL_MULT = 0.4

                ORDER_SIZE = 20
                INVENTORY_SKEW = 0.01

                if "hydrogel_fair" not in data:
                    data["hydrogel_fair"] = mid

                fair = data["hydrogel_fair"]

                if "hydrogel_last_mid" not in data:
                    data["hydrogel_last_mid"] = mid

                last_mid = data["hydrogel_last_mid"]
                instant_vol = abs(mid - last_mid)

                if "hydrogel_vol" not in data:
                    data["hydrogel_vol"] = instant_vol
                else:
                    data["hydrogel_vol"] = (
                        0.05 * instant_vol
                        + 0.95 * data["hydrogel_vol"]
                    )

                vol = data["hydrogel_vol"]

                fair = ALPHA * mid + (1 - ALPHA) * fair

                data["hydrogel_fair"] = fair
                data["hydrogel_last_mid"] = mid

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                adjusted_fair = fair - INVENTORY_SKEW * position

                edge = BASE_EDGE + VOL_MULT * vol
                edge = max(4, min(20, edge))

                bid_price = int(round(adjusted_fair - edge))
                ask_price = int(round(adjusted_fair + edge))

                # More competitive, but usually not crossing
                bid_price = min(bid_price, best_bid + 1)
                ask_price = max(ask_price, best_ask - 1)

                if bid_price >= ask_price:
                    bid_price = best_bid
                    ask_price = best_ask

                if buy_room > 0:
                    buy_qty = min(ORDER_SIZE, buy_room)
                    orders.append(Order(product, bid_price, buy_qty))

                if sell_room > 0:
                    sell_qty = min(ORDER_SIZE, sell_room)
                    orders.append(Order(product, ask_price, -sell_qty))

        result[product] = orders
        return result, 0, json.dumps(data)
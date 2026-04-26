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
            order_depth = state.order_depths[product]

            if order_depth.buy_orders and order_depth.sell_orders:
                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())

                mid = (best_bid + best_ask) / 2

                LIMIT = 200
                ALPHA = 0.03
                BASE_EDGE = 5
                VOL_MULT = 0.5
                ORDER_SIZE = 30
                INVENTORY_SKEW = 0.008

                if "hydrogel_fair" not in data:
                    data["hydrogel_fair"] = mid

                if "hydrogel_last_mid" not in data:
                    data["hydrogel_last_mid"] = mid

                if "hydrogel_vol" not in data:
                    data["hydrogel_vol"] = 0

                fair = data["hydrogel_fair"]
                last_mid = data["hydrogel_last_mid"]

                instant_vol = abs(mid - last_mid)
                vol = 0.05 * instant_vol + 0.95 * data["hydrogel_vol"]

                fair = ALPHA * mid + (1 - ALPHA) * fair

                data["hydrogel_fair"] = fair
                data["hydrogel_last_mid"] = mid
                data["hydrogel_vol"] = vol

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                adjusted_fair = fair - INVENTORY_SKEW * position

                edge = BASE_EDGE + VOL_MULT * vol
                edge = max(3, min(15, edge))

                bid_price = int(round(adjusted_fair - edge))
                ask_price = int(round(adjusted_fair + edge))

                bid_price = min(bid_price, best_bid + 1)
                ask_price = max(ask_price, best_ask - 1)

                if bid_price >= ask_price:
                    bid_price = best_bid
                    ask_price = best_ask

                if buy_room > 0:
                    orders.append(Order(product, bid_price, min(ORDER_SIZE, buy_room)))

                if sell_room > 0:
                    orders.append(Order(product, ask_price, -min(ORDER_SIZE, sell_room)))

        result[product] = orders
        return result, 0, json.dumps(data)
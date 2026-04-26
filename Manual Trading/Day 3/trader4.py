from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:

    def run(self, state: TradingState):

        result = {}

        data = json.loads(state.traderData) if state.traderData else {}

        product = "VELVETFRUIT_EXTRACT"
        orders: List[Order] = []

        if product in state.order_depths:

            order_depth: OrderDepth = state.order_depths[product]

            if order_depth.buy_orders and order_depth.sell_orders:

                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())

                mid = (best_bid + best_ask) / 2

                # Parameters
                LIMIT = 200
                BASE_FAIR = 5250

                ALPHA = 0.003
                EDGE = 6
                ORDER_SIZE = 12
                INVENTORY_SKEW = 0.06

                # Fair value
                if "velvet_fair" not in data:
                    data["velvet_fair"] = BASE_FAIR
                else:
                    data["velvet_fair"] = (
                        ALPHA * mid
                        + (1 - ALPHA) * data["velvet_fair"]
                    )

                fair = data["velvet_fair"]

                # Pull gently back to known long-run mean
                fair = 0.9 * fair + 0.1 * BASE_FAIR
                data["velvet_fair"] = fair

                # Position
                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                # Inventory skew
                adjusted_fair = fair - INVENTORY_SKEW * position

                # Passive market-making quotes
                bid_price = int(round(adjusted_fair - EDGE))
                ask_price = int(round(adjusted_fair + EDGE))

                # Do not cross the book
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
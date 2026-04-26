from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:

    def run(self, state: TradingState):

        result = {}

        if state.traderData:
            data = json.loads(state.traderData)
        else:
            data = {}

        product = "VELVETFRUIT_EXTRACT"
        orders = []

        if product in state.order_depths:

            order_depth = state.order_depths[product]

            if order_depth.buy_orders and order_depth.sell_orders:

                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())

                mid = (best_bid + best_ask) / 2

                # EMA fair value
                alpha = 0.05

                if "fair" not in data:
                    data["fair"] = mid
                else:
                    data["fair"] = (
                        alpha * mid
                        + (1 - alpha) * data["fair"]
                    )

                fair = data["fair"]

                position = state.position.get(product, 0)

                LIMIT = 200

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                # inventory skew
                fair_adjusted = fair - position * 0.05

                edge = 4

                buy_price = int(fair_adjusted - edge)
                sell_price = int(fair_adjusted + edge)

                order_size = 10

                if buy_room > 0:
                    orders.append(
                        Order(
                            product,
                            buy_price,
                            min(order_size, buy_room)
                        )
                    )

                if sell_room > 0:
                    orders.append(
                        Order(
                            product,
                            sell_price,
                            -min(order_size, sell_room)
                        )
                    )

        result[product] = orders

        traderData = json.dumps(data)

        conversions = 0

        return result, conversions, traderData
    
#simpler market making i think
#profit = 1126
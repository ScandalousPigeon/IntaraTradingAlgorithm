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
                BASE_FAIR = 9991

                ALPHA = 0.03
                ANCHOR_WEIGHT = 0.02

                EDGE = 5
                ORDER_SIZE = 16
                INVENTORY_SKEW = 0.03

                # =====================
                # FAIR VALUE
                # =====================

                if "hydrogel_fair" not in data:
                    data["hydrogel_fair"] = BASE_FAIR
                else:
                    data["hydrogel_fair"] = (
                        ALPHA * mid
                        + (1 - ALPHA) * data["hydrogel_fair"]
                    )

                fair = data["hydrogel_fair"]

                fair = (
                    (1 - ANCHOR_WEIGHT) * fair
                    + ANCHOR_WEIGHT * BASE_FAIR
                )

                data["hydrogel_fair"] = fair

                # =====================
                # MARK 14 BULLISH MODE
                # =====================

                if "hydrogel_bullish_timer" not in data:
                    data["hydrogel_bullish_timer"] = 0

                data["hydrogel_bullish_timer"] = max(
                    0,
                    data["hydrogel_bullish_timer"] - 1
                )

                recent_trades = state.market_trades.get(product, [])

                for trade in recent_trades:
                    if trade.buyer == "Mark 14":
                        data["hydrogel_bullish_timer"] = 20

                # =====================
                # POSITION
                # =====================

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                # =====================
                # DYNAMIC QUOTING
                # =====================

                if data["hydrogel_bullish_timer"] > 0:
                    bid_edge = 1
                    ask_edge = 10
                    flow_fair_shift = 5
                else:
                    bid_edge = EDGE
                    ask_edge = EDGE
                    flow_fair_shift = 0

                adjusted_fair = (
                    fair
                    - INVENTORY_SKEW * position
                    + flow_fair_shift
                )

                bid_price = int(round(adjusted_fair - bid_edge))
                ask_price = int(round(adjusted_fair + ask_edge))

                # Do not cross with passive orders
                bid_price = min(bid_price, best_ask - 1)
                ask_price = max(ask_price, best_bid + 1)

                if data["hydrogel_bullish_timer"] > 0:
                    buy_qty = min(int(ORDER_SIZE * 2.5), buy_room)
                    sell_qty = min(int(ORDER_SIZE * 0.5), sell_room)
                else:
                    buy_qty = min(ORDER_SIZE, buy_room)
                    sell_qty = min(ORDER_SIZE, sell_room)


                if buy_room > 0:
                    orders.append(Order(product, bid_price, buy_qty))

                if sell_room > 0:
                    orders.append(Order(product, ask_price, -sell_qty))

        result[product] = orders

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData
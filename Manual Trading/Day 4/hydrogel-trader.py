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
                BASE_FAIR = 9991

                ALPHA = 0.03
                ANCHOR_WEIGHT = 0.02

                EDGE = 5
                ORDER_SIZE = 16
                INVENTORY_SKEW = 0.03

                # Fair value
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

                # =====================
                # FLOW SIGNAL
                # =====================

                if "hydrogel_flow" not in data:
                    data["hydrogel_flow"] = 0.0

                # persistent but not permanent
                data["hydrogel_flow"] *= 0.95

                recent_trades = state.market_trades.get(product, [])

                for trade in recent_trades:

                    qty_weight = min(2.0, max(1.0, trade.quantity / 4))

                    # Mark 14 buying was bullish
                    if trade.buyer == "Mark 14":
                        data["hydrogel_flow"] += 2.0 * qty_weight

                    # Mark 38 selling was bullish
                    if trade.seller == "Mark 38":
                        data["hydrogel_flow"] += 2.0 * qty_weight

                flow_signal = max(-20, min(20, data["hydrogel_flow"]))

                # Position
                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                # Add flow to fair value
                FLOW_FAIR_WEIGHT = 2.0

                adjusted_fair = (
                    fair
                    - INVENTORY_SKEW * position
                    + FLOW_FAIR_WEIGHT * flow_signal
                )

                # Passive quotes
                bid_price = int(round(adjusted_fair - EDGE))
                ask_price = int(round(adjusted_fair + EDGE))

                bid_price = min(bid_price, best_ask - 1)
                ask_price = max(ask_price, best_bid + 1)

                if buy_room > 0:
                    orders.append(
                        Order(product, bid_price, min(ORDER_SIZE, buy_room))
                    )

                if sell_room > 0:
                    orders.append(
                        Order(product, ask_price, -min(ORDER_SIZE, sell_room))
                    )

                # Aggressive buy when strong bullish flow appears
                if flow_signal > 6 and buy_room > 0:
                    ask_volume = -order_depth.sell_orders[best_ask]
                    qty = min(20, ask_volume, buy_room)

                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))

        result[product] = orders

        return result, 0, json.dumps(data)
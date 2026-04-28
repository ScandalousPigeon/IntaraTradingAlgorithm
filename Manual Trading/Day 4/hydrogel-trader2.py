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

                # =====================
                # PARAMETERS
                # =====================

                LIMIT = 200
                BASE_FAIR = 9991

                ALPHA = 0.03
                ANCHOR_WEIGHT = 0.02

                BASE_EDGE = 5
                ORDER_SIZE = 18
                INVENTORY_SKEW = 0.035

                FLOW_DECAY = 0.93
                FLOW_CAP = 12

                TARGET_MULTIPLIER = 8
                TARGET_SKEW = 0.04

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
                fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
                data["hydrogel_fair"] = fair

                # =====================
                # FLOW SIGNAL
                # =====================
                # Mark 14 buy = bullish
                # Mark 14 sell = bearish
                # Mark 38 buy = bearish
                # Mark 38 sell = bullish

                if "hydrogel_flow" not in data:
                    data["hydrogel_flow"] = 0.0

                data["hydrogel_flow"] *= FLOW_DECAY

                recent_trades = state.market_trades.get(product, [])

                for trade in recent_trades:

                    qty_weight = min(2.0, max(1.0, trade.quantity / 4))

                    if trade.buyer == "Mark 14":
                        data["hydrogel_flow"] += 1.5 * qty_weight

                    if trade.seller == "Mark 14":
                        data["hydrogel_flow"] -= 1.5 * qty_weight

                    if trade.buyer == "Mark 38":
                        data["hydrogel_flow"] -= 1.5 * qty_weight

                    if trade.seller == "Mark 38":
                        data["hydrogel_flow"] += 1.5 * qty_weight

                flow = max(-FLOW_CAP, min(FLOW_CAP, data["hydrogel_flow"]))

                # =====================
                # POSITION TARGET
                # =====================

                position = state.position.get(product, 0)

                target_position = int(TARGET_MULTIPLIER * flow)
                target_position = max(-LIMIT, min(LIMIT, target_position))

                position_gap = target_position - position

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                # =====================
                # CONDITIONAL QUOTING
                # =====================

                adjusted_fair = (
                    fair
                    - INVENTORY_SKEW * position
                    + TARGET_SKEW * position_gap
                )

                # If bullish flow, bid more aggressively and ask less aggressively.
                # If bearish flow, ask more aggressively and bid less aggressively.
                if flow > 2:
                    bid_edge = max(2, BASE_EDGE - 2)
                    ask_edge = BASE_EDGE + 2
                elif flow < -2:
                    bid_edge = BASE_EDGE + 2
                    ask_edge = max(2, BASE_EDGE - 2)
                else:
                    bid_edge = BASE_EDGE
                    ask_edge = BASE_EDGE

                bid_price = int(round(adjusted_fair - bid_edge))
                ask_price = int(round(adjusted_fair + ask_edge))

                # Passive only: do not cross
                bid_price = min(bid_price, best_ask - 1)
                ask_price = max(ask_price, best_bid + 1)

                # Size slightly larger when moving toward target
                buy_size = ORDER_SIZE
                sell_size = ORDER_SIZE

                if position_gap > 0:
                    buy_size = int(ORDER_SIZE * 1.5)
                    sell_size = int(ORDER_SIZE * 0.7)

                elif position_gap < 0:
                    buy_size = int(ORDER_SIZE * 0.7)
                    sell_size = int(ORDER_SIZE * 1.5)

                if buy_room > 0 and buy_size > 0:
                    orders.append(
                        Order(product, bid_price, min(buy_size, buy_room))
                    )

                if sell_room > 0 and sell_size > 0:
                    orders.append(
                        Order(product, ask_price, -min(sell_size, sell_room))
                    )

        result[product] = orders

        return result, 0, json.dumps(data)
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

                # Flow signal params
                FLOW_DECAY = 0.82
                MARK14_BUY_IMPACT = 3.0
                MARK14_SELL_IMPACT = -3.0
                MAX_FLOW_SIGNAL = 8.0

                # =========================
                # EMA FAIR
                # =========================

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

                # =========================
                # MARK 14 FLOW SIGNAL
                # =========================

                if "hydrogel_flow_signal" not in data:
                    data["hydrogel_flow_signal"] = 0.0

                # decay old signal every tick
                data["hydrogel_flow_signal"] *= FLOW_DECAY

                if product in state.market_trades:
                    for trade in state.market_trades[product]:

                        if trade.buyer == "Mark 14":
                            data["hydrogel_flow_signal"] += MARK14_BUY_IMPACT

                        if trade.seller == "Mark 14":
                            data["hydrogel_flow_signal"] += MARK14_SELL_IMPACT

                # cap signal
                if data["hydrogel_flow_signal"] > MAX_FLOW_SIGNAL:
                    data["hydrogel_flow_signal"] = MAX_FLOW_SIGNAL
                if data["hydrogel_flow_signal"] < -MAX_FLOW_SIGNAL:
                    data["hydrogel_flow_signal"] = -MAX_FLOW_SIGNAL

                flow_signal = data["hydrogel_flow_signal"]

                # =========================
                # POSITION / INVENTORY
                # =========================

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                inventory_adjustment = INVENTORY_SKEW * position

                adjusted_fair = fair + flow_signal - inventory_adjustment

                # =========================
                # ASYMMETRIC QUOTE SKEW
                # =========================

                bid_price = int(round(adjusted_fair - EDGE))
                ask_price = int(round(adjusted_fair + EDGE))

                # If bullish flow, avoid selling too cheaply
                if flow_signal > 1:
                    bid_price += 1
                    ask_price += 3

                # If bearish flow, avoid buying too expensively
                elif flow_signal < -1:
                    bid_price -= 3
                    ask_price -= 1

                # Keep passive / near touch
                bid_price = min(bid_price, best_bid + 1)
                ask_price = max(ask_price, best_ask - 1)

                # Emergency: don't quote crossed
                if bid_price >= ask_price:
                    bid_price = best_bid
                    ask_price = best_ask

                # =========================
                # SIZE ADJUSTMENT
                # =========================

                buy_qty = ORDER_SIZE
                sell_qty = ORDER_SIZE

                # Bullish flow: prefer buying, reduce selling
                if flow_signal > 1:
                    buy_qty = 20
                    sell_qty = 8

                # Bearish flow: prefer selling, reduce buying
                elif flow_signal < -1:
                    buy_qty = 8
                    sell_qty = 20

                # If already too long, don't keep leaning long
                if position > 120:
                    buy_qty = 4
                    sell_qty = 24

                # If already too short, don't keep leaning short
                if position < -120:
                    buy_qty = 24
                    sell_qty = 4

                # =========================
                # SEND ORDERS
                # =========================

                if buy_room > 0:
                    orders.append(
                        Order(product, bid_price, min(buy_qty, buy_room))
                    )

                if sell_room > 0:
                    orders.append(
                        Order(product, ask_price, -min(sell_qty, sell_room))
                    )

        result[product] = orders

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData
    
    # 1449
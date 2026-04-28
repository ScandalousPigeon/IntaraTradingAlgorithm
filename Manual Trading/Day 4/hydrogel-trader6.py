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

                best_bid_volume = order_depth.buy_orders[best_bid]
                best_ask_volume = abs(order_depth.sell_orders[best_ask])

                spread = best_ask - best_bid
                mid = (best_bid + best_ask) / 2

                microprice = (
                    best_bid * best_ask_volume
                    + best_ask * best_bid_volume
                ) / (best_bid_volume + best_ask_volume)

                # =========================
                # PARAMETERS
                # =========================

                LIMIT = 200
                BASE_FAIR = 9991

                ALPHA = 0.04
                ANCHOR_WEIGHT = 0.02

                BASE_EDGE = 5
                ORDER_SIZE = 18

                # Flow signal
                FLOW_DECAY = 0.88
                MARK14_IMPACT_PER_UNIT = 0.45
                MARK55_IMPACT_PER_UNIT = 0.20
                MAX_FLOW_SIGNAL = 8.0

                # Inventory
                LINEAR_INVENTORY_SKEW = 0.015
                NONLINEAR_INVENTORY_SKEW = 0.00055

                # =========================
                # FAIR VALUE EMA
                # =========================

                if "hydrogel_fair" not in data:
                    data["hydrogel_fair"] = BASE_FAIR
                else:
                    data["hydrogel_fair"] = (
                        ALPHA * microprice
                        + (1 - ALPHA) * data["hydrogel_fair"]
                    )

                fair = data["hydrogel_fair"]
                fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
                data["hydrogel_fair"] = fair

                # =========================
                # FLOW SIGNAL
                # =========================

                if "hydrogel_flow_signal" not in data:
                    data["hydrogel_flow_signal"] = 0.0

                data["hydrogel_flow_signal"] *= FLOW_DECAY

                flow_change_this_tick = 0.0

                if product in state.market_trades:
                    for trade in state.market_trades[product]:

                        qty = abs(trade.quantity)

                        if trade.buyer == "Mark 14":
                            impact = MARK14_IMPACT_PER_UNIT * qty
                            data["hydrogel_flow_signal"] += impact
                            flow_change_this_tick += impact

                        if trade.seller == "Mark 14":
                            impact = -MARK14_IMPACT_PER_UNIT * qty
                            data["hydrogel_flow_signal"] += impact
                            flow_change_this_tick += impact

                        if trade.buyer == "Mark 55":
                            impact = -MARK55_IMPACT_PER_UNIT * qty
                            data["hydrogel_flow_signal"] += impact
                            flow_change_this_tick += impact

                        if trade.seller == "Mark 55":
                            impact = MARK55_IMPACT_PER_UNIT * qty
                            data["hydrogel_flow_signal"] += impact
                            flow_change_this_tick += impact

                data["hydrogel_flow_signal"] = max(
                    -MAX_FLOW_SIGNAL,
                    min(MAX_FLOW_SIGNAL, data["hydrogel_flow_signal"])
                )

                flow_signal = data["hydrogel_flow_signal"]

                # =========================
                # POSITION / INVENTORY
                # =========================

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                inventory_penalty = (
                    LINEAR_INVENTORY_SKEW * position
                    + NONLINEAR_INVENTORY_SKEW * position * abs(position)
                )

                adjusted_fair = fair + flow_signal - inventory_penalty

                # =========================
                # DYNAMIC EDGE
                # =========================

                edge = BASE_EDGE

                # Wider when inventory is dangerous
                if abs(position) > 100:
                    edge += 1

                if abs(position) > 150:
                    edge += 1

                # Wider during sudden toxic-flow bursts
                if abs(flow_change_this_tick) > 4:
                    edge += 1

                # Don't quote too tight when spread is wide
                edge = max(edge, int(round(spread / 2)))

                # =========================
                # BASE QUOTES
                # =========================

                bid_price = int(round(adjusted_fair - edge))
                ask_price = int(round(adjusted_fair + edge))

                # =========================
                # FLOW LEAN
                # =========================

                if flow_signal > 1:
                    bid_price += 2
                    ask_price += 2

                elif flow_signal < -1:
                    bid_price -= 2
                    ask_price -= 2

                # =========================
                # INVENTORY-BASED LIQUIDATION NUDGE
                # =========================

                # If too long, make selling easier
                if position > 100:
                    ask_price -= 1

                if position > 150:
                    ask_price -= 1

                # If too short, make buying easier
                if position < -100:
                    bid_price += 1

                if position < -150:
                    bid_price += 1

                # =========================
                # PASSIVE / NEAR TOUCH CONTROL
                # =========================

                # Less aggressive than best_bid + 1 / best_ask - 1.
                # This captures spread more safely.
                bid_price = min(bid_price, best_bid + 1)
                ask_price = max(ask_price, best_ask - 1)

                if bid_price >= ask_price:
                    bid_price = best_bid
                    ask_price = best_ask

                # =========================
                # SIZE LOGIC
                # =========================

                buy_qty = ORDER_SIZE
                sell_qty = ORDER_SIZE

                if flow_signal > 1:
                    buy_qty = 22
                    sell_qty = 10

                elif flow_signal < -1:
                    buy_qty = 10
                    sell_qty = 22

                if flow_signal > 5:
                    buy_qty = 26
                    sell_qty = 8

                elif flow_signal < -5:
                    buy_qty = 8
                    sell_qty = 26

                # Inventory control
                if position > 100:
                    buy_qty = min(buy_qty, 8)
                    sell_qty = max(sell_qty, 24)

                if position < -100:
                    buy_qty = max(buy_qty, 24)
                    sell_qty = min(sell_qty, 8)

                if position > 170:
                    buy_qty = 0
                    sell_qty = 30

                if position < -170:
                    buy_qty = 30
                    sell_qty = 0

                # =========================
                # SEND ORDERS
                # =========================

                if buy_room > 0 and buy_qty > 0:
                    orders.append(
                        Order(product, bid_price, min(buy_qty, buy_room))
                    )

                if sell_room > 0 and sell_qty > 0:
                    orders.append(
                        Order(product, ask_price, -min(sell_qty, sell_room))
                    )

        result[product] = orders

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData
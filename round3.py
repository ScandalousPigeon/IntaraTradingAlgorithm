from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}

        if state.traderData:
            data = json.loads(state.traderData)
        else:
            data = {"iteration" : 0,
                    "hist_mid_price" : 0}

        product = "HYDROGEL_PACK"
        
        # each OrderDepth contains two dicts: buy_orders and sell_orders, mapping price to quantity
        if product in state.order_depths:
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            result[product] = self.trade_hydrogel(product, order_depth, position, data)
        else:
            result[product] = []

        product = "VELVETFRUIT_EXTRACT"
        if product in state.order_depths:
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            result[product] = self.trade_velvetfruit(product, order_depth, position, data)
        else:
            result[product] = []

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData

    def trade_hydrogel(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        # Parameters
        LIMIT = 200
        BASE_FAIR = 10000

        ALPHA = 0.01
        ANCHOR_WEIGHT = 0.02

        EDGE = 10
        ORDER_SIZE = 12
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

        # Weak pull to long-run centre
        fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
        data["hydrogel_fair"] = fair

        # Position limits
        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # Inventory skew
        adjusted_fair = fair - INVENTORY_SKEW * position

        # Passive market-making quotes
        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        # Avoid crossing too much
        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        if buy_room > 0:
            buy_qty = min(ORDER_SIZE, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(ORDER_SIZE, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        return orders

    def trade_velvetfruit(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        # Parameters
        LIMIT = 200

        BASE_FAIR = 5250
        ALPHA = 0.003
        EDGE = 6
        ORDER_SIZE = 12
        INVENTORY_SKEW = 0.04

        # Fair value model
        if "velvet_fair" not in data:
            data["velvet_fair"] = BASE_FAIR
        else:
            data["velvet_fair"] = (
                ALPHA * mid
                + (1 - ALPHA) * data["velvet_fair"]
            )

        fair = data["velvet_fair"]

        # Pull fair slightly back toward long-run centre
        fair = 0.9 * fair + 0.1 * BASE_FAIR
        data["velvet_fair"] = fair

        # Position limits
        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # Inventory skew
        adjusted_fair = fair - INVENTORY_SKEW * position

        # Passive market-making
        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        # Do not cross the spread
        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        if buy_room > 0:
            buy_qty = min(ORDER_SIZE, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(ORDER_SIZE, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        # Aggressive mean reversion
        AGGRESSIVE_EDGE = 18

        if best_ask < adjusted_fair - AGGRESSIVE_EDGE and buy_room > 0:
            available = -order_depth.sell_orders[best_ask]
            qty = min(available, buy_room, 25)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        if best_bid > adjusted_fair + AGGRESSIVE_EDGE and sell_room > 0:
            available = order_depth.buy_orders[best_bid]
            qty = min(available, sell_room, 25)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        return orders
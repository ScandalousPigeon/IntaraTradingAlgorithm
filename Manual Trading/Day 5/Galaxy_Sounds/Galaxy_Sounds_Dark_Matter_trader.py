from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        product = "GALAXY_SOUNDS_DARK_MATTER"

        if product in state.order_depths:
            result[product] = self.trade_dark_matter(
                product=product,
                order_depth=state.order_depths[product],
                position=state.position.get(product, 0),
                data=data
            )

        return result, 0, json.dumps(data)

    def trade_dark_matter(
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

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        # =====================
        # PARAMETERS
        # =====================

        LIMIT = 10

        FAIR_ALPHA = 0.01       # slow mean estimate
        EDGE = 200              # passive quoting edge
        TAKE_EDGE = 300         # active taking threshold
        ORDER_SIZE = 2
        TAKE_SIZE = 3

        INVENTORY_SKEW = 2.0

        # =====================
        # FAIR VALUE / MEAN
        # =====================

        fair_key = product + "_fair"

        if fair_key not in data:
            data[fair_key] = mid

        fair = FAIR_ALPHA * mid + (1 - FAIR_ALPHA) * data[fair_key]
        data[fair_key] = fair

        adjusted_fair = fair - INVENTORY_SKEW * position

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # =====================
        # ACTIVE MEAN REVERSION
        # =====================

        # If market is too cheap versus fair, buy
        if best_ask < adjusted_fair - TAKE_EDGE and buy_room > 0:
            qty = min(TAKE_SIZE, best_ask_volume, buy_room)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_room -= qty

        # If market is too expensive versus fair, sell
        if best_bid > adjusted_fair + TAKE_EDGE and sell_room > 0:
            qty = min(TAKE_SIZE, best_bid_volume, sell_room)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_room -= qty

        # =====================
        # PASSIVE MEAN REVERSION QUOTES
        # =====================

        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        if bid_price >= ask_price:
            bid_price = best_bid
            ask_price = best_ask

        if buy_room > 0:
            orders.append(
                Order(product, bid_price, min(ORDER_SIZE, buy_room))
            )

        if sell_room > 0:
            orders.append(
                Order(product, ask_price, -min(ORDER_SIZE, sell_room))
            )

        return orders
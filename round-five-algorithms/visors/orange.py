from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_uv_visor_orange(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_orange(self, state: TradingState, result: dict, data: dict) -> None:
        product = "UV_VISOR_ORANGE"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = abs(order_depth.buy_orders[best_bid])
        best_ask_volume = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        LIMIT = 10

        # Tuned for UV_VISOR_ORANGE
        ALPHA = 0.30
        EDGE = 7
        INVENTORY_SKEW = 2.0
        ORDER_SIZE = 2

        # Very rare aggressive trading only when book is far from fair
        TAKE_EDGE = 60
        TAKE_SIZE = 2

        key = "uv_orange"

        # Reset safely at the start of a new run/day
        if key not in data or state.timestamp == 0:
            data[key] = {
                "fair": mid,
                "last_mid": mid,
                "last_timestamp": state.timestamp,
            }

        fair = data[key]["fair"]

        # Fast EMA fair value: follows the large orange trends better than fixed fair
        fair = fair + ALPHA * (mid - fair)

        # Inventory skew:
        # If long, lower our fair so we become more likely to sell.
        # If short, raise our fair so we become more likely to buy.
        skewed_fair = fair - INVENTORY_SKEW * position

        # =========================
        # Aggressive taking
        # =========================
        # Only take when price is extremely far from fair.
        # This avoids constantly crossing the spread.
        if best_ask <= skewed_fair - TAKE_EDGE and position < LIMIT:
            buy_qty = min(TAKE_SIZE, LIMIT - position, best_ask_volume)
            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))
                position += buy_qty

        if best_bid >= skewed_fair + TAKE_EDGE and position > -LIMIT:
            sell_qty = min(TAKE_SIZE, LIMIT + position, best_bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
                position -= sell_qty

        # =========================
        # Passive market making
        # =========================
        # Orange has a normal spread around 13-14, so quoting passively is better
        # than constantly taking liquidity.
        if spread <= 20:
            if position < LIMIT:
                raw_buy_price = math.floor(skewed_fair - EDGE)

                # Do not cross. Usually join best bid; go lower if fair is weak.
                buy_price = min(best_bid, raw_buy_price)

                buy_qty = min(ORDER_SIZE, LIMIT - position)

                if buy_qty > 0:
                    orders.append(Order(product, buy_price, buy_qty))

            if position > -LIMIT:
                raw_sell_price = math.ceil(skewed_fair + EDGE)

                # Do not cross. Usually join best ask; go higher if fair is weak.
                sell_price = max(best_ask, raw_sell_price)

                sell_qty = min(ORDER_SIZE, LIMIT + position)

                if sell_qty > 0:
                    orders.append(Order(product, sell_price, -sell_qty))

        data[key]["fair"] = fair
        data[key]["last_mid"] = mid
        data[key]["last_timestamp"] = state.timestamp

        result[product] = orders
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

        self.trade_sleep_pod_nylon(state, result, data)

        return result, 0, json.dumps(data)

    def trade_sleep_pod_nylon(self, state: TradingState, result: dict, data: dict) -> None:
        product = "SLEEP_POD_NYLON"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        position = state.position.get(product, 0)

        key = "sleep_pod_nylon"

        if key not in data:
            data[key] = {
                "fair": mid,
                "fast": mid,
                "slow": mid,
            }

        mem = data[key]

        # Nylon moves directionally, so use adaptive fair value, not fixed fair.
        mem["fair"] = 0.88 * mem["fair"] + 0.12 * mid
        mem["fast"] = 0.80 * mem["fast"] + 0.20 * mid
        mem["slow"] = 0.98 * mem["slow"] + 0.02 * mid

        trend = mem["fast"] - mem["slow"]

        total_volume = best_bid_volume + best_ask_volume

        if total_volume > 0:
            microprice = (
                best_ask * best_bid_volume
                + best_bid * best_ask_volume
            ) / total_volume

            imbalance = (
                best_bid_volume - best_ask_volume
            ) / total_volume
        else:
            microprice = mid
            imbalance = 0

        fair = mem["fair"]

        # Small fair adjustments.
        fair += 0.35 * (microprice - mid)
        fair += 0.08 * trend
        fair += 1.50 * imbalance

        # Inventory skew.
        # If long, lower fair to encourage selling.
        # If short, raise fair to encourage buying.
        fair -= 0.55 * position

        buy_used = 0
        sell_used = 0

        def virtual_position() -> int:
            return position + buy_used - sell_used

        def buy(price: int, quantity: int) -> None:
            nonlocal buy_used

            quantity = int(min(quantity, LIMIT - position - buy_used))

            if quantity > 0:
                orders.append(Order(product, price, quantity))
                buy_used += quantity

        def sell(price: int, quantity: int) -> None:
            nonlocal sell_used

            quantity = int(min(quantity, LIMIT + position - sell_used))

            if quantity > 0:
                orders.append(Order(product, price, -quantity))
                sell_used += quantity

        # Rare aggressive trades only when book is clearly mispriced.
        TAKE_EDGE = 4
        TAKE_SIZE = 2

        if best_ask <= fair - TAKE_EDGE:
            buy(best_ask, min(TAKE_SIZE, best_ask_volume))

        if best_bid >= fair + TAKE_EDGE:
            sell(best_bid, min(TAKE_SIZE, best_bid_volume))

        # Inventory cleanup when near limits.
        if virtual_position() >= 7 and best_bid >= fair - 2:
            sell(best_bid, min(3, best_bid_volume, virtual_position()))

        if virtual_position() <= -7 and best_ask <= fair + 2:
            buy(best_ask, min(3, best_ask_volume, -virtual_position()))

        # Main strategy: passive spread capture.
        # Nylon usually has a wide spread, so improve one tick inside if safe.
        if spread >= 6:
            PASSIVE_EDGE = 3
            PASSIVE_SIZE = 3

            raw_bid = math.floor(fair - PASSIVE_EDGE)
            raw_ask = math.ceil(fair + PASSIVE_EDGE)

            bid_price = min(best_bid + 1, raw_bid)
            ask_price = max(best_ask - 1, raw_ask)

            # Safety: never cross.
            bid_price = min(bid_price, best_ask - 1)
            ask_price = max(ask_price, best_bid + 1)

            if virtual_position() < 8:
                buy(bid_price, PASSIVE_SIZE)

            if virtual_position() > -8:
                sell(ask_price, PASSIVE_SIZE)

        result[product] = orders
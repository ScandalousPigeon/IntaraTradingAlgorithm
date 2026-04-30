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

        self.trade_uv_visor_yellow(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_yellow(self, state: TradingState, result: dict, data: dict) -> None:
        product = "UV_VISOR_YELLOW"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        # Position limit should be 10 for this round.
        LIMIT = 10

        # Yellow is volatile and trends by day, so avoid a fixed 10000 fair.
        FAST_ALPHA = 0.12
        SLOW_ALPHA = 0.018
        VOL_ALPHA = 0.08

        TREND_WEIGHT = 1.15
        MICRO_MOMENTUM_WEIGHT = 0.15
        INVENTORY_SKEW = 0.75

        TAKE_SIZE = 3
        PASSIVE_SIZE = 2

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = abs(order_depth.sell_orders[best_ask])

        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        if product not in data:
            data[product] = {}

        memory = data[product]

        if "fast" not in memory:
            memory["fast"] = mid
            memory["slow"] = mid
            memory["last_mid"] = mid
            memory["absret"] = 8.0

        last_mid = memory["last_mid"]
        price_change = mid - last_mid

        fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * memory["fast"]
        slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * memory["slow"]
        absret = VOL_ALPHA * abs(price_change) + (1 - VOL_ALPHA) * memory["absret"]

        memory["fast"] = fast
        memory["slow"] = slow
        memory["last_mid"] = mid
        memory["absret"] = absret

        trend = fast - slow

        fair = (
            slow
            + TREND_WEIGHT * trend
            + MICRO_MOMENTUM_WEIGHT * price_change
            - INVENTORY_SKEW * position
        )

        # Dynamic edges: wider when yellow is jumping around.
        take_edge = max(7.0, 0.70 * absret)
        passive_edge = max(2.0, min(5.0, 0.25 * absret))

        orders: List[Order] = result[product]

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # =========================
        # 1. Aggressive taking
        # =========================
        # Only cross the spread when the top of book is clearly wrong.
        if buy_room > 0 and best_ask <= fair - take_edge:
            quantity = min(TAKE_SIZE, best_ask_volume, buy_room)
            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))
                position += quantity
                buy_room -= quantity
                sell_room += quantity

        if sell_room > 0 and best_bid >= fair + take_edge:
            quantity = min(TAKE_SIZE, best_bid_volume, sell_room)
            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))
                position -= quantity
                sell_room -= quantity
                buy_room += quantity

        # =========================
        # 2. Passive spread capture
        # =========================
        # The usual yellow spread is wide, so quote inside the spread when safe.
        # Inventory skew already pushes fair lower when long and higher when short.
        if spread >= 4:
            if buy_room > 0:
                buy_quantity = min(PASSIVE_SIZE, buy_room)

                # Do not bid above our fair-value edge.
                fair_bid_ceiling = math.floor(fair - passive_edge)
                passive_bid = min(best_bid + 1, best_ask - 1, fair_bid_ceiling)

                if buy_quantity > 0 and passive_bid > 0 and passive_bid < best_ask:
                    orders.append(Order(product, passive_bid, buy_quantity))

            if sell_room > 0:
                sell_quantity = min(PASSIVE_SIZE, sell_room)

                # Do not ask below our fair-value edge.
                fair_ask_floor = math.ceil(fair + passive_edge)
                passive_ask = max(best_ask - 1, best_bid + 1, fair_ask_floor)

                if sell_quantity > 0 and passive_ask > best_bid:
                    orders.append(Order(product, passive_ask, -sell_quantity))
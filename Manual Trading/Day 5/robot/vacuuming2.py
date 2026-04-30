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

        product = "ROBOT_VACUUMING"

        if product in state.order_depths:
            result[product] = self.trade_robot_vacuuming(
                product=product,
                order_depth=state.order_depths[product],
                position=state.position.get(product, 0),
                data=data
            )

        return result, 0, json.dumps(data)

    def trade_robot_vacuuming(
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

        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        # =====================
        # PARAMETERS
        # =====================

        LIMIT = 12
        SIZE = 2

        FAIR_ALPHA = 0.0015
        VAR_ALPHA = 0.005

        ENTRY_Z = 2.0
        EXIT_Z = 0.4
        STOP_Z = 3.5

        # =====================
        # FAIR + VOL
        # =====================

        fair_key = product + "_fair"
        var_key = product + "_var"
        mode_key = product + "_mode"

        if fair_key not in data:
            data[fair_key] = mid

        fair = FAIR_ALPHA * mid + (1 - FAIR_ALPHA) * data[fair_key]
        data[fair_key] = fair

        deviation = mid - fair

        if var_key not in data:
            data[var_key] = 5000.0

        var = VAR_ALPHA * (deviation ** 2) + (1 - VAR_ALPHA) * data[var_key]
        data[var_key] = var

        std = math.sqrt(max(var, 1.0))
        z = deviation / std

        # =====================
        # MODE
        # =====================

        if mode_key not in data:
            data[mode_key] = 0

        mode = data[mode_key]

        if mode == 0:
            if z < -ENTRY_Z:
                mode = 1
            elif z > ENTRY_Z:
                mode = -1

        elif mode == 1:
            if z > -EXIT_Z:
                mode = 0
            elif z < -STOP_Z:
                mode = 0

        elif mode == -1:
            if z < EXIT_Z:
                mode = 0
            elif z > STOP_Z:
                mode = 0

        data[mode_key] = mode

        # =====================
        # TARGET POSITION
        # =====================

        if mode == 1:
            target = LIMIT
        elif mode == -1:
            target = -LIMIT
        else:
            target = 0

        diff = target - position

        # =====================
        # EXECUTION
        # =====================

        if diff > 0:
            qty = min(diff, SIZE, ask_volume)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        elif diff < 0:
            qty = min(-diff, SIZE, bid_volume)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        return orders
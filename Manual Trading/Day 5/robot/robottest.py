from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        products = [
            "ROBOT_DISHES",
            "ROBOT_IRONING",
        ]

        for product in products:
            if product in state.order_depths:
                result[product] = self.trade_jump_reversal(
                    product=product,
                    order_depth=state.order_depths[product],
                    position=state.position.get(product, 0),
                    data=data,
                )

        return result, 0, json.dumps(data)

    def trade_jump_reversal(
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

        if product == "ROBOT_DISHES":
            LIMIT = 10
            SIZE = 2
            ENTRY_JUMP = 40
            MAX_HOLD = 20

        elif product == "ROBOT_IRONING":
            LIMIT = 6
            SIZE = 1
            ENTRY_JUMP = 60
            MAX_HOLD = 20

        else:
            return orders

        # =====================
        # DATA KEYS
        # =====================

        last_mid_key = product + "_last_mid"
        mode_key = product + "_mode"
        hold_key = product + "_hold"

        if last_mid_key not in data:
            data[last_mid_key] = mid
            data[mode_key] = 0
            data[hold_key] = 0
            return orders

        last_mid = data[last_mid_key]
        move = mid - last_mid

        data[last_mid_key] = mid

        mode = data.get(mode_key, 0)
        hold = data.get(hold_key, 0)

        # =====================
        # SIGNAL
        # mode  1 = long
        # mode -1 = short
        # =====================

        if mode == 0:

            if move >= ENTRY_JUMP:
                mode = -1
                hold = 0

            elif move <= -ENTRY_JUMP:
                mode = 1
                hold = 0

        else:
            hold += 1

            # exit after holding long enough
            if hold >= MAX_HOLD:
                mode = 0
                hold = 0

            # also exit early if the reversal already happens strongly
            elif mode == 1 and move > 10:
                mode = 0
                hold = 0

            elif mode == -1 and move < -10:
                mode = 0
                hold = 0

        data[mode_key] = mode
        data[hold_key] = hold

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
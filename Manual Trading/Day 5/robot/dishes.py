from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        product = "ROBOT_DISHES"

        if product in state.order_depths:

            result[product] = self.trade_robot_dishes(
                order_depth=state.order_depths[product],
                position=state.position.get(product, 0),
                data=data
            )

        return result, 0, json.dumps(data)

    def trade_robot_dishes(
        self,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        # =====================================
        # BEST PRICES
        # =====================================

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        # =====================================
        # PARAMETERS
        # =====================================

        LIMIT = 10

        SIZE = 10

        ENTRY_JUMP = 30

        EXIT_MOVE = 5

        # =====================================
        # LAST MID
        # =====================================

        if "last_mid" not in data:
            data["last_mid"] = mid
            return orders

        last_mid = data["last_mid"]

        move = mid - last_mid

        data["last_mid"] = mid

        # =====================================
        # MODE
        # =====================================

        if "mode" not in data:
            data["mode"] = 0

        mode = data["mode"]

        # =====================================
        # ENTRY SHORT
        # =====================================

        if mode == 0:

            if move >= ENTRY_JUMP:

                mode = -1

            elif move <= -ENTRY_JUMP:

                mode = 1

        # =====================================
        # EXIT LONG
        # =====================================

        elif mode == 1:

            # got rebound

            if move >= EXIT_MOVE:

                mode = 0

        # =====================================
        # EXIT SHORT
        # =====================================

        elif mode == -1:

            # got pullback

            if move <= -EXIT_MOVE:

                mode = 0

        data["mode"] = mode

        # =====================================
        # TARGET POSITION
        # =====================================

        if mode == 1:

            target = LIMIT

        elif mode == -1:

            target = -LIMIT

        else:

            target = 0

        diff = target - position

        # =====================================
        # EXECUTION
        # =====================================

        if diff > 0:

            qty = min(
                diff,
                SIZE,
                ask_volume
            )

            if qty > 0:

                orders.append(
                    Order(
                        "ROBOT_DISHES",
                        best_ask,
                        qty
                    )
                )

        elif diff < 0:

            qty = min(
                -diff,
                SIZE,
                bid_volume
            )

            if qty > 0:

                orders.append(
                    Order(
                        "ROBOT_DISHES",
                        best_bid,
                        -qty
                    )
                )

        return orders
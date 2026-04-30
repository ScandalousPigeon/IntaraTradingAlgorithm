from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        pebbles = [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL",
        ]

        has_all = True

        for p in pebbles:
            if p not in state.order_depths:
                has_all = False

        if has_all:

            pebble_orders = self.trade_pebbles(
                state=state
            )

            for product in pebble_orders:
                result[product] = pebble_orders[product]

        return result, 0, json.dumps(data)

    def trade_pebbles(
        self,
        state: TradingState,
    ):

        orders = {}

        products = [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL",
        ]

        mids = {}

        best_bids = {}
        best_asks = {}

        buy_volumes = {}
        sell_volumes = {}

        # =====================================
        # BUILD BOOK DATA
        # =====================================

        for product in products:

            orders[product] = []

            depth = state.order_depths[product]

            if not depth.buy_orders or not depth.sell_orders:
                return orders

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())

            best_bids[product] = best_bid
            best_asks[product] = best_ask

            mids[product] = (
                best_bid + best_ask
            ) / 2

            buy_volumes[product] = depth.buy_orders[best_bid]

            sell_volumes[product] = -depth.sell_orders[best_ask]

        # =====================================
        # PARAMETERS
        # =====================================

        LIMIT = 50

        ENTRY = 12
        EXIT = 1

        SIZE = 3

        MAX_ERROR = 80

        # =====================================
        # CHECK EACH PRODUCT
        # =====================================

        for target in products:

            others = []

            for p in products:
                if p != target:
                    others.append(p)

            fair = (
                50000
                - mids[others[0]]
                - mids[others[1]]
                - mids[others[2]]
                - mids[others[3]]
            )

            error = mids[target] - fair

            if abs(error) > MAX_ERROR:
                continue

            position = state.position.get(target, 0)

            # =====================================
            # OVERPRICED -> SELL
            # =====================================

            if error > ENTRY:

                if position > -LIMIT:

                    qty = min(
                        SIZE,
                        LIMIT + position,
                        buy_volumes[target]
                    )

                    if qty > 0:

                        orders[target].append(
                            Order(
                                target,
                                best_bids[target],
                                -qty
                            )
                        )

            # =====================================
            # UNDERPRICED -> BUY
            # =====================================

            elif error < -ENTRY:

                if position < LIMIT:

                    qty = min(
                        SIZE,
                        LIMIT - position,
                        sell_volumes[target]
                    )

                    if qty > 0:

                        orders[target].append(
                            Order(
                                target,
                                best_asks[target],
                                qty
                            )
                        )

            # =====================================
            # EXIT SHORT
            # =====================================

            elif position < 0 and error < EXIT:

                qty = min(
                    SIZE,
                    -position,
                    sell_volumes[target]
                )

                if qty > 0:

                    orders[target].append(
                        Order(
                            target,
                            best_asks[target],
                            qty
                        )
                    )

            # =====================================
            # EXIT LONG
            # =====================================

            elif position > 0 and error > -EXIT:

                qty = min(
                    SIZE,
                    position,
                    buy_volumes[target]
                )

                if qty > 0:

                    orders[target].append(
                        Order(
                            target,
                            best_bids[target],
                            -qty
                        )
                    )

        return orders
    
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        required = [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL",
        ]

        ok = True

        for p in required:
            if p not in state.order_depths:
                ok = False

        if ok:

            result["PEBBLES_XL"] = self.trade_pebbles(
                state,
                state.position.get("PEBBLES_XL", 0)
            )

        return result, 0, json.dumps(data)

    def trade_pebbles(
        self,
        state,
        position
    ):

        orders = []

        xl = state.order_depths["PEBBLES_XL"]
        xs = state.order_depths["PEBBLES_XS"]
        s = state.order_depths["PEBBLES_S"]
        m = state.order_depths["PEBBLES_M"]
        l = state.order_depths["PEBBLES_L"]

        books = [xl, xs, s, m, l]

        for book in books:
            if not book.buy_orders or not book.sell_orders:
                return orders

        # =====================================
        # BEST PRICES
        # =====================================

        xl_bid = max(xl.buy_orders.keys())
        xl_ask = min(xl.sell_orders.keys())

        xs_mid = (
            max(xs.buy_orders.keys())
            + min(xs.sell_orders.keys())
        ) / 2

        s_mid = (
            max(s.buy_orders.keys())
            + min(s.sell_orders.keys())
        ) / 2

        m_mid = (
            max(m.buy_orders.keys())
            + min(m.sell_orders.keys())
        ) / 2

        l_mid = (
            max(l.buy_orders.keys())
            + min(l.sell_orders.keys())
        ) / 2

        xl_mid = (xl_bid + xl_ask) / 2

        # =====================================
        # FAIR
        # =====================================

        fair = (
            50000
            - xs_mid
            - s_mid
            - m_mid
            - l_mid
        )

        error = xl_mid - fair

        # =====================================
        # PARAMETERS
        # =====================================

        LIMIT = 50

        ENTRY = 30
        EXIT = 10

        SIZE = 5

        # =====================================
        # SHORT SIGNAL
        # =====================================

        if error > ENTRY:

            if position > -LIMIT:

                qty = min(
                    SIZE,
                    LIMIT + position,
                    xl.buy_orders[xl_bid]
                )

                if qty > 0:

                    orders.append(
                        Order(
                            "PEBBLES_XL",
                            xl_bid,
                            -qty
                        )
                    )

        # =====================================
        # LONG SIGNAL
        # =====================================

        elif error < -ENTRY:

            ask_volume = -xl.sell_orders[xl_ask]

            if position < LIMIT:

                qty = min(
                    SIZE,
                    LIMIT - position,
                    ask_volume
                )

                if qty > 0:

                    orders.append(
                        Order(
                            "PEBBLES_XL",
                            xl_ask,
                            qty
                        )
                    )

        # =====================================
        # EXIT SHORT
        # =====================================

        elif position < 0 and error < EXIT:

            ask_volume = -xl.sell_orders[xl_ask]

            qty = min(
                SIZE,
                -position,
                ask_volume
            )

            if qty > 0:

                orders.append(
                    Order(
                        "PEBBLES_XL",
                        xl_ask,
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
                xl.buy_orders[xl_bid]
            )

            if qty > 0:

                orders.append(
                    Order(
                        "PEBBLES_XL",
                        xl_bid,
                        -qty
                    )
                )

        return orders
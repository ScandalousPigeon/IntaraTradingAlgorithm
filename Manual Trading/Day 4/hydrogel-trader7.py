from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.update_hydrogel_counterparty_signal(state, data)

        hydrogel = "HYDROGEL_PACK"

        if hydrogel in state.order_depths:
            result[hydrogel] = self.trade_hydrogel(
                product=hydrogel,
                order_depth=state.order_depths[hydrogel],
                position=state.position.get(hydrogel, 0),
                data=data
            )

        return result, 0, json.dumps(data)

    # ============================================================
    # COUNTERPARTY SIGNAL
    # ============================================================

    def update_hydrogel_counterparty_signal(self, state: TradingState, data: dict) -> None:

        product = "HYDROGEL_PACK"

        DECAY = 0.6

        if "hydrogel_flow" not in data:
            data["hydrogel_flow"] = 0.0

        data["hydrogel_flow"] *= DECAY

        for trade in state.market_trades.get(product, []):
            qty = abs(trade.quantity)

            # Bullish signals
            if trade.buyer == "Mark 14":
                data["hydrogel_flow"] += qty

            if trade.seller == "Mark 38":
                data["hydrogel_flow"] += qty

            # Bearish symmetric signals
            if trade.seller == "Mark 14":
                data["hydrogel_flow"] -= qty

            if trade.buyer == "Mark 38":
                data["hydrogel_flow"] -= qty

        data["hydrogel_flow"] = max(
            -50,
            min(50, data["hydrogel_flow"])
        )

    # ============================================================
    # HYDROGEL
    # ============================================================

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

        LIMIT = 200
        BASE_FAIR = 9991

        ALPHA = 0.03
        ANCHOR_WEIGHT = 0.02

        EDGE = 5
        ORDER_SIZE = 16
        INVENTORY_SKEW = 0.05

        COUNTERPARTY_FAIR_WEIGHT = 0.25
        SIGNAL_TAKE_THRESHOLD = 10
        SIGNAL_TAKE_SIZE = 5
        SIGNAL_TAKE_EDGE = 1

        # =========================
        # FAIR VALUE
        # =========================

        if "hydrogel_fair" not in data:
            data["hydrogel_fair"] = BASE_FAIR
        else:
            data["hydrogel_fair"] = (
                ALPHA * mid
                + (1 - ALPHA) * data["hydrogel_fair"]
            )

        fair = data["hydrogel_fair"]

        fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
        data["hydrogel_fair"] = fair

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        hydrogel_flow = data.get("hydrogel_flow", 0.0)

        counterparty_bias = COUNTERPARTY_FAIR_WEIGHT * hydrogel_flow

        adjusted_fair = (
            fair
            - INVENTORY_SKEW * position
            + counterparty_bias
        )

        # =========================
        # SIGNAL-BASED ACTIVE TRADING
        # =========================

        if (
            hydrogel_flow >= SIGNAL_TAKE_THRESHOLD
            and buy_room > 0
            and position < 80
        ):
            best_ask_volume = -order_depth.sell_orders[best_ask]

            if best_ask <= adjusted_fair + SIGNAL_TAKE_EDGE:
                buy_qty = min(
                    SIGNAL_TAKE_SIZE,
                    best_ask_volume,
                    buy_room
                )

                if buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))
                    buy_room -= buy_qty

        if (
            hydrogel_flow <= -SIGNAL_TAKE_THRESHOLD
            and sell_room > 0
            and position > -80
        ):
            best_bid_volume = order_depth.buy_orders[best_bid]

            if best_bid >= adjusted_fair - SIGNAL_TAKE_EDGE:
                sell_qty = min(
                    SIGNAL_TAKE_SIZE,
                    best_bid_volume,
                    sell_room
                )

                if sell_qty > 0:
                    orders.append(Order(product, best_bid, -sell_qty))
                    sell_room -= sell_qty

        # =========================
        # PASSIVE MARKET MAKING
        # =========================

        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

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
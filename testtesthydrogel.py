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
            order_depth = state.order_depths[hydrogel]
            position = state.position.get(hydrogel, 0)

            result[hydrogel] = self.trade_hydrogel(
                product=hydrogel,
                order_depth=order_depth,
                position=position,
                data=data
            )

        return result, 0, json.dumps(data)

    # ============================================================
    # COUNTERPARTY SIGNAL
    # ============================================================

    def update_hydrogel_counterparty_signal(
        self,
        state: TradingState,
        data: dict
    ) -> None:

        product = "HYDROGEL_PACK"

        DECAY = 0.85

        if "hydrogel_flow" not in data:
            data["hydrogel_flow"] = 0

        data["hydrogel_flow"] *= DECAY

        for trade in state.market_trades.get(product, []):
            qty = trade.quantity

            # Bullish signals you observed
            if trade.buyer == "Mark 14":
                data["hydrogel_flow"] += qty

            if trade.seller == "Mark 38":
                data["hydrogel_flow"] += qty

            # Optional opposite-side logic:
            # If the opposite of the bullish signal happens, treat it as bearish.
            if trade.seller == "Mark 14":
                data["hydrogel_flow"] -= qty

            if trade.buyer == "Mark 38":
                data["hydrogel_flow"] -= qty

        # Allow both bullish and bearish flow now
        data["hydrogel_flow"] = max(-50, min(50, data["hydrogel_flow"]))

    # ============================================================
    # HYDROGEL_PACK
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

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        # Parameters
        LIMIT = 200
        BASE_FAIR = 9991

        ALPHA = 0.03
        ANCHOR_WEIGHT = 0.02

        EDGE = 5
        ORDER_SIZE = 16

        # Increased from 0.03 to reduce inventory risk
        INVENTORY_SKEW = 0.07

        # Counterparty parameters
        COUNTERPARTY_FAIR_WEIGHT = 0.20

        # Position control
        MAX_SIGNAL_LONG = 70
        MAX_SIGNAL_SHORT = -40

        REDUCE_LONG_THRESHOLD = 80
        REDUCE_SHORT_THRESHOLD = -80

        REDUCE_SIZE = 12

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # -------------------------
        # FAIR VALUE
        # -------------------------

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

        hydrogel_flow = data.get("hydrogel_flow", 0)

        counterparty_bias = COUNTERPARTY_FAIR_WEIGHT * hydrogel_flow

        adjusted_fair = (
            fair
            - INVENTORY_SKEW * position
            + counterparty_bias
        )

        # -------------------------
        # POSITION TARGET
        # -------------------------

        # Positive Mark signal means we want to be somewhat long,
        # but not blindly max long.
        target_position = int(hydrogel_flow * 2)

        target_position = max(
            MAX_SIGNAL_SHORT,
            min(MAX_SIGNAL_LONG, target_position)
        )

        # -------------------------
        # ACTIVE INVENTORY REDUCTION
        # -------------------------

        # If we are too long, sell into the best bid.
        # This directly addresses the "we are buying too much" problem.
        if position > REDUCE_LONG_THRESHOLD and sell_room > 0:
            qty = min(
                REDUCE_SIZE,
                best_bid_volume,
                position - REDUCE_LONG_THRESHOLD,
                sell_room
            )

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_room -= qty

        # If we are too short, buy back from the best ask.
        if position < REDUCE_SHORT_THRESHOLD and buy_room > 0:
            qty = min(
                REDUCE_SIZE,
                best_ask_volume,
                REDUCE_SHORT_THRESHOLD - position,
                buy_room
            )

            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_room -= qty

        # -------------------------
        # SIGNAL-BASED ACTIVE BUY
        # -------------------------

        # Only buy actively if:
        # 1. signal is bullish,
        # 2. we are below target position,
        # 3. ask is not too expensive.
        SIGNAL_TAKE_THRESHOLD = 8
        SIGNAL_TAKE_SIZE = 8
        SIGNAL_TAKE_EDGE = 1

        if (
            hydrogel_flow >= SIGNAL_TAKE_THRESHOLD
            and position < target_position
            and buy_room > 0
        ):
            if best_ask <= adjusted_fair + SIGNAL_TAKE_EDGE:
                qty = min(
                    SIGNAL_TAKE_SIZE,
                    best_ask_volume,
                    target_position - position,
                    buy_room
                )

                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_room -= qty

        # -------------------------
        # PASSIVE MARKET-MAKING QUOTES
        # -------------------------

        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        # Asymmetric sizing:
        # If we are above target, reduce buy size and increase sell size.
        # If we are below target, allow more buying.
        if position > target_position:
            passive_buy_size = max(2, ORDER_SIZE // 3)
            passive_sell_size = ORDER_SIZE + 8
        elif position < target_position:
            passive_buy_size = ORDER_SIZE
            passive_sell_size = max(4, ORDER_SIZE // 2)
        else:
            passive_buy_size = ORDER_SIZE
            passive_sell_size = ORDER_SIZE

        if buy_room > 0:
            buy_qty = min(passive_buy_size, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(passive_sell_size, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        return orders
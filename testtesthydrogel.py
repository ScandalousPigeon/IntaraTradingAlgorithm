from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        # Make sure every visible product has an entry
        for product in state.order_depths:
            result[product] = []

        # Update Hydrogel counterparty signal before trading
        self.update_hydrogel_counterparty_signal(state, data)

        # -------------------------
        # HYDROGEL_PACK ONLY
        # -------------------------

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

        # Decay old signal over time so one old trade does not dominate forever.
        DECAY = 0.85

        if "hydrogel_flow" not in data:
            data["hydrogel_flow"] = 0

        data["hydrogel_flow"] *= DECAY

        # Look at the latest market trades.
        for trade in state.market_trades.get(product, []):
            qty = trade.quantity

            # Your observed signal:
            # When Mark 14 buys, Hydrogel tends to go up.
            if trade.buyer == "Mark 14":
                data["hydrogel_flow"] += qty

            # Your observed signal:
            # When Mark 38 sells, Hydrogel tends to go up.
            if trade.seller == "Mark 38":
                data["hydrogel_flow"] += qty

        # Clamp the signal so it does not become too extreme.
        data["hydrogel_flow"] = max(0, min(50, data["hydrogel_flow"]))

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

        mid = (best_bid + best_ask) / 2

        # Parameters
        LIMIT = 200
        BASE_FAIR = 9991

        ALPHA = 0.03
        ANCHOR_WEIGHT = 0.02

        EDGE = 5
        ORDER_SIZE = 16
        INVENTORY_SKEW = 0.03

        # New counterparty parameters
        COUNTERPARTY_FAIR_WEIGHT = 0.25
        SIGNAL_TAKE_THRESHOLD = 8
        SIGNAL_TAKE_SIZE = 8
        SIGNAL_TAKE_EDGE = 2

        # Fair value
        if "hydrogel_fair" not in data:
            data["hydrogel_fair"] = BASE_FAIR
        else:
            data["hydrogel_fair"] = (
                ALPHA * mid
                + (1 - ALPHA) * data["hydrogel_fair"]
            )

        fair = data["hydrogel_fair"]

        # Weak pull to long-run centre
        fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
        data["hydrogel_fair"] = fair

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # Counterparty signal
        hydrogel_flow = data.get("hydrogel_flow", 0)

        # If Mark 14 buys or Mark 38 sells, this becomes positive.
        # Positive flow raises our estimated fair value.
        counterparty_bias = COUNTERPARTY_FAIR_WEIGHT * hydrogel_flow

        # Inventory skew + counterparty bias
        adjusted_fair = fair - INVENTORY_SKEW * position + counterparty_bias

        # -------------------------
        # SIGNAL-BASED ACTIVE BUY
        # -------------------------

        # If the signal is strong enough, buy the best ask,
        # but only if the ask is still close to our adjusted fair value.
        if hydrogel_flow >= SIGNAL_TAKE_THRESHOLD and buy_room > 0:
            best_ask_volume = -order_depth.sell_orders[best_ask]

            if best_ask <= adjusted_fair + SIGNAL_TAKE_EDGE:
                buy_qty = min(SIGNAL_TAKE_SIZE, best_ask_volume, buy_room)

                if buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))
                    buy_room -= buy_qty

        # -------------------------
        # PASSIVE MARKET-MAKING QUOTES
        # -------------------------

        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        # Avoid crossing too much
        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        if buy_room > 0:
            buy_qty = min(ORDER_SIZE, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(ORDER_SIZE, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        return orders
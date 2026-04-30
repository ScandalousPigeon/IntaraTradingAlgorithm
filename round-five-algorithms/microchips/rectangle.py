from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "MICROCHIP_RECTANGLE"

    LIMIT = 10

    # V2: stricter reversal parameters
    WARMUP = 50

    FAIR_ALPHA = 0.35
    MOM_ALPHA = 0.05

    # Higher = less aggressive
    MOM_DAMPER = 10.0
    ENTRY_SIGNAL = 40.0
    EXIT_SIGNAL = 5.0

    MAX_SPREAD = 12
    MAX_STEP = 6

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except:
            data = {}

        self.trade_microchip_rectangle(state, result, data)

        return result, 0, json.dumps(data)

    def trade_microchip_rectangle(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        fair_key = "rect_v2_fair"
        prev_key = "rect_v2_prev_mid"
        mom_key = "rect_v2_mom"
        tick_key = "rect_v2_ticks"

        if fair_key not in data:
            data[fair_key] = mid
            data[prev_key] = mid
            data[mom_key] = 0.0
            data[tick_key] = 0
            return

        fair = data[fair_key]
        prev_mid = data[prev_key]
        momentum = data[mom_key]
        ticks = data.get(tick_key, 0) + 1

        price_change = mid - prev_mid

        momentum = (1 - self.MOM_ALPHA) * momentum + self.MOM_ALPHA * price_change
        fair = (1 - self.FAIR_ALPHA) * fair + self.FAIR_ALPHA * mid

        data[fair_key] = fair
        data[prev_key] = mid
        data[mom_key] = momentum
        data[tick_key] = ticks

        if ticks < self.WARMUP:
            return

        # Reversal signal:
        # positive = price has dumped too hard, expect bounce, go long
        # negative = price has pumped too hard, expect pullback, go short
        signal = (mid - fair) - self.MOM_DAMPER * momentum

        target = position

        if position > 0:
            if signal < -self.ENTRY_SIGNAL:
                target = -self.LIMIT
            elif signal < self.EXIT_SIGNAL:
                target = 0
            else:
                target = self.LIMIT

        elif position < 0:
            if signal > self.ENTRY_SIGNAL:
                target = self.LIMIT
            elif signal > -self.EXIT_SIGNAL:
                target = 0
            else:
                target = -self.LIMIT

        else:
            if signal > self.ENTRY_SIGNAL:
                target = self.LIMIT
            elif signal < -self.ENTRY_SIGNAL:
                target = -self.LIMIT
            else:
                target = 0

        orders: List[Order] = []

        # Avoid entering on ugly/wide books.
        # Still allow position reduction if already exposed.
        widening_risk = spread > self.MAX_SPREAD
        increasing_position = abs(target) > abs(position)

        if widening_risk and increasing_position:
            result[product] = orders
            return

        if target > position:
            quantity = min(
                target - position,
                self.MAX_STEP,
                best_ask_volume,
                self.LIMIT - position
            )

            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))

        elif target < position:
            quantity = min(
                position - target,
                self.MAX_STEP,
                best_bid_volume,
                self.LIMIT + position
            )

            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))

        result[product] = orders
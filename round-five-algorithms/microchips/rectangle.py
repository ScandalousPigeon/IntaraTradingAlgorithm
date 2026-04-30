from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:

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

    def trade_microchip_rectangle(self, state: TradingState, result: Dict[str, List[Order]], data: dict):
        PRODUCT = "MICROCHIP_RECTANGLE"

        if PRODUCT not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[PRODUCT]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        # Position limit for round 5 products
        LIMIT = 10

        # Tuned from days 2, 3, 4
        EMA_ALPHA = 0.30
        MOM_ALPHA = 0.10
        MOM_DAMPER = 5.0
        ENTRY_SIGNAL = 20.0

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        position = state.position.get(PRODUCT, 0)

        fair_key = "rect_fair"
        prev_key = "rect_prev_mid"
        mom_key = "rect_mom"

        if fair_key not in data:
            data[fair_key] = mid
            data[prev_key] = mid
            data[mom_key] = 0.0
            return

        fair = data[fair_key]
        prev_mid = data[prev_key]
        momentum = data[mom_key]

        # Update short-term momentum and fair value
        price_change = mid - prev_mid
        momentum = (1 - MOM_ALPHA) * momentum + MOM_ALPHA * price_change
        fair = (1 - EMA_ALPHA) * fair + EMA_ALPHA * mid

        data[fair_key] = fair
        data[prev_key] = mid
        data[mom_key] = momentum

        # Trend/pullback signal:
        # positive = favour long
        # negative = favour short
        signal = (mid - fair) - MOM_DAMPER * momentum

        target_position = position

        if signal > ENTRY_SIGNAL:
            target_position = LIMIT
        elif signal < -ENTRY_SIGNAL:
            target_position = -LIMIT

        orders: List[Order] = []

        # Move toward target position using best available price only.
        # This avoids paying too deeply into the book.
        if target_position > position:
            buy_amount = target_position - position
            available = -order_depth.sell_orders[best_ask]
            quantity = min(buy_amount, available)

            if quantity > 0:
                orders.append(Order(PRODUCT, best_ask, quantity))

        elif target_position < position:
            sell_amount = position - target_position
            available = order_depth.buy_orders[best_bid]
            quantity = min(sell_amount, available)

            if quantity > 0:
                orders.append(Order(PRODUCT, best_bid, -quantity))

        result[PRODUCT] = orders
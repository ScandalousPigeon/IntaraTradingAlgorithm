from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_translator_space_gray(state, result, data)

        return result, 0, json.dumps(data)

    def trade_translator_space_gray(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        PRODUCT = "TRANSLATOR_ASTRO_BLACK"

        if PRODUCT not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[PRODUCT]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        # === Tuned constants ===
        LIMIT = 10
        EMA_ALPHA = 0.20

        # Only trade when price has moved far away from its short EMA.
        # This avoids chop and only enters strong trend moves.
        ENTRY_SIGNAL = 50.0

        # Trade in chunks so reversals are less brutal.
        MAX_CLIP = 5

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(PRODUCT, 0)

        product_data = data.setdefault(PRODUCT, {})

        # Reset safely at start or initialise EMA.
        if "ema" not in product_data or state.timestamp == 0:
            product_data["ema"] = mid

        ema = product_data["ema"]

        # Momentum signal: positive means price is strongly above recent fair.
        signal = mid - ema

        orders: List[Order] = []

        # Default: keep current position.
        target_position = position

        # Strong upward momentum -> get long.
        if signal > ENTRY_SIGNAL:
            target_position = LIMIT

        # Strong downward momentum -> get short.
        elif signal < -ENTRY_SIGNAL:
            target_position = -LIMIT

        # Move toward target position by crossing the spread.
        if position < target_position:
            buy_qty = min(
                target_position - position,
                LIMIT - position,
                MAX_CLIP,
                best_ask_volume
            )

            if buy_qty > 0:
                orders.append(Order(PRODUCT, best_ask, buy_qty))

        elif position > target_position:
            sell_qty = min(
                position - target_position,
                LIMIT + position,
                MAX_CLIP,
                best_bid_volume
            )

            if sell_qty > 0:
                orders.append(Order(PRODUCT, best_bid, -sell_qty))

        # Update EMA after using the current signal.
        product_data["ema"] = (1 - EMA_ALPHA) * ema + EMA_ALPHA * mid

        result[PRODUCT] = orders
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_black_holes(state, result, data)

        return result, 0, json.dumps(data)

    def trade_black_holes(self, state: TradingState, result: dict, data: dict) -> None:
        product = "GALAXY_SOUNDS_BLACK_HOLES"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        LIMIT = 10

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        key = "black_holes_state"

        # Reset cleanly at the start of a new simulation/day.
        if state.timestamp == 0 or key not in data:
            data[key] = {
                "fast_ema": mid,
                "slow_ema": mid,
                "history": []
            }

        info = data[key]

        # Parameters tuned for the sample:
        # Product has strong upward drift, so use slow trend filters.
        FAST_SPAN = 120
        SLOW_SPAN = 400
        MOMENTUM_WINDOW = 80

        fast_alpha = 2 / (FAST_SPAN + 1)
        slow_alpha = 2 / (SLOW_SPAN + 1)

        info["fast_ema"] = (1 - fast_alpha) * info["fast_ema"] + fast_alpha * mid
        info["slow_ema"] = (1 - slow_alpha) * info["slow_ema"] + slow_alpha * mid

        history = info.get("history", [])
        history.append(mid)

        if len(history) > MOMENTUM_WINDOW + 1:
            history = history[-(MOMENTUM_WINDOW + 1):]

        info["history"] = history

        trend = info["fast_ema"] - info["slow_ema"]

        if len(history) > MOMENTUM_WINDOW:
            momentum = mid - history[0]
        else:
            momentum = 0

        # Default is to be long because Black Holes trends upward strongly.
        # Only cut exposure if both EMA trend and recent momentum are very negative.
        if trend < -240 and momentum < -240:
            target_position = 0
        elif trend < -120 and momentum < -120:
            target_position = 5
        else:
            target_position = LIMIT

        BUY_SIZE = 5
        SELL_SIZE = 3

        # Move toward target position.
        if position < target_position:
            buy_quantity = min(BUY_SIZE, target_position - position, LIMIT - position)

            if buy_quantity > 0:
                orders.append(Order(product, best_ask, buy_quantity))

        elif position > target_position:
            sell_quantity = min(SELL_SIZE, position - target_position, position + LIMIT)

            if sell_quantity > 0:
                orders.append(Order(product, best_bid, -sell_quantity))

        result[product] = orders
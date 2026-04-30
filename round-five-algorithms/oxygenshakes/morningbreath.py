from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except:
            data = {}

        for product in state.order_depths:
            result[product] = []

        self.trade_oxygen_morning_breath(state, result, data)

        return result, 0, json.dumps(data)

    def trade_oxygen_morning_breath(self, state: TradingState, result: dict, data: dict) -> None:
        product = "OXYGEN_SHAKE_MORNING_BREATH"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        LIMIT = 10

        # Tuned for this product:
        # Long trend product, wide spread, so trade only when slow trend is clear.
        FAST_SPAN = 200
        SLOW_SPAN = 1000

        ALPHA_FAST = 2 / (FAST_SPAN + 1)
        ALPHA_SLOW = 2 / (SLOW_SPAN + 1)

        TREND_MULT = 3.0
        ENTRY_SIGNAL = 6.0
        EXIT_SIGNAL = 2.0
        TARGET_SCALE = 4.0

        MAX_TRADE_SIZE = 2

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        pdata = data.setdefault(product, {})

        if "fast_ema" not in pdata:
            pdata["fast_ema"] = mid
            pdata["slow_ema"] = mid
            pdata["target"] = 0

        fast_ema = pdata["fast_ema"]
        slow_ema = pdata["slow_ema"]
        old_target = pdata.get("target", 0)

        fast_ema = fast_ema + ALPHA_FAST * (mid - fast_ema)
        slow_ema = slow_ema + ALPHA_SLOW * (mid - slow_ema)

        pdata["fast_ema"] = fast_ema
        pdata["slow_ema"] = slow_ema

        trend = fast_ema - slow_ema
        signal = TREND_MULT * trend

        # Hysteresis:
        # Enter when signal is strong.
        # Exit only when signal becomes very weak.
        # Otherwise keep previous target to avoid churn.
        if signal > ENTRY_SIGNAL:
            target = int(1 + (signal - ENTRY_SIGNAL) / TARGET_SCALE)
            target = min(LIMIT, target)

        elif signal < -ENTRY_SIGNAL:
            target = -int(1 + (-signal - ENTRY_SIGNAL) / TARGET_SCALE)
            target = max(-LIMIT, target)

        elif abs(signal) < EXIT_SIGNAL:
            target = 0

        else:
            target = old_target

        pdata["target"] = target

        desired_change = target - position

        # Move toward target slowly so we don't instantly max-risk on noisy moves.
        if desired_change > 0:
            buy_qty = min(
                desired_change,
                MAX_TRADE_SIZE,
                LIMIT - position,
                best_ask_volume
            )

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif desired_change < 0:
            sell_qty = min(
                -desired_change,
                MAX_TRADE_SIZE,
                LIMIT + position,
                best_bid_volume
            )

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
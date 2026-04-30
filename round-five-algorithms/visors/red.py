from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "UV_VISOR_RED"
    LIMIT = 10

    # Tuned for UV_VISOR_RED behaviour
    FAST_ALPHA = 0.02
    SLOW_ALPHA = 0.005

    # Enter only when trend is strong, exit when it fades
    ENTER_SIGNAL = 60.0
    EXIT_SIGNAL = 40.0

    # Avoid entering on weirdly wide books
    MAX_SPREAD = 18

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_uv_visor_red(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_red(self, state: TradingState, result: Dict[str, List[Order]], data: dict):
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_volume = depth.buy_orders[best_bid]
        ask_volume = -depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        pdata = data.get(product, {})

        fast = pdata.get("fast", mid)
        slow = pdata.get("slow", mid)
        target = pdata.get("target", 0)

        # Update EMAs
        fast = fast + self.FAST_ALPHA * (mid - fast)
        slow = slow + self.SLOW_ALPHA * (mid - slow)

        signal = fast - slow

        # End-of-day de-risking
        if state.timestamp >= 985000:
            target = 0

        # Do not open new positions if spread is abnormal
        elif spread > self.MAX_SPREAD:
            if position > 0:
                target = 0
            elif position < 0:
                target = 0

        else:
            # Strong uptrend: go long
            if signal > self.ENTER_SIGNAL:
                target = self.LIMIT

            # Strong downtrend: go short
            elif signal < -self.ENTER_SIGNAL:
                target = -self.LIMIT

            # Exit long when trend weakens
            elif target > 0 and signal < self.EXIT_SIGNAL:
                target = 0

            # Exit short when trend weakens
            elif target < 0 and signal > -self.EXIT_SIGNAL:
                target = 0

        # Clamp target just in case
        target = max(-self.LIMIT, min(self.LIMIT, int(target)))

        orders: List[Order] = []

        # Move position toward target
        if target > position:
            buy_qty = min(target - position, self.LIMIT - position, ask_volume)
            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif target < position:
            sell_qty = min(position - target, self.LIMIT + position, bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        result[product] = orders

        data[product] = {
            "fast": fast,
            "slow": slow,
            "target": target,
            "last_signal": signal,
        }
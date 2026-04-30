from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_oxygen_shake_mint(state, result, data)

        return result, 0, json.dumps(data)

    def trade_oxygen_shake_mint(self, state: TradingState, result: dict, data: dict) -> None:
        product = "OXYGEN_SHAKE_MINT"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        # =========================
        # PARAMETERS
        # =========================

        LIMIT = 10

        FAST_ALPHA = 0.15
        SLOW_ALPHA = 0.01

        VOL_ALPHA = 0.003

        BASE_THRESHOLD = 120
        VOL_MULT = 0.5

        MAX_SPREAD = 20

        # =========================
        # EMA STATE
        # =========================

        fast_key = "oxygen_mint_fast"
        slow_key = "oxygen_mint_slow"
        vol_key = "oxygen_mint_signal_vol"

        if fast_key not in data:
            data[fast_key] = mid

        if slow_key not in data:
            data[slow_key] = mid

        if vol_key not in data:
            data[vol_key] = 0

        fast = data[fast_key]
        slow = data[slow_key]
        signal_vol = data[vol_key]

        fast = (1 - FAST_ALPHA) * fast + FAST_ALPHA * mid
        slow = (1 - SLOW_ALPHA) * slow + SLOW_ALPHA * mid

        # Positive signal means price is stretched DOWN, so buy.
        # Negative signal means price is stretched UP, so sell.
        signal = slow - fast

        signal_vol = (1 - VOL_ALPHA) * signal_vol + VOL_ALPHA * abs(signal)

        data[fast_key] = fast
        data[slow_key] = slow
        data[vol_key] = signal_vol

        threshold = BASE_THRESHOLD + VOL_MULT * signal_vol

        position = state.position.get(product, 0)

        # Avoid crossing if spread becomes unusually wide
        if spread > MAX_SPREAD:
            result[product] = orders
            return

        # =========================
        # TARGET POSITION LOGIC
        # =========================

        target_position = position

        if signal > threshold:
            # Mint looks too cheap relative to slow EMA
            target_position = LIMIT

        elif signal < -threshold:
            # Mint looks too expensive relative to slow EMA
            target_position = -LIMIT

        # =========================
        # EXECUTE TOWARDS TARGET
        # =========================

        if target_position > position:
            buy_quantity = target_position - position
            buy_quantity = min(buy_quantity, LIMIT - position)
            buy_quantity = min(buy_quantity, best_ask_volume)

            if buy_quantity > 0:
                orders.append(Order(product, best_ask, buy_quantity))

        elif target_position < position:
            sell_quantity = position - target_position
            sell_quantity = min(sell_quantity, LIMIT + position)
            sell_quantity = min(sell_quantity, best_bid_volume)

            if sell_quantity > 0:
                orders.append(Order(product, best_bid, -sell_quantity))

        result[product] = orders
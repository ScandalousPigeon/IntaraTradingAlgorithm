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

        self.trade_sleep_pod_lamb_wool(state, result, data)

        return result, 0, json.dumps(data)

    def trade_sleep_pod_lamb_wool(self, state: TradingState, result: dict, data: dict) -> None:
        product = "SLEEP_POD_LAMB_WOOL"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        position = state.position.get(product, 0)

        LIMIT = 10
        ORDER_SIZE = 10

        # Momentum parameters
        FAST_ALPHA = 0.02
        SLOW_ALPHA = 0.001

        ENTRY_SIGNAL = 100
        EXIT_SIGNAL = 5

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        key = "sleep_pod_lamb_wool"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid
            }

        fast = data[key]["fast"]
        slow = data[key]["slow"]

        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        signal = fast - slow

        data[key]["fast"] = fast
        data[key]["slow"] = slow

        # =========================
        # STRONG UPTREND: BUY
        # =========================
        if signal > ENTRY_SIGNAL and position < LIMIT:
            buy_qty = min(
                ORDER_SIZE,
                best_ask_volume,
                LIMIT - position
            )

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        # =========================
        # STRONG DOWNTREND: SELL
        # =========================
        elif signal < -ENTRY_SIGNAL and position > -LIMIT:
            sell_qty = min(
                ORDER_SIZE,
                best_bid_volume,
                position + LIMIT
            )

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        # =========================
        # EXIT LONG WHEN TREND FADES
        # =========================
        elif position > 0 and signal < EXIT_SIGNAL:
            sell_qty = min(
                ORDER_SIZE,
                best_bid_volume,
                position
            )

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        # =========================
        # EXIT SHORT WHEN TREND FADES
        # =========================
        elif position < 0 and signal > -EXIT_SIGNAL:
            buy_qty = min(
                ORDER_SIZE,
                best_ask_volume,
                -position
            )

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        result[product] = orders
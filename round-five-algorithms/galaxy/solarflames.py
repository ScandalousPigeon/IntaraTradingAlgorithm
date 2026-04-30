from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_solar_flames(state, result, data)

        return result, 0, json.dumps(data)

    def trade_solar_flames(self, state: TradingState, result: dict, data: dict) -> None:
        product = "GALAXY_SOUNDS_SOLAR_FLAMES"

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

        position = state.position.get(product, 0)

        # =========================
        # PARAMETERS
        # =========================
        LIMIT = 10

        SLOW_ALPHA = 0.01
        FAST_ALPHA = 0.12

        ENTRY_EDGE = 100
        TREND_BLOCK = 100

        ORDER_SIZE = 2
        INVENTORY_SKEW = 0.4

        # =========================
        # STORED FAIR VALUES
        # =========================
        slow_key = "solar_flames_slow"
        fast_key = "solar_flames_fast"

        if slow_key not in data:
            data[slow_key] = mid

        if fast_key not in data:
            data[fast_key] = mid

        slow_fair = data[slow_key]
        fast_fair = data[fast_key]

        trend = fast_fair - slow_fair

        # If long, lower fair to encourage selling.
        # If short, raise fair to encourage buying.
        fair = slow_fair - INVENTORY_SKEW * position

        can_buy = LIMIT - position
        can_sell = LIMIT + position

        # =========================
        # AGGRESSIVE MEAN REVERSION
        # =========================

        # Buy only when ask is far below fair,
        # unless fast EMA says we are in a strong downtrend.
        if best_ask <= fair - ENTRY_EDGE and trend > -TREND_BLOCK:
            buy_quantity = min(ORDER_SIZE, can_buy, best_ask_volume)

            if buy_quantity > 0:
                orders.append(Order(product, best_ask, buy_quantity))

        # Sell only when bid is far above fair,
        # unless fast EMA says we are in a strong uptrend.
        if best_bid >= fair + ENTRY_EDGE and trend < TREND_BLOCK:
            sell_quantity = min(ORDER_SIZE, can_sell, best_bid_volume)

            if sell_quantity > 0:
                orders.append(Order(product, best_bid, -sell_quantity))

        # =========================
        # UPDATE EMAS AFTER TRADING
        # =========================
        data[slow_key] = (1 - SLOW_ALPHA) * slow_fair + SLOW_ALPHA * mid
        data[fast_key] = (1 - FAST_ALPHA) * fast_fair + FAST_ALPHA * mid

        result[product] = orders
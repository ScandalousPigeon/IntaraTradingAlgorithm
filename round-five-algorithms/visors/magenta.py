from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "UV_VISOR_MAGENTA"
    LIMIT = 10

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_uv_visor_magenta(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_magenta(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        memory = data.setdefault(product, {})

        if "fast_ema" not in memory:
            memory["fast_ema"] = mid
            memory["slow_ema"] = mid
            memory["risk_off"] = False
            memory["ticks"] = 0

        memory["ticks"] += 1

        # Very slow EMAs because MAGENTA is noisy and spread is expensive.
        FAST_ALPHA = 2 / (500 + 1)
        SLOW_ALPHA = 2 / (2000 + 1)

        memory["fast_ema"] = FAST_ALPHA * mid + (1 - FAST_ALPHA) * memory["fast_ema"]
        memory["slow_ema"] = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * memory["slow_ema"]

        fast_ema = memory["fast_ema"]
        slow_ema = memory["slow_ema"]

        trend = fast_ema - slow_ema
        deviation = mid - slow_ema

        # Historical MAGENTA has positive drift, so default is to hold long.
        target_position = self.LIMIT

        # Emergency risk-off only. Do not flip constantly.
        # This avoids selling on normal noise but protects against a real breakdown.
        if memory["ticks"] > 200:
            if not memory["risk_off"]:
                if trend < -300 and deviation < -200:
                    memory["risk_off"] = True
            else:
                if trend > -50 or deviation > -50:
                    memory["risk_off"] = False

        if memory["risk_off"]:
            target_position = 0

        # Move toward target. This strategy intentionally trades rarely.
        if position < target_position:
            buy_qty = min(target_position - position, best_ask_volume)
            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif position > target_position:
            sell_qty = min(position - target_position, best_bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
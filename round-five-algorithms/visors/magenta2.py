from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
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

    def trade_uv_visor_magenta(
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
            memory["ticks"] = 0
            memory["mode"] = 0

        memory["ticks"] += 1

        # =====================
        # PARAMETERS
        # =====================

        FAST_ALPHA = 2 / (300 + 1)
        SLOW_ALPHA = 2 / (1500 + 1)

        ENTER_TREND = 30
        EXIT_TREND = -20

        WARMUP_TICKS = 200

        ORDER_SIZE = 5

        # =====================
        # EMA UPDATE
        # =====================

        memory["fast_ema"] = (
            FAST_ALPHA * mid
            + (1 - FAST_ALPHA) * memory["fast_ema"]
        )

        memory["slow_ema"] = (
            SLOW_ALPHA * mid
            + (1 - SLOW_ALPHA) * memory["slow_ema"]
        )

        fast_ema = memory["fast_ema"]
        slow_ema = memory["slow_ema"]

        trend = fast_ema - slow_ema

        mode = memory.get("mode", 0)

        # =====================
        # MODE
        # 1 = long
        # 0 = flat
        # =====================

        if memory["ticks"] > WARMUP_TICKS:

            if mode == 0:
                if trend > ENTER_TREND:
                    mode = 1

            elif mode == 1:
                if trend < EXIT_TREND:
                    mode = 0

        memory["mode"] = mode

        # =====================
        # TARGET
        # =====================

        if mode == 1:
            target_position = self.LIMIT
        else:
            target_position = 0

        diff = target_position - position

        # =====================
        # EXECUTION
        # =====================

        if diff > 0:
            buy_qty = min(diff, best_ask_volume, ORDER_SIZE)

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif diff < 0:
            sell_qty = min(-diff, best_bid_volume, ORDER_SIZE)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
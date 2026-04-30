from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math

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
        except Exception:
            data = {}

        self.trade_uv_visor_amber(state, result, data)
        self.trade_uv_visor_magenta(state, result, data)
        self.trade_uv_visor_red(state, result, data)

        return result, 0, json.dumps(data)

    # ============================================================
    # UV_VISOR_AMBER
    # Directional short strategy
    # ============================================================

    def trade_uv_visor_amber(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "UV_VISOR_AMBER"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        LIMIT = 10
        ORDER_SIZE = 10

        TRAIL_REBOUND = 300
        TAKE_PROFIT = 600
        COOLDOWN_TICKS = 100
        LAST_ENTRY_TIMESTAMP = 850000

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        if "uv_amber" not in data:
            data["uv_amber"] = {
                "lowest_mid": None,
                "avg_short": None,
                "cooldown": 0,
                "last_timestamp": None,
            }

        d = data["uv_amber"]

        if d.get("last_timestamp") is not None and state.timestamp < d["last_timestamp"]:
            d["lowest_mid"] = None
            d["avg_short"] = None
            d["cooldown"] = 0

        d["last_timestamp"] = state.timestamp

        if d.get("cooldown", 0) > 0:
            d["cooldown"] -= 1

        if position > 0:
            sell_qty = min(position, best_bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
            return

        if position < 0:
            if d.get("lowest_mid") is None:
                d["lowest_mid"] = mid
            else:
                d["lowest_mid"] = min(d["lowest_mid"], mid)

            if d.get("avg_short") is None:
                d["avg_short"] = mid
        else:
            d["lowest_mid"] = None
            d["avg_short"] = None

        if position < 0:
            lowest_mid = d.get("lowest_mid", mid)
            avg_short = d.get("avg_short", mid)

            rebound_from_low = mid - lowest_mid
            profit_from_entry = avg_short - mid

            should_cover = False

            if profit_from_entry >= TAKE_PROFIT:
                should_cover = True

            if rebound_from_low >= TRAIL_REBOUND:
                should_cover = True

            if should_cover:
                buy_qty = min(-position, best_ask_volume)

                if buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))
                    d["cooldown"] = COOLDOWN_TICKS
                    d["lowest_mid"] = None
                    d["avg_short"] = None

                return

        if (
            d.get("cooldown", 0) <= 0
            and state.timestamp <= LAST_ENTRY_TIMESTAMP
            and position > -LIMIT
        ):
            sell_capacity = LIMIT + position
            sell_qty = min(sell_capacity, best_bid_volume, ORDER_SIZE)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

                current_short_size = max(0, -position)
                old_avg = d.get("avg_short")

                if old_avg is None or current_short_size == 0:
                    d["avg_short"] = best_bid
                else:
                    d["avg_short"] = (
                        old_avg * current_short_size + best_bid * sell_qty
                    ) / (current_short_size + sell_qty)

                if d.get("lowest_mid") is None:
                    d["lowest_mid"] = mid
                else:
                    d["lowest_mid"] = min(d["lowest_mid"], mid)

    # ============================================================
    # UV_VISOR_MAGENTA
    # Directional long strategy
    # ============================================================

    def trade_uv_visor_magenta(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "UV_VISOR_MAGENTA"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        LIMIT = 10

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

        FAST_ALPHA = 2 / (500 + 1)
        SLOW_ALPHA = 2 / (2000 + 1)

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
        deviation = mid - slow_ema

        target_position = LIMIT

        if memory["ticks"] > 200:
            if not memory["risk_off"]:
                if trend < -300 and deviation < -200:
                    memory["risk_off"] = True
            else:
                if trend > -50 or deviation > -50:
                    memory["risk_off"] = False

        if memory["risk_off"]:
            target_position = 0

        if position < target_position:
            buy_qty = min(target_position - position, best_ask_volume)

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif position > target_position:
            sell_qty = min(position - target_position, best_bid_volume)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

    # ============================================================
    # UV_VISOR_RED
    # Trend-following strategy
    # ============================================================

    def trade_uv_visor_red(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "UV_VISOR_RED"

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

        LIMIT = 10

        FAST_ALPHA = 0.02
        SLOW_ALPHA = 0.005

        ENTER_SIGNAL = 60.0
        EXIT_SIGNAL = 40.0

        MAX_SPREAD = 18

        key = "UV_VISOR_RED"

        pdata = data.get(key, {})

        fast = pdata.get("fast", mid)
        slow = pdata.get("slow", mid)
        target = pdata.get("target", 0)

        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        signal = fast - slow

        if state.timestamp >= 985000:
            target = 0

        elif spread > MAX_SPREAD:
            target = 0

        else:
            if signal > ENTER_SIGNAL:
                target = LIMIT

            elif signal < -ENTER_SIGNAL:
                target = -LIMIT

            elif target > 0 and signal < EXIT_SIGNAL:
                target = 0

            elif target < 0 and signal > -EXIT_SIGNAL:
                target = 0

        target = max(-LIMIT, min(LIMIT, int(target)))

        orders: List[Order] = result[product]

        if target > position:
            buy_qty = min(target - position, LIMIT - position, ask_volume)

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif target < position:
            sell_qty = min(position - target, LIMIT + position, bid_volume)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        data[key] = {
            "fast": fast,
            "slow": slow,
            "target": target,
            "last_signal": signal,
        }
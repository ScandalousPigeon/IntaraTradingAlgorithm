from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except:
            data = {}

        self.trade_uv_visor_amber(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_amber(self, state: TradingState, result: dict, data: dict) -> None:
        product = "UV_VISOR_AMBER"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        # =========================
        # PARAMETERS
        # =========================

        LIMIT = 10
        ORDER_SIZE = 5

        FAST_ALPHA = 0.01
        SLOW_ALPHA = 0.001

        MIN_DOWNTREND = -20

        TRAIL_REBOUND = 250
        HARD_STOP_REBOUND = 450

        COOLDOWN_TICKS = 40

        # avoid entering very late, but less harsh than 850000
        LAST_ENTRY_TIMESTAMP = 930000

        # =========================
        # STATE
        # =========================

        if "uv_amber" not in data:
            data["uv_amber"] = {
                "fast": mid,
                "slow": mid,
                "lowest_mid": None,
                "avg_short": None,
                "cooldown": 0,
                "last_timestamp": None,
            }

        d = data["uv_amber"]

        if d.get("last_timestamp") is not None and state.timestamp < d["last_timestamp"]:
            d["fast"] = mid
            d["slow"] = mid
            d["lowest_mid"] = None
            d["avg_short"] = None
            d["cooldown"] = 0

        d["last_timestamp"] = state.timestamp

        d["fast"] = FAST_ALPHA * mid + (1 - FAST_ALPHA) * d["fast"]
        d["slow"] = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * d["slow"]

        trend = d["fast"] - d["slow"]

        if d.get("cooldown", 0) > 0:
            d["cooldown"] -= 1

        # =========================
        # NEVER STAY LONG
        # =========================

        if position > 0:
            sell_qty = min(position, best_bid_volume)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

            return

        # =========================
        # UPDATE SHORT TRACKING
        # =========================

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

        # =========================
        # EXIT SHORT
        # =========================

        if position < 0:
            lowest_mid = d.get("lowest_mid", mid)
            rebound_from_low = mid - lowest_mid

            should_cover = False

            # trend has flipped against us
            if trend > 0:
                should_cover = True

            # price has bounced meaningfully from the low
            if rebound_from_low >= TRAIL_REBOUND:
                should_cover = True

            # hard emergency stop
            if rebound_from_low >= HARD_STOP_REBOUND:
                should_cover = True

            if should_cover:
                buy_qty = min(-position, best_ask_volume, ORDER_SIZE)

                if buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))

                    if buy_qty == -position:
                        d["cooldown"] = COOLDOWN_TICKS
                        d["lowest_mid"] = None
                        d["avg_short"] = None

                return

        # =========================
        # ENTER / ADD SHORT
        # =========================

        allow_short = (
            trend < MIN_DOWNTREND
            and d.get("cooldown", 0) <= 0
            and state.timestamp <= LAST_ENTRY_TIMESTAMP
            and position > -LIMIT
        )

        if allow_short:
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
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

        LIMIT = 10
        ORDER_SIZE = 10

        # Amber was consistently downward-trending in the sample.
        # Strategy: stay short, but cover after large profit / large rebound.
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
                "last_timestamp": None
            }

        d = data["uv_amber"]

        # Reset stored state if timestamp restarts
        if d.get("last_timestamp") is not None and state.timestamp < d["last_timestamp"]:
            d["lowest_mid"] = None
            d["avg_short"] = None
            d["cooldown"] = 0

        d["last_timestamp"] = state.timestamp

        # Reduce cooldown
        if d.get("cooldown", 0) > 0:
            d["cooldown"] -= 1

        # If somehow long, flatten immediately.
        if position > 0:
            sell_qty = min(position, best_bid_volume)
            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
            return

        # Update lowest seen while short
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
        # EXIT SHORT / LOCK PROFIT
        # =========================
        if position < 0:
            lowest_mid = d.get("lowest_mid", mid)
            avg_short = d.get("avg_short", mid)

            rebound_from_low = mid - lowest_mid
            profit_from_entry = avg_short - mid

            should_cover = False

            # Price has fallen a lot from our short entry
            if profit_from_entry >= TAKE_PROFIT:
                should_cover = True

            # Price bounced hard from the low, so lock gains
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

        # =========================
        # ENTER / RE-ENTER SHORT
        # =========================
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
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_microchip_square_optimised(state, result, data)

        return result, 0, json.dumps(data)

    def trade_microchip_square_optimised(self, state: TradingState, result: dict, data: dict) -> None:

        product = "MICROCHIP_SQUARE"

        # Real position limit is 10, but using all 10 caused large drawdowns.
        LIMIT = 6

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

        position = state.position.get(product, 0)

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        timestamp = state.timestamp

        # ============================================================
        # INITIALISE / RESET MEMORY
        # ============================================================

        if "microchip_square_opt" not in data:
            data["microchip_square_opt"] = {}

        d = data["microchip_square_opt"]

        # Reset if timestamp goes backwards, which usually means a new test/day.
        if not d or timestamp < d.get("last_timestamp", -1):
            data["microchip_square_opt"] = {
                "fast": mid,
                "slow": mid,
                "ticks": 0,
                "target": 0,

                # PnL estimate for risk control.
                "cash": 0.0,
                "last_pos": position,
                "last_buy_price": best_ask,
                "last_sell_price": best_bid,
                "peak_pnl": 0.0,
                "locked": False,

                "last_timestamp": timestamp
            }
            d = data["microchip_square_opt"]

        # ============================================================
        # UPDATE ESTIMATED CASH / PNL
        # ============================================================
        # We estimate fills from position changes. Since this strategy crosses
        # the spread with size 1 or 2, this estimate should be close enough
        # for risk control.

        last_pos = d.get("last_pos", position)

        if position != last_pos:
            delta = position - last_pos

            if delta > 0:
                # Position increased, so we bought.
                d["cash"] = d.get("cash", 0.0) - delta * d.get("last_buy_price", best_ask)

            elif delta < 0:
                # Position decreased, so we sold.
                d["cash"] = d.get("cash", 0.0) + (-delta) * d.get("last_sell_price", best_bid)

            d["last_pos"] = position

        estimated_pnl = d.get("cash", 0.0) + position * mid

        if estimated_pnl > d.get("peak_pnl", 0.0):
            d["peak_pnl"] = estimated_pnl

        peak_pnl = d.get("peak_pnl", 0.0)
        drawdown = peak_pnl - estimated_pnl

        # ============================================================
        # RISK LOCK
        # ============================================================
        # Your graph showed the strategy peaking, then bleeding heavily.
        # These rules try to preserve gains and avoid the late collapse.

        PROFIT_LOCK_START = 1500
        MAX_GIVEBACK = 1600

        if peak_pnl >= PROFIT_LOCK_START and drawdown >= MAX_GIVEBACK:
            d["locked"] = True

        # Extra safety: if it is clearly failing, stop digging.
        HARD_LOSS_STOP = -3500

        if estimated_pnl <= HARD_LOSS_STOP:
            d["locked"] = True

        # If locked, only flatten. Do not open new trades.
        if d.get("locked", False):

            FLATTEN_SIZE = 2

            if position > 0 and sell_room > 0:
                qty = min(FLATTEN_SIZE, best_bid_volume, position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    d["last_sell_price"] = best_bid

            elif position < 0 and buy_room > 0:
                qty = min(FLATTEN_SIZE, best_ask_volume, -position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    d["last_buy_price"] = best_ask

            result[product] = orders
            d["last_timestamp"] = timestamp
            return

        # ============================================================
        # TREND INDICATORS
        # ============================================================

        old_fast = d.get("fast", mid)
        old_slow = d.get("slow", mid)

        # Faster fast EMA and slower slow EMA than the previous version.
        # The previous settings reacted too late and got caught in reversals.
        FAST_ALPHA = 0.020
        SLOW_ALPHA = 0.003

        fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * old_fast
        slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * old_slow

        trend = fast - slow

        d["fast"] = fast
        d["slow"] = slow
        d["ticks"] = d.get("ticks", 0) + 1

        # Warm up indicators.
        if d["ticks"] < 40:
            result[product] = orders
            d["last_timestamp"] = timestamp
            return

        # Avoid paying very wide spreads.
        if spread > 14:
            result[product] = orders
            d["last_timestamp"] = timestamp
            return

        # ============================================================
        # TARGET POSITION
        # ============================================================

        ENTRY_TREND = 40
        EXIT_TREND = 5

        target_position = d.get("target", 0)

        if trend > ENTRY_TREND:
            target_position = LIMIT

        elif trend < -ENTRY_TREND:
            target_position = -LIMIT

        elif abs(trend) < EXIT_TREND:
            target_position = 0

        # Do not flip straight from long to short or short to long.
        # First flatten, then re-enter if the signal persists.
        if target_position * position < 0:
            target_position = 0

        d["target"] = target_position

        # ============================================================
        # EXECUTION
        # ============================================================

        ORDER_SIZE = 1

        if target_position > position and buy_room > 0:
            qty = min(
                ORDER_SIZE,
                target_position - position,
                buy_room,
                best_ask_volume
            )

            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                d["last_buy_price"] = best_ask

        elif target_position < position and sell_room > 0:
            qty = min(
                ORDER_SIZE,
                position - target_position,
                sell_room,
                best_bid_volume
            )

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                d["last_sell_price"] = best_bid

        result[product] = orders
        d["last_timestamp"] = timestamp
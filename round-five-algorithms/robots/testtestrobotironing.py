from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_robot_ironing(state, result, data)

        return result, 0, json.dumps(data)

    def trade_robot_ironing(self, state: TradingState, result: dict, data: dict) -> None:

        product = "ROBOT_IRONING"

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

        LIMIT = 10
        buy_room = LIMIT - position
        sell_room = LIMIT + position

        if "robot_ironing" not in data:
            data["robot_ironing"] = {
                "last_mid": mid,
                "fast": mid,
                "slow": mid,
                "ticks": 0,
                "cooldown": 0
            }

        d = data["robot_ironing"]

        last_mid = d["last_mid"]
        old_fast = d["fast"]
        old_slow = d["slow"]

        move = mid - last_mid

        # Fast/slow EMAs are not used as fair value.
        # They are only used to detect whether the market is trending.
        FAST_ALPHA = 0.06
        SLOW_ALPHA = 0.004

        fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * old_fast
        slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * old_slow

        trend = fast - slow

        d["fast"] = fast
        d["slow"] = slow
        d["last_mid"] = mid
        d["ticks"] = d.get("ticks", 0) + 1

        # Warmup period so the EMAs mean something.
        if d["ticks"] < 50:
            result[product] = orders
            return

        # Tuned for ROBOT_IRONING.
        MOVE_THRESHOLD = 25
        TREND_LIMIT = 40
        ORDER_SIZE = 1
        COOLDOWN_TICKS = 1

        # Avoid trading weirdly wide books.
        if spread > 10:
            result[product] = orders
            return

        # =====================================================
        # EMERGENCY INVENTORY REDUCTION
        # =====================================================
        # If we are long and the product is trending down, reduce.
        if position > 0 and trend < -TREND_LIMIT:
            qty = min(ORDER_SIZE, position, best_bid_volume)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                d["cooldown"] = COOLDOWN_TICKS
                result[product] = orders
                return

        # If we are short and the product is trending up, reduce.
        if position < 0 and trend > TREND_LIMIT:
            qty = min(ORDER_SIZE, -position, best_ask_volume)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                d["cooldown"] = COOLDOWN_TICKS
                result[product] = orders
                return

        # Cooldown stops the bot from overtrading every small bounce.
        if d.get("cooldown", 0) > 0:
            d["cooldown"] = d.get("cooldown", 0) - 1
            result[product] = orders
            return

        # =====================================================
        # REGIME-AWARE MEAN REVERSION
        # =====================================================

        # Strong downtrend:
        # Do NOT buy dips. Only sell sharp upward bounces.
        if trend < -TREND_LIMIT:

            if move >= MOVE_THRESHOLD and sell_room > 0:
                qty = min(ORDER_SIZE, sell_room, best_bid_volume)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    d["cooldown"] = COOLDOWN_TICKS

        # Strong uptrend:
        # Do NOT sell spikes. Only buy sharp downward dips.
        elif trend > TREND_LIMIT:

            if move <= -MOVE_THRESHOLD and buy_room > 0:
                qty = min(ORDER_SIZE, buy_room, best_ask_volume)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    d["cooldown"] = COOLDOWN_TICKS

        # Calm/choppy regime:
        # Trade normal one-step mean reversion.
        else:

            # Sharp drop -> buy bounce.
            if move <= -MOVE_THRESHOLD and buy_room > 0:
                qty = min(ORDER_SIZE, buy_room, best_ask_volume)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    d["cooldown"] = COOLDOWN_TICKS

            # Sharp rise -> sell fade.
            elif move >= MOVE_THRESHOLD and sell_room > 0:
                qty = min(ORDER_SIZE, sell_room, best_bid_volume)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    d["cooldown"] = COOLDOWN_TICKS

        result[product] = orders
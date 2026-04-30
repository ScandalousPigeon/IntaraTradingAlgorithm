from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_uv_visor_yellow(state, result, data)

        return result, 0, json.dumps(data)

    def trade_uv_visor_yellow(self, state: TradingState, result: dict, data: dict) -> None:
        product = "UV_VISOR_YELLOW"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        # True position limit.
        LIMIT = 10

        # We intentionally trade smaller than the real limit to reduce PnL swings.
        SOFT_LIMIT = 6

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = abs(order_depth.buy_orders[best_bid])
        best_ask_volume = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        if product not in data:
            data[product] = {}

        memory = data[product]

        if "slow" not in memory:
            memory["slow"] = mid
            memory["fast"] = mid
            memory["last_mid"] = mid
            memory["last_slow"] = mid
            memory["absret"] = 8.5
            memory["ticks"] = 0

        memory["ticks"] += 1

        last_mid = memory["last_mid"]
        last_slow = memory["last_slow"]

        price_change = mid - last_mid

        FAST_ALPHA = 0.08
        SLOW_ALPHA = 0.018
        VOL_ALPHA = 0.06

        fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * memory["fast"]
        slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * memory["slow"]
        absret = VOL_ALPHA * abs(price_change) + (1 - VOL_ALPHA) * memory["absret"]

        memory["fast"] = fast
        memory["slow"] = slow
        memory["last_mid"] = mid
        memory["last_slow"] = slow
        memory["absret"] = absret

        # Let the indicators warm up slightly.
        if memory["ticks"] < 20:
            return

        # =========================
        # Signal calculation
        # =========================
        # Yellow tends to whip around. Instead of chasing fast trend,
        # this version fades over-extension.
        deviation = fast - slow
        slow_slope = slow - last_slow

        volatility = max(6.0, absret)

        z = deviation / max(1.0, volatility)

        # Mean-reverting fair:
        # If fast is far above slow, fair is pulled lower.
        # If fast is far below slow, fair is pulled higher.
        REVERSION_WEIGHT = 0.65
        INVENTORY_SKEW = 1.25

        fair = mid - REVERSION_WEIGHT * deviation - INVENTORY_SKEW * position

        # =========================
        # Target position
        # =========================
        target_position = 0

        if z <= -4.0:
            target_position = 6
        elif z <= -2.5:
            target_position = 4
        elif z <= -1.4:
            target_position = 2
        elif z >= 4.0:
            target_position = -6
        elif z >= 2.5:
            target_position = -4
        elif z >= 1.4:
            target_position = -2
        else:
            target_position = 0

        # Do not fight a strong slow trend too hard.
        # This prevents repeatedly shorting a strong uptrend or buying a strong downtrend.
        if slow_slope > 1.2 and target_position < 0:
            target_position = max(target_position, -2)

        if slow_slope < -1.2 and target_position > 0:
            target_position = min(target_position, 2)

        target_position = max(-SOFT_LIMIT, min(SOFT_LIMIT, target_position))

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # =========================
        # 1. Emergency de-risking
        # =========================
        # If we accidentally get near the hard limit, reduce quickly.
        if position >= 8 and sell_room > 0:
            quantity = min(3, sell_room, best_bid_volume)
            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))
                position -= quantity
                sell_room -= quantity
                buy_room += quantity

        elif position <= -8 and buy_room > 0:
            quantity = min(3, buy_room, best_ask_volume)
            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))
                position += quantity
                buy_room -= quantity
                sell_room += quantity

        # =========================
        # 2. Aggressive taking only on strong mispricing
        # =========================
        # Much less aggressive than the previous version.
        take_edge = max(12.0, 1.15 * volatility)

        if buy_room > 0 and position < target_position:
            if best_ask <= fair - take_edge:
                quantity = min(2, buy_room, target_position - position, best_ask_volume)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    position += quantity
                    buy_room -= quantity
                    sell_room += quantity

        if sell_room > 0 and position > target_position:
            if best_bid >= fair + take_edge:
                quantity = min(2, sell_room, position - target_position, best_bid_volume)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    position -= quantity
                    sell_room -= quantity
                    buy_room += quantity

        # =========================
        # 3. Passive quoting
        # =========================
        # Wide spread means passive orders are valuable.
        # But only quote in the direction that moves us toward target.
        if spread < 4:
            return

        passive_edge = max(2.0, min(6.0, 0.35 * volatility))

        # Buy if we are below target.
        if buy_room > 0 and position < target_position:
            quantity = min(2, buy_room, target_position - position)

            fair_bid_ceiling = math.floor(fair - passive_edge)
            passive_bid = min(best_bid + 1, best_ask - 1, fair_bid_ceiling)

            if quantity > 0 and passive_bid > 0 and passive_bid < best_ask:
                orders.append(Order(product, passive_bid, quantity))

        # Sell if we are above target.
        if sell_room > 0 and position > target_position:
            quantity = min(2, sell_room, position - target_position)

            fair_ask_floor = math.ceil(fair + passive_edge)
            passive_ask = max(best_ask - 1, best_bid + 1, fair_ask_floor)

            if quantity > 0 and passive_ask > best_bid:
                orders.append(Order(product, passive_ask, -quantity))

        # =========================
        # 4. Small neutral market making
        # =========================
        # Only when almost flat and signal is weak.
        # This captures spread without taking a big directional bet.
        if abs(position) <= 2 and abs(z) < 1.2 and spread >= 10:
            neutral_size = 1

            if buy_room > 0:
                neutral_bid = min(best_bid + 1, best_ask - 1, math.floor(fair - 3))
                if neutral_bid > 0 and neutral_bid < best_ask:
                    orders.append(Order(product, neutral_bid, neutral_size))

            if sell_room > 0:
                neutral_ask = max(best_ask - 1, best_bid + 1, math.ceil(fair + 3))
                if neutral_ask > best_bid:
                    orders.append(Order(product, neutral_ask, -neutral_size))
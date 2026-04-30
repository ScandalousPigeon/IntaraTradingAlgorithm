from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_black_holes(state, result, data)
        self.trade_dark_matter(state, result)
        self.trade_solar_flames(state, result, data)
        self.trade_planetary_rings(state, result, data)
        self.trade_solar_winds(state, result, data)

        return result, 0, json.dumps(data)

    # ============================================================
    # GALAXY_SOUNDS_BLACK_HOLES
    # Directional long/uptrend strategy
    # ============================================================

    def trade_black_holes(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "GALAXY_SOUNDS_BLACK_HOLES"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        LIMIT = 10

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        position = state.position.get(product, 0)

        key = "black_holes_state"

        if state.timestamp == 0 or key not in data:
            data[key] = {
                "fast_ema": mid,
                "slow_ema": mid,
                "history": [],
            }

        info = data[key]

        FAST_SPAN = 120
        SLOW_SPAN = 400
        MOMENTUM_WINDOW = 80

        fast_alpha = 2 / (FAST_SPAN + 1)
        slow_alpha = 2 / (SLOW_SPAN + 1)

        info["fast_ema"] = (
            (1 - fast_alpha) * info["fast_ema"]
            + fast_alpha * mid
        )

        info["slow_ema"] = (
            (1 - slow_alpha) * info["slow_ema"]
            + slow_alpha * mid
        )

        history = info.get("history", [])
        history.append(mid)

        if len(history) > MOMENTUM_WINDOW + 1:
            history = history[-(MOMENTUM_WINDOW + 1):]

        info["history"] = history

        trend = info["fast_ema"] - info["slow_ema"]

        if len(history) > MOMENTUM_WINDOW:
            momentum = mid - history[0]
        else:
            momentum = 0

        if trend < -240 and momentum < -240:
            target_position = 0
        elif trend < -120 and momentum < -120:
            target_position = 5
        else:
            target_position = LIMIT

        BUY_SIZE = 5
        SELL_SIZE = 3

        if position < target_position:
            buy_quantity = min(
                BUY_SIZE,
                target_position - position,
                LIMIT - position,
                best_ask_volume,
            )

            if buy_quantity > 0:
                orders.append(Order(product, best_ask, buy_quantity))

        elif position > target_position:
            sell_quantity = min(
                SELL_SIZE,
                position - target_position,
                position + LIMIT,
                best_bid_volume,
            )

            if sell_quantity > 0:
                orders.append(Order(product, best_bid, -sell_quantity))

    # ============================================================
    # GALAXY_SOUNDS_DARK_MATTER
    # Time-seasonality strategy
    # ============================================================

    def trade_dark_matter(
        self,
        state: TradingState,
        result: Dict[str, List[Order]]
    ) -> None:

        product = "GALAXY_SOUNDS_DARK_MATTER"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders and not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        LIMIT = 10
        position = state.position.get(product, 0)
        timestamp = state.timestamp

        if timestamp < 325000:
            target_position = -LIMIT
        elif timestamp < 375000:
            target_position = 0
        else:
            target_position = LIMIT

        diff = target_position - position

        if diff > 0 and order_depth.sell_orders:
            buy_qty = diff

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if buy_qty <= 0:
                    break

                ask_volume = abs(order_depth.sell_orders[ask_price])
                quantity = min(buy_qty, ask_volume)

                if quantity > 0:
                    orders.append(Order(product, ask_price, quantity))
                    buy_qty -= quantity

        elif diff < 0 and order_depth.buy_orders:
            sell_qty = -diff

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if sell_qty <= 0:
                    break

                bid_volume = abs(order_depth.buy_orders[bid_price])
                quantity = min(sell_qty, bid_volume)

                if quantity > 0:
                    orders.append(Order(product, bid_price, -quantity))
                    sell_qty -= quantity

    # ============================================================
    # GALAXY_SOUNDS_SOLAR_FLAMES
    # Slow fair mean-reversion with trend block
    # ============================================================

    def trade_solar_flames(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "GALAXY_SOUNDS_SOLAR_FLAMES"

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

        LIMIT = 10

        SLOW_ALPHA = 0.01
        FAST_ALPHA = 0.12

        ENTRY_EDGE = 100
        TREND_BLOCK = 100

        ORDER_SIZE = 2
        INVENTORY_SKEW = 0.4

        slow_key = "solar_flames_slow"
        fast_key = "solar_flames_fast"

        if slow_key not in data:
            data[slow_key] = mid

        if fast_key not in data:
            data[fast_key] = mid

        slow_fair = data[slow_key]
        fast_fair = data[fast_key]

        trend = fast_fair - slow_fair
        fair = slow_fair - INVENTORY_SKEW * position

        can_buy = LIMIT - position
        can_sell = LIMIT + position

        if best_ask <= fair - ENTRY_EDGE and trend > -TREND_BLOCK:
            buy_quantity = min(ORDER_SIZE, can_buy, best_ask_volume)

            if buy_quantity > 0:
                orders.append(Order(product, best_ask, buy_quantity))

        if best_bid >= fair + ENTRY_EDGE and trend < TREND_BLOCK:
            sell_quantity = min(ORDER_SIZE, can_sell, best_bid_volume)

            if sell_quantity > 0:
                orders.append(Order(product, best_bid, -sell_quantity))

        data[slow_key] = (1 - SLOW_ALPHA) * slow_fair + SLOW_ALPHA * mid
        data[fast_key] = (1 - FAST_ALPHA) * fast_fair + FAST_ALPHA * mid

    # ============================================================
    # GALAXY_SOUNDS_PLANETARY_RINGS
    # Trend-following fair + passive market making
    # ============================================================

    def trade_planetary_rings(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "GALAXY_SOUNDS_PLANETARY_RINGS"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        LIMIT = 10
        position = state.position.get(product, 0)

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        key = "planetary_rings"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "vol": 10.0,
                "last_mid": mid,
            }

        product_data = data[key]

        fast = product_data["fast"]
        slow = product_data["slow"]
        vol = product_data["vol"]
        last_mid = product_data["last_mid"]

        FAST_ALPHA = 0.004
        SLOW_ALPHA = 0.0015
        VOL_ALPHA = 0.05

        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        change = abs(mid - last_mid)
        vol = vol + VOL_ALPHA * (change - vol)

        trend = fast - slow

        product_data["fast"] = fast
        product_data["slow"] = slow
        product_data["vol"] = vol
        product_data["last_mid"] = mid

        MOMENTUM_MULT = 1.0
        INVENTORY_SKEW = 1.25

        fair = mid + MOMENTUM_MULT * trend - INVENTORY_SKEW * position

        TAKE_EDGE = max(3, int(vol * 0.35))

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        if buy_capacity > 0:
            for ask_price in sorted(order_depth.sell_orders.keys()):
                ask_volume = -order_depth.sell_orders[ask_price]

                if ask_price <= fair - TAKE_EDGE:
                    quantity = min(buy_capacity, ask_volume)

                    if quantity > 0:
                        orders.append(Order(product, ask_price, quantity))
                        buy_capacity -= quantity
                        position += quantity

                if buy_capacity <= 0:
                    break

        if sell_capacity > 0:
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                bid_volume = order_depth.buy_orders[bid_price]

                if bid_price >= fair + TAKE_EDGE:
                    quantity = min(sell_capacity, bid_volume)

                    if quantity > 0:
                        orders.append(Order(product, bid_price, -quantity))
                        sell_capacity -= quantity
                        position -= quantity

                if sell_capacity <= 0:
                    break

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        if spread >= 8:
            PASSIVE_SIZE = 2
            FAIR_EDGE = 2

            buy_price = min(best_bid + 1, math.floor(fair - FAIR_EDGE))
            sell_price = max(best_ask - 1, math.ceil(fair + FAIR_EDGE))

            if buy_price >= sell_price:
                buy_price = best_bid
                sell_price = best_ask

            if trend > 12:
                buy_size = 3
                sell_size = 1
            elif trend < -12:
                buy_size = 1
                sell_size = 3
            else:
                buy_size = PASSIVE_SIZE
                sell_size = PASSIVE_SIZE

            if position > 5:
                buy_size = 1

            if position < -5:
                sell_size = 1

            if buy_capacity > 0 and buy_price < best_ask:
                quantity = min(buy_size, buy_capacity)

                if quantity > 0:
                    orders.append(Order(product, int(buy_price), quantity))

            if sell_capacity > 0 and sell_price > best_bid:
                quantity = min(sell_size, sell_capacity)

                if quantity > 0:
                    orders.append(Order(product, int(sell_price), -quantity))

    # ============================================================
    # GALAXY_SOUNDS_SOLAR_WINDS
    # Microprice / fair-value / passive MM
    # ============================================================

    def trade_solar_winds(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "GALAXY_SOUNDS_SOLAR_WINDS"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        if best_bid >= best_ask:
            return

        bid_vol = abs(order_depth.buy_orders[best_bid])
        ask_vol = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        memory = data.get(product, {})

        fast = memory.get("fast", mid)
        slow = memory.get("slow", mid)
        vol = memory.get("vol", best_ask - best_bid)
        last_mid = memory.get("last_mid", mid)

        fast = 0.35 * mid + 0.65 * fast
        slow = 0.04 * mid + 0.96 * slow

        move = abs(mid - last_mid)
        vol = 0.12 * move + 0.88 * vol

        memory["fast"] = fast
        memory["slow"] = slow
        memory["vol"] = vol
        memory["last_mid"] = mid
        data[product] = memory

        total_top_volume = max(1, bid_vol + ask_vol)
        imbalance = (bid_vol - ask_vol) / total_top_volume

        micro_price = (
            best_ask * bid_vol + best_bid * ask_vol
        ) / total_top_volume

        micro_bias = micro_price - mid
        trend = fast - slow

        inventory_skew = position * 0.75

        fair = mid
        fair += 1.15 * micro_bias
        fair += 0.06 * trend
        fair -= inventory_skew

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        take_edge = max(9.0, min(15.0, 0.95 * vol))

        if buy_capacity > 0 and best_ask <= fair - take_edge:
            qty = min(buy_capacity, ask_vol, 2)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_capacity -= qty
                position += qty

        if sell_capacity > 0 and best_bid >= fair + take_edge:
            qty = min(sell_capacity, bid_vol, 2)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_capacity -= qty
                position -= qty

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        passive_edge = max(4.0, min(7.0, 0.45 * vol + 1.0))

        buy_price = min(best_bid + 1, int(round(fair - passive_edge)))
        sell_price = max(best_ask - 1, int(round(fair + passive_edge)))

        buy_price = min(buy_price, best_ask - 1)
        sell_price = max(sell_price, best_bid + 1)

        if position >= 7:
            buy_size = 1
            sell_size = 4
        elif position <= -7:
            buy_size = 4
            sell_size = 1
        elif position > 2:
            buy_size = 2
            sell_size = 3
        elif position < -2:
            buy_size = 3
            sell_size = 2
        else:
            buy_size = 3
            sell_size = 3

        if buy_capacity > 0 and buy_price < best_ask:
            qty = min(buy_capacity, buy_size)

            if qty > 0:
                orders.append(Order(product, int(buy_price), qty))

        if sell_capacity > 0 and sell_price > best_bid:
            qty = min(sell_capacity, sell_size)

            if qty > 0:
                orders.append(Order(product, int(sell_price), -qty))
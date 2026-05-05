from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    PEBBLES = ["PEBBLES_XS",
        "PEBBLES_S",
        "PEBBLES_M",
        "PEBBLES_L",
        "PEBBLES_XL",
    ]

    BASKET_FAIR = 50000
    PEBBLES_LIMIT = 10

    TAKE_EDGE = 2
    TAKE_SIZE = 1

    PASSIVE_EDGE = 15
    PASSIVE_SIZE = 2

    SOFT_LIMIT = 6

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        # PEBBLES
        self.trade_pebbles(state, result, data)

        self.trade_microchip_oval(state, result, data)
        self.trade_panel_4x4(state, result, data)

        # UV VISORS
        self.trade_uv_visor_amber(state, result, data)
        self.trade_uv_visor_magenta(state, result, data)
        self.trade_uv_visor_red(state, result, data)

        # TRANSLATORS
        self.trade_translator_space_gray(state, result, data)
        self.trade_translator_astro_black(state, result, data)
        self.trade_translator_eclipse_charcoal(state, result, data)
        self.trade_graphite_mist(state, result, data)
        self.trade_void_blue(state, result, data)

        # GALAXY SOUNDS
        self.trade_black_holes(state, result, data)
        self.trade_dark_matter(state, result)
        self.trade_solar_flames(state, result, data)
        self.trade_planetary_rings(state, result, data)
        self.trade_solar_winds(state, result, data)

        # SNACKPACKS
        self.trade_raspberry(state, result, data)
        self.trade_snackpack_strawberry(state, result, data)
        self.trade_vanilla(state, result, data)
        self.trade_chocolate(state, result, data)

        # SLEEP PODS
        self.trade_sleep_pod_lamb_wool(state, result, data)

        # ROBOTS
        self.trade_robot_dishes(state, result, data)

        # OXYGEN SHAKES
        self.trade_oxygen_chocolate(state, result, data)
        self.trade_evening_breath(state, result, data)
        self.trade_garlic(state, result)
        self.trade_morning_breath(state, result, data)

        return result, 0, json.dumps(data)

    # ============================================================
    # HELPERS
    # ============================================================

    def best_bid_ask(self, depth: OrderDepth):
        if not depth.buy_orders or not depth.sell_orders:
            return None

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_vol = depth.buy_orders[best_bid]
        ask_vol = abs(depth.sell_orders[best_ask])

        return best_bid, best_ask, bid_vol, ask_vol

    def mid_price(self, depth: OrderDepth):
        best = self.best_bid_ask(depth)

        if best is None:
            return None

        best_bid, best_ask, _, _ = best

        return (best_bid + best_ask) / 2

    # ============================================================
    # UV_VISOR_AMBER
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

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

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
                "last_timestamp": None
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

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

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

        memory["fast_ema"] = FAST_ALPHA * mid + (1 - FAST_ALPHA) * memory["fast_ema"]
        memory["slow_ema"] = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * memory["slow_ema"]

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

        depth = state.order_depths[product]

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

        orders = result[product]

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

    # ============================================================
    # TRANSLATORS
    # ============================================================

    def trade_translator_momentum(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict,
        product: str,
        ema_alpha: float = 0.20,
        entry_signal: float = 50.0,
        max_clip: int = 5,
        limit: int = 10,
    ) -> None:

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        product_data = data.setdefault(product, {})

        if "ema" not in product_data or state.timestamp == 0:
            product_data["ema"] = mid

        ema = product_data["ema"]
        signal = mid - ema

        target_position = position

        if signal > entry_signal:
            target_position = limit

        elif signal < -entry_signal:
            target_position = -limit

        if position < target_position:
            buy_qty = min(
                target_position - position,
                limit - position,
                max_clip,
                best_ask_volume,
            )

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif position > target_position:
            sell_qty = min(
                position - target_position,
                limit + position,
                max_clip,
                best_bid_volume,
            )

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        product_data["ema"] = (1 - ema_alpha) * ema + ema_alpha * mid

    def trade_translator_space_gray(self, state, result, data) -> None:
        self.trade_translator_momentum(
            state, result, data,
            product="TRANSLATOR_SPACE_GRAY",
            ema_alpha=0.20,
            entry_signal=50.0,
            max_clip=5,
            limit=10,
        )

    def trade_translator_astro_black(self, state, result, data) -> None:
        self.trade_translator_momentum(
            state, result, data,
            product="TRANSLATOR_ASTRO_BLACK",
            ema_alpha=0.20,
            entry_signal=50.0,
            max_clip=5,
            limit=10,
        )

    def trade_translator_eclipse_charcoal(self, state, result, data) -> None:
        product = "TRANSLATOR_ECLIPSE_CHARCOAL"
        limit = 10

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_vol = abs(order_depth.buy_orders[best_bid])
        ask_vol = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        key = "TRANSLATOR_ECLIPSE_CHARCOAL_DATA"

        if key not in data:
            data[key] = {
                "prev_mid": mid,
                "fast": mid,
                "slow": mid,
                "vol": 8.0,
            }

        d = data[key]

        prev_mid = d.get("prev_mid", mid)
        fast = d.get("fast", mid)
        slow = d.get("slow", mid)
        vol = d.get("vol", 8.0)

        ret = mid - prev_mid

        fast = 0.35 * mid + 0.65 * fast
        slow = 0.03 * mid + 0.97 * slow
        vol = 0.93 * vol + 0.07 * abs(ret)

        trend = fast - slow

        if bid_vol + ask_vol > 0:
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        else:
            imbalance = 0

        fair = (
            mid
            + 0.50 * trend
            + 0.75 * spread * imbalance
            - 1.00 * position
        )

        edge = 5

        if vol > 12:
            edge = 6
        elif vol < 6 and spread >= 9:
            edge = 4

        if spread < 6:
            d["prev_mid"] = mid
            d["fast"] = fast
            d["slow"] = slow
            d["vol"] = vol
            return

        buy_capacity = limit - position
        sell_capacity = limit + position

        buy_price = min(best_bid + 1, math.floor(fair - edge))
        sell_price = max(best_ask - 1, math.ceil(fair + edge))

        buy_price = min(buy_price, best_ask - 1)
        sell_price = max(sell_price, best_bid + 1)

        if buy_price >= sell_price:
            buy_price = best_bid
            sell_price = best_ask

        base_size = 1

        buy_size = base_size
        sell_size = base_size

        if position <= -4:
            buy_size = 2
            sell_size = 1

        elif position >= 4:
            buy_size = 1
            sell_size = 2

        if position >= 7:
            buy_size = 0
            sell_size = 3

        if position <= -7:
            buy_size = 3
            sell_size = 0

        buy_size = min(buy_size, buy_capacity)
        sell_size = min(sell_size, sell_capacity)

        if buy_size > 0:
            orders.append(Order(product, int(buy_price), int(buy_size)))

        if sell_size > 0:
            orders.append(Order(product, int(sell_price), -int(sell_size)))

        d["prev_mid"] = mid
        d["fast"] = fast
        d["slow"] = slow
        d["vol"] = vol

    def trade_graphite_mist(self, state, result, data) -> None:
        product = "TRANSLATOR_GRAPHITE_MIST"
        limit = 10

        if product not in state.order_depths:
            return

        depth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders = result[product]
        position = state.position.get(product, 0)

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        best_bid_vol = depth.buy_orders[best_bid]
        best_ask_vol = -depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        key = "graphite_mist"

        if key not in data:
            data[key] = {
                "ema": mid,
                "slow": mid,
                "vol": 8.0,
                "last_mid": mid,
            }

        info = data[key]

        last_mid = info.get("last_mid", mid)
        move = abs(mid - last_mid)

        ema = info.get("ema", mid)
        slow = info.get("slow", mid)
        vol = info.get("vol", 8.0)

        ema = 0.82 * ema + 0.18 * mid
        slow = 0.985 * slow + 0.015 * mid
        vol = 0.92 * vol + 0.08 * move

        if best_bid_vol + best_ask_vol > 0:
            micro = (
                best_bid * best_ask_vol
                + best_ask * best_bid_vol
            ) / (best_bid_vol + best_ask_vol)
        else:
            micro = mid

        inventory_skew = 0.65 * position
        micro_signal = 1.20 * (micro - mid)
        slow_reversion = -0.08 * (mid - slow)

        fair = mid + micro_signal + slow_reversion - inventory_skew

        info["ema"] = ema
        info["slow"] = slow
        info["vol"] = vol
        info["last_mid"] = mid
        data[key] = info

        pos = position

        passive_edge = max(3, min(6, int(round(vol * 0.28))))
        take_edge = passive_edge + 3

        if pos < limit:
            for ask_price in sorted(depth.sell_orders.keys()):
                ask_vol = -depth.sell_orders[ask_price]

                if ask_price <= fair - take_edge:
                    qty = min(ask_vol, 2, limit - pos)

                    if qty > 0:
                        orders.append(Order(product, ask_price, qty))
                        pos += qty
                else:
                    break

                if pos >= limit:
                    break

        if pos > -limit:
            for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
                bid_vol = depth.buy_orders[bid_price]

                if bid_price >= fair + take_edge:
                    qty = min(bid_vol, 2, limit + pos)

                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty))
                        pos -= qty
                else:
                    break

                if pos <= -limit:
                    break

        buy_capacity = limit - pos
        sell_capacity = limit + pos

        if spread >= 5:
            bid_quote = min(best_bid + 1, math.floor(fair - passive_edge))
            ask_quote = max(best_ask - 1, math.ceil(fair + passive_edge))

            bid_quote = min(bid_quote, best_ask - 1)
            ask_quote = max(ask_quote, best_bid + 1)

            if bid_quote < ask_quote:
                base_size = 2 if spread >= 8 else 1

                buy_size = base_size
                sell_size = base_size

                if pos >= 5:
                    buy_size = 1
                    sell_size = 3

                if pos <= -5:
                    buy_size = 3
                    sell_size = 1

                if buy_capacity > 0:
                    qty = min(buy_size, buy_capacity)
                    orders.append(Order(product, int(bid_quote), int(qty)))

                if sell_capacity > 0:
                    qty = min(sell_size, sell_capacity)
                    orders.append(Order(product, int(ask_quote), -int(qty)))

    def trade_void_blue(self, state, result, data) -> None:
        product = "TRANSLATOR_VOID_BLUE"
        limit = 10

        EMA_ALPHA = 0.02
        REVERSION_STRENGTH = 0.20
        MICRO_WEIGHT = 0.30

        BASE_EDGE = 7.0
        VOL_EDGE = 0.15
        INV_SKEW = 0.80

        MAX_TAKE_SIZE = 4

        if product not in state.order_depths:
            return

        depth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        position = state.position.get(product, 0)

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_qty = depth.buy_orders[best_bid]
        ask_qty = -depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        key = "void_blue_state"

        if key not in data:
            data[key] = {
                "ema": mid,
                "last_mid": mid,
                "absret": 8.0,
            }

        s = data[key]

        last_mid = s["last_mid"]
        ret = mid - last_mid

        s["absret"] = 0.94 * s["absret"] + 0.06 * abs(ret)
        s["ema"] = EMA_ALPHA * mid + (1 - EMA_ALPHA) * s["ema"]
        s["last_mid"] = mid

        ema = s["ema"]
        absret = s["absret"]

        if bid_qty + ask_qty > 0:
            microprice = (
                best_ask * bid_qty
                + best_bid * ask_qty
            ) / (bid_qty + ask_qty)
        else:
            microprice = mid

        micro_dev = microprice - mid

        fair = mid - REVERSION_STRENGTH * (mid - ema)
        fair += MICRO_WEIGHT * micro_dev
        fair -= INV_SKEW * position

        edge = BASE_EDGE + VOL_EDGE * absret

        orders = result[product]

        if best_ask <= fair - edge and position < limit:
            buy_size = min(
                ask_qty,
                MAX_TAKE_SIZE,
                limit - position,
            )

            if buy_size > 0:
                orders.append(Order(product, best_ask, buy_size))
                position += buy_size

        fair_after_buy = fair - INV_SKEW * (
            position - state.position.get(product, 0)
        )

        if best_bid >= fair_after_buy + edge and position > -limit:
            sell_size = min(
                bid_qty,
                MAX_TAKE_SIZE,
                limit + position,
            )

            if sell_size > 0:
                orders.append(Order(product, best_bid, -sell_size))
                position -= sell_size

    # ============================================================
    # GALAXY SOUNDS
    # ============================================================

    def trade_black_holes(self, state, result, data) -> None:
        product = "GALAXY_SOUNDS_BLACK_HOLES"

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

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
                "history": []
            }

        info = data[key]

        FAST_SPAN = 120
        SLOW_SPAN = 400
        MOMENTUM_WINDOW = 80

        fast_alpha = 2 / (FAST_SPAN + 1)
        slow_alpha = 2 / (SLOW_SPAN + 1)

        info["fast_ema"] = (1 - fast_alpha) * info["fast_ema"] + fast_alpha * mid
        info["slow_ema"] = (1 - slow_alpha) * info["slow_ema"] + slow_alpha * mid

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
                best_ask_volume
            )

            if buy_quantity > 0:
                orders.append(Order(product, best_ask, buy_quantity))

        elif position > target_position:
            sell_quantity = min(
                SELL_SIZE,
                position - target_position,
                position + LIMIT,
                best_bid_volume
            )

            if sell_quantity > 0:
                orders.append(Order(product, best_bid, -sell_quantity))

    def trade_dark_matter(self, state, result) -> None:
        product = "GALAXY_SOUNDS_DARK_MATTER"

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        orders = result[product]

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

    def trade_solar_flames(self, state, result, data) -> None:
        product = "GALAXY_SOUNDS_SOLAR_FLAMES"

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

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

    def trade_planetary_rings(self, state, result, data) -> None:
        product = "GALAXY_SOUNDS_PLANETARY_RINGS"

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        LIMIT = 10
        position = state.position.get(product, 0)

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        key = "planetary_rings"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "vol": 10.0,
                "last_mid": mid
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

    def trade_solar_winds(self, state, result, data) -> None:
        product = "GALAXY_SOUNDS_SOLAR_WINDS"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

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

    # ============================================================
    # SNACKPACKS
    # ============================================================

    def trade_raspberry(self, state, result, data) -> None:
        PRODUCT = "SNACKPACK_RASPBERRY"
        HEDGE_PRODUCT = "SNACKPACK_PISTACHIO"

        LIMIT = 10
        PAIR_INTERCEPT = 14355.3001
        PAIR_BETA = -0.450459
        PAIR_WEIGHT = 0.75
        EMA_ALPHA = 0.001
        WARMUP = 120
        ENTRY_EDGE = 120
        EXIT_EDGE = 3
        MAX_SPREAD = 14
        MAX_STEP = 10

        if PRODUCT not in state.order_depths:
            return

        depth = state.order_depths[PRODUCT]
        best = self.best_bid_ask(depth)

        if best is None:
            return

        best_bid, best_ask, bid_vol, ask_vol = best

        spread = best_ask - best_bid
        raspberry_mid = (best_bid + best_ask) / 2

        store = data.setdefault("snackpack_raspberry_v2", {})

        if "ema" not in store:
            store["ema"] = raspberry_mid
            store["n"] = 0

        store["ema"] = EMA_ALPHA * raspberry_mid + (1 - EMA_ALPHA) * store["ema"]
        store["n"] += 1

        if store["n"] < WARMUP:
            return

        pair_fair = None

        if HEDGE_PRODUCT in state.order_depths:
            pistachio_mid = self.mid_price(state.order_depths[HEDGE_PRODUCT])

            if pistachio_mid is not None:
                pair_fair = PAIR_INTERCEPT + PAIR_BETA * pistachio_mid

        if pair_fair is None:
            fair = store["ema"]
        else:
            fair = PAIR_WEIGHT * pair_fair + (1 - PAIR_WEIGHT) * store["ema"]

        position = state.position.get(PRODUCT, 0)

        if spread > MAX_SPREAD:
            return

        if best_ask < fair - ENTRY_EDGE and position < LIMIT:
            qty = min(LIMIT - position, ask_vol, MAX_STEP)

            if qty > 0:
                result[PRODUCT].append(Order(PRODUCT, best_ask, qty))
                position += qty

        elif best_bid > fair + ENTRY_EDGE and position > -LIMIT:
            qty = min(position + LIMIT, bid_vol, MAX_STEP)

            if qty > 0:
                result[PRODUCT].append(Order(PRODUCT, best_bid, -qty))
                position -= qty

        if position > 0 and best_bid >= fair - EXIT_EDGE:
            qty = min(position, bid_vol, MAX_STEP)

            if qty > 0:
                result[PRODUCT].append(Order(PRODUCT, best_bid, -qty))
                position -= qty

        elif position < 0 and best_ask <= fair + EXIT_EDGE:
            qty = min(-position, ask_vol, MAX_STEP)

            if qty > 0:
                result[PRODUCT].append(Order(PRODUCT, best_ask, qty))
                position += qty

    def trade_snackpack_strawberry(self, state, result, data) -> None:
        product = "SNACKPACK_STRAWBERRY"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        key = "snackpack_strawberry"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "absret": 5.0,
                "last_mid": mid
            }

        info = data[key]

        last_mid = info.get("last_mid", mid)
        ret = mid - last_mid

        ALPHA_FAST = 0.08
        ALPHA_SLOW = 0.015
        ALPHA_VOL = 0.05

        fast = info.get("fast", mid)
        slow = info.get("slow", mid)
        absret = info.get("absret", 5.0)

        fast = fast + ALPHA_FAST * (mid - fast)
        slow = slow + ALPHA_SLOW * (mid - slow)
        absret = absret + ALPHA_VOL * (abs(ret) - absret)

        info["fast"] = fast
        info["slow"] = slow
        info["absret"] = absret
        info["last_mid"] = mid

        if bid_volume + ask_volume > 0:
            microprice = (
                best_ask * bid_volume +
                best_bid * ask_volume
            ) / (bid_volume + ask_volume)
        else:
            microprice = mid

        pressure = microprice - mid

        short_deviation = mid - fast
        long_deviation = mid - slow

        fair = mid
        fair -= 0.18 * short_deviation
        fair -= 0.04 * long_deviation
        fair += 0.85 * pressure
        fair -= 0.45 * position

        TAKE_EDGE = max(2.0, min(4.0, absret * 0.20))

        if position < LIMIT:
            for ask_price in sorted(order_depth.sell_orders.keys()):
                ask_qty = abs(order_depth.sell_orders[ask_price])

                if ask_price <= fair - TAKE_EDGE:
                    buy_qty = min(ask_qty, LIMIT - position, 4)

                    if buy_qty > 0:
                        orders.append(Order(product, ask_price, buy_qty))
                        position += buy_qty
                else:
                    break

        if position > -LIMIT:
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                bid_qty = order_depth.buy_orders[bid_price]

                if bid_price >= fair + TAKE_EDGE:
                    sell_qty = min(bid_qty, position + LIMIT, 4)

                    if sell_qty > 0:
                        orders.append(Order(product, bid_price, -sell_qty))
                        position -= sell_qty
                else:
                    break

        if spread < 8:
            return

        fair_after_inventory = fair - 0.35 * position

        base_edge = 2.0 if spread >= 15 else 3.0

        buy_edge = base_edge
        sell_edge = base_edge

        if pressure > 0.5:
            buy_edge -= 1.0
            sell_edge += 1.0

        elif pressure < -0.5:
            buy_edge += 1.0
            sell_edge -= 1.0

        if short_deviation > 8:
            sell_edge -= 0.5
            buy_edge += 0.5

        elif short_deviation < -8:
            buy_edge -= 0.5
            sell_edge += 0.5

        buy_edge = max(1.0, min(5.0, buy_edge))
        sell_edge = max(1.0, min(5.0, sell_edge))

        bid_quote = min(best_bid + 1, math.floor(fair_after_inventory - buy_edge))
        ask_quote = max(best_ask - 1, math.ceil(fair_after_inventory + sell_edge))

        if bid_quote >= best_ask:
            bid_quote = best_bid

        if ask_quote <= best_bid:
            ask_quote = best_ask

        clear_up = pressure > 0.5
        clear_down = pressure < -0.5

        buy_capacity = LIMIT - position

        if buy_capacity > 0:
            buy_size = 3

            if pressure > 0.5:
                buy_size = 5

            if position < 0:
                buy_size += 2

            if position > 5:
                buy_size = 1

            buy_size = min(buy_size, buy_capacity)

            if not (clear_down and position >= 0):
                if buy_size > 0 and bid_quote < best_ask:
                    orders.append(Order(product, bid_quote, buy_size))

        sell_capacity = position + LIMIT

        if sell_capacity > 0:
            sell_size = 3

            if pressure < -0.5:
                sell_size = 5

            if position > 0:
                sell_size += 2

            if position < -5:
                sell_size = 1

            sell_size = min(sell_size, sell_capacity)

            if not (clear_up and position <= 0):
                if sell_size > 0 and ask_quote > best_bid:
                    orders.append(Order(product, ask_quote, -sell_size))

    def trade_vanilla(self, state, result, data) -> None:
        PRODUCT = "SNACKPACK_VANILLA"
        REF_PRODUCT = "SNACKPACK_CHOCOLATE"

        LIMIT = 10
        MAX_STEP = 10
        WARMUP = 120
        SUM_ALPHA = 0.02
        OLS_ALPHA = 0.001
        ENTRY_EDGE = 20
        EXIT_EDGE = 2
        CONFIRM_FRAC = 0.60

        if PRODUCT not in state.order_depths:
            return

        od = state.order_depths[PRODUCT]

        if not od.buy_orders or not od.sell_orders:
            return

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        mid = (best_bid + best_ask) / 2

        pos = state.position.get(PRODUCT, 0)

        key = "snackpack_vanilla_pair_v1"
        s = data.get(key, {})

        last_ts = s.get("last_ts")
        if last_ts is not None and state.timestamp < last_ts:
            s = {}

        count = s.get("count", 0)

        vanilla_ema = s.get("vanilla_ema", mid)
        fallback_fair = vanilla_ema

        fair = fallback_fair
        fair_sum = fallback_fair
        fair_ols = fallback_fair

        has_ref = REF_PRODUCT in state.order_depths

        if has_ref:
            ref_od = state.order_depths[REF_PRODUCT]

            if ref_od.buy_orders and ref_od.sell_orders:
                ref_bid = max(ref_od.buy_orders)
                ref_ask = min(ref_od.sell_orders)
                ref_mid = (ref_bid + ref_ask) / 2

                pair_sum = mid + ref_mid

                sum_ema = s.get("sum_ema", pair_sum)
                fair_sum = sum_ema - ref_mid

                mx = s.get("mx", ref_mid)
                my = s.get("my", mid)
                mxx = s.get("mxx", ref_mid * ref_mid)
                mxy = s.get("mxy", ref_mid * mid)

                var_x = mxx - mx * mx
                cov_xy = mxy - mx * my

                if var_x > 1.0:
                    beta = cov_xy / var_x
                else:
                    beta = -1.0

                if beta > -0.20 or beta < -1.80:
                    beta = -1.0

                intercept = my - beta * mx
                fair_ols = intercept + beta * ref_mid

                fair = 0.50 * fair_sum + 0.50 * fair_ols

                s["next_sum_ema"] = (1 - SUM_ALPHA) * sum_ema + SUM_ALPHA * pair_sum
                s["next_mx"] = (1 - OLS_ALPHA) * mx + OLS_ALPHA * ref_mid
                s["next_my"] = (1 - OLS_ALPHA) * my + OLS_ALPHA * mid
                s["next_mxx"] = (1 - OLS_ALPHA) * mxx + OLS_ALPHA * ref_mid * ref_mid
                s["next_mxy"] = (1 - OLS_ALPHA) * mxy + OLS_ALPHA * ref_mid * mid

        if count >= WARMUP:
            ask_volume = abs(od.sell_orders[best_ask])
            bid_volume = abs(od.buy_orders[best_bid])

            buy_room = LIMIT - pos
            sell_room = LIMIT + pos

            buy_signal = (
                best_ask <= fair - ENTRY_EDGE
                and best_ask <= fair_sum - ENTRY_EDGE * CONFIRM_FRAC
                and best_ask <= fair_ols - ENTRY_EDGE * CONFIRM_FRAC
            )

            sell_signal = (
                best_bid >= fair + ENTRY_EDGE
                and best_bid >= fair_sum + ENTRY_EDGE * CONFIRM_FRAC
                and best_bid >= fair_ols + ENTRY_EDGE * CONFIRM_FRAC
            )

            if buy_signal and buy_room > 0:
                qty = min(MAX_STEP, buy_room, ask_volume)

                if qty > 0:
                    result[PRODUCT].append(Order(PRODUCT, best_ask, qty))

            elif sell_signal and sell_room > 0:
                qty = min(MAX_STEP, sell_room, bid_volume)

                if qty > 0:
                    result[PRODUCT].append(Order(PRODUCT, best_bid, -qty))

            elif pos > 0 and best_bid >= fair - EXIT_EDGE:
                qty = min(MAX_STEP, pos, bid_volume)

                if qty > 0:
                    result[PRODUCT].append(Order(PRODUCT, best_bid, -qty))

            elif pos < 0 and best_ask <= fair + EXIT_EDGE:
                qty = min(MAX_STEP, -pos, ask_volume)

                if qty > 0:
                    result[PRODUCT].append(Order(PRODUCT, best_ask, qty))

        s["count"] = count + 1
        s["last_ts"] = state.timestamp
        s["vanilla_ema"] = (1 - SUM_ALPHA) * vanilla_ema + SUM_ALPHA * mid

        if "next_sum_ema" in s:
            s["sum_ema"] = s.pop("next_sum_ema")
            s["mx"] = s.pop("next_mx")
            s["my"] = s.pop("next_my")
            s["mxx"] = s.pop("next_mxx")
            s["mxy"] = s.pop("next_mxy")

        data[key] = s

    def trade_chocolate(self, state, result, data) -> None:
        product = "SNACKPACK_CHOCOLATE"

        LIMIT = 100
        ALPHA = 0.0002
        WARMUP = 500
        ENTRY_EDGE = 120
        EXIT_EDGE = 0
        MAX_SPREAD = 20
        MAX_STEP = 1
        POSITION_SKEW = 0.05

        if product not in state.order_depths:
            return

        depth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_volume = depth.buy_orders[best_bid]
        ask_volume = abs(depth.sell_orders[best_ask])

        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2

        product_data = data.setdefault(product, {})
        ticks = product_data.get("ticks", 0)

        if "ema" not in product_data:
            product_data["ema"] = mid

        ema = product_data["ema"]
        ema = (1 - ALPHA) * ema + ALPHA * mid

        product_data["ema"] = ema
        product_data["ticks"] = ticks + 1

        if ticks < WARMUP:
            return

        if spread > MAX_SPREAD:
            return

        position = state.position.get(product, 0)

        fair = ema - POSITION_SKEW * position

        orders = result[product]

        def buy(qty: int, price: int) -> None:
            nonlocal position
            qty = min(qty, LIMIT - position)

            if qty > 0:
                orders.append(Order(product, price, qty))
                position += qty

        def sell(qty: int, price: int) -> None:
            nonlocal position
            qty = min(qty, LIMIT + position)

            if qty > 0:
                orders.append(Order(product, price, -qty))
                position -= qty

        if position < 0 and best_ask <= fair + EXIT_EDGE:
            buy_qty = min(MAX_STEP, ask_volume, -position)
            buy(buy_qty, best_ask)

        if position > 0 and best_bid >= fair - EXIT_EDGE:
            sell_qty = min(MAX_STEP, bid_volume, position)
            sell(sell_qty, best_bid)

        if best_ask <= fair - ENTRY_EDGE:
            buy_qty = min(MAX_STEP, ask_volume)
            buy(buy_qty, best_ask)

        if best_bid >= fair + ENTRY_EDGE:
            sell_qty = min(MAX_STEP, bid_volume)
            sell(sell_qty, best_bid)

    # ============================================================
    # SLEEP_POD_LAMB_WOOL
    # ============================================================

    def trade_sleep_pod_lamb_wool(self, state, result, data) -> None:
        product = "SLEEP_POD_LAMB_WOOL"

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        position = state.position.get(product, 0)

        LIMIT = 10
        ORDER_SIZE = 10

        FAST_ALPHA = 0.02
        SLOW_ALPHA = 0.001

        ENTRY_SIGNAL = 100
        EXIT_SIGNAL = 5

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        key = "sleep_pod_lamb_wool"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid
            }

        fast = data[key]["fast"]
        slow = data[key]["slow"]

        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        signal = fast - slow

        data[key]["fast"] = fast
        data[key]["slow"] = slow

        if signal > ENTRY_SIGNAL and position < LIMIT:
            buy_qty = min(
                ORDER_SIZE,
                best_ask_volume,
                LIMIT - position
            )

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif signal < -ENTRY_SIGNAL and position > -LIMIT:
            sell_qty = min(
                ORDER_SIZE,
                best_bid_volume,
                position + LIMIT
            )

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        elif position > 0 and signal < EXIT_SIGNAL:
            sell_qty = min(
                ORDER_SIZE,
                best_bid_volume,
                position
            )

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

        elif position < 0 and signal > -EXIT_SIGNAL:
            buy_qty = min(
                ORDER_SIZE,
                best_ask_volume,
                -position
            )

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

    # ============================================================
    # ROBOT_DISHES
    # ============================================================

    def trade_robot_dishes(self, state, result, data) -> None:
        product = "ROBOT_DISHES"

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        LIMIT = 4
        SIZE = 1
        ENTRY_JUMP = 40
        MAX_HOLD = 5

        last_mid_key = product + "_last_mid"
        mode_key = product + "_mode"
        hold_key = product + "_hold"

        if last_mid_key not in data:
            data[last_mid_key] = mid
            data[mode_key] = 0
            data[hold_key] = 0
            return

        last_mid = data[last_mid_key]
        move = mid - last_mid

        data[last_mid_key] = mid

        mode = data.get(mode_key, 0)
        hold = data.get(hold_key, 0)

        if mode == 0:
            if move >= ENTRY_JUMP:
                mode = -1
                hold = 0

            elif move <= -ENTRY_JUMP:
                mode = 1
                hold = 0

        else:
            hold += 1

            if hold >= MAX_HOLD:
                mode = 0
                hold = 0

            elif mode == 1 and move > 10:
                mode = 0
                hold = 0

            elif mode == -1 and move < -10:
                mode = 0
                hold = 0

        data[mode_key] = mode
        data[hold_key] = hold

        if mode == 1:
            target = LIMIT

        elif mode == -1:
            target = -LIMIT

        else:
            target = 0

        diff = target - position

        if diff > 0:
            qty = min(diff, SIZE, ask_volume)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        elif diff < 0:
            qty = min(-diff, SIZE, bid_volume)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

    # ============================================================
    # MICROCHIP_OVAL
    # Early bounce fade / short strategy
    # ============================================================

    def trade_microchip_oval(self, state, result, data) -> None:
        product = "MICROCHIP_OVAL"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]
        position = state.position.get(product, 0)

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        if product not in data:
            data[product] = {
                "start_mid": mid,
                "high_mid": mid,
                "ticks": 0,
                "armed": False,
            }

        d = data[product]

        d["ticks"] += 1
        d["high_mid"] = max(d["high_mid"], mid)

        start_mid = d["start_mid"]
        high_mid = d["high_mid"]

        # Adaptive warmup:
        # Higher starting price historically had a longer early bounce.
        if start_mid > 9800:
            warmup_ticks = 3000
            pullback = 20
        elif start_mid > 8500:
            warmup_ticks = 1500
            pullback = 50
        else:
            warmup_ticks = 500
            pullback = 10

        # Enter short after early bounce starts fading.
        if d["ticks"] >= warmup_ticks and high_mid - mid >= pullback:
            d["armed"] = True

        # Emergency entry if it falls immediately.
        if d["ticks"] >= warmup_ticks and mid < start_mid - 80:
            d["armed"] = True

        target_position = -LIMIT if d["armed"] else 0

        self.trade_to_target(
            product=product,
            order_depth=order_depth,
            orders=orders,
            position=position,
            target_position=target_position
        )

    # ============================================================
    # PANEL_4X4
    # EMA trend-following strategy
    # ============================================================

    def trade_panel_4x4(self, state, result, data) -> None:
        product = "PANEL_4X4"

        LIMIT = 10

        FAST_ALPHA = 2 / (100 + 1)
        SLOW_ALPHA = 2 / (800 + 1)

        ENTRY = 8.0
        EXIT = 3.0

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        pdata = data.setdefault(product, {})

        if "fast" not in pdata:
            pdata["fast"] = mid
            pdata["slow"] = mid
            pdata["target"] = 0
            pdata["count"] = 0
            return

        pdata["count"] += 1

        fast = pdata["fast"]
        slow = pdata["slow"]

        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        pdata["fast"] = fast
        pdata["slow"] = slow

        signal = fast - slow
        old_target = int(pdata.get("target", 0))

        target = old_target

        if signal > ENTRY:
            target = LIMIT
        elif signal < -ENTRY:
            target = -LIMIT
        elif abs(signal) < EXIT:
            target = 0

        pdata["target"] = target

        current_pos = state.position.get(product, 0)

        self.trade_to_target(
            product=product,
            order_depth=order_depth,
            orders=result[product],
            position=current_pos,
            target_position=target
        )

    # ============================================================
    # SHARED TARGET EXECUTION HELPER
    # Used by MICROCHIP_OVAL and PANEL_4X4
    # ============================================================

    def trade_to_target(
        self,
        product: str,
        order_depth,
        orders: List[Order],
        position: int,
        target_position: int,
    ) -> None:

        if target_position < position:
            # Need to sell.
            quantity_to_sell = position - target_position

            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if quantity_to_sell <= 0:
                    break

                available = order_depth.buy_orders[price]
                quantity = min(quantity_to_sell, available)

                if quantity > 0:
                    orders.append(Order(product, price, -quantity))
                    quantity_to_sell -= quantity

        elif target_position > position:
            # Need to buy / cover.
            quantity_to_buy = target_position - position

            for price in sorted(order_depth.sell_orders.keys()):
                if quantity_to_buy <= 0:
                    break

                available = abs(order_depth.sell_orders[price])
                quantity = min(quantity_to_buy, available)

                if quantity > 0:
                    orders.append(Order(product, price, quantity))
                    quantity_to_buy -= quantity
    # ============================================================
    # OXYGEN_SHAKE_CHOCOLATE
    # ============================================================

    def trade_oxygen_chocolate(self, state, result, data) -> None:
        product = "OXYGEN_SHAKE_CHOCOLATE"

        LIMIT = 10
        ORDER_SIZE = 10

        EMA_SPAN = 800
        ENTRY_EDGE = 220
        EXIT_EDGE = 10

        STOP_LOSS = 350
        COOLDOWN_TICKS = 3

        if product not in state.order_depths:
            return

        depth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        best_bid_volume = depth.buy_orders[best_bid]
        best_ask_volume = -depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        key = "oxygen_chocolate"

        if key not in data:
            data[key] = {
                "ema": mid,
                "entry_mid": None,
                "cooldown": 0,
            }

        mem = data[key]

        alpha = 2 / (EMA_SPAN + 1)

        ema = mem.get("ema", mid)
        ema = alpha * mid + (1 - alpha) * ema
        mem["ema"] = ema

        entry_mid = mem.get("entry_mid", None)
        cooldown = mem.get("cooldown", 0)

        if cooldown > 0:
            cooldown -= 1

        dev = mid - ema

        if position == 0:
            entry_mid = None

        # =========================
        # STOP LOSS
        # =========================

        if entry_mid is not None and position != 0:

            if position > 0 and mid < entry_mid - STOP_LOSS:
                sell_qty = min(position, best_bid_volume)

                if sell_qty > 0:
                    orders.append(Order(product, best_bid, -sell_qty))
                    position -= sell_qty
                    cooldown = COOLDOWN_TICKS

                    if position == 0:
                        entry_mid = None

            elif position < 0 and mid > entry_mid + STOP_LOSS:
                buy_qty = min(-position, best_ask_volume)

                if buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))
                    position += buy_qty
                    cooldown = COOLDOWN_TICKS

                    if position == 0:
                        entry_mid = None

        # =========================
        # ENTRIES
        # =========================

        if cooldown == 0:

            if dev < -ENTRY_EDGE and position < LIMIT:
                buy_qty = min(
                    ORDER_SIZE,
                    LIMIT - position,
                    best_ask_volume,
                )

                if buy_qty > 0:
                    if position == 0:
                        entry_mid = mid

                    orders.append(Order(product, best_ask, buy_qty))
                    position += buy_qty

            elif dev > ENTRY_EDGE and position > -LIMIT:
                sell_qty = min(
                    ORDER_SIZE,
                    LIMIT + position,
                    best_bid_volume,
                )

                if sell_qty > 0:
                    if position == 0:
                        entry_mid = mid

                    orders.append(Order(product, best_bid, -sell_qty))
                    position -= sell_qty

        # =========================
        # EXITS
        # =========================

        if position > 0 and dev > -EXIT_EDGE:
            sell_qty = min(position, best_bid_volume)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
                position -= sell_qty

                if position == 0:
                    entry_mid = None
                    cooldown = COOLDOWN_TICKS

        elif position < 0 and dev < EXIT_EDGE:
            buy_qty = min(-position, best_ask_volume)

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))
                position += buy_qty

                if position == 0:
                    entry_mid = None
                    cooldown = COOLDOWN_TICKS

        mem["entry_mid"] = entry_mid
        mem["cooldown"] = cooldown
        data[key] = mem

    # ============================================================
    # OXYGEN_SHAKE_EVENING_BREATH
    # ============================================================

    def trade_evening_breath(self, state, result, data) -> None:
        product = "OXYGEN_SHAKE_EVENING_BREATH"

        LIMIT = 10

        if product not in state.order_depths:
            return

        depth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_vol = abs(depth.buy_orders[best_bid])
        ask_vol = abs(depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        pos = state.position.get(product, 0)

        pdata = data.get(product, {})

        ema = pdata.get("ema", mid)

        alpha = 0.34
        ema = alpha * mid + (1 - alpha) * ema

        last_mid = pdata.get("last_mid", mid)
        last_ret = mid - last_mid

        vol = pdata.get("vol", 8.0)
        vol = 0.94 * vol + 0.06 * abs(last_ret)

        if bid_vol + ask_vol > 0:
            micro = (
                best_ask * bid_vol
                + best_bid * ask_vol
            ) / (bid_vol + ask_vol)
        else:
            micro = mid

        micro_signal = micro - mid

        fair = (
            ema
            - 0.25 * last_ret
            + 0.20 * micro_signal
            - 0.85 * pos
        )

        pdata["ema"] = ema
        pdata["last_mid"] = mid
        pdata["vol"] = vol
        data[product] = pdata

        buy_cap = LIMIT - pos
        sell_cap = LIMIT + pos

        def add_buy(price: int, qty: int):
            nonlocal buy_cap

            qty = max(0, min(qty, buy_cap))

            if qty > 0:
                orders.append(Order(product, price, qty))
                buy_cap -= qty

        def add_sell(price: int, qty: int):
            nonlocal sell_cap

            qty = max(0, min(qty, sell_cap))

            if qty > 0:
                orders.append(Order(product, price, -qty))
                sell_cap -= qty

        TAKE_EDGE = max(17, min(26, int(15 + 0.45 * vol)))
        TAKE_SIZE = 5

        # Aggressive buys
        for ask_price in sorted(depth.sell_orders.keys()):
            if buy_cap <= 0:
                break

            ask_qty = abs(depth.sell_orders[ask_price])

            if ask_price <= fair - TAKE_EDGE:
                add_buy(ask_price, min(TAKE_SIZE, ask_qty))
            else:
                break

        # Aggressive sells
        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if sell_cap <= 0:
                break

            bid_qty = abs(depth.buy_orders[bid_price])

            if bid_price >= fair + TAKE_EDGE:
                add_sell(bid_price, min(TAKE_SIZE, bid_qty))
            else:
                break

        # Passive quotes
        if spread >= 6:
            PASSIVE_EDGE = 4
            BASE_SIZE = 2

            bid_quote = min(best_bid + 1, math.floor(fair - PASSIVE_EDGE))
            ask_quote = max(best_ask - 1, math.ceil(fair + PASSIVE_EDGE))

            buy_size = BASE_SIZE
            sell_size = BASE_SIZE

            if pos < 0:
                buy_size += 2
            elif pos > 0:
                sell_size += 2

            if fair > mid + 5:
                buy_size += 1
            elif fair < mid - 5:
                sell_size += 1

            if bid_quote < best_ask:
                add_buy(int(bid_quote), buy_size)

            if ask_quote > best_bid:
                add_sell(int(ask_quote), sell_size)

    # ============================================================
    # OXYGEN_SHAKE_GARLIC
    # ============================================================

    def trade_garlic(self, state, result) -> None:
        product = "OXYGEN_SHAKE_GARLIC"

        LIMIT = 10

        if product not in state.order_depths:
            return

        depth = state.order_depths[product]

        if not depth.sell_orders or not depth.buy_orders:
            return

        orders = result[product]

        position = state.position.get(product, 0)

        best_ask = min(depth.sell_orders.keys())
        best_ask_volume = -depth.sell_orders[best_ask]

        best_bid = max(depth.buy_orders.keys())
        best_bid_volume = depth.buy_orders[best_bid]

        spread = best_ask - best_bid

        target_position = LIMIT

        if position < target_position:
            buy_qty = min(target_position - position, best_ask_volume)

            if buy_qty > 0 and spread <= 25:
                orders.append(Order(product, best_ask, buy_qty))

        if position > LIMIT:
            sell_qty = min(position - LIMIT, best_bid_volume)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))

    # ============================================================
    # OXYGEN_SHAKE_MORNING_BREATH
    # ============================================================

    def trade_morning_breath(self, state, result, data) -> None:
        product = "OXYGEN_SHAKE_MORNING_BREATH"

        if product not in state.order_depths:
            return

        depth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders = result[product]

        LIMIT = 10

        FAST_SPAN = 200
        SLOW_SPAN = 1000

        ALPHA_FAST = 2 / (FAST_SPAN + 1)
        ALPHA_SLOW = 2 / (SLOW_SPAN + 1)

        TREND_MULT = 3.0
        ENTRY_SIGNAL = 6.0
        EXIT_SIGNAL = 2.0
        TARGET_SCALE = 4.0

        MAX_TRADE_SIZE = 2

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        best_bid_volume = depth.buy_orders[best_bid]
        best_ask_volume = -depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        pdata = data.setdefault(product, {})

        if "fast_ema" not in pdata:
            pdata["fast_ema"] = mid
            pdata["slow_ema"] = mid
            pdata["target"] = 0

        fast_ema = pdata["fast_ema"]
        slow_ema = pdata["slow_ema"]
        old_target = pdata.get("target", 0)

        fast_ema = fast_ema + ALPHA_FAST * (mid - fast_ema)
        slow_ema = slow_ema + ALPHA_SLOW * (mid - slow_ema)

        pdata["fast_ema"] = fast_ema
        pdata["slow_ema"] = slow_ema

        trend = fast_ema - slow_ema
        signal = TREND_MULT * trend

        if signal > ENTRY_SIGNAL:
            target = int(1 + (signal - ENTRY_SIGNAL) / TARGET_SCALE)
            target = min(LIMIT, target)

        elif signal < -ENTRY_SIGNAL:
            target = -int(1 + (-signal - ENTRY_SIGNAL) / TARGET_SCALE)
            target = max(-LIMIT, target)

        elif abs(signal) < EXIT_SIGNAL:
            target = 0

        else:
            target = old_target

        pdata["target"] = target

        desired_change = target - position

        if desired_change > 0:
            buy_qty = min(
                desired_change,
                MAX_TRADE_SIZE,
                LIMIT - position,
                best_ask_volume,
            )

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))

        elif desired_change < 0:
            sell_qty = min(
                -desired_change,
                MAX_TRADE_SIZE,
                LIMIT + position,
                best_bid_volume,
            )

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
    # ============================================================
    # PEBBLES PACKAGE STRATEGY
    # ============================================================

    def trade_pebbles(self, state, result, data) -> None:

        info = {}

        # Need all 5 Pebbles visible.
        for product in self.PEBBLES:
            if product not in state.order_depths:
                return

            depth = state.order_depths[product]

            if not depth.buy_orders or not depth.sell_orders:
                return

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())

            if product not in result:
                result[product] = []

            info[product] = {
                "depth": depth,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "best_bid_volume": depth.buy_orders[best_bid],
                "best_ask_volume": -depth.sell_orders[best_ask],
                "mid": (best_bid + best_ask) / 2,
                "position": state.position.get(product, 0),
            }

        positions = {p: info[p]["position"] for p in self.PEBBLES}
        avg_position = sum(positions.values()) / len(self.PEBBLES)

        basket_mid = sum(info[p]["mid"] for p in self.PEBBLES)
        basket_error = basket_mid - self.BASKET_FAIR

        data["pebbles_basket_error"] = basket_error
        data["pebbles_avg_position"] = avg_position

        # ============================================================
        # 1. TRUE PACKAGE TAKE LOGIC
        # ============================================================

        best_ask_sum = sum(info[p]["best_ask"] for p in self.PEBBLES)
        best_bid_sum = sum(info[p]["best_bid"] for p in self.PEBBLES)

        take_buy_edge = self.BASKET_FAIR - best_ask_sum
        take_sell_edge = best_bid_sum - self.BASKET_FAIR

        buy_room = min(self.PEBBLES_LIMIT - positions[p] for p in self.PEBBLES)
        sell_room = min(self.PEBBLES_LIMIT + positions[p] for p in self.PEBBLES)

        max_take_buy_qty = min(
            self.TAKE_SIZE,
            buy_room,
            min(info[p]["best_ask_volume"] for p in self.PEBBLES),
        )

        max_take_sell_qty = min(
            self.TAKE_SIZE,
            sell_room,
            min(info[p]["best_bid_volume"] for p in self.PEBBLES),
        )

        # Buy full basket only when full ask package is cheap.
        if (
            take_buy_edge >= self.TAKE_EDGE
            and max_take_buy_qty > 0
            and avg_position < self.SOFT_LIMIT
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, info[product]["best_ask"], max_take_buy_qty)
                )
            return

        # Sell full basket only when full bid package is expensive.
        if (
            take_sell_edge >= self.TAKE_EDGE
            and max_take_sell_qty > 0
            and avg_position > -self.SOFT_LIMIT
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, info[product]["best_bid"], -max_take_sell_qty)
                )
            return

        # ============================================================
        # 2. PACKAGE PASSIVE QUOTING
        # ============================================================

        passive_bid_prices = {}
        passive_ask_prices = {}

        for product in self.PEBBLES:
            best_bid = info[product]["best_bid"]
            best_ask = info[product]["best_ask"]

            bid_price = best_bid + 1
            ask_price = best_ask - 1

            if bid_price >= best_ask:
                bid_price = best_bid

            if ask_price <= best_bid:
                ask_price = best_ask

            passive_bid_prices[product] = bid_price
            passive_ask_prices[product] = ask_price

        passive_bid_sum = sum(passive_bid_prices[p] for p in self.PEBBLES)
        passive_ask_sum = sum(passive_ask_prices[p] for p in self.PEBBLES)

        passive_buy_edge = self.BASKET_FAIR - passive_bid_sum
        passive_sell_edge = passive_ask_sum - self.BASKET_FAIR

        data["pebbles_passive_buy_edge"] = passive_buy_edge
        data["pebbles_passive_sell_edge"] = passive_sell_edge

        passive_buy_qty = min(self.PASSIVE_SIZE, buy_room)
        passive_sell_qty = min(self.PASSIVE_SIZE, sell_room)

        allow_passive_buy = avg_position < self.SOFT_LIMIT
        allow_passive_sell = avg_position > -self.SOFT_LIMIT

        if (
            passive_buy_edge >= self.PASSIVE_EDGE
            and passive_buy_qty > 0
            and allow_passive_buy
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, passive_bid_prices[product], passive_buy_qty)
                )

        if (
            passive_sell_edge >= self.PASSIVE_EDGE
            and passive_sell_qty > 0
            and allow_passive_sell
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, passive_ask_prices[product], -passive_sell_qty)
                )
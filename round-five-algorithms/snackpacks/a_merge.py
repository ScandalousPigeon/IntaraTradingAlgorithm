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

        self.trade_raspberry(state, result, data)
        self.trade_snackpack_strawberry(state, result, data)
        self.trade_vanilla(state, result, data)
        self.trade_chocolate(state, result, data)

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
    # SNACKPACK_RASPBERRY
    # Pair model using SNACKPACK_PISTACHIO
    # ============================================================

    def trade_raspberry(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict,
    ) -> None:

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

        store["ema"] = (
            EMA_ALPHA * raspberry_mid
            + (1 - EMA_ALPHA) * store["ema"]
        )

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
            qty = min(
                LIMIT - position,
                ask_vol,
                MAX_STEP,
            )

            if qty > 0:
                result[PRODUCT].append(Order(PRODUCT, best_ask, qty))
                position += qty

        elif best_bid > fair + ENTRY_EDGE and position > -LIMIT:
            qty = min(
                position + LIMIT,
                bid_vol,
                MAX_STEP,
            )

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

    # ============================================================
    # SNACKPACK_STRAWBERRY
    # Microprice / mean-reversion / passive MM
    # ============================================================

    def trade_snackpack_strawberry(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "SNACKPACK_STRAWBERRY"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

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

    # ============================================================
    # SNACKPACK_VANILLA
    # Pair model using SNACKPACK_CHOCOLATE
    # ============================================================

    def trade_vanilla(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

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

                s["next_sum_ema"] = (
                    (1 - SUM_ALPHA) * sum_ema
                    + SUM_ALPHA * pair_sum
                )

                s["next_mx"] = (
                    (1 - OLS_ALPHA) * mx
                    + OLS_ALPHA * ref_mid
                )

                s["next_my"] = (
                    (1 - OLS_ALPHA) * my
                    + OLS_ALPHA * mid
                )

                s["next_mxx"] = (
                    (1 - OLS_ALPHA) * mxx
                    + OLS_ALPHA * ref_mid * ref_mid
                )

                s["next_mxy"] = (
                    (1 - OLS_ALPHA) * mxy
                    + OLS_ALPHA * ref_mid * mid
                )

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
        s["vanilla_ema"] = (
            (1 - SUM_ALPHA) * vanilla_ema
            + SUM_ALPHA * mid
        )

        if "next_sum_ema" in s:
            s["sum_ema"] = s.pop("next_sum_ema")
            s["mx"] = s.pop("next_mx")
            s["my"] = s.pop("next_my")
            s["mxx"] = s.pop("next_mxx")
            s["mxy"] = s.pop("next_mxy")

        data[key] = s

    # ============================================================
    # SNACKPACK_CHOCOLATE
    # Slow EMA mean reversion
    # ============================================================

    def trade_chocolate(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

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

        depth: OrderDepth = state.order_depths[product]

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

        orders: List[Order] = result[product]

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
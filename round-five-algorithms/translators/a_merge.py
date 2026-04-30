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

        self.trade_translator_space_gray(state, result, data)
        self.trade_translator_astro_black(state, result, data)
        self.trade_translator_eclipse_charcoal(state, result, data)
        self.trade_graphite_mist(state, result, data)
        self.trade_void_blue(state, result, data)

        return result, 0, json.dumps(data)

    # ============================================================
    # SHARED MOMENTUM TEMPLATE
    # Used for SPACE_GRAY and ASTRO_BLACK
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

    def trade_translator_space_gray(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        self.trade_translator_momentum(
            state=state,
            result=result,
            data=data,
            product="TRANSLATOR_SPACE_GRAY",
            ema_alpha=0.20,
            entry_signal=50.0,
            max_clip=5,
            limit=10,
        )

    def trade_translator_astro_black(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        self.trade_translator_momentum(
            state=state,
            result=result,
            data=data,
            product="TRANSLATOR_ASTRO_BLACK",
            ema_alpha=0.20,
            entry_signal=50.0,
            max_clip=5,
            limit=10,
        )

    # ============================================================
    # TRANSLATOR_ECLIPSE_CHARCOAL
    # Passive market-making / fair value strategy
    # ============================================================

    def trade_translator_eclipse_charcoal(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "TRANSLATOR_ECLIPSE_CHARCOAL"
        limit = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

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

    # ============================================================
    # TRANSLATOR_GRAPHITE_MIST
    # Microprice / slow reversion / passive MM
    # ============================================================

    def trade_graphite_mist(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        product = "TRANSLATOR_GRAPHITE_MIST"
        limit = 10

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders: List[Order] = result[product]
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

        # Aggressive taking
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

        # Passive market-making
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

    # ============================================================
    # TRANSLATOR_VOID_BLUE
    # EMA reversion + microprice
    # ============================================================

    def trade_void_blue(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

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

        depth: OrderDepth = state.order_depths[product]

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

        orders: List[Order] = result[product]

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
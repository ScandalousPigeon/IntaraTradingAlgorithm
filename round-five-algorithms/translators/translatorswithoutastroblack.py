from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    # Shared position limits
    TRANSLATOR_LIMIT = 10

    # === TRANSLATOR_VOID_BLUE constants ===
    VOID_BLUE = "TRANSLATOR_VOID_BLUE"
    VOID_EMA_ALPHA = 0.02
    VOID_REVERSION_STRENGTH = 0.20
    VOID_MICRO_WEIGHT = 0.30
    VOID_BASE_EDGE = 7.0
    VOID_VOL_EDGE = 0.15
    VOID_INV_SKEW = 0.80
    VOID_MAX_TAKE_SIZE = 4

    # === TRANSLATOR_GRAPHITE_MIST constants ===
    GRAPHITE_MIST = "TRANSLATOR_GRAPHITE_MIST"

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_translator_eclipse_charcoal(state, result, data)
        self.trade_translator_space_gray(state, result, data)
        self.trade_translator_void_blue(state, result, data)
        self.trade_translator_graphite_mist(state, result, data)

        return result, 0, json.dumps(data)

    # ============================================================
    # TRANSLATOR_ECLIPSE_CHARCOAL
    # ============================================================

    def trade_translator_eclipse_charcoal(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:
        PRODUCT = "TRANSLATOR_ECLIPSE_CHARCOAL"
        LIMIT = 10

        if PRODUCT not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[PRODUCT]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[PRODUCT]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_vol = abs(order_depth.buy_orders[best_bid])
        ask_vol = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(PRODUCT, 0)

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

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        buy_price = min(best_bid + 1, math.floor(fair - edge))
        sell_price = max(best_ask - 1, math.ceil(fair + edge))

        buy_price = min(buy_price, best_ask - 1)
        sell_price = max(sell_price, best_bid + 1)

        if buy_price >= sell_price:
            buy_price = best_bid
            sell_price = best_ask

        buy_size = 1
        sell_size = 1

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
            orders.append(Order(PRODUCT, int(buy_price), int(buy_size)))

        if sell_size > 0:
            orders.append(Order(PRODUCT, int(sell_price), -int(sell_size)))

        d["prev_mid"] = mid
        d["fast"] = fast
        d["slow"] = slow
        d["vol"] = vol

    # ============================================================
    # TRANSLATOR_SPACE_GRAY
    # ============================================================

    def trade_translator_space_gray(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:
        PRODUCT = "TRANSLATOR_SPACE_GRAY"

        if PRODUCT not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[PRODUCT]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        LIMIT = 10
        EMA_ALPHA = 0.20
        ENTRY_SIGNAL = 50.0
        MAX_CLIP = 5

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        position = state.position.get(PRODUCT, 0)

        product_data = data.setdefault(PRODUCT, {})

        if "ema" not in product_data or state.timestamp == 0:
            product_data["ema"] = mid

        ema = product_data["ema"]

        signal = mid - ema

        orders: List[Order] = result[PRODUCT]

        target_position = position

        if signal > ENTRY_SIGNAL:
            target_position = LIMIT
        elif signal < -ENTRY_SIGNAL:
            target_position = -LIMIT

        if position < target_position:
            buy_qty = min(
                target_position - position,
                LIMIT - position,
                MAX_CLIP,
                best_ask_volume
            )

            if buy_qty > 0:
                orders.append(Order(PRODUCT, best_ask, buy_qty))

        elif position > target_position:
            sell_qty = min(
                position - target_position,
                LIMIT + position,
                MAX_CLIP,
                best_bid_volume
            )

            if sell_qty > 0:
                orders.append(Order(PRODUCT, best_bid, -sell_qty))

        product_data["ema"] = (1 - EMA_ALPHA) * ema + EMA_ALPHA * mid

    # ============================================================
    # TRANSLATOR_VOID_BLUE
    # ============================================================

    def trade_translator_void_blue(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:
        product = self.VOID_BLUE

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
        s["ema"] = self.VOID_EMA_ALPHA * mid + (1 - self.VOID_EMA_ALPHA) * s["ema"]
        s["last_mid"] = mid

        ema = s["ema"]
        absret = s["absret"]

        if bid_qty + ask_qty > 0:
            microprice = (best_ask * bid_qty + best_bid * ask_qty) / (bid_qty + ask_qty)
        else:
            microprice = mid

        micro_dev = microprice - mid

        fair = mid - self.VOID_REVERSION_STRENGTH * (mid - ema)
        fair += self.VOID_MICRO_WEIGHT * micro_dev
        fair -= self.VOID_INV_SKEW * position

        edge = self.VOID_BASE_EDGE + self.VOID_VOL_EDGE * absret

        orders: List[Order] = result[product]

        if best_ask <= fair - edge and position < self.TRANSLATOR_LIMIT:
            buy_size = min(
                ask_qty,
                self.VOID_MAX_TAKE_SIZE,
                self.TRANSLATOR_LIMIT - position,
            )

            if buy_size > 0:
                orders.append(Order(product, best_ask, buy_size))
                position += buy_size

        original_position = state.position.get(product, 0)
        fair_after_buy = fair - self.VOID_INV_SKEW * (position - original_position)

        if best_bid >= fair_after_buy + edge and position > -self.TRANSLATOR_LIMIT:
            sell_size = min(
                bid_qty,
                self.VOID_MAX_TAKE_SIZE,
                self.TRANSLATOR_LIMIT + position,
            )

            if sell_size > 0:
                orders.append(Order(product, best_bid, -sell_size))
                position -= sell_size

    # ============================================================
    # TRANSLATOR_GRAPHITE_MIST
    # ============================================================

    def trade_translator_graphite_mist(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:
        product = self.GRAPHITE_MIST

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
                "last_mid": mid
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
        if pos < self.TRANSLATOR_LIMIT:
            for ask_price in sorted(depth.sell_orders.keys()):
                ask_vol = -depth.sell_orders[ask_price]

                if ask_price <= fair - take_edge:
                    qty = min(ask_vol, 2, self.TRANSLATOR_LIMIT - pos)

                    if qty > 0:
                        orders.append(Order(product, ask_price, qty))
                        pos += qty
                else:
                    break

                if pos >= self.TRANSLATOR_LIMIT:
                    break

        if pos > -self.TRANSLATOR_LIMIT:
            for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
                bid_vol = depth.buy_orders[bid_price]

                if bid_price >= fair + take_edge:
                    qty = min(bid_vol, 2, self.TRANSLATOR_LIMIT + pos)

                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty))
                        pos -= qty
                else:
                    break

                if pos <= -self.TRANSLATOR_LIMIT:
                    break

        # Passive market making
        buy_capacity = self.TRANSLATOR_LIMIT - pos
        sell_capacity = self.TRANSLATOR_LIMIT + pos

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
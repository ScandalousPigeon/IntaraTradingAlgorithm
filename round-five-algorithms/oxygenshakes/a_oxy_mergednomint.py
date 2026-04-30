from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    LIMIT = 10

    CHOCOLATE = "OXYGEN_SHAKE_CHOCOLATE"
    EVENING_BREATH = "OXYGEN_SHAKE_EVENING_BREATH"
    GARLIC = "OXYGEN_SHAKE_GARLIC"
    MORNING_BREATH = "OXYGEN_SHAKE_MORNING_BREATH"

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_chocolate(state, result, data)
        self.trade_evening_breath(state, result, data)
        self.trade_garlic(state, result)
        self.trade_morning_breath(state, result, data)

        return result, 0, json.dumps(data)

    # ----------------------------------------------------------------------
    # OXYGEN_SHAKE_CHOCOLATE
    # ----------------------------------------------------------------------

    def trade_chocolate(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:
        product = self.CHOCOLATE

        LIMIT = 10
        ORDER_SIZE = 10

        EMA_SPAN = 800
        ENTRY_EDGE = 220
        EXIT_EDGE = 10

        STOP_LOSS = 350
        COOLDOWN_TICKS = 3

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

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
        orders: List[Order] = []

        if position == 0:
            entry_mid = None

        # Stop-loss protection
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

        # Mean-reversion entries
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

        # Exit after reversion
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

        result[product] = orders

    # ----------------------------------------------------------------------
    # OXYGEN_SHAKE_EVENING_BREATH
    # ----------------------------------------------------------------------

    def trade_evening_breath(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:
        product = self.EVENING_BREATH
        LIMIT = 10

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders: List[Order] = result[product]

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
            micro = (best_ask * bid_vol + best_bid * ask_vol) / (bid_vol + ask_vol)
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

        for ask_price in sorted(depth.sell_orders.keys()):
            if buy_cap <= 0:
                break

            ask_qty = abs(depth.sell_orders[ask_price])

            if ask_price <= fair - TAKE_EDGE:
                add_buy(ask_price, min(TAKE_SIZE, ask_qty))
            else:
                break

        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if sell_cap <= 0:
                break

            bid_qty = abs(depth.buy_orders[bid_price])

            if bid_price >= fair + TAKE_EDGE:
                add_sell(bid_price, min(TAKE_SIZE, bid_qty))
            else:
                break

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

    # ----------------------------------------------------------------------
    # OXYGEN_SHAKE_GARLIC
    # ----------------------------------------------------------------------

    def trade_garlic(
        self,
        state: TradingState,
        result: Dict[str, List[Order]]
    ) -> None:
        product = self.GARLIC
        LIMIT = 10

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.sell_orders or not depth.buy_orders:
            return

        orders: List[Order] = result[product]

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

    # ----------------------------------------------------------------------
    # OXYGEN_SHAKE_MORNING_BREATH
    # ----------------------------------------------------------------------

    def trade_morning_breath(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:
        product = self.MORNING_BREATH

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders: List[Order] = result[product]

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
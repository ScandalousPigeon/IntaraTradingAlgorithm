from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "OXYGEN_SHAKE_CHOCOLATE"

    LIMIT = 10
    ORDER_SIZE = 10

    # Tuned from days 2, 3, 4
    EMA_SPAN = 800
    ENTRY_EDGE = 220
    EXIT_EDGE = 10

    # Protection against catching a huge trend too early
    STOP_LOSS = 350
    COOLDOWN_TICKS = 3

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_chocolate(state, result, data)

        return result, 0, json.dumps(data)

    def trade_chocolate(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

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

        alpha = 2 / (self.EMA_SPAN + 1)
        ema = mem.get("ema", mid)
        ema = alpha * mid + (1 - alpha) * ema
        mem["ema"] = ema

        entry_mid = mem.get("entry_mid", None)
        cooldown = mem.get("cooldown", 0)

        if cooldown > 0:
            cooldown -= 1

        dev = mid - ema
        orders: List[Order] = []

        # Reset entry tracking if flat
        if position == 0:
            entry_mid = None

        # Stop-loss protection
        if entry_mid is not None and position != 0:
            if position > 0 and mid < entry_mid - self.STOP_LOSS:
                sell_qty = min(position, best_bid_volume)
                if sell_qty > 0:
                    orders.append(Order(product, best_bid, -sell_qty))
                    position -= sell_qty
                    cooldown = self.COOLDOWN_TICKS
                    if position == 0:
                        entry_mid = None

            elif position < 0 and mid > entry_mid + self.STOP_LOSS:
                buy_qty = min(-position, best_ask_volume)
                if buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))
                    position += buy_qty
                    cooldown = self.COOLDOWN_TICKS
                    if position == 0:
                        entry_mid = None

        # Main signal:
        # price far below EMA -> buy
        # price far above EMA -> sell
        if cooldown == 0:
            if dev < -self.ENTRY_EDGE and position < self.LIMIT:
                buy_qty = min(
                    self.ORDER_SIZE,
                    self.LIMIT - position,
                    best_ask_volume,
                )

                if buy_qty > 0:
                    if position == 0:
                        entry_mid = mid
                    orders.append(Order(product, best_ask, buy_qty))
                    position += buy_qty

            elif dev > self.ENTRY_EDGE and position > -self.LIMIT:
                sell_qty = min(
                    self.ORDER_SIZE,
                    self.LIMIT + position,
                    best_bid_volume,
                )

                if sell_qty > 0:
                    if position == 0:
                        entry_mid = mid
                    orders.append(Order(product, best_bid, -sell_qty))
                    position -= sell_qty

        # Exit when price has reverted close to EMA
        if position > 0 and dev > -self.EXIT_EDGE:
            sell_qty = min(position, best_bid_volume)

            if sell_qty > 0:
                orders.append(Order(product, best_bid, -sell_qty))
                position -= sell_qty
                if position == 0:
                    entry_mid = None
                    cooldown = self.COOLDOWN_TICKS

        elif position < 0 and dev < self.EXIT_EDGE:
            buy_qty = min(-position, best_ask_volume)

            if buy_qty > 0:
                orders.append(Order(product, best_ask, buy_qty))
                position += buy_qty
                if position == 0:
                    entry_mid = None
                    cooldown = self.COOLDOWN_TICKS

        mem["entry_mid"] = entry_mid
        mem["cooldown"] = cooldown
        data[key] = mem

        result[product] = orders
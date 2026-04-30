from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    PRODUCT = "TRANSLATOR_VOID_BLUE"
    LIMIT = 10

    # Tuned from round 5 day 2-4 behaviour
    EMA_ALPHA = 0.02
    REVERSION_STRENGTH = 0.20
    MICRO_WEIGHT = 0.30

    BASE_EDGE = 7.0
    VOL_EDGE = 0.15
    INV_SKEW = 0.80

    MAX_TAKE_SIZE = 4

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        data = json.loads(state.traderData) if state.traderData else {}

        self.trade_void_blue(state, result, data)

        return result, 0, json.dumps(data)

    def trade_void_blue(self, state: TradingState, result: Dict[str, List[Order]], data: dict):
        product = self.PRODUCT

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
        spread = best_ask - best_bid

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
        s["ema"] = self.EMA_ALPHA * mid + (1 - self.EMA_ALPHA) * s["ema"]
        s["last_mid"] = mid

        ema = s["ema"]
        absret = s["absret"]

        # Microprice leans towards the side with more volume.
        if bid_qty + ask_qty > 0:
            microprice = (best_ask * bid_qty + best_bid * ask_qty) / (bid_qty + ask_qty)
        else:
            microprice = mid

        micro_dev = microprice - mid

        # If price is far above EMA, fair is pulled down.
        # If price is far below EMA, fair is pulled up.
        fair = mid - self.REVERSION_STRENGTH * (mid - ema)
        fair += self.MICRO_WEIGHT * micro_dev

        # Inventory skew: if long, lower fair so we sell sooner.
        # If short, raise fair so we buy back sooner.
        fair -= self.INV_SKEW * position

        edge = self.BASE_EDGE + self.VOL_EDGE * absret

        orders: List[Order] = []

        # Buy when ask is meaningfully below fair.
        if best_ask <= fair - edge and position < self.LIMIT:
            buy_size = min(
                ask_qty,
                self.MAX_TAKE_SIZE,
                self.LIMIT - position,
            )

            if buy_size > 0:
                orders.append(Order(product, best_ask, buy_size))
                position += buy_size

        # Recalculate fair after possible buy inventory change.
        fair_after_buy = fair - self.INV_SKEW * (position - state.position.get(product, 0))

        # Sell when bid is meaningfully above fair.
        if best_bid >= fair_after_buy + edge and position > -self.LIMIT:
            sell_size = min(
                bid_qty,
                self.MAX_TAKE_SIZE,
                self.LIMIT + position,
            )

            if sell_size > 0:
                orders.append(Order(product, best_bid, -sell_size))
                position -= sell_size

        result[product] = orders
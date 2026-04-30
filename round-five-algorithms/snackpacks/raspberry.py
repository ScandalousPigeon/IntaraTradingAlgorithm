from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "SNACKPACK_RASPBERRY"
    HEDGE_PRODUCT = "SNACKPACK_PISTACHIO"

    LIMIT = 10

    # Historical fair model:
    # RASPBERRY fair ~= 14355.3001 - 0.450459 * PISTACHIO_mid
    PAIR_INTERCEPT = 14355.3001
    PAIR_BETA = -0.450459

    # Blend pair fair with own slow EMA
    PAIR_WEIGHT = 0.75
    EMA_ALPHA = 0.001

    WARMUP = 120

    # Only trade large dislocations because spread is often wide.
    ENTRY_EDGE = 120
    EXIT_EDGE = 3

    MAX_SPREAD = 14
    MAX_STEP = 10

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_raspberry(state, result, data)

        return result, 0, json.dumps(data)

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

    def trade_raspberry(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict,
    ) -> None:

        if self.PRODUCT not in state.order_depths:
            return

        depth = state.order_depths[self.PRODUCT]
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
            self.EMA_ALPHA * raspberry_mid
            + (1 - self.EMA_ALPHA) * store["ema"]
        )
        store["n"] += 1

        if store["n"] < self.WARMUP:
            return

        # Pair fair from Pistachio if available
        pair_fair = None
        if self.HEDGE_PRODUCT in state.order_depths:
            pistachio_mid = self.mid_price(state.order_depths[self.HEDGE_PRODUCT])
            if pistachio_mid is not None:
                pair_fair = self.PAIR_INTERCEPT + self.PAIR_BETA * pistachio_mid

        # Fallback to own EMA if Pistachio is missing
        if pair_fair is None:
            fair = store["ema"]
        else:
            fair = self.PAIR_WEIGHT * pair_fair + (1 - self.PAIR_WEIGHT) * store["ema"]

        position = state.position.get(self.PRODUCT, 0)

        # Avoid donating edge in wide books
        if spread > self.MAX_SPREAD:
            return

        # Buy when Raspberry is much cheaper than relative fair
        if best_ask < fair - self.ENTRY_EDGE and position < self.LIMIT:
            qty = min(
                self.LIMIT - position,
                ask_vol,
                self.MAX_STEP,
            )
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_ask, qty))
                position += qty

        # Sell when Raspberry is much richer than relative fair
        elif best_bid > fair + self.ENTRY_EDGE and position > -self.LIMIT:
            qty = min(
                position + self.LIMIT,
                bid_vol,
                self.MAX_STEP,
            )
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_bid, -qty))
                position -= qty

        # Exit long when price has mean-reverted near fair
        if position > 0 and best_bid >= fair - self.EXIT_EDGE:
            qty = min(position, bid_vol, self.MAX_STEP)
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_bid, -qty))
                position -= qty

        # Exit short when price has mean-reverted near fair
        elif position < 0 and best_ask <= fair + self.EXIT_EDGE:
            qty = min(-position, ask_vol, self.MAX_STEP)
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_ask, qty))
                position += qty
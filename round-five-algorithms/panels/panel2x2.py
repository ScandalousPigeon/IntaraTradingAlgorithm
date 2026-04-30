from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "PANEL_2X2"

    LIMIT = 10

    # Long rolling fair-value mean reversion
    WINDOW = 1000
    WARMUP = 120

    # Enter only when price is far from fair.
    ENTRY_EDGE = 70

    # Exit when it mean-reverts close to fair.
    EXIT_EDGE = 3

    # Avoid bad/wide books.
    MAX_SPREAD = 12

    # Max quantity to move per tick.
    MAX_STEP = 10

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_panel_2x2(state, result, data)

        return result, 0, json.dumps(data)

    def trade_panel_2x2(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        hist_key = product + "_hist"
        target_key = product + "_target"

        hist = data.get(hist_key, [])
        hist.append(mid)

        if len(hist) > self.WINDOW:
            hist = hist[-self.WINDOW:]

        data[hist_key] = hist

        if len(hist) < self.WARMUP:
            data[target_key] = 0
            return

        fair = sum(hist) / len(hist)
        dev = mid - fair

        target = int(data.get(target_key, 0))

        # Hysteresis target logic:
        # dev < 0 means price is below fair, so we want to buy.
        # dev > 0 means price is above fair, so we want to sell.
        if target == 0:
            if dev <= -self.ENTRY_EDGE:
                target = self.LIMIT
            elif dev >= self.ENTRY_EDGE:
                target = -self.LIMIT

        elif target > 0:
            # Long: exit when price comes back near fair.
            if dev >= -self.EXIT_EDGE:
                target = 0

            # Flip short if it overshoots high.
            if dev >= self.ENTRY_EDGE:
                target = -self.LIMIT

        elif target < 0:
            # Short: exit when price comes back near fair.
            if dev <= self.EXIT_EDGE:
                target = 0

            # Flip long if it overshoots low.
            if dev <= -self.ENTRY_EDGE:
                target = self.LIMIT

        data[target_key] = target

        if spread > self.MAX_SPREAD:
            return

        position = state.position.get(product, 0)

        if target > position:
            self.buy_towards_target(product, order_depth, result, position, target)

        elif target < position:
            self.sell_towards_target(product, order_depth, result, position, target)

    def buy_towards_target(
        self,
        product: str,
        order_depth: OrderDepth,
        result: Dict[str, List[Order]],
        position: int,
        target: int,
    ) -> None:
        need = min(target - position, self.LIMIT - position, self.MAX_STEP)

        if need <= 0:
            return

        for ask_price in sorted(order_depth.sell_orders.keys()):
            ask_volume = order_depth.sell_orders[ask_price]

            # IMC sell volumes are normally negative.
            available = -ask_volume if ask_volume < 0 else ask_volume

            qty = min(need, available)

            if qty > 0:
                result[product].append(Order(product, ask_price, qty))
                need -= qty

            if need <= 0:
                break

    def sell_towards_target(
        self,
        product: str,
        order_depth: OrderDepth,
        result: Dict[str, List[Order]],
        position: int,
        target: int,
    ) -> None:
        need = min(position - target, self.LIMIT + position, self.MAX_STEP)

        if need <= 0:
            return

        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            bid_volume = order_depth.buy_orders[bid_price]

            # IMC buy volumes are normally positive.
            available = bid_volume if bid_volume > 0 else -bid_volume

            qty = min(need, available)

            if qty > 0:
                result[product].append(Order(product, bid_price, -qty))
                need -= qty

            if need <= 0:
                break
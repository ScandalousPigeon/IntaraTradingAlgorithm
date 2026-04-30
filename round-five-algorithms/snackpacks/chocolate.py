from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "SNACKPACK_CHOCOLATE"

    # Assumed position limit. Lower this to 50 if your backtester says limit exceeded.
    LIMIT = 100

    # Very slow EMA because chocolate drifts but also mean-reverts from large extremes.
    ALPHA = 0.0002
    WARMUP = 500

    # Only enter when price is very far from slow fair.
    ENTRY_EDGE = 120

    # Exit once price has reverted back close to fair.
    EXIT_EDGE = 0

    # Chocolate usually has spread around 16-17, so avoid only very bad books.
    MAX_SPREAD = 20

    # Small step prevents instantly maxing out at bad prices.
    MAX_STEP = 1

    # Small inventory skew to avoid leaning too hard in one direction.
    POSITION_SKEW = 0.05

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_chocolate(state, result, data)

        return result, 0, json.dumps(data)

    def trade_chocolate(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict,
    ) -> None:

        product = self.PRODUCT

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
        ema = (1 - self.ALPHA) * ema + self.ALPHA * mid

        product_data["ema"] = ema
        product_data["ticks"] = ticks + 1

        if ticks < self.WARMUP:
            return

        if spread > self.MAX_SPREAD:
            return

        position = state.position.get(product, 0)

        # Inventory-adjusted fair value.
        # If long, fair is pulled down, discouraging more buys.
        # If short, fair is pulled up, discouraging more sells.
        fair = ema - self.POSITION_SKEW * position

        orders: List[Order] = []

        def buy(qty: int, price: int) -> None:
            nonlocal position
            qty = min(qty, self.LIMIT - position)
            if qty > 0:
                orders.append(Order(product, price, qty))
                position += qty

        def sell(qty: int, price: int) -> None:
            nonlocal position
            qty = min(qty, self.LIMIT + position)
            if qty > 0:
                orders.append(Order(product, price, -qty))
                position -= qty

        # 1. Exit first when price mean-reverts back to fair.
        if position < 0 and best_ask <= fair + self.EXIT_EDGE:
            buy_qty = min(self.MAX_STEP, ask_volume, -position)
            buy(buy_qty, best_ask)

        if position > 0 and best_bid >= fair - self.EXIT_EDGE:
            sell_qty = min(self.MAX_STEP, bid_volume, position)
            sell(sell_qty, best_bid)

        # 2. Enter only on large deviations.
        if best_ask <= fair - self.ENTRY_EDGE:
            buy_qty = min(self.MAX_STEP, ask_volume)
            buy(buy_qty, best_ask)

        if best_bid >= fair + self.ENTRY_EDGE:
            sell_qty = min(self.MAX_STEP, bid_volume)
            sell(sell_qty, best_bid)

        result[product] = orders
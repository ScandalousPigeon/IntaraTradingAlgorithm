from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "ROBOT_LAUNDRY"

    LIMIT = 10

    # Slow fair-value tracker. ROBOT_LAUNDRY trends too much for a fixed fair.
    EMA_ALPHA = 0.01

    # Wait for a large deviation from EMA before crossing the spread.
    ENTRY_EDGE = 120

    # Avoid trading during the first few ticks while EMA is being initialized.
    WARMUP_TICKS = 120

    # Product normally has spread around 7-8. Wider than this is probably bad.
    MAX_SPREAD = 10

    # Maximum quantity to take in one tick.
    MAX_STEP = 10

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_robot_laundry(state, result, data)

        return result, 0, json.dumps(data)

    def trade_robot_laundry(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_volume = abs(order_depth.buy_orders[best_bid])
        ask_volume = abs(order_depth.sell_orders[best_ask])

        spread = best_ask - best_bid
        if spread > self.MAX_SPREAD:
            return

        mid = (best_bid + best_ask) / 2
        position = state.position.get(product, 0)

        product_data = data.get(product, {})

        # Reset if the timestamp goes backwards, which can happen between separate backtest days.
        last_timestamp = product_data.get("last_timestamp", None)
        if last_timestamp is not None and state.timestamp < last_timestamp:
            product_data = {}

        ema = product_data.get("ema", mid)
        ticks = product_data.get("ticks", 0)

        orders: List[Order] = result[product]

        # Important: use the previous EMA as fair, then update after decisions.
        fair = ema

        if ticks >= self.WARMUP_TICKS:
            # Buy if the current ask is deeply undervalued versus slow EMA.
            if best_ask <= fair - self.ENTRY_EDGE and position < self.LIMIT:
                buy_qty = min(
                    self.MAX_STEP,
                    ask_volume,
                    self.LIMIT - position
                )

                if buy_qty > 0:
                    orders.append(Order(product, best_ask, buy_qty))
                    position += buy_qty

            # Sell if the current bid is deeply overvalued versus slow EMA.
            if best_bid >= fair + self.ENTRY_EDGE and position > -self.LIMIT:
                sell_qty = min(
                    self.MAX_STEP,
                    bid_volume,
                    position + self.LIMIT
                )

                if sell_qty > 0:
                    orders.append(Order(product, best_bid, -sell_qty))
                    position -= sell_qty

        # Update EMA after trading logic.
        ema = (1 - self.EMA_ALPHA) * ema + self.EMA_ALPHA * mid

        product_data["ema"] = ema
        product_data["ticks"] = ticks + 1
        product_data["last_timestamp"] = state.timestamp

        data[product] = product_data
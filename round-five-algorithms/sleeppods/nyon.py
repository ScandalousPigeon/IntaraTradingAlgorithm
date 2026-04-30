from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "SLEEP_POD_NYLON"
    LIMIT = 10

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_sleep_pod_nylon_v3(state, result, data)

        return result, 0, json.dumps(data)

    def trade_sleep_pod_nylon_v3(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        position = state.position.get(product, 0)

        key = "nylon_v3_breakout"

        if key not in data:
            data[key] = {
                "mids": [],
                "entry_price": None,
                "cooldown": 0,
            }

        mem = data[key]

        mids = mem.get("mids", [])
        mids.append(mid)

        if len(mids) > 230:
            mids = mids[-230:]

        mem["mids"] = mids

        if mem.get("cooldown", 0) > 0:
            mem["cooldown"] -= 1

        # Not enough history yet.
        if len(mids) < 205:
            result[product] = orders
            return

        # 200-tick breakout signal.
        # Nylon is too noisy for short-window signals.
        momentum_200 = mid - mids[-201]

        # Recent momentum used only as a sanity check.
        momentum_50 = mid - mids[-51]

        ENTRY_MOMENTUM = 250
        EXIT_MOMENTUM = -50
        STOP_LOSS = 80

        MAX_SPREAD = 10

        # Track entry price once we actually have a long position.
        if position > 0 and mem.get("entry_price") is None:
            mem["entry_price"] = mid

        if position <= 0:
            mem["entry_price"] = None

        entry_price = mem.get("entry_price")

        def buy(price: int, quantity: int) -> None:
            quantity = int(min(quantity, self.LIMIT - position))

            if quantity > 0:
                orders.append(Order(product, price, quantity))

        def sell(price: int, quantity: int) -> None:
            quantity = int(min(quantity, self.LIMIT + position))

            if quantity > 0:
                orders.append(Order(product, price, -quantity))

        # Exit logic first.
        if position > 0:
            should_exit = False

            # Breakout failed.
            if entry_price is not None and mid < entry_price - STOP_LOSS:
                should_exit = True
                mem["cooldown"] = 60

            # Long-term momentum died.
            if momentum_200 < EXIT_MOMENTUM:
                should_exit = True

            # Short-term dump after entry.
            if momentum_50 < -120:
                should_exit = True
                mem["cooldown"] = 40

            if should_exit:
                sell(best_bid, min(position, best_bid_volume))
                result[product] = orders
                return

        # Entry logic.
        # V3 only trades strong upside continuation.
        if (
            position == 0
            and mem.get("cooldown", 0) == 0
            and spread <= MAX_SPREAD
            and momentum_200 > ENTRY_MOMENTUM
            and momentum_50 > 20
        ):
            buy(best_ask, min(self.LIMIT, best_ask_volume))
            mem["entry_price"] = mid

        result[product] = orders
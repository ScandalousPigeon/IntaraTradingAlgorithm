from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    PRODUCT = "TRANSLATOR_ASTRO_BLACK"
    LIMIT = 10

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_astro_black(state, result, data)

        return result, 0, json.dumps(data)

    def trade_translator_space_gray(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        PRODUCT = "TRANSLATOR_SPACE_GRAY"

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_vol = depth.buy_orders[best_bid]
        ask_vol = abs(depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        stats = data.setdefault("astro_black", {})

        if "fast" not in stats:
            stats["fast"] = mid
            stats["slow"] = mid
            stats["ema"] = mid
            stats["prev_mid"] = mid
            stats["vol"] = 0.0

        prev_mid = stats["prev_mid"]

        # Fast/slow EMAs for a small trend-following adjustment.
        stats["fast"] = 0.75 * stats["fast"] + 0.25 * mid
        stats["slow"] = 0.97 * stats["slow"] + 0.03 * mid
        stats["ema"] = 0.95 * stats["ema"] + 0.05 * mid

        recent_move = mid - prev_mid
        stats["vol"] = 0.95 * stats["vol"] + 0.05 * abs(recent_move)
        stats["prev_mid"] = mid

        momentum = stats["fast"] - stats["slow"]

        # Keep fair close to current mid. Astro Black trends too much to anchor hard to long EMA.
        fair = mid + 0.10 * momentum

        # Inventory skew: if long, lower our reservation price to encourage selling.
        # If short, raise it to encourage buying.
        reservation_price = fair - 0.50 * position

        orders: List[Order] = []

        # -------------------------
        # 1. Take clearly good prices
        # -------------------------
        TAKE_EDGE = 7
        TAKE_SIZE = 3

        pos_after_take = position

        if best_ask <= fair - TAKE_EDGE and pos_after_take < self.LIMIT:
            qty = min(TAKE_SIZE, ask_vol, self.LIMIT - pos_after_take)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                pos_after_take += qty

        if best_bid >= fair + TAKE_EDGE and pos_after_take > -self.LIMIT:
            qty = min(TAKE_SIZE, bid_vol, self.LIMIT + pos_after_take)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                pos_after_take -= qty

        # -------------------------
        # 2. Main market-making logic
        # -------------------------
        # Historical spread is usually 8-9, so quote when spread is wide enough.
        MIN_SPREAD = 8
        QUOTE_EDGE = 1
        BASE_SIZE = 2

        if spread >= MIN_SPREAD:
            bid_price = min(best_bid, math.floor(reservation_price - QUOTE_EDGE))
            ask_price = max(best_ask, math.ceil(reservation_price + QUOTE_EDGE))

            # Safety check: never cross ourselves.
            if bid_price < ask_price:
                buy_size = BASE_SIZE
                sell_size = BASE_SIZE

                # If inventory is already leaning one way, reduce the order that worsens it.
                if pos_after_take > 3:
                    buy_size = 1
                if pos_after_take < -3:
                    sell_size = 1

                # Hard stop near the limits.
                if pos_after_take >= 8:
                    buy_size = 0
                if pos_after_take <= -8:
                    sell_size = 0

                buy_size = min(buy_size, self.LIMIT - pos_after_take)
                sell_size = min(sell_size, self.LIMIT + pos_after_take)

                if buy_size > 0:
                    orders.append(Order(product, bid_price, buy_size))

                if sell_size > 0:
                    orders.append(Order(product, ask_price, -sell_size))

        result[product] = orders
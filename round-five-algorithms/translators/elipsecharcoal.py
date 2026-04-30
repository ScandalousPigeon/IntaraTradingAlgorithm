from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        data = json.loads(state.traderData) if state.traderData else {}

        self.trade_translator_eclipse_charcoal(state, result, data)

        return result, 0, json.dumps(data)

    def trade_translator_eclipse_charcoal(self, state: TradingState, result: Dict, data: Dict) -> None:
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

        # Fast and slow EMAs.
        fast = 0.35 * mid + 0.65 * fast
        slow = 0.03 * mid + 0.97 * slow

        # Realised volatility estimate.
        vol = 0.93 * vol + 0.07 * abs(ret)

        trend = fast - slow

        if bid_vol + ask_vol > 0:
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        else:
            imbalance = 0

        # Fair value:
        # - current mid anchors us
        # - small trend lean
        # - tiny book imbalance lean
        # - strong inventory skew
        fair = (
            mid
            + 0.50 * trend
            + 0.75 * spread * imbalance
            - 1.00 * position
        )

        # Conservative edge. This product is jumpy, so do not quote too tight.
        edge = 5

        if vol > 12:
            edge = 6
        elif vol < 6 and spread >= 9:
            edge = 4

        # Only market-make when there is enough spread to capture.
        if spread < 6:
            d["prev_mid"] = mid
            d["fast"] = fast
            d["slow"] = slow
            d["vol"] = vol
            return

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # Passive inside-spread quotes.
        buy_price = min(best_bid + 1, math.floor(fair - edge))
        sell_price = max(best_ask - 1, math.ceil(fair + edge))

        # Never cross the spread accidentally.
        buy_price = min(buy_price, best_ask - 1)
        sell_price = max(sell_price, best_bid + 1)

        # Avoid inverted quotes.
        if buy_price >= sell_price:
            buy_price = best_bid
            sell_price = best_ask

        BASE_SIZE = 1

        buy_size = BASE_SIZE
        sell_size = BASE_SIZE

        # If short, prioritise buying back.
        if position <= -4:
            buy_size = 2
            sell_size = 1

        # If long, prioritise selling down.
        elif position >= 4:
            buy_size = 1
            sell_size = 2

        # Hard inventory protection near limits.
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
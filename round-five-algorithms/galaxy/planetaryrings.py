from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):
        result = {}

        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_planetary_rings(state, result, data)

        return result, 0, json.dumps(data)

    def trade_planetary_rings(self, state: TradingState, result: dict, data: dict) -> None:
        product = "GALAXY_SOUNDS_PLANETARY_RINGS"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        LIMIT = 10

        position = state.position.get(product, 0)

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        # =========================
        # ADAPTIVE FAIR VALUE
        # =========================
        key = "planetary_rings"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "vol": 10.0,
                "last_mid": mid
            }

        product_data = data[key]

        fast = product_data["fast"]
        slow = product_data["slow"]
        vol = product_data["vol"]
        last_mid = product_data["last_mid"]

        # Slow trend-following EMAs.
        # Planetary Rings trends over long windows, so these are intentionally slow.
        FAST_ALPHA = 0.004
        SLOW_ALPHA = 0.0015
        VOL_ALPHA = 0.05

        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        change = abs(mid - last_mid)
        vol = vol + VOL_ALPHA * (change - vol)

        trend = fast - slow

        product_data["fast"] = fast
        product_data["slow"] = slow
        product_data["vol"] = vol
        product_data["last_mid"] = mid

        # Fair value is mostly current mid, shifted by slow trend and inventory.
        MOMENTUM_MULT = 1.0
        INVENTORY_SKEW = 1.25

        fair = mid + MOMENTUM_MULT * trend - INVENTORY_SKEW * position

        # =========================
        # MARKET TAKING
        # =========================
        # Only cross the spread when the signal is strong.
        TAKE_EDGE = max(3, int(vol * 0.35))

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # Buy cheap asks if fair is clearly above the ask.
        if buy_capacity > 0:
            for ask_price in sorted(order_depth.sell_orders.keys()):
                ask_volume = -order_depth.sell_orders[ask_price]

                if ask_price <= fair - TAKE_EDGE:
                    quantity = min(buy_capacity, ask_volume)

                    if quantity > 0:
                        orders.append(Order(product, ask_price, quantity))
                        buy_capacity -= quantity
                        position += quantity

                if buy_capacity <= 0:
                    break

        # Sell expensive bids if fair is clearly below the bid.
        if sell_capacity > 0:
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                bid_volume = order_depth.buy_orders[bid_price]

                if bid_price >= fair + TAKE_EDGE:
                    quantity = min(sell_capacity, bid_volume)

                    if quantity > 0:
                        orders.append(Order(product, bid_price, -quantity))
                        sell_capacity -= quantity
                        position -= quantity

                if sell_capacity <= 0:
                    break

        # Recalculate capacity after aggressive orders.
        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # =========================
        # PASSIVE MARKET MAKING
        # =========================
        # Planetary Rings usually has a wide spread, so quote inside the book.
        # Bias the side depending on the trend.
        if spread >= 8:
            PASSIVE_SIZE = 2
            FAIR_EDGE = 2

            buy_price = min(best_bid + 1, math.floor(fair - FAIR_EDGE))
            sell_price = max(best_ask - 1, math.ceil(fair + FAIR_EDGE))

            # Make sure orders do not cross each other.
            if buy_price >= sell_price:
                buy_price = best_bid
                sell_price = best_ask

            # If trend is strongly up, quote more buy-side and less sell-side.
            # If trend is strongly down, quote more sell-side and less buy-side.
            if trend > 12:
                buy_size = 3
                sell_size = 1
            elif trend < -12:
                buy_size = 1
                sell_size = 3
            else:
                buy_size = PASSIVE_SIZE
                sell_size = PASSIVE_SIZE

            # Reduce buying when already long.
            if position > 5:
                buy_size = 1

            # Reduce selling when already short.
            if position < -5:
                sell_size = 1

            if buy_capacity > 0 and buy_price < best_ask:
                quantity = min(buy_size, buy_capacity)
                if quantity > 0:
                    orders.append(Order(product, int(buy_price), quantity))

            if sell_capacity > 0 and sell_price > best_bid:
                quantity = min(sell_size, sell_capacity)
                if quantity > 0:
                    orders.append(Order(product, int(sell_price), -quantity))

        result[product] = orders
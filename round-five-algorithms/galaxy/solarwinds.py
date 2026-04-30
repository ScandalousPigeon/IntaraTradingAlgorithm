from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    PRODUCT = "GALAXY_SOUNDS_SOLAR_WINDS"
    LIMIT = 10

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_solar_winds(state, result, data)

        return result, 0, json.dumps(data)

    def trade_solar_winds(self, state: TradingState, result: dict, data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        if best_bid >= best_ask:
            return

        bid_vol = abs(order_depth.buy_orders[best_bid])
        ask_vol = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        # =========================
        # HISTORY / ADAPTIVE FAIR
        # =========================

        memory = data.get(product, {})

        fast = memory.get("fast", mid)
        slow = memory.get("slow", mid)
        vol = memory.get("vol", spread)
        last_mid = memory.get("last_mid", mid)

        # Fast fair tracks the current random-walk price.
        fast = 0.35 * mid + 0.65 * fast

        # Slow fair is only used for a small trend lean.
        slow = 0.04 * mid + 0.96 * slow

        # Estimate normal short-term movement.
        move = abs(mid - last_mid)
        vol = 0.12 * move + 0.88 * vol

        memory["fast"] = fast
        memory["slow"] = slow
        memory["vol"] = vol
        memory["last_mid"] = mid
        data[product] = memory

        # =========================
        # BOOK PRESSURE SIGNAL
        # =========================

        total_top_volume = max(1, bid_vol + ask_vol)

        imbalance = (bid_vol - ask_vol) / total_top_volume

        micro_price = (
            best_ask * bid_vol + best_bid * ask_vol
        ) / total_top_volume

        micro_bias = micro_price - mid
        trend = fast - slow

        # Inventory skew:
        # If long, lower fair so we sell more easily.
        # If short, raise fair so we buy more easily.
        inventory_skew = position * 0.75

        fair = mid
        fair += 1.15 * micro_bias
        fair += 0.06 * trend
        fair -= inventory_skew

        # =========================
        # POSITION CAPACITY
        # =========================

        buy_capacity = self.LIMIT - position
        sell_capacity = self.LIMIT + position

        # =========================
        # AGGRESSIVE MISPRICING TAKE
        # =========================

        # Only cross the spread when the price is clearly wrong.
        take_edge = max(9.0, min(15.0, 0.95 * vol))

        if buy_capacity > 0 and best_ask <= fair - take_edge:
            qty = min(buy_capacity, ask_vol, 2)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_capacity -= qty
                position += qty

        if sell_capacity > 0 and best_bid >= fair + take_edge:
            qty = min(sell_capacity, bid_vol, 2)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_capacity -= qty
                position -= qty

        # Refresh capacity after any aggressive fills we attempted.
        buy_capacity = self.LIMIT - position
        sell_capacity = self.LIMIT + position

        # =========================
        # PASSIVE MARKET MAKING
        # =========================

        # Solar Winds has a fairly wide spread, so quote inside the spread,
        # but do not overpay when fair has moved against us.
        passive_edge = max(4.0, min(7.0, 0.45 * vol + 1.0))

        buy_price = min(best_bid + 1, int(round(fair - passive_edge)))
        sell_price = max(best_ask - 1, int(round(fair + passive_edge)))

        # Keep quotes valid.
        buy_price = min(buy_price, best_ask - 1)
        sell_price = max(sell_price, best_bid + 1)

        # Inventory-aware sizing.
        if position >= 7:
            buy_size = 1
            sell_size = 4
        elif position <= -7:
            buy_size = 4
            sell_size = 1
        elif position > 2:
            buy_size = 2
            sell_size = 3
        elif position < -2:
            buy_size = 3
            sell_size = 2
        else:
            buy_size = 3
            sell_size = 3

        if buy_capacity > 0 and buy_price < best_ask:
            qty = min(buy_capacity, buy_size)
            if qty > 0:
                orders.append(Order(product, buy_price, qty))

        if sell_capacity > 0 and sell_price > best_bid:
            qty = min(sell_capacity, sell_size)
            if qty > 0:
                orders.append(Order(product, sell_price, -qty))
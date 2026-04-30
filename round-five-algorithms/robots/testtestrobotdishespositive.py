from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:
    PRODUCT = "ROBOT_DISHES"
    LIMIT = 10

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        data = json.loads(state.traderData) if state.traderData else {}

        self.trade_robot_dishes(state, result, data)

        return result, 0, json.dumps(data)

    def trade_robot_dishes(self, state: TradingState, result: dict, data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)
        virtual_pos = position

        if product not in data:
            data[product] = {}

        pdata = data[product]

        # =========================
        # Historical state
        # =========================

        fast = pdata.get("fast", mid)
        slow = pdata.get("slow", mid)

        FAST_ALPHA = 0.20
        SLOW_ALPHA = 0.035

        # Detect the special ROBOT_DISHES regime where price sits near 100-levels.
        remainder = mid % 100
        distance_to_grid = min(remainder, 100 - remainder)
        is_roundish = distance_to_grid <= 2.5

        round_hist = pdata.get("round_hist", [])
        round_hist.append(1 if is_roundish else 0)
        round_hist = round_hist[-50:]

        round_ratio = sum(round_hist) / len(round_hist)
        grid_mode = len(round_hist) >= 20 and round_ratio >= 0.55

        # =========================
        # Fair value
        # =========================

        inventory_skew = 0.8 * virtual_pos

        if grid_mode:
            # In the grid regime, fast EMA works better because the price often
            # jumps away then snaps back.
            fair = fast - inventory_skew
            TAKE_EDGE = 30
            PASSIVE_EDGE = 6
            PASSIVE_SIZE = 3
        else:
            # Normal regime: conservative trend-following EMA fair.
            trend = fast - slow
            fair = slow + 0.20 * trend - inventory_skew
            TAKE_EDGE = 18
            PASSIVE_EDGE = 5
            PASSIVE_SIZE = 2

        # =========================
        # Aggressive taking
        # =========================

        # Buy asks that are clearly below fair.
        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            if ask_price > fair - TAKE_EDGE:
                break

            buy_capacity = self.LIMIT - virtual_pos
            if buy_capacity <= 0:
                break

            qty = min(abs(ask_volume), buy_capacity)

            if qty > 0:
                orders.append(Order(product, ask_price, qty))
                virtual_pos += qty

        # Sell bids that are clearly above fair.
        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if bid_price < fair + TAKE_EDGE:
                break

            sell_capacity = self.LIMIT + virtual_pos
            if sell_capacity <= 0:
                break

            qty = min(abs(bid_volume), sell_capacity)

            if qty > 0:
                orders.append(Order(product, bid_price, -qty))
                virtual_pos -= qty

        # =========================
        # Passive market making
        # =========================

        buy_price = int(round(fair - PASSIVE_EDGE))
        sell_price = int(round(fair + PASSIVE_EDGE))

        # Try to improve the book without crossing.
        buy_price = min(buy_price, best_bid + 1)
        sell_price = max(sell_price, best_ask - 1)

        if buy_price >= best_ask:
            buy_price = best_ask - 1

        if sell_price <= best_bid:
            sell_price = best_bid + 1

        buy_capacity = self.LIMIT - virtual_pos
        sell_capacity = self.LIMIT + virtual_pos

        # Lean quotes away from current inventory.
        buy_size = PASSIVE_SIZE
        sell_size = PASSIVE_SIZE

        if virtual_pos < 0:
            buy_size += 2
        elif virtual_pos > 0:
            sell_size += 2

        if buy_capacity > 0:
            qty = min(buy_size, buy_capacity)
            orders.append(Order(product, buy_price, qty))
            virtual_pos += qty

        if sell_capacity > 0:
            qty = min(sell_size, sell_capacity)
            orders.append(Order(product, sell_price, -qty))
            virtual_pos -= qty

        # =========================
        # Save updated history
        # =========================

        fast = (1 - FAST_ALPHA) * fast + FAST_ALPHA * mid
        slow = (1 - SLOW_ALPHA) * slow + SLOW_ALPHA * mid

        pdata["fast"] = fast
        pdata["slow"] = slow
        pdata["round_hist"] = round_hist

        result[product] = orders
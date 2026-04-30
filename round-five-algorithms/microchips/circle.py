from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except:
            data = {}

        self.trade_microchip_circle(state, result, data)

        return result, 0, json.dumps(data)

    def trade_microchip_circle(self, state: TradingState, result: Dict[str, List[Order]], data: dict):
        product = "MICROCHIP_CIRCLE"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        # =========================
        # PARAMETERS
        # =========================
        LIMIT = 10

        FAST_ALPHA = 0.01
        SLOW_ALPHA = 0.002

        TREND_TRIGGER = 20
        TARGET_SCALE = 4

        WARMUP = 50

        # =========================
        # MARKET DATA
        # =========================
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        key = "microchip_circle"

        # Reset if timestamp goes backwards between tests
        if key not in data or data[key].get("last_timestamp", -1) > state.timestamp:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "count": 0,
                "last_timestamp": state.timestamp,
            }

        store = data[key]

        fast = store["fast"]
        slow = store["slow"]
        count = store["count"]

        # =========================
        # EMA TREND UPDATE
        # =========================
        fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * fast
        slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * slow

        trend = fast - slow

        count += 1

        store["fast"] = fast
        store["slow"] = slow
        store["count"] = count
        store["last_timestamp"] = state.timestamp

        # =========================
        # TARGET POSITION
        # =========================
        target_position = 0

        if count >= WARMUP and abs(trend) >= TREND_TRIGGER:
            raw_target = trend / TARGET_SCALE

            if raw_target > 0:
                target_position = int(raw_target + 0.5)
            else:
                target_position = int(raw_target - 0.5)

            target_position = max(-LIMIT, min(LIMIT, target_position))

        # =========================
        # TRADE TOWARDS TARGET
        # =========================

        # Need to buy
        if target_position > position:
            buy_needed = min(target_position - position, LIMIT - position)

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if buy_needed <= 0:
                    break

                ask_volume = -order_depth.sell_orders[ask_price]
                quantity = min(buy_needed, ask_volume)

                if quantity > 0:
                    orders.append(Order(product, ask_price, quantity))
                    buy_needed -= quantity

        # Need to sell
        elif target_position < position:
            sell_needed = min(position - target_position, LIMIT + position)

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if sell_needed <= 0:
                    break

                bid_volume = order_depth.buy_orders[bid_price]
                quantity = min(sell_needed, bid_volume)

                if quantity > 0:
                    orders.append(Order(product, bid_price, -quantity))
                    sell_needed -= quantity

        result[product] = orders
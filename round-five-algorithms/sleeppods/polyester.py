from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_sleep_pod_polyester(state, result, data)

        return result, 0, json.dumps(data)

    def trade_sleep_pod_polyester(self, state: TradingState, result: dict, data: dict) -> None:
        product = "SLEEP_POD_POLYESTER"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        # =====================
        # PARAMETERS
        # =====================
        LIMIT = 10

        FAST_ALPHA = 0.12
        SLOW_ALPHA = 0.02

        TREND_WEIGHT = 0.18
        MICRO_WEIGHT = 1.10

        INVENTORY_SKEW = 0.85

        PASSIVE_EDGE = 4
        TAKE_EDGE = 7

        PASSIVE_SIZE = 2
        TAKE_SIZE = 3

        TARGET_DIVISOR = 4.0
        TARGET_CAP = 6

        # =====================
        # BOOK DATA
        # =====================
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)
        local_position = position

        # =====================
        # STATE / EMA
        # =====================
        if product not in data:
            data[product] = {}

        product_data = data[product]

        if "fast" not in product_data:
            product_data["fast"] = mid

        if "slow" not in product_data:
            product_data["slow"] = mid

        fast = product_data["fast"]
        slow = product_data["slow"]

        fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * fast
        slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * slow

        product_data["fast"] = fast
        product_data["slow"] = slow

        # =====================
        # FAIR VALUE
        # =====================
        if best_bid_volume + best_ask_volume > 0:
            micro_price = (
                best_ask * best_bid_volume +
                best_bid * best_ask_volume
            ) / (best_bid_volume + best_ask_volume)
        else:
            micro_price = mid

        trend_signal = fast - slow
        micro_signal = micro_price - mid

        signal = TREND_WEIGHT * trend_signal + MICRO_WEIGHT * micro_signal

        target_position = round(signal / TARGET_DIVISOR)
        target_position = max(-TARGET_CAP, min(TARGET_CAP, target_position))

        fair = mid + signal - INVENTORY_SKEW * (position - target_position)

        # =====================
        # AGGRESSIVE MISPRICING TAKES
        # =====================
        buy_capacity = LIMIT - local_position
        sell_capacity = LIMIT + local_position

        if buy_capacity > 0 and best_ask <= fair - TAKE_EDGE:
            quantity = min(TAKE_SIZE, best_ask_volume, buy_capacity)
            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))
                local_position += quantity

        buy_capacity = LIMIT - local_position
        sell_capacity = LIMIT + local_position

        if sell_capacity > 0 and best_bid >= fair + TAKE_EDGE:
            quantity = min(TAKE_SIZE, best_bid_volume, sell_capacity)
            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))
                local_position -= quantity

        # =====================
        # PASSIVE MARKET MAKING
        # =====================
        buy_capacity = LIMIT - local_position
        sell_capacity = LIMIT + local_position

        if spread >= 3:
            raw_bid = round(fair - PASSIVE_EDGE)
            raw_ask = round(fair + PASSIVE_EDGE)

            bid_quote = min(best_bid + 1, best_ask - 1, raw_bid)
            ask_quote = max(best_ask - 1, best_bid + 1, raw_ask)

            # Buy more if we are below target, less if already long.
            buy_size = PASSIVE_SIZE
            if local_position < target_position:
                buy_size += 1
            if local_position > target_position + 2:
                buy_size = 1

            # Sell more if we are above target, less if already short.
            sell_size = PASSIVE_SIZE
            if local_position > target_position:
                sell_size += 1
            if local_position < target_position - 2:
                sell_size = 1

            if buy_capacity > 0 and bid_quote < best_ask:
                quantity = min(buy_size, buy_capacity)
                if quantity > 0:
                    orders.append(Order(product, bid_quote, quantity))

            if sell_capacity > 0 and ask_quote > best_bid:
                quantity = min(sell_size, sell_capacity)
                if quantity > 0:
                    orders.append(Order(product, ask_quote, -quantity))

        result[product] = orders
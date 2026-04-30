from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        product = "ROBOT_VACUUMING"
        result[product] = []

        if product not in state.order_depths:
            return result, 0, json.dumps(data)

        self.trade_robot_vacuuming(state, result, data)

        return result, 0, json.dumps(data)

    def trade_robot_vacuuming(self, state: TradingState, result: dict, data: dict) -> None:
        product = "ROBOT_VACUUMING"
        order_depth: OrderDepth = state.order_depths[product]
        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        # =========================
        # Parameters
        # =========================
        LIMIT = 10

        # Robot vacuuming is very trend-heavy, so avoid fixed fair value.
        ALPHA_FAST = 0.03
        ALPHA_SLOW = 0.008

        # 0 means always follow the EMA crossover.
        # Increase to 5 or 10 if it overtrades in testing.
        TREND_THRESHOLD = 0

        # Prevent flipping from +10 to -10 instantly.
        MAX_TRADE_PER_TICK = 10

        # =========================
        # Best bid / ask
        # =========================
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        # =========================
        # Persistent EMA data
        # =========================
        if product not in data:
            data[product] = {
                "ema_fast": mid,
                "ema_slow": mid
            }

        pdata = data[product]

        pdata["ema_fast"] = (
            ALPHA_FAST * mid
            + (1 - ALPHA_FAST) * pdata["ema_fast"]
        )

        pdata["ema_slow"] = (
            ALPHA_SLOW * mid
            + (1 - ALPHA_SLOW) * pdata["ema_slow"]
        )

        trend_signal = pdata["ema_fast"] - pdata["ema_slow"]

        # =========================
        # Target position
        # =========================
        if trend_signal > TREND_THRESHOLD:
            target_position = LIMIT
        elif trend_signal < -TREND_THRESHOLD:
            target_position = -LIMIT
        else:
            target_position = 0

        current_position = state.position.get(product, 0)

        desired_change = target_position - current_position

        # Do not change too aggressively in one tick.
        if desired_change > MAX_TRADE_PER_TICK:
            desired_change = MAX_TRADE_PER_TICK
        elif desired_change < -MAX_TRADE_PER_TICK:
            desired_change = -MAX_TRADE_PER_TICK

        # =========================
        # Buy towards target
        # =========================
        if desired_change > 0:
            remaining = min(desired_change, LIMIT - current_position)

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if remaining <= 0:
                    break

                ask_volume = order_depth.sell_orders[ask_price]

                # In Prosperity, sell volumes are usually negative.
                available_volume = -ask_volume if ask_volume < 0 else ask_volume

                buy_quantity = min(available_volume, remaining)

                if buy_quantity > 0:
                    orders.append(Order(product, ask_price, buy_quantity))
                    current_position += buy_quantity
                    remaining -= buy_quantity

        # =========================
        # Sell towards target
        # =========================
        elif desired_change < 0:
            remaining = min(-desired_change, LIMIT + current_position)

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if remaining <= 0:
                    break

                bid_volume = order_depth.buy_orders[bid_price]
                available_volume = bid_volume if bid_volume > 0 else -bid_volume

                sell_quantity = min(available_volume, remaining)

                if sell_quantity > 0:
                    orders.append(Order(product, bid_price, -sell_quantity))
                    current_position -= sell_quantity
                    remaining -= sell_quantity

        result[product] = orders
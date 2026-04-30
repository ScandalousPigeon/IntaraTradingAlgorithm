from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        data = json.loads(state.traderData) if state.traderData else {}

        self.trade_microchip_oval(state, result, data)

        return result, 0, json.dumps(data)

    def trade_microchip_oval(self, state: TradingState, result: dict, data: dict) -> None:
        product = "MICROCHIP_OVAL"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []
        position = state.position.get(product, 0)

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        if product not in data:
            data[product] = {
                "start_mid": mid,
                "high_mid": mid,
                "ticks": 0,
                "armed": False,
            }

        d = data[product]
        d["ticks"] += 1
        d["high_mid"] = max(d["high_mid"], mid)

        start_mid = d["start_mid"]
        high_mid = d["high_mid"]

        # Adaptive warmup:
        # Higher starting price historically had a longer early bounce.
        if start_mid > 9800:
            warmup_ticks = 3000
            pullback = 20
        elif start_mid > 8500:
            warmup_ticks = 1500
            pullback = 50
        else:
            warmup_ticks = 500
            pullback = 10

        # Enter short after the early bounce starts fading.
        if d["ticks"] >= warmup_ticks and high_mid - mid >= pullback:
            d["armed"] = True

        # Emergency entry if the product just starts falling immediately.
        if d["ticks"] >= warmup_ticks and mid < start_mid - 80:
            d["armed"] = True

        target_position = -LIMIT if d["armed"] else 0

        self.trade_to_target(product, order_depth, orders, position, target_position)

        result[product] = orders

    def trade_to_target(
        self,
        product: str,
        order_depth: OrderDepth,
        orders: List[Order],
        position: int,
        target_position: int,
    ) -> None:

        if target_position < position:
            # Need to sell.
            quantity_to_sell = position - target_position

            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                available = order_depth.buy_orders[price]
                quantity = min(quantity_to_sell, available)

                if quantity > 0:
                    orders.append(Order(product, price, -quantity))
                    quantity_to_sell -= quantity

                if quantity_to_sell <= 0:
                    break

        elif target_position > position:
            # Need to buy / cover.
            quantity_to_buy = target_position - position

            for price in sorted(order_depth.sell_orders.keys()):
                available = abs(order_depth.sell_orders[price])
                quantity = min(quantity_to_buy, available)

                if quantity > 0:
                    orders.append(Order(product, price, quantity))
                    quantity_to_buy -= quantity

                if quantity_to_buy <= 0:
                    break
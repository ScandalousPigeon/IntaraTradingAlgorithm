from datamodel import OrderDepth, TradingState, Order
import json


class Trader:

    PEBBLES = [
        "PEBBLES_XS",
        "PEBBLES_S",
        "PEBBLES_M",
        "PEBBLES_L",
        "PEBBLES_XL",
    ]

    BASKET_FAIR = 50000
    LIMIT = 10

    # Conservative because your graph had a large drawdown.
    TAKE_EDGE = 2
    TAKE_SIZE = 1

    # Passive package market-making.
    PASSIVE_EDGE = 15
    PASSIVE_SIZE = 2

    # Stop adding to inventory when already quite long/short.
    SOFT_LIMIT = 6

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        self.trade_pebbles(state, result, data)

        return result, 0, json.dumps(data)

    def trade_pebbles(self, state: TradingState, result: dict, data: dict) -> None:

        info = {}

        # Need all 5 Pebbles visible.
        for product in self.PEBBLES:
            if product not in state.order_depths:
                return

            depth: OrderDepth = state.order_depths[product]

            if not depth.buy_orders or not depth.sell_orders:
                return

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())

            result[product] = []

            info[product] = {
                "depth": depth,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "best_bid_volume": depth.buy_orders[best_bid],
                "best_ask_volume": -depth.sell_orders[best_ask],
                "mid": (best_bid + best_ask) / 2,
                "position": state.position.get(product, 0),
            }

        positions = {p: info[p]["position"] for p in self.PEBBLES}
        avg_position = sum(positions.values()) / len(self.PEBBLES)

        basket_mid = sum(info[p]["mid"] for p in self.PEBBLES)
        basket_error = basket_mid - self.BASKET_FAIR

        data["pebbles_basket_error"] = basket_error
        data["pebbles_avg_position"] = avg_position

        # ============================================================
        # 1. TRUE PACKAGE TAKE LOGIC
        # ============================================================
        # Only cross if the whole 5-product package has edge.
        # This avoids the old problem where each product counted the full
        # basket error separately.

        best_ask_sum = sum(info[p]["best_ask"] for p in self.PEBBLES)
        best_bid_sum = sum(info[p]["best_bid"] for p in self.PEBBLES)

        take_buy_edge = self.BASKET_FAIR - best_ask_sum
        take_sell_edge = best_bid_sum - self.BASKET_FAIR

        buy_room = min(self.LIMIT - positions[p] for p in self.PEBBLES)
        sell_room = min(self.LIMIT + positions[p] for p in self.PEBBLES)

        max_take_buy_qty = min(
            self.TAKE_SIZE,
            buy_room,
            min(info[p]["best_ask_volume"] for p in self.PEBBLES),
        )

        max_take_sell_qty = min(
            self.TAKE_SIZE,
            sell_room,
            min(info[p]["best_bid_volume"] for p in self.PEBBLES),
        )

        # Buy the full basket only when the full ask package is cheap.
        if (
            take_buy_edge >= self.TAKE_EDGE
            and max_take_buy_qty > 0
            and avg_position < self.SOFT_LIMIT
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, info[product]["best_ask"], max_take_buy_qty)
                )
            return

        # Sell the full basket only when the full bid package is expensive.
        # This probably triggers rarely, but it is logically correct.
        if (
            take_sell_edge >= self.TAKE_EDGE
            and max_take_sell_qty > 0
            and avg_position > -self.SOFT_LIMIT
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, info[product]["best_bid"], -max_take_sell_qty)
                )
            return

        # ============================================================
        # 2. PACKAGE PASSIVE QUOTING
        # ============================================================
        # Quote all 5 products together with the same size.
        # This keeps positions balanced and reduces the drawdown risk.

        passive_bid_prices = {}
        passive_ask_prices = {}

        for product in self.PEBBLES:
            best_bid = info[product]["best_bid"]
            best_ask = info[product]["best_ask"]

            bid_price = best_bid + 1
            ask_price = best_ask - 1

            # Do not cross accidentally.
            if bid_price >= best_ask:
                bid_price = best_bid

            if ask_price <= best_bid:
                ask_price = best_ask

            passive_bid_prices[product] = bid_price
            passive_ask_prices[product] = ask_price

        passive_bid_sum = sum(passive_bid_prices[p] for p in self.PEBBLES)
        passive_ask_sum = sum(passive_ask_prices[p] for p in self.PEBBLES)

        passive_buy_edge = self.BASKET_FAIR - passive_bid_sum
        passive_sell_edge = passive_ask_sum - self.BASKET_FAIR

        data["pebbles_passive_buy_edge"] = passive_buy_edge
        data["pebbles_passive_sell_edge"] = passive_sell_edge

        passive_buy_qty = min(self.PASSIVE_SIZE, buy_room)
        passive_sell_qty = min(self.PASSIVE_SIZE, sell_room)

        # If already long, stop placing more bids unless the buy edge is very good.
        allow_passive_buy = avg_position < self.SOFT_LIMIT

        # If already short, stop placing more asks unless the sell edge is very good.
        allow_passive_sell = avg_position > -self.SOFT_LIMIT

        if (
            passive_buy_edge >= self.PASSIVE_EDGE
            and passive_buy_qty > 0
            and allow_passive_buy
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, passive_bid_prices[product], passive_buy_qty)
                )

        if (
            passive_sell_edge >= self.PASSIVE_EDGE
            and passive_sell_qty > 0
            and allow_passive_sell
        ):
            for product in self.PEBBLES:
                result[product].append(
                    Order(product, passive_ask_prices[product], -passive_sell_qty)
                )
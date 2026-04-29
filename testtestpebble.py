from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        # Make sure every visible product has an entry
        for product in state.order_depths:
            result[product] = []

        # -------------------------
        # PEBBLES
        # -------------------------

        self.trade_pebbles(
            state=state,
            result=result,
            data=data
        )

        return result, 0, json.dumps(data)

    # ============================================================
    # PEBBLES
    # ============================================================

    def trade_pebbles(
        self,
        state: TradingState,
        result: dict,
        data: dict
    ) -> None:

        pebble_products = [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL"
        ]

        # Hidden basket relationship found from historical data:
        # XS + S + M + L + XL ~= 50000
        BASKET_FAIR = 50000

        LIMIT = 10

        # Aggressive orders only when there is clear edge after crossing spread.
        TAKE_EDGE = 1.0
        TAKE_SIZE = 4

        # Passive market-making around relationship fair value.
        PASSIVE_EDGE = 2.0
        PASSIVE_SIZE = 2

        # Since limit is only 10, inventory skew needs to matter.
        INVENTORY_SKEW = 0.6

        # Need all 5 Pebbles visible to use the basket relationship.
        for product in pebble_products:
            if product not in state.order_depths:
                return

            depth = state.order_depths[product]

            if not depth.buy_orders or not depth.sell_orders:
                return

        pebble_data = {}

        for product in pebble_products:

            depth = state.order_depths[product]

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())

            best_bid_volume = depth.buy_orders[best_bid]
            best_ask_volume = -depth.sell_orders[best_ask]

            mid = (best_bid + best_ask) / 2

            pebble_data[product] = {
                "depth": depth,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "best_bid_volume": best_bid_volume,
                "best_ask_volume": best_ask_volume,
                "mid": mid
            }

        basket_mid = sum(pebble_data[product]["mid"] for product in pebble_products)

        # Positive means the whole basket is expensive.
        # Negative means the whole basket is cheap.
        basket_error = basket_mid - BASKET_FAIR

        data["pebbles_basket_error"] = basket_error

        for product in pebble_products:

            info = pebble_data[product]
            depth = info["depth"]

            best_bid = info["best_bid"]
            best_ask = info["best_ask"]

            best_bid_volume = info["best_bid_volume"]
            best_ask_volume = info["best_ask_volume"]

            mid = info["mid"]

            position = state.position.get(product, 0)

            buy_room = LIMIT - position
            sell_room = LIMIT + position

            # Fair value of this product implied by the other 4 Pebbles.
            fair = BASKET_FAIR - (basket_mid - mid)

            # If ask is below fair, buying is good.
            buy_edge = fair - best_ask

            # If bid is above fair, selling is good.
            sell_edge = best_bid - fair

            traded_aggressively = False

            # =====================
            # AGGRESSIVE TAKE LOGIC
            # =====================

            if buy_edge > TAKE_EDGE and buy_room > 0:

                qty = min(
                    TAKE_SIZE,
                    best_ask_volume,
                    buy_room
                )

                if qty > 0:
                    result[product].append(Order(product, best_ask, qty))
                    traded_aggressively = True

            elif sell_edge > TAKE_EDGE and sell_room > 0:

                qty = min(
                    TAKE_SIZE,
                    best_bid_volume,
                    sell_room
                )

                if qty > 0:
                    result[product].append(Order(product, best_bid, -qty))
                    traded_aggressively = True

            # =====================
            # PASSIVE QUOTE LOGIC
            # =====================
            # Only place passive quotes if we did not already cross the spread.
            # This prevents us from over-trading in the same tick.

            if traded_aggressively:
                continue

            adjusted_fair = fair - INVENTORY_SKEW * position

            bid_price = int(round(adjusted_fair - PASSIVE_EDGE))
            ask_price = int(round(adjusted_fair + PASSIVE_EDGE))

            # Improve the current market by at most 1 tick,
            # but never cross the spread.
            bid_price = min(bid_price, best_bid + 1)
            bid_price = min(bid_price, best_ask - 1)

            ask_price = max(ask_price, best_ask - 1)
            ask_price = max(ask_price, best_bid + 1)

            if buy_room > 0 and bid_price < best_ask:
                buy_qty = min(PASSIVE_SIZE, buy_room)
                result[product].append(Order(product, bid_price, buy_qty))

            if sell_room > 0 and ask_price > best_bid:
                sell_qty = min(PASSIVE_SIZE, sell_room)
                result[product].append(Order(product, ask_price, -sell_qty))
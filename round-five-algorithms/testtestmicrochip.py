from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        # Make sure every visible product has an entry
        for product in state.order_depths:
            result[product] = []

        # -------------------------
        # MICROCHIPS
        # -------------------------

        self.trade_microchips(
            state=state,
            result=result,
            data=data
        )

        return result, 0, json.dumps(data)

    # ============================================================
    # SMALL HELPERS
    # ============================================================

    def clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    # ============================================================
    # MICROCHIPS
    # ============================================================

    def trade_microchips(
        self,
        state: TradingState,
        result: dict,
        data: dict
    ) -> None:

        microchip_products = [
            "MICROCHIP_CIRCLE",
            "MICROCHIP_OVAL",
            "MICROCHIP_SQUARE",
            "MICROCHIP_RECTANGLE",
            "MICROCHIP_TRIANGLE"
        ]

        LIMIT = 10

        # Store persistent microchip data
        if "microchips" not in data:
            data["microchips"] = {}

        for product in microchip_products:

            if product not in state.order_depths:
                continue

            order_depth: OrderDepth = state.order_depths[product]

            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            orders: List[Order] = []

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())

            best_bid_volume = order_depth.buy_orders[best_bid]
            best_ask_volume = -order_depth.sell_orders[best_ask]

            mid = (best_bid + best_ask) / 2
            spread = best_ask - best_bid

            position = state.position.get(product, 0)

            buy_room = LIMIT - position
            sell_room = LIMIT + position

            # -------------------------
            # Product-specific settings
            # -------------------------
            # SQUARE was the most volatile historically, so it gets wider edges.
            # OVAL and TRIANGLE were also volatile but had tighter spreads.
            # CIRCLE and RECTANGLE are a bit more conservative.

            if product == "MICROCHIP_SQUARE":
                FAST_ALPHA = 0.045
                SLOW_ALPHA = 0.004
                TREND_WEIGHT = 0.45
                MOMENTUM_WEIGHT = 0.08
                TAKE_EDGE = 5.0
                PASSIVE_EDGE = 6.0
                ORDER_SIZE = 2
                TREND_CAP = 35.0

            elif product == "MICROCHIP_OVAL":
                FAST_ALPHA = 0.035
                SLOW_ALPHA = 0.004
                TREND_WEIGHT = 0.40
                MOMENTUM_WEIGHT = 0.06
                TAKE_EDGE = 4.0
                PASSIVE_EDGE = 5.0
                ORDER_SIZE = 2
                TREND_CAP = 30.0

            elif product == "MICROCHIP_TRIANGLE":
                FAST_ALPHA = 0.035
                SLOW_ALPHA = 0.004
                TREND_WEIGHT = 0.35
                MOMENTUM_WEIGHT = 0.06
                TAKE_EDGE = 4.0
                PASSIVE_EDGE = 5.0
                ORDER_SIZE = 2
                TREND_CAP = 30.0

            elif product == "MICROCHIP_RECTANGLE":
                FAST_ALPHA = 0.030
                SLOW_ALPHA = 0.003
                TREND_WEIGHT = 0.30
                MOMENTUM_WEIGHT = 0.05
                TAKE_EDGE = 4.0
                PASSIVE_EDGE = 5.0
                ORDER_SIZE = 1
                TREND_CAP = 25.0

            else:  # MICROCHIP_CIRCLE
                FAST_ALPHA = 0.030
                SLOW_ALPHA = 0.003
                TREND_WEIGHT = 0.30
                MOMENTUM_WEIGHT = 0.05
                TAKE_EDGE = 4.0
                PASSIVE_EDGE = 5.0
                ORDER_SIZE = 1
                TREND_CAP = 25.0

            INVENTORY_SKEW = 0.8

            # -------------------------
            # Initialise/update memory
            # -------------------------

            if product not in data["microchips"]:
                data["microchips"][product] = {
                    "fast": mid,
                    "slow": mid,
                    "last_mid": mid,
                    "ticks": 0
                }

            product_data = data["microchips"][product]

            old_fast = product_data["fast"]
            old_slow = product_data["slow"]
            last_mid = product_data["last_mid"]

            fast = FAST_ALPHA * mid + (1 - FAST_ALPHA) * old_fast
            slow = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * old_slow

            momentum = mid - last_mid
            trend = fast - slow

            product_data["fast"] = fast
            product_data["slow"] = slow
            product_data["last_mid"] = mid
            product_data["ticks"] = product_data.get("ticks", 0) + 1

            # Avoid trading immediately before the EMAs have any useful meaning.
            if product_data["ticks"] < 30:
                result[product] = orders
                continue

            # -------------------------
            # Fair value
            # -------------------------
            # We start from mid, then bias fair value in the trend direction.
            # If fast > slow, trend is positive, so fair is lifted.
            # If fast < slow, trend is negative, so fair is lowered.

            trend_bias = (
                TREND_WEIGHT * trend
                + MOMENTUM_WEIGHT * momentum
            )

            trend_bias = self.clamp(
                trend_bias,
                -TREND_CAP,
                TREND_CAP
            )

            fair = mid + trend_bias

            # Penalise inventory so we do not sit at +10 or -10 forever.
            adjusted_fair = fair - INVENTORY_SKEW * position

            buy_edge = adjusted_fair - best_ask
            sell_edge = best_bid - adjusted_fair

            traded_aggressively = False

            # =====================
            # AGGRESSIVE TAKE LOGIC
            # =====================

            if buy_edge > TAKE_EDGE and buy_room > 0:

                qty = min(
                    ORDER_SIZE,
                    best_ask_volume,
                    buy_room
                )

                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    traded_aggressively = True

            elif sell_edge > TAKE_EDGE and sell_room > 0:

                qty = min(
                    ORDER_SIZE,
                    best_bid_volume,
                    sell_room
                )

                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    traded_aggressively = True

            # =====================
            # PASSIVE QUOTE LOGIC
            # =====================
            # If we did not cross the spread, place passive quotes around fair.
            # This is similar to your Hydrogel style, but with a trend-biased fair.

            if not traded_aggressively:

                bid_price = int(round(adjusted_fair - PASSIVE_EDGE))
                ask_price = int(round(adjusted_fair + PASSIVE_EDGE))

                # Improve by at most 1 tick, but do not cross.
                bid_price = min(bid_price, best_bid + 1)
                bid_price = min(bid_price, best_ask - 1)

                ask_price = max(ask_price, best_ask - 1)
                ask_price = max(ask_price, best_bid + 1)

                # If spread is very tight, be more careful.
                if spread <= 2:
                    result[product] = orders
                    continue

                if buy_room > 0 and bid_price < best_ask:
                    buy_qty = min(ORDER_SIZE, buy_room)
                    orders.append(Order(product, bid_price, buy_qty))

                if sell_room > 0 and ask_price > best_bid:
                    sell_qty = min(ORDER_SIZE, sell_room)
                    orders.append(Order(product, ask_price, -sell_qty))

            result[product] = orders
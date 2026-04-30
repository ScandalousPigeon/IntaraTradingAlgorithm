from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except:
            data = {}

        self.trade_snackpack_strawberry(state, result, data)

        return result, 0, json.dumps(data)

    def trade_snackpack_strawberry(self, state: TradingState, result: dict, data: dict) -> None:
        product = "SNACKPACK_STRAWBERRY"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = abs(order_depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        key = "snackpack_strawberry"

        if key not in data:
            data[key] = {
                "fast": mid,
                "slow": mid,
                "absret": 5.0,
                "last_mid": mid
            }

        info = data[key]

        last_mid = info.get("last_mid", mid)
        ret = mid - last_mid

        # Update fair value estimates
        ALPHA_FAST = 0.08
        ALPHA_SLOW = 0.015
        ALPHA_VOL = 0.05

        fast = info.get("fast", mid)
        slow = info.get("slow", mid)
        absret = info.get("absret", 5.0)

        fast = fast + ALPHA_FAST * (mid - fast)
        slow = slow + ALPHA_SLOW * (mid - slow)
        absret = absret + ALPHA_VOL * (abs(ret) - absret)

        info["fast"] = fast
        info["slow"] = slow
        info["absret"] = absret
        info["last_mid"] = mid

        # -----------------------------
        # Order book imbalance signal
        # -----------------------------
        # Usually volumes are equal.
        # When they are not equal, it is a useful short-term signal.
        if bid_volume + ask_volume > 0:
            microprice = (
                best_ask * bid_volume +
                best_bid * ask_volume
            ) / (bid_volume + ask_volume)
        else:
            microprice = mid

        pressure = microprice - mid

        # -----------------------------
        # Mean reversion signal
        # -----------------------------
        # If price is stretched above fast EMA, lean sell.
        # If price is stretched below fast EMA, lean buy.
        short_deviation = mid - fast
        long_deviation = mid - slow

        fair = mid

        # mean reversion component
        fair -= 0.18 * short_deviation
        fair -= 0.04 * long_deviation

        # imbalance component
        fair += 0.85 * pressure

        # inventory skew
        fair -= 0.45 * position

        # -----------------------------
        # 1. Take clearly mispriced orders
        # -----------------------------
        TAKE_EDGE = max(2.0, min(4.0, absret * 0.20))

        # Buy cheap asks
        if position < LIMIT:
            for ask_price in sorted(order_depth.sell_orders.keys()):
                ask_qty = abs(order_depth.sell_orders[ask_price])

                if ask_price <= fair - TAKE_EDGE:
                    buy_qty = min(ask_qty, LIMIT - position, 4)

                    if buy_qty > 0:
                        orders.append(Order(product, ask_price, buy_qty))
                        position += buy_qty
                else:
                    break

        # Sell expensive bids
        if position > -LIMIT:
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                bid_qty = order_depth.buy_orders[bid_price]

                if bid_price >= fair + TAKE_EDGE:
                    sell_qty = min(bid_qty, position + LIMIT, 4)

                    if sell_qty > 0:
                        orders.append(Order(product, bid_price, -sell_qty))
                        position -= sell_qty
                else:
                    break

        # -----------------------------
        # 2. Passive market making
        # -----------------------------
        if spread < 8:
            result[product] = orders
            return

        # Recalculate fair after possible inventory change
        fair_after_inventory = fair - 0.35 * position

        base_edge = 2.0 if spread >= 15 else 3.0

        buy_edge = base_edge
        sell_edge = base_edge

        # If book is bid-heavy, lean buy and avoid selling too cheaply
        if pressure > 0.5:
            buy_edge -= 1.0
            sell_edge += 1.0

        # If book is ask-heavy, lean sell and avoid buying too high
        elif pressure < -0.5:
            buy_edge += 1.0
            sell_edge -= 1.0

        # If price is stretched upward, lean sell
        if short_deviation > 8:
            sell_edge -= 0.5
            buy_edge += 0.5

        # If price is stretched downward, lean buy
        elif short_deviation < -8:
            buy_edge -= 0.5
            sell_edge += 0.5

        buy_edge = max(1.0, min(5.0, buy_edge))
        sell_edge = max(1.0, min(5.0, sell_edge))

        bid_quote = min(best_bid + 1, math.floor(fair_after_inventory - buy_edge))
        ask_quote = max(best_ask - 1, math.ceil(fair_after_inventory + sell_edge))

        # Safety: never accidentally cross with passive orders
        if bid_quote >= best_ask:
            bid_quote = best_bid

        if ask_quote <= best_bid:
            ask_quote = best_ask

        clear_up = pressure > 0.5
        clear_down = pressure < -0.5

        # Buy size
        buy_capacity = LIMIT - position
        if buy_capacity > 0:
            buy_size = 3

            if pressure > 0.5:
                buy_size = 5

            if position < 0:
                buy_size += 2

            if position > 5:
                buy_size = 1

            buy_size = min(buy_size, buy_capacity)

            # Do not fight a clear down signal unless we are already short
            if not (clear_down and position >= 0):
                if buy_size > 0 and bid_quote < best_ask:
                    orders.append(Order(product, bid_quote, buy_size))

        # Sell size
        sell_capacity = position + LIMIT
        if sell_capacity > 0:
            sell_size = 3

            if pressure < -0.5:
                sell_size = 5

            if position > 0:
                sell_size += 2

            if position < -5:
                sell_size = 1

            sell_size = min(sell_size, sell_capacity)

            # Do not fight a clear up signal unless we are already long
            if not (clear_up and position <= 0):
                if sell_size > 0 and ask_quote > best_bid:
                    orders.append(Order(product, ask_quote, -sell_size))

        result[product] = orders
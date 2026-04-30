from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    PRODUCT = "OXYGEN_SHAKE_EVENING_BREATH"
    LIMIT = 10

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_evening_breath(state, result, data)

        return result, 0, json.dumps(data)

    def trade_evening_breath(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_vol = abs(depth.buy_orders[best_bid])
        ask_vol = abs(depth.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        pos = state.position.get(product, 0)

        pdata = data.get(product, {})

        # Fast EMA because Evening Breath mean-reverts quickly.
        ema = pdata.get("ema", mid)
        alpha = 0.34
        ema = alpha * mid + (1 - alpha) * ema

        last_mid = pdata.get("last_mid", mid)
        last_ret = mid - last_mid

        vol = pdata.get("vol", 8.0)
        vol = 0.94 * vol + 0.06 * abs(last_ret)

        # Microprice gives a small book-imbalance adjustment.
        if bid_vol + ask_vol > 0:
            micro = (best_ask * bid_vol + best_bid * ask_vol) / (bid_vol + ask_vol)
        else:
            micro = mid

        micro_signal = micro - mid

        # Fair value:
        # - EMA anchors value
        # - last_ret is faded because this product has short-term reversal
        # - inventory skew prevents getting stuck at +/-10
        fair = (
            ema
            - 0.25 * last_ret
            + 0.20 * micro_signal
            - 0.85 * pos
        )

        pdata["ema"] = ema
        pdata["last_mid"] = mid
        pdata["vol"] = vol
        data[product] = pdata

        buy_cap = self.LIMIT - pos
        sell_cap = self.LIMIT + pos

        def add_buy(price: int, qty: int):
            nonlocal buy_cap
            qty = max(0, min(qty, buy_cap))
            if qty > 0:
                orders.append(Order(product, price, qty))
                buy_cap -= qty

        def add_sell(price: int, qty: int):
            nonlocal sell_cap
            qty = max(0, min(qty, sell_cap))
            if qty > 0:
                orders.append(Order(product, price, -qty))
                sell_cap -= qty

        # Strong edge required before taking liquidity.
        # This avoids bleeding spread on normal noise.
        TAKE_EDGE = max(17, min(26, int(15 + 0.45 * vol)))
        TAKE_SIZE = 5

        # Buy cheap asks.
        for ask_price in sorted(depth.sell_orders.keys()):
            if buy_cap <= 0:
                break

            ask_qty = abs(depth.sell_orders[ask_price])

            if ask_price <= fair - TAKE_EDGE:
                add_buy(ask_price, min(TAKE_SIZE, ask_qty))
            else:
                break

        # Sell expensive bids.
        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if sell_cap <= 0:
                break

            bid_qty = abs(depth.buy_orders[bid_price])

            if bid_price >= fair + TAKE_EDGE:
                add_sell(bid_price, min(TAKE_SIZE, bid_qty))
            else:
                break

        # Passive quoting for spread capture.
        # Keep this small because the product can trend over longer windows.
        if spread >= 6:
            PASSIVE_EDGE = 4
            BASE_SIZE = 2

            bid_quote = min(best_bid + 1, math.floor(fair - PASSIVE_EDGE))
            ask_quote = max(best_ask - 1, math.ceil(fair + PASSIVE_EDGE))

            # Inventory-aware sizing.
            buy_size = BASE_SIZE
            sell_size = BASE_SIZE

            if pos < 0:
                buy_size += 2
            elif pos > 0:
                sell_size += 2

            # Tilt towards the fair-value side.
            if fair > mid + 5:
                buy_size += 1
            elif fair < mid - 5:
                sell_size += 1

            # Do not cross with passive quotes.
            if bid_quote < best_ask:
                add_buy(int(bid_quote), buy_size)

            if ask_quote > best_bid:
                add_sell(int(ask_quote), sell_size)
from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    PRODUCT = "TRANSLATOR_GRAPHITE_MIST"
    LIMIT = 10

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        if self.PRODUCT in state.order_depths:
            self.trade_graphite_mist(state, result, data)

        return result, 0, json.dumps(data)

    def trade_graphite_mist(self, state: TradingState, result: Dict[str, List[Order]], data: dict):
        product = self.PRODUCT
        depth: OrderDepth = state.order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            return

        orders: List[Order] = result[product]
        position = state.position.get(product, 0)

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        best_bid_vol = depth.buy_orders[best_bid]
        best_ask_vol = -depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        key = "graphite_mist"

        if key not in data:
            data[key] = {
                "ema": mid,
                "slow": mid,
                "vol": 8.0,
                "last_mid": mid
            }

        info = data[key]

        last_mid = info.get("last_mid", mid)
        move = abs(mid - last_mid)

        # Smooth fair-value tracking
        ema = info.get("ema", mid)
        slow = info.get("slow", mid)
        vol = info.get("vol", 8.0)

        ema = 0.82 * ema + 0.18 * mid
        slow = 0.985 * slow + 0.015 * mid
        vol = 0.92 * vol + 0.08 * move

        # Microprice: if bid volume is heavier, fair value is slightly higher
        if best_bid_vol + best_ask_vol > 0:
            micro = (
                best_bid * best_ask_vol +
                best_ask * best_bid_vol
            ) / (best_bid_vol + best_ask_vol)
        else:
            micro = mid

        # Graphite Mist is noisy, so only weakly mean-revert to slow EMA.
        # Inventory skew is important because the product moves around a lot.
        inventory_skew = 0.65 * position
        micro_signal = 1.20 * (micro - mid)
        slow_reversion = -0.08 * (mid - slow)

        fair = mid + micro_signal + slow_reversion - inventory_skew

        info["ema"] = ema
        info["slow"] = slow
        info["vol"] = vol
        info["last_mid"] = mid
        data[key] = info

        pos = position

        # Dynamic edge: wider during noisy periods
        passive_edge = max(3, min(6, int(round(vol * 0.28))))
        take_edge = passive_edge + 3

        # ------------------------------------------------------------
        # 1. Aggressive taking only when the book is clearly mispriced
        # ------------------------------------------------------------

        if pos < self.LIMIT:
            for ask_price in sorted(depth.sell_orders.keys()):
                ask_vol = -depth.sell_orders[ask_price]

                if ask_price <= fair - take_edge:
                    qty = min(ask_vol, 2, self.LIMIT - pos)
                    if qty > 0:
                        orders.append(Order(product, ask_price, qty))
                        pos += qty
                else:
                    break

                if pos >= self.LIMIT:
                    break

        if pos > -self.LIMIT:
            for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
                bid_vol = depth.buy_orders[bid_price]

                if bid_price >= fair + take_edge:
                    qty = min(bid_vol, 2, self.LIMIT + pos)
                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty))
                        pos -= qty
                else:
                    break

                if pos <= -self.LIMIT:
                    break

        # ------------------------------------------------------------
        # 2. Passive market-making inside the spread
        # ------------------------------------------------------------

        buy_capacity = self.LIMIT - pos
        sell_capacity = self.LIMIT + pos

        if spread >= 5:
            bid_quote = min(best_bid + 1, math.floor(fair - passive_edge))
            ask_quote = max(best_ask - 1, math.ceil(fair + passive_edge))

            # Make sure passive orders do not accidentally cross.
            bid_quote = min(bid_quote, best_ask - 1)
            ask_quote = max(ask_quote, best_bid + 1)

            if bid_quote < ask_quote:
                base_size = 2 if spread >= 8 else 1

                buy_size = base_size
                sell_size = base_size

                # If already long, sell more and buy less.
                if pos >= 5:
                    buy_size = 1
                    sell_size = 3

                # If already short, buy more and sell less.
                if pos <= -5:
                    buy_size = 3
                    sell_size = 1

                if buy_capacity > 0:
                    qty = min(buy_size, buy_capacity)
                    orders.append(Order(product, bid_quote, qty))

                if sell_capacity > 0:
                    qty = min(sell_size, sell_capacity)
                    orders.append(Order(product, ask_quote, -qty))
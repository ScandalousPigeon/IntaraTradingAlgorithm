from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:
    PRODUCT = "SLEEP_POD_SUEDE"
    LIMIT = 10

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_sleep_pod_suede_v2(state, result, data)

        return result, 0, json.dumps(data)

    def clamp(self, x, lo, hi):
        return max(lo, min(hi, x))

    def trade_sleep_pod_suede_v2(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict,
    ) -> None:

        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)

        bid_vol = order_depth.buy_orders[best_bid]
        ask_vol = -order_depth.sell_orders[best_ask]

        if bid_vol <= 0 or ask_vol <= 0:
            return

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        real_pos = state.position.get(product, 0)
        sim_pos = real_pos

        k = "suede_v2_"

        # ---------- Approx PnL tracking for safety lock ----------
        last_pos = int(data.get(k + "last_pos", real_pos))
        last_mid = float(data.get(k + "last_mid", mid))
        cash = float(data.get(k + "cash", 0.0))

        pos_change = real_pos - last_pos
        if pos_change != 0:
            # Approximate fill price. Good enough for profit-lock logic.
            cash -= pos_change * last_mid

        mtm = cash + real_pos * mid
        peak = float(data.get(k + "peak", mtm))
        peak = max(peak, mtm)

        locked = bool(data.get(k + "locked", False))

        PROFIT_LOCK = 1150
        TRAIL_STOP = 450
        HARD_STOP = -850

        if mtm >= PROFIT_LOCK:
            locked = True

        if peak - mtm >= TRAIL_STOP and peak > 500:
            locked = True

        if mtm <= HARD_STOP:
            locked = True

        # If locked, flatten and stop trading the product.
        if locked:
            if real_pos > 0:
                qty = min(real_pos, bid_vol)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))

            elif real_pos < 0:
                qty = min(-real_pos, ask_vol)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))

            data[k + "cash"] = cash
            data[k + "peak"] = peak
            data[k + "locked"] = locked
            data[k + "last_pos"] = real_pos
            data[k + "last_mid"] = mid
            return

        # ---------- Fast trend model ----------
        fast = float(data.get(k + "fast", mid))
        slow = float(data.get(k + "slow", mid))
        vol = float(data.get(k + "vol", 6.0))

        FAST_ALPHA = 0.18
        SLOW_ALPHA = 0.025

        fast = fast + FAST_ALPHA * (mid - fast)
        slow = slow + SLOW_ALPHA * (mid - slow)

        trend = fast - slow
        vol = 0.88 * vol + 0.12 * abs(mid - last_mid)

        hist = data.get(k + "hist", [])
        hist.append(mid)
        if len(hist) > 40:
            hist = hist[-40:]

        ret_5 = 0
        ret_15 = 0
        ret_30 = 0

        if len(hist) > 6:
            ret_5 = mid - hist[-6]
        if len(hist) > 16:
            ret_15 = mid - hist[-16]
        if len(hist) > 31:
            ret_30 = mid - hist[-31]

        total_book = bid_vol + ask_vol
        imbalance = 0
        if total_book > 0:
            imbalance = (bid_vol - ask_vol) / total_book

        # ---------- Crash / squeeze filters ----------
        falling_fast = ret_5 < -30 or ret_15 < -70 or ret_30 < -110
        rising_fast = ret_5 > 30 or ret_15 > 70 or ret_30 > 110

        # Avoid trading garbage books.
        if spread > 16:
            target = 0
        else:
            target = 0

            if trend > 16 and not falling_fast:
                target = 6
            if trend > 28 and not falling_fast:
                target = 10

            if trend < -16 and not rising_fast:
                target = -6
            if trend < -28 and not rising_fast:
                target = -10

            # Small order-book confirmation.
            if target > 0 and imbalance < -0.35:
                target = max(0, target - 4)
            elif target < 0 and imbalance > 0.35:
                target = min(0, target + 4)

        # Emergency: if we are long and price is falling hard, get out.
        if real_pos > 0 and falling_fast:
            target = min(target, 0)

        # Emergency: if we are short and price is rising hard, get out.
        if real_pos < 0 and rising_fast:
            target = max(target, 0)

        # Use current mid as fair base. This prevents stale fair-value dip buying.
        trend_skew = self.clamp(0.45 * trend, -18, 18)
        imbalance_skew = 2.0 * imbalance
        inventory_skew = -0.75 * sim_pos

        fair = mid + trend_skew + imbalance_skew + inventory_skew

        TAKE_EDGE = max(8, 6 + 0.35 * vol)
        PASSIVE_EDGE = 3

        MAX_TAKE = 4
        MAX_PASSIVE = 2
        MAX_EXIT = 6

        def buy_capacity():
            return self.LIMIT - sim_pos

        def sell_capacity():
            return self.LIMIT + sim_pos

        # ---------- If target is lower than current position, sell / flatten ----------
        if target < sim_pos:
            need = sim_pos - target
            qty = min(need, sell_capacity(), bid_vol, MAX_EXIT)

            # Cross when we are reducing risk or bid is rich.
            if qty > 0 and (sim_pos > 0 or best_bid >= fair + TAKE_EDGE):
                orders.append(Order(product, best_bid, -qty))
                sim_pos -= qty

        # ---------- If target is higher than current position, buy / cover ----------
        if target > sim_pos:
            need = target - sim_pos
            qty = min(need, buy_capacity(), ask_vol, MAX_EXIT)

            # Cross when we are reducing risk or ask is cheap.
            if qty > 0 and (sim_pos < 0 or best_ask <= fair - TAKE_EDGE):
                orders.append(Order(product, best_ask, qty))
                sim_pos += qty

        # ---------- Passive one-sided entry only ----------
        # This avoids the old version constantly quoting both sides and getting trapped.

        if target > sim_pos and not falling_fast and spread >= 6:
            need = target - sim_pos
            qty = min(need, buy_capacity(), MAX_PASSIVE)

            if qty > 0:
                buy_price = min(best_bid + 1, best_ask - 1, math.floor(fair - PASSIVE_EDGE))
                if buy_price > best_bid - 3 and buy_price < best_ask:
                    orders.append(Order(product, int(buy_price), qty))
                    sim_pos += qty

        elif target < sim_pos and not rising_fast and spread >= 6:
            need = sim_pos - target
            qty = min(need, sell_capacity(), MAX_PASSIVE)

            if qty > 0:
                sell_price = max(best_ask - 1, best_bid + 1, math.ceil(fair + PASSIVE_EDGE))
                if sell_price < best_ask + 3 and sell_price > best_bid:
                    orders.append(Order(product, int(sell_price), -qty))
                    sim_pos -= qty

        # ---------- Save state ----------
        data[k + "fast"] = fast
        data[k + "slow"] = slow
        data[k + "vol"] = vol
        data[k + "hist"] = hist

        data[k + "cash"] = cash
        data[k + "peak"] = peak
        data[k + "locked"] = locked

        data[k + "last_pos"] = real_pos
        data[k + "last_mid"] = mid
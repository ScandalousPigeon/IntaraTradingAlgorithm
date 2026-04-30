from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "SNACKPACK_VANILLA"
    REF_PRODUCT = "SNACKPACK_CHOCOLATE"

    LIMIT = 10
    MAX_STEP = 10

    # Vanilla and Chocolate are strongly inverse.
    WARMUP = 120

    # Fast mean of VANILLA + CHOCOLATE.
    SUM_ALPHA = 0.02

    # Slow rolling regression VANILLA ~= intercept + beta * CHOCOLATE.
    OLS_ALPHA = 0.001

    # Spread is wide, so only cross when edge is real.
    ENTRY_EDGE = 20
    EXIT_EDGE = 2

    # Require both models to mostly agree.
    CONFIRM_FRAC = 0.60

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_vanilla(state, result, data)

        return result, 0, json.dumps(data)

    def trade_vanilla(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        od = state.order_depths[product]
        if not od.buy_orders or not od.sell_orders:
            return

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        mid = (best_bid + best_ask) / 2

        pos = state.position.get(product, 0)

        key = "snackpack_vanilla_pair_v1"
        s = data.get(key, {})

        # Reset if timestamp rolls over between days.
        last_ts = s.get("last_ts")
        if last_ts is not None and state.timestamp < last_ts:
            s = {}

        count = s.get("count", 0)

        # Vanilla-only fallback.
        vanilla_ema = s.get("vanilla_ema", mid)
        fallback_fair = vanilla_ema

        fair = fallback_fair
        fair_sum = fallback_fair
        fair_ols = fallback_fair

        has_ref = self.REF_PRODUCT in state.order_depths

        if has_ref:
            ref_od = state.order_depths[self.REF_PRODUCT]

            if ref_od.buy_orders and ref_od.sell_orders:
                ref_bid = max(ref_od.buy_orders)
                ref_ask = min(ref_od.sell_orders)
                ref_mid = (ref_bid + ref_ask) / 2

                pair_sum = mid + ref_mid

                sum_ema = s.get("sum_ema", pair_sum)
                fair_sum = sum_ema - ref_mid

                # Rolling OLS moments.
                mx = s.get("mx", ref_mid)
                my = s.get("my", mid)
                mxx = s.get("mxx", ref_mid * ref_mid)
                mxy = s.get("mxy", ref_mid * mid)

                var_x = mxx - mx * mx
                cov_xy = mxy - mx * my

                if var_x > 1.0:
                    beta = cov_xy / var_x
                else:
                    beta = -1.0

                # Vanilla/chocolate should be inverse. Clamp bad early estimates.
                if beta > -0.20 or beta < -1.80:
                    beta = -1.0

                intercept = my - beta * mx
                fair_ols = intercept + beta * ref_mid

                fair = 0.50 * fair_sum + 0.50 * fair_ols

                # Update after decision.
                s["next_sum_ema"] = (1 - self.SUM_ALPHA) * sum_ema + self.SUM_ALPHA * pair_sum
                s["next_mx"] = (1 - self.OLS_ALPHA) * mx + self.OLS_ALPHA * ref_mid
                s["next_my"] = (1 - self.OLS_ALPHA) * my + self.OLS_ALPHA * mid
                s["next_mxx"] = (1 - self.OLS_ALPHA) * mxx + self.OLS_ALPHA * ref_mid * ref_mid
                s["next_mxy"] = (1 - self.OLS_ALPHA) * mxy + self.OLS_ALPHA * ref_mid * mid

        if count >= self.WARMUP:
            ask_volume = abs(od.sell_orders[best_ask])
            bid_volume = abs(od.buy_orders[best_bid])

            buy_room = self.LIMIT - pos
            sell_room = self.LIMIT + pos

            buy_signal = (
                best_ask <= fair - self.ENTRY_EDGE
                and best_ask <= fair_sum - self.ENTRY_EDGE * self.CONFIRM_FRAC
                and best_ask <= fair_ols - self.ENTRY_EDGE * self.CONFIRM_FRAC
            )

            sell_signal = (
                best_bid >= fair + self.ENTRY_EDGE
                and best_bid >= fair_sum + self.ENTRY_EDGE * self.CONFIRM_FRAC
                and best_bid >= fair_ols + self.ENTRY_EDGE * self.CONFIRM_FRAC
            )

            if buy_signal and buy_room > 0:
                qty = min(self.MAX_STEP, buy_room, ask_volume)
                if qty > 0:
                    result[product].append(Order(product, best_ask, qty))

            elif sell_signal and sell_room > 0:
                qty = min(self.MAX_STEP, sell_room, bid_volume)
                if qty > 0:
                    result[product].append(Order(product, best_bid, -qty))

            # Exit once vanilla mean-reverts close to fair.
            elif pos > 0 and best_bid >= fair - self.EXIT_EDGE:
                qty = min(self.MAX_STEP, pos, bid_volume)
                if qty > 0:
                    result[product].append(Order(product, best_bid, -qty))

            elif pos < 0 and best_ask <= fair + self.EXIT_EDGE:
                qty = min(self.MAX_STEP, -pos, ask_volume)
                if qty > 0:
                    result[product].append(Order(product, best_ask, qty))

        # Finalise state.
        s["count"] = count + 1
        s["last_ts"] = state.timestamp
        s["vanilla_ema"] = (1 - self.SUM_ALPHA) * vanilla_ema + self.SUM_ALPHA * mid

        if "next_sum_ema" in s:
            s["sum_ema"] = s.pop("next_sum_ema")
            s["mx"] = s.pop("next_mx")
            s["my"] = s.pop("next_my")
            s["mxx"] = s.pop("next_mxx")
            s["mxy"] = s.pop("next_mxy")

        data[key] = s
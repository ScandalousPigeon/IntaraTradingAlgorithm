from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_panel_2x4_v2(state, result, data)

        return result, 0, json.dumps(data)

    def trade_panel_2x4_v2(self, state: TradingState, result: dict, data: dict) -> None:
        product = "PANEL_2X4"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        # =====================
        # MEMORY
        # =====================

        key = "panel_2x4_v2"

        if key not in data:
            data[key] = {}

        memory = data[key]

        # Reset memory if timestamp goes backwards, useful across separate tests/days.
        if "last_timestamp" in memory and state.timestamp < memory["last_timestamp"]:
            memory.clear()

        if "open_mid" not in memory:
            memory["open_mid"] = mid
            memory["fast"] = mid
            memory["slow"] = mid
            memory["previous_mid"] = mid
            memory["session_high"] = mid
            memory["session_low"] = mid
            memory["target"] = 0
            memory["tick"] = 0
            memory["last_switch_tick"] = -9999

        memory["tick"] += 1
        memory["last_timestamp"] = state.timestamp

        tick = memory["tick"]

        previous_mid = memory["previous_mid"]
        change = mid - previous_mid

        FAST_ALPHA = 0.15
        SLOW_ALPHA = 0.025

        fast = memory["fast"] + FAST_ALPHA * (mid - memory["fast"])
        slow = memory["slow"] + SLOW_ALPHA * (mid - memory["slow"])

        memory["fast"] = fast
        memory["slow"] = slow
        memory["previous_mid"] = mid

        memory["session_high"] = max(memory["session_high"], mid)
        memory["session_low"] = min(memory["session_low"], mid)

        open_mid = memory["open_mid"]
        session_high = memory["session_high"]
        session_low = memory["session_low"]

        momentum = fast - slow
        from_open = mid - open_mid
        bounce_from_low = mid - session_low
        pullback_from_high = session_high - mid

        # =====================
        # SIGNAL PARAMETERS
        # =====================

        WARMUP_TICKS = 8

        # How far from open before we trust a directional move.
        OPEN_ENTRY = 80

        # EMA trend threshold.
        MOMENTUM_ENTRY = 25

        # Recovery threshold from the day's low.
        RECOVERY_BOUNCE = 180

        # Breakdown threshold from the day's high.
        BREAKDOWN_PULLBACK = 140

        # Exit thresholds.
        MOMENTUM_EXIT = 8
        OPEN_EXIT = 25

        # Prevent constant flipping.
        COOLDOWN_TICKS = 8

        old_target = memory.get("target", 0)
        desired_target = old_target

        # =====================
        # TARGET POSITION LOGIC
        # =====================

        if tick < WARMUP_TICKS:
            desired_target = 0

        else:
            strong_downtrend = (
                from_open < -OPEN_ENTRY
                or momentum < -MOMENTUM_ENTRY
                or (pullback_from_high > BREAKDOWN_PULLBACK and momentum < 0)
            )

            strong_uptrend = (
                from_open > OPEN_ENTRY
                or momentum > MOMENTUM_ENTRY
                or (bounce_from_low > RECOVERY_BOUNCE and momentum > 0)
            )

            recovery_after_selloff = (
                old_target <= 0
                and bounce_from_low > RECOVERY_BOUNCE
                and momentum > MOMENTUM_EXIT
            )

            breakdown_after_rally = (
                old_target >= 0
                and pullback_from_high > BREAKDOWN_PULLBACK
                and momentum < -MOMENTUM_EXIT
            )

            # Main idea:
            # - short the kind of downtrend shown in your PnL graph
            # - only flip long after a real bounce from the low
            if recovery_after_selloff:
                desired_target = LIMIT

            elif breakdown_after_rally:
                desired_target = -LIMIT

            elif strong_downtrend and not recovery_after_selloff:
                desired_target = -LIMIT

            elif strong_uptrend:
                desired_target = LIMIT

            else:
                # If the signal weakens, flatten instead of blindly holding risk.
                if old_target > 0:
                    if momentum > MOMENTUM_EXIT or from_open > OPEN_EXIT:
                        desired_target = old_target
                    else:
                        desired_target = 0

                elif old_target < 0:
                    if momentum < -MOMENTUM_EXIT or from_open < -OPEN_EXIT:
                        desired_target = old_target
                    else:
                        desired_target = 0

                else:
                    desired_target = 0

        # Cooldown to avoid overtrading.
        last_switch_tick = memory.get("last_switch_tick", -9999)

        if desired_target != old_target:
            if tick - last_switch_tick >= COOLDOWN_TICKS:
                memory["target"] = desired_target
                memory["last_switch_tick"] = tick
            else:
                desired_target = old_target

        target_position = max(-LIMIT, min(LIMIT, memory["target"]))

        # =====================
        # EXECUTE TOWARDS TARGET
        # =====================

        # Need to buy.
        if position < target_position:
            buy_needed = target_position - position

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if buy_needed <= 0:
                    break

                ask_volume = -order_depth.sell_orders[ask_price]

                if ask_volume <= 0:
                    continue

                qty = min(ask_volume, buy_needed, LIMIT - position)

                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    position += qty
                    buy_needed -= qty

            # Passive top-up if not fully filled.
            if position < target_position:
                passive_price = min(best_bid + 1, best_ask - 1)

                if passive_price < best_ask:
                    qty = min(target_position - position, LIMIT - position)

                    if qty > 0:
                        orders.append(Order(product, passive_price, qty))

        # Need to sell.
        elif position > target_position:
            sell_needed = position - target_position

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if sell_needed <= 0:
                    break

                bid_volume = order_depth.buy_orders[bid_price]

                if bid_volume <= 0:
                    continue

                qty = min(bid_volume, sell_needed, LIMIT + position)

                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    position -= qty
                    sell_needed -= qty

            # Passive top-up if not fully filled.
            if position > target_position:
                passive_price = max(best_ask - 1, best_bid + 1)

                if passive_price > best_bid:
                    qty = min(position - target_position, LIMIT + position)

                    if qty > 0:
                        orders.append(Order(product, passive_price, -qty))
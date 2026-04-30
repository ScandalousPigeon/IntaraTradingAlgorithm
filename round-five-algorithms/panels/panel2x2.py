from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json


class Trader:
    PRODUCT = "PANEL_2X2"

    LIMIT = 10

    # Faster fair value than the old 1000-tick rolling mean.
    FAIR_ALPHA = 2 / (200 + 1)

    # Trend EMAs.
    FAST_ALPHA = 2 / (40 + 1)
    SLOW_ALPHA = 2 / (220 + 1)

    WARMUP = 100

    # Mean reversion only when price is very far from fair.
    ENTRY_EDGE = 120
    EXIT_EDGE = 5

    # Strong trend threshold.
    TREND_EDGE = 160
    TREND_EXIT = 35

    # Risk control.
    STOP_LOSS = 180
    MAX_HOLD = 700
    COOLDOWN = 35

    MAX_SPREAD = 12
    MAX_STEP = 10

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_panel_2x2(state, result, data)

        return result, 0, json.dumps(data)

    def trade_panel_2x2(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2

        key = product + "_v2"
        pdata = data.get(key, {})

        seen = int(pdata.get("seen", 0))

        if seen == 0:
            fair = mid
            fast = mid
            slow = mid
        else:
            fair = float(pdata.get("fair", mid))
            fast = float(pdata.get("fast", mid))
            slow = float(pdata.get("slow", mid))

            fair += self.FAIR_ALPHA * (mid - fair)
            fast += self.FAST_ALPHA * (mid - fast)
            slow += self.SLOW_ALPHA * (mid - slow)

        seen += 1

        target = int(pdata.get("target", 0))
        entry_price = pdata.get("entry_price", None)
        mode = pdata.get("mode", "")
        hold = int(pdata.get("hold", 0))
        cooldown = int(pdata.get("cooldown", 0))

        if cooldown > 0:
            cooldown -= 1

        if target != 0:
            hold += 1
        else:
            hold = 0
            mode = ""

        dev = mid - fair
        trend = fast - slow

        if seen >= self.WARMUP:
            exit_now = False

            # Risk exits.
            if target > 0:
                adverse_move = entry_price - mid if entry_price is not None else 0

                if adverse_move >= self.STOP_LOSS:
                    exit_now = True
                elif hold >= self.MAX_HOLD:
                    exit_now = True
                elif mode == "mr" and dev >= -self.EXIT_EDGE:
                    exit_now = True
                elif mode == "mr" and trend < -self.TREND_EDGE * 1.25:
                    exit_now = True
                elif mode == "trend" and trend < self.TREND_EXIT:
                    exit_now = True

            elif target < 0:
                adverse_move = mid - entry_price if entry_price is not None else 0

                if adverse_move >= self.STOP_LOSS:
                    exit_now = True
                elif hold >= self.MAX_HOLD:
                    exit_now = True
                elif mode == "mr" and dev <= self.EXIT_EDGE:
                    exit_now = True
                elif mode == "mr" and trend > self.TREND_EDGE * 1.25:
                    exit_now = True
                elif mode == "trend" and trend > -self.TREND_EXIT:
                    exit_now = True

            if exit_now:
                target = 0
                entry_price = None
                mode = ""
                hold = 0
                cooldown = self.COOLDOWN

            # Entries.
            if target == 0 and cooldown <= 0:
                # Strong uptrend: follow long.
                if trend >= self.TREND_EDGE and dev > self.EXIT_EDGE:
                    target = self.LIMIT
                    entry_price = mid
                    mode = "trend"
                    hold = 0

                # Strong downtrend: follow short.
                elif trend <= -self.TREND_EDGE and dev < -self.EXIT_EDGE:
                    target = -self.LIMIT
                    entry_price = mid
                    mode = "trend"
                    hold = 0

                # Mean reversion long, but only if trend is not strongly down.
                elif dev <= -self.ENTRY_EDGE and trend >= -self.TREND_EDGE:
                    target = self.LIMIT
                    entry_price = mid
                    mode = "mr"
                    hold = 0

                # Mean reversion short, but only if trend is not strongly up.
                elif dev >= self.ENTRY_EDGE and trend <= self.TREND_EDGE:
                    target = -self.LIMIT
                    entry_price = mid
                    mode = "mr"
                    hold = 0

        pdata["seen"] = seen
        pdata["fair"] = fair
        pdata["fast"] = fast
        pdata["slow"] = slow
        pdata["target"] = target
        pdata["entry_price"] = entry_price
        pdata["mode"] = mode
        pdata["hold"] = hold
        pdata["cooldown"] = cooldown
        data[key] = pdata

        if spread > self.MAX_SPREAD:
            return

        position = state.position.get(product, 0)

        if target > position:
            self.buy_towards_target(product, order_depth, result, position, target)

        elif target < position:
            self.sell_towards_target(product, order_depth, result, position, target)

    def buy_towards_target(
        self,
        product: str,
        order_depth: OrderDepth,
        result: Dict[str, List[Order]],
        position: int,
        target: int,
    ) -> None:
        need = min(target - position, self.LIMIT - position, self.MAX_STEP)

        if need <= 0:
            return

        for ask_price in sorted(order_depth.sell_orders.keys()):
            ask_volume = order_depth.sell_orders[ask_price]
            available = -ask_volume if ask_volume < 0 else ask_volume

            qty = min(need, available)

            if qty > 0:
                result[product].append(Order(product, ask_price, qty))
                need -= qty

            if need <= 0:
                break

    def sell_towards_target(
        self,
        product: str,
        order_depth: OrderDepth,
        result: Dict[str, List[Order]],
        position: int,
        target: int,
    ) -> None:
        need = min(position - target, self.LIMIT + position, self.MAX_STEP)

        if need <= 0:
            return

        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            bid_volume = order_depth.buy_orders[bid_price]
            available = bid_volume if bid_volume > 0 else -bid_volume

            qty = min(need, available)

            if qty > 0:
                result[product].append(Order(product, bid_price, -qty))
                need -= qty

            if need <= 0:
                break
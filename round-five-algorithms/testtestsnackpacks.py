from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json
import math


class Trader:

    CHOCOLATE = "SNACKPACK_CHOCOLATE"
    VANILLA = "SNACKPACK_VANILLA"

    LIMIT = 10

    # Slow moving estimate of CHOCOLATE + VANILLA fair sum
    ALPHA = 0.015

    # Wait before trading so the EMA/std can stabilise
    WARMUP = 40

    # Z-score thresholds
    ENTRY_Z = 1.15
    STRONG_ENTRY_Z = 1.90
    EXIT_Z = 0.45

    # If z-score is too extreme, assume regime break and flatten
    REGIME_BREAK_Z = 3.40

    # Position targets
    SMALL_TARGET = 3
    NORMAL_TARGET = 5
    STRONG_TARGET = 8

    ORDER_SIZE = 2

    # Avoid aggressive crossing in wide spreads
    MAX_AGGRESSIVE_SPREAD = 8

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            result[product] = []

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        if "snack_cv" not in data:
            data["snack_cv"] = {}

        self.trade_chocolate_vanilla(state, result, data)

        return result, 0, json.dumps(data)

    def best_bid_ask(self, order_depth: OrderDepth):
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None, None

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        return best_bid, best_ask

    def mid_price(self, order_depth: OrderDepth):
        best_bid, best_ask = self.best_bid_ask(order_depth)

        if best_bid is None or best_ask is None:
            return None

        return (best_bid + best_ask) / 2

    def update_pair_stats(self, data: dict, pair_sum: float):
        stats = data["snack_cv"]

        count = stats.get("count", 0) + 1

        if count == 1:
            stats["count"] = count
            stats["mean"] = pair_sum
            stats["var"] = 100.0
            stats["prev_residual"] = 0.0
            stats["residual_momentum"] = 0.0

            return {
                "count": count,
                "mean": pair_sum,
                "std": 10.0,
                "residual": 0.0,
                "z": 0.0,
                "momentum": 0.0,
            }

        old_mean = stats["mean"]
        old_var = stats["var"]
        old_residual = stats.get("prev_residual", 0.0)
        old_momentum = stats.get("residual_momentum", 0.0)

        mean = (1 - self.ALPHA) * old_mean + self.ALPHA * pair_sum
        residual = pair_sum - mean

        var = (1 - self.ALPHA) * old_var + self.ALPHA * (residual ** 2)
        std = max(math.sqrt(var), 8.0)

        residual_change = residual - old_residual
        momentum = 0.85 * old_momentum + 0.15 * residual_change

        z = residual / std

        stats["count"] = count
        stats["mean"] = mean
        stats["var"] = var
        stats["prev_residual"] = residual
        stats["residual_momentum"] = momentum

        return {
            "count": count,
            "mean": mean,
            "std": std,
            "residual": residual,
            "z": z,
            "momentum": momentum,
        }

    def choose_pair_target(self, z: float, momentum: float):
        abs_z = abs(z)

        # Spread is behaving abnormally.
        # Do not keep fighting it. Flatten instead.
        if abs_z >= self.REGIME_BREAK_Z:
            return 0, True

        # Pair sum is too high:
        # CHOCOLATE + VANILLA expensive, so short both.
        if z >= self.STRONG_ENTRY_Z:
            if momentum <= 0:
                return -self.STRONG_TARGET, True
            else:
                return -self.SMALL_TARGET, False

        if z >= self.ENTRY_Z:
            return -self.NORMAL_TARGET, False

        # Pair sum is too low:
        # CHOCOLATE + VANILLA cheap, so long both.
        if z <= -self.STRONG_ENTRY_Z:
            if momentum >= 0:
                return self.STRONG_TARGET, True
            else:
                return self.SMALL_TARGET, False

        if z <= -self.ENTRY_Z:
            return self.NORMAL_TARGET, False

        # Signal has mostly disappeared, flatten.
        if abs_z <= self.EXIT_Z:
            return 0, False

        # Between exit and entry: reduce exposure slowly.
        return 0, False

    def move_towards_target(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        product: str,
        target: int,
        aggressive: bool
    ) -> None:

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid, best_ask = self.best_bid_ask(order_depth)

        if best_bid is None or best_ask is None:
            return

        spread = best_ask - best_bid
        position = state.position.get(product, 0)

        target = max(-self.LIMIT, min(self.LIMIT, target))

        delta = target - position

        if delta == 0:
            return

        orders = result[product]

        # Need to buy
        if delta > 0:
            buy_capacity = self.LIMIT - position

            if buy_capacity <= 0:
                return

            quantity = min(self.ORDER_SIZE, delta, buy_capacity)

            if quantity <= 0:
                return

            if aggressive and spread <= self.MAX_AGGRESSIVE_SPREAD:
                price = best_ask
            else:
                # Passive/improving bid without crossing the ask
                price = min(best_bid + 1, best_ask - 1)
                price = max(price, best_bid)

            orders.append(Order(product, price, quantity))

        # Need to sell
        else:
            sell_capacity = self.LIMIT + position

            if sell_capacity <= 0:
                return

            quantity = min(self.ORDER_SIZE, -delta, sell_capacity)

            if quantity <= 0:
                return

            if aggressive and spread <= self.MAX_AGGRESSIVE_SPREAD:
                price = best_bid
            else:
                # Passive/improving ask without crossing the bid
                price = max(best_ask - 1, best_bid + 1)
                price = min(price, best_ask)

            orders.append(Order(product, price, -quantity))

    def trade_chocolate_vanilla(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict
    ) -> None:

        if self.CHOCOLATE not in state.order_depths:
            return

        if self.VANILLA not in state.order_depths:
            return

        chocolate_mid = self.mid_price(state.order_depths[self.CHOCOLATE])
        vanilla_mid = self.mid_price(state.order_depths[self.VANILLA])

        if chocolate_mid is None or vanilla_mid is None:
            return

        pair_sum = chocolate_mid + vanilla_mid

        stats = self.update_pair_stats(data, pair_sum)

        if stats["count"] < self.WARMUP:
            return

        z = stats["z"]
        momentum = stats["momentum"]

        target, aggressive = self.choose_pair_target(z, momentum)

        self.move_towards_target(
            state,
            result,
            self.CHOCOLATE,
            target,
            aggressive
        )

        self.move_towards_target(
            state,
            result,
            self.VANILLA,
            target,
            aggressive
        )
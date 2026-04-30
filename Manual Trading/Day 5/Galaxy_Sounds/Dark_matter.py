from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        product = "GALAXY_SOUNDS_DARK_MATTER"

        if product in state.order_depths:
            result[product] = self.trade_dark_matter_swing_mr(
                product=product,
                order_depth=state.order_depths[product],
                position=state.position.get(product, 0),
                data=data
            )

        return result, 0, json.dumps(data)

    def trade_dark_matter_swing_mr(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        # =====================
        # PARAMETERS
        # =====================

        LIMIT = 10

        # very slow swing fair
        FAIR_ALPHA = 0.0001

        # EW variance estimate
        VAR_ALPHA = 0.0005

        ENTRY_Z = 1.5
        EXIT_Z = 0.4

        TRADE_SIZE = 2

        # =====================
        # FAIR + VOL ESTIMATE
        # =====================

        fair_key = product + "_fair"
        var_key = product + "_var"
        mode_key = product + "_mode"

        if fair_key not in data:
            data[fair_key] = mid

        fair = FAIR_ALPHA * mid + (1 - FAIR_ALPHA) * data[fair_key]
        data[fair_key] = fair

        deviation = mid - fair

        if var_key not in data:
            data[var_key] = 10000.0

        var = VAR_ALPHA * (deviation ** 2) + (1 - VAR_ALPHA) * data[var_key]
        data[var_key] = var

        std = math.sqrt(max(var, 1.0))

        z = deviation / std

        trend_key = product + "_trend_fair"

        if trend_key not in data:
            data[trend_key] = mid

        trend_fair = 0.00005 * mid + (1 - 0.00005) * data[trend_key]
        trend = fair - trend_fair

        data[trend_key] = trend_fair

        STOP_Z = 3.2

        if mode_key not in data:
            data[mode_key] = 0

        mode = data[mode_key]

        if mode == 0:
            # only buy dips if broader trend is not strongly down
            if z < -ENTRY_Z and trend > -40:
                mode = 1

            # only short rallies if broader trend is not strongly up
            elif z > ENTRY_Z and trend < 40:
                mode = -1

        elif mode == 1:
            # normal exit
            if z > -EXIT_Z:
                mode = 0

            # stop loss: dip kept falling
            elif z < -STOP_Z:
                mode = 0

        elif mode == -1:
            # normal exit
            if z < EXIT_Z:
                mode = 0

            # stop loss: rally kept going
            elif z > STOP_Z:
                mode = 0
        
        data[mode_key] = mode

        # =====================
        # TARGET POSITION
        # =====================

        if mode == 1:
            target_position = LIMIT
        elif mode == -1:
            target_position = -LIMIT
        else:
            target_position = 0

        diff = target_position - position

        # =====================
        # EXECUTION
        # =====================

        if diff > 0:
            qty = min(diff, TRADE_SIZE, best_ask_volume)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        elif diff < 0:
            qty = min(-diff, TRADE_SIZE, best_bid_volume)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        return orders
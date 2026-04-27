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
        # HYDROGEL_PACK
        # -------------------------

        hydrogel = "HYDROGEL_PACK"

        if hydrogel in state.order_depths:
            order_depth = state.order_depths[hydrogel]
            position = state.position.get(hydrogel, 0)

            result[hydrogel] = self.trade_hydrogel(
                product=hydrogel,
                order_depth=order_depth,
                position=position,
                data=data
            )

        # -------------------------
        # VELVETFRUIT + OPTIONS
        # -------------------------

        self.trade_velvetfruit_and_options(
            state=state,
            result=result,
            data=data
        )

        return result, 0, json.dumps(data)

    # ============================================================
    # HYDROGEL_PACK
    # ============================================================

    def trade_hydrogel(
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

        mid = (best_bid + best_ask) / 2

        # Parameters
        LIMIT = 200
        BASE_FAIR = 9991

        ALPHA = 0.03
        ANCHOR_WEIGHT = 0.02

        EDGE = 5
        ORDER_SIZE = 16
        INVENTORY_SKEW = 0.03

        # Fair value
        if "hydrogel_fair" not in data:
            data["hydrogel_fair"] = BASE_FAIR
        else:
            data["hydrogel_fair"] = (
                ALPHA * mid
                + (1 - ALPHA) * data["hydrogel_fair"]
            )

        fair = data["hydrogel_fair"]

        # Weak pull to long-run centre
        fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
        data["hydrogel_fair"] = fair

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # Inventory skew
        adjusted_fair = fair - INVENTORY_SKEW * position

        # Passive market-making quotes
        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        # Avoid crossing too much
        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        if buy_room > 0:
            buy_qty = min(ORDER_SIZE, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(ORDER_SIZE, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        return orders

    # ============================================================
    # VELVETFRUIT + OPTIONS
    # ============================================================

    def trade_velvetfruit_and_options(
        self,
        state: TradingState,
        result: dict,
        data: dict
    ) -> None:

        underlying = "VELVETFRUIT_EXTRACT"
        option_products = ["VEV_5100", "VEV_5200", "VEV_5300"]

        if underlying not in state.order_depths:
            return

        order_depth = state.order_depths[underlying]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        # =====================
        # UNDERLYING SIGNAL
        # =====================

        BASE_FAIR = 5250
        ALPHA = 0.002

        if "fair" not in data:
            data["fair"] = BASE_FAIR

        fair = ALPHA * mid + (1 - ALPHA) * data["fair"]
        data["fair"] = fair

        if "last_mid" not in data:
            data["last_mid"] = mid

        momentum = mid - data["last_mid"]
        data["last_mid"] = mid

        MOMENTUM_SKEW = 0.1

        signal = fair - mid - MOMENTUM_SKEW * momentum

        WARMUP_TIME = 5000

        # In the single-product version, warmup returned from run().
        # Here we only skip Velvetfruit/options so Hydrogel can still trade.
        if state.timestamp < WARMUP_TIME:
            return

        # =====================
        # TRADE UNDERLYING
        # =====================

        position = state.position.get(underlying, 0)

        UNDERLYING_LIMIT = 200
        PASSIVE_SIZE = 15
        PASSIVE_EDGE = 4
        INVENTORY_SKEW = 0.08

        buy_room = UNDERLYING_LIMIT - position
        sell_room = UNDERLYING_LIMIT + position

        adjusted_fair = fair - INVENTORY_SKEW * position + MOMENTUM_SKEW * momentum

        bid_price = int(round(adjusted_fair - PASSIVE_EDGE))
        ask_price = int(round(adjusted_fair + PASSIVE_EDGE))

        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        if buy_room > 0:
            result[underlying].append(
                Order(underlying, bid_price, min(PASSIVE_SIZE, buy_room))
            )

        if sell_room > 0:
            result[underlying].append(
                Order(underlying, ask_price, -min(PASSIVE_SIZE, sell_room))
            )

        # =====================
        # TRADE OPTIONS DIRECTIONALLY
        # =====================

        OPTION_LIMIT = 300
        OPTION_SIZE = 30

        BUY_CALL_THRESHOLD = 10
        SELL_CALL_THRESHOLD = -10

        # bullish: fair value above market -> buy calls
        bullish = signal > BUY_CALL_THRESHOLD

        # bearish: fair value below market -> sell calls
        bearish = signal < SELL_CALL_THRESHOLD

        for option in option_products:

            if option not in state.order_depths:
                continue

            depth = state.order_depths[option]

            if not depth.buy_orders or not depth.sell_orders:
                continue

            opt_bid = max(depth.buy_orders.keys())
            opt_ask = min(depth.sell_orders.keys())

            opt_bid_volume = depth.buy_orders[opt_bid]
            opt_ask_volume = -depth.sell_orders[opt_ask]

            opt_position = state.position.get(option, 0)

            opt_buy_room = OPTION_LIMIT - opt_position
            opt_sell_room = OPTION_LIMIT + opt_position

            # Buy calls when underlying looks cheap
            if bullish and opt_buy_room > 0:
                qty = min(OPTION_SIZE, opt_ask_volume, opt_buy_room)

                if qty > 0:
                    result[option].append(Order(option, opt_ask, qty))

            # Sell calls when underlying looks expensive
            if bearish and opt_sell_room > 0:
                qty = min(OPTION_SIZE, opt_bid_volume, opt_sell_room)

                if qty > 0:
                    result[option].append(Order(option, opt_bid, -qty))
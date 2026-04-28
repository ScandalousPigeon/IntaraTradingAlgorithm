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

        hydrogel = "HYDROGEL_PACK"

        if hydrogel in state.order_depths:
            result[hydrogel] = self.trade_hydrogel(
                product=hydrogel,
                order_depth=state.order_depths[hydrogel],
                position=state.position.get(hydrogel, 0),
                data=data
            )

        self.trade_velvetfruit_and_options(state, result, data)

        return result, 0, json.dumps(data)

    # ============================================================
    # HELPERS
    # ============================================================

    def norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def call_delta(self, S: float, K: float, T: float, sigma: float) -> float:
        if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
            return 0.0

        d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
        return self.norm_cdf(d1)

    def get_strike_from_voucher(self, product: str):
        try:
            return int(product.split("_")[1])
        except:
            return None

    # ============================================================
    # HYDROGEL
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

        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        mid = (best_bid + best_ask) / 2

        LIMIT = 200
        BASE_FAIR = 9991

        ALPHA = 0.03
        ANCHOR_WEIGHT = 0.02

        EDGE = 5
        ORDER_SIZE = 16
        INVENTORY_SKEW = 0.03

        if "hydrogel_fair" not in data:
            data["hydrogel_fair"] = BASE_FAIR
        else:
            data["hydrogel_fair"] = (
                ALPHA * mid + (1 - ALPHA) * data["hydrogel_fair"]
            )

        fair = data["hydrogel_fair"]
        fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
        data["hydrogel_fair"] = fair

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        adjusted_fair = fair - INVENTORY_SKEW * position

        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        if buy_room > 0:
            orders.append(Order(product, bid_price, min(ORDER_SIZE, buy_room)))

        if sell_room > 0:
            orders.append(Order(product, ask_price, -min(ORDER_SIZE, sell_room)))

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

        option_products = [
            product for product in state.order_depths
            if product.startswith("VEV_")
        ]

        if underlying not in state.order_depths:
            return

        order_depth = state.order_depths[underlying]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        mid = (best_bid + best_ask) / 2

        # =====================
        # UNDERLYING SIGNAL
        # =====================

        BASE_FAIR = 5250
        ALPHA = 0.002
        MOMENTUM_SKEW = 0.1

        if "fair" not in data:
            data["fair"] = BASE_FAIR

        fair = ALPHA * mid + (1 - ALPHA) * data["fair"]
        data["fair"] = fair

        if "last_mid" not in data:
            data["last_mid"] = mid

        momentum = mid - data["last_mid"]
        data["last_mid"] = mid

        signal = fair - mid - MOMENTUM_SKEW * momentum

        # longer warmup, since this worked better for you
        WARMUP_TIME = 12000

        if state.timestamp < WARMUP_TIME:
            return

        # =====================
        # UNDERLYING PASSIVE TRADE
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
        # OPTION TRADING
        # =====================

        OPTION_LIMIT = 300

        TTE_DAYS = 4
        TRADING_DAYS_PER_YEAR = 252
        T = TTE_DAYS / TRADING_DAYS_PER_YEAR

        ASSUMED_VOL = 0.18

        BASE_OPTION_SIZE = 60
        MIN_OPTION_SIZE = 5

        HIGH_THRESHOLD = 17
        LOW_THRESHOLD = 10

        MOMENTUM_CONFIRM = 8

        # adaptive threshold:
        # strict in chop, looser when move is strong
        if abs(momentum) >= MOMENTUM_CONFIRM:
            threshold = LOW_THRESHOLD
        else:
            threshold = HIGH_THRESHOLD

        bullish = signal > threshold
        bearish = signal < -threshold

        for option in option_products:

            if option not in state.order_depths:
                continue

            strike = self.get_strike_from_voucher(option)

            if strike is None:
                continue

            depth = state.order_depths[option]

            if not depth.buy_orders or not depth.sell_orders:
                continue

            opt_bid = max(depth.buy_orders)
            opt_ask = min(depth.sell_orders)

            opt_bid_volume = depth.buy_orders[opt_bid]
            opt_ask_volume = -depth.sell_orders[opt_ask]

            opt_position = state.position.get(option, 0)

            opt_buy_room = OPTION_LIMIT - opt_position
            opt_sell_room = OPTION_LIMIT + opt_position

            delta = self.call_delta(
                S=mid,
                K=strike,
                T=T,
                sigma=ASSUMED_VOL
            )

            option_size = max(MIN_OPTION_SIZE, int(BASE_OPTION_SIZE * delta))

            # hit much harder only on elite signals
            abs_signal = abs(signal)

            if abs_signal > 35:
                option_size *= 3
            elif abs_signal > 25:
                option_size *= 2

            # avoid exploding into max inventory too fast
            position_scale = max(
                0.4,
                1.0 - abs(opt_position) / OPTION_LIMIT
            )

            option_size = int(option_size * position_scale)

            if option_size <= 0:
                continue

            if bullish and opt_buy_room > 0:
                qty = min(option_size, opt_ask_volume, opt_buy_room)

                if qty > 0:
                    result[option].append(Order(option, opt_ask, qty))

            elif bearish and opt_sell_room > 0:
                qty = min(option_size, opt_bid_volume, opt_sell_room)

                if qty > 0:
                    result[option].append(Order(option, opt_bid, -qty))
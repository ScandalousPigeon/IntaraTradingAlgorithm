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

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        # =====================
        # BASE SIGNAL
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

        base_signal = fair - mid - MOMENTUM_SKEW * momentum

        # =====================
        # VEV_4000 + VEV_5400 TRADER FLOW
        # =====================

        FLOW_DECAY = 0.85

        FLOW_WEIGHT_4000 = 0.15
        FLOW_WEIGHT_5400 = 0.20

        if "vev4000_flow" not in data:
            data["vev4000_flow"] = 0.0

        if "vev5400_flow" not in data:
            data["vev5400_flow"] = 0.0

        vev4000_flow = data["vev4000_flow"] * FLOW_DECAY
        vev5400_flow = data["vev5400_flow"] * FLOW_DECAY

        # ---- VEV_4000 behaviour ----
        for trade in state.market_trades.get("VEV_4000", []):

            buyer = trade.buyer
            seller = trade.seller
            qty = trade.quantity

            if buyer == "Mark 14":
                vev4000_flow += qty

            if seller == "Mark 14":
                vev4000_flow -= qty

            if buyer == "Mark 38":
                vev4000_flow -= qty

            if seller == "Mark 38":
                vev4000_flow += qty

        # ---- VEV_5400 behaviour ----
        for trade in state.market_trades.get("VEV_5400", []):

            buyer = trade.buyer
            seller = trade.seller
            qty = trade.quantity

            # Mark 14 buying calls = bullish
            if buyer == "Mark 14":
                vev5400_flow += qty

            # Mark 38 buying calls = bearish / fade
            if buyer == "Mark 38":
                vev5400_flow -= qty

            # Mark 1 buying VEV_5400 = bearish
            if buyer == "Mark 1":
                vev5400_flow -= qty

            # Mark 22 selling VEV_5400 = bearish
            if seller == "Mark 22":
                vev5400_flow -= qty

        data["vev4000_flow"] = vev4000_flow
        data["vev5400_flow"] = vev5400_flow

        signal = (
            base_signal
            + FLOW_WEIGHT_4000 * vev4000_flow
            + FLOW_WEIGHT_5400 * vev5400_flow
        )

        WARMUP_TIME = 8000

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
        # TRADE ALL OPTIONS
        # =====================

        OPTION_LIMIT = 300

        TTE_DAYS = 4
        TRADING_DAYS_PER_YEAR = 252
        T = TTE_DAYS / TRADING_DAYS_PER_YEAR

        ASSUMED_VOL = 0.18

        BASE_OPTION_SIZE = 60

        BUY_CALL_THRESHOLD = 17
        SELL_CALL_THRESHOLD = -17

        for option in option_products:

            if option not in state.order_depths:
                continue

            strike = self.get_strike_from_voucher(option)

            if strike is None:
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

            delta = self.call_delta(
                S=mid,
                K=strike,
                T=T,
                sigma=ASSUMED_VOL
            )

            option_size = max(5, int(BASE_OPTION_SIZE * delta))

            if signal > BUY_CALL_THRESHOLD and opt_buy_room > 0:
                qty = min(option_size, opt_ask_volume, opt_buy_room)

                if qty > 0:
                    result[option].append(Order(option, opt_ask, qty))

            if signal < SELL_CALL_THRESHOLD and opt_sell_room > 0:
                qty = min(option_size, opt_bid_volume, opt_sell_room)

                if qty > 0:
                    result[option].append(Order(option, opt_bid, -qty))
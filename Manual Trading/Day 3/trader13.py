from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        underlying = "VELVETFRUIT_EXTRACT"

        option_products = [
            "VEV_4000",
            "VEV_4500",
            "VEV_5000",
            "VEV_5100",
            "VEV_5200",
            "VEV_5300",
            "VEV_5400",
        ]

        if underlying not in state.order_depths:
            return result, 0, json.dumps(data)

        depth = state.order_depths[underlying]
        if not depth.buy_orders or not depth.sell_orders:
            return result, 0, json.dumps(data)

        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        mid = (best_bid + best_ask) / 2

        # =====================
        # SIGNAL MODEL
        # =====================

        FAST_ALPHA = 0.05
        SLOW_ALPHA = 0.003
        SIGNAL_ALPHA = 0.25

        if "fast_fair" not in data:
            data["fast_fair"] = mid
        if "slow_fair" not in data:
            data["slow_fair"] = mid
        if "last_mid" not in data:
            data["last_mid"] = mid

        fast_fair = FAST_ALPHA * mid + (1 - FAST_ALPHA) * data["fast_fair"]
        slow_fair = SLOW_ALPHA * mid + (1 - SLOW_ALPHA) * data["slow_fair"]

        momentum = mid - data["last_mid"]

        raw_signal = fast_fair - slow_fair + 0.20 * momentum

        if "signal" not in data:
            data["signal"] = raw_signal

        signal = SIGNAL_ALPHA * raw_signal + (1 - SIGNAL_ALPHA) * data["signal"]

        data["fast_fair"] = fast_fair
        data["slow_fair"] = slow_fair
        data["last_mid"] = mid
        data["signal"] = signal

        if state.timestamp < 500:
            return result, 0, json.dumps(data)

        # =====================
        # UNDERLYING PASSIVE TRADING
        # =====================

        UNDERLYING_LIMIT = 200
        PASSIVE_SIZE = 20
        PASSIVE_EDGE = 3
        INVENTORY_SKEW = 0.06

        position = state.position.get(underlying, 0)

        buy_room = UNDERLYING_LIMIT - position
        sell_room = UNDERLYING_LIMIT + position

        adjusted_fair = slow_fair - INVENTORY_SKEW * position + 0.15 * momentum

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
        # ALL OPTION STRIKES
        # =====================

        OPTION_LIMIT = 300

        BUY_THRESHOLD = 3
        SELL_THRESHOLD = -3
        EXIT_THRESHOLD = 1

        option_params = {
            "VEV_4000": {"size": 0,  "max_spread": 0},   # disable
            "VEV_4500": {"size": 15, "max_spread": 18},
            "VEV_5000": {"size": 40, "max_spread": 22},
            "VEV_5100": {"size": 85, "max_spread": 30},
            "VEV_5200": {"size": 80, "max_spread": 30},
            "VEV_5300": {"size": 65, "max_spread": 28},
            "VEV_5400": {"size": 25, "max_spread": 20},
        }
        
        bullish = signal > BUY_THRESHOLD
        bearish = signal < SELL_THRESHOLD
        weak = abs(signal) < EXIT_THRESHOLD

        for option in option_products:

            if option not in state.order_depths:
                continue

            od = state.order_depths[option]
            if not od.buy_orders or not od.sell_orders:
                continue

            opt_bid = max(od.buy_orders)
            opt_ask = min(od.sell_orders)

            spread = opt_ask - opt_bid

            if spread > option_params[option]["max_spread"]:
                continue

            bid_volume = od.buy_orders[opt_bid]
            ask_volume = -od.sell_orders[opt_ask]

            opt_position = state.position.get(option, 0)

            opt_buy_room = OPTION_LIMIT - opt_position
            opt_sell_room = OPTION_LIMIT + opt_position

            base_size = option_params[option]["size"]

            trade_size = int(
                base_size * min(3.5, 1.0 + abs(signal) / 6.0)
            )

            if bullish and opt_buy_room > 0:
                qty = min(trade_size, ask_volume, opt_buy_room)
                if qty > 0:
                    result[option].append(Order(option, opt_ask, qty))

            elif bearish and opt_sell_room > 0:
                qty = min(trade_size, bid_volume, opt_sell_room)
                if qty > 0:
                    result[option].append(Order(option, opt_bid, -qty))

            elif weak:
                if opt_position > 0:
                    qty = min(abs(opt_position), base_size, bid_volume)
                    if qty > 0:
                        result[option].append(Order(option, opt_bid, -qty))

                elif opt_position < 0:
                    qty = min(abs(opt_position), base_size, ask_volume)
                    if qty > 0:
                        result[option].append(Order(option, opt_ask, qty))

        return result, 0, json.dumps(data)
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        # -------------------------
        # HYDROGEL_PACK
        # -------------------------

        hydrogel = "HYDROGEL_PACK"

        if hydrogel in state.order_depths:
            order_depth: OrderDepth = state.order_depths[hydrogel]
            position = state.position.get(hydrogel, 0)

            result[hydrogel] = self.trade_hydrogel(
                product=hydrogel,
                order_depth=order_depth,
                position=position,
                data=data
            )
        else:
            result[hydrogel] = []

        # -------------------------
        # VELVETFRUIT_EXTRACT
        # Commented out for now
        # -------------------------

        """
        velvetfruit = "VELVETFRUIT_EXTRACT"

        if velvetfruit in state.order_depths:
            order_depth: OrderDepth = state.order_depths[velvetfruit]
            position = state.position.get(velvetfruit, 0)

            result[velvetfruit] = self.trade_velvetfruit(
                product=velvetfruit,
                order_depth=order_depth,
                position=position,
                data=data,
                timestamp=state.timestamp
            )
        else:
            result[velvetfruit] = []
        """

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData

    def ema(self, previous, value, alpha):
        if previous is None:
            return value
        return alpha * value + (1 - alpha) * previous

    def update_hydrogel_history(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> dict:

        if "hydrogel_hist" not in data:
            data["hydrogel_hist"] = {}

        hist = data["hydrogel_hist"]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        if "last_mid" not in hist:
            hist["last_mid"] = mid

        momentum = mid - hist["last_mid"]
        hist["last_mid"] = mid

        hist["ticks"] = hist.get("ticks", 0) + 1

        # Smooth momentum
        hist["momentum_ema"] = self.ema(
            hist.get("momentum_ema"),
            momentum,
            0.20
        )

        # Fast/slow EMAs for trend detection
        hist["fast_ema"] = self.ema(
            hist.get("fast_ema"),
            mid,
            0.20
        )

        hist["slow_ema"] = self.ema(
            hist.get("slow_ema"),
            mid,
            0.03
        )

        trend = hist["fast_ema"] - hist["slow_ema"]
        hist["trend"] = trend

        # Spread EMA for dynamic edge
        hist["spread_ema"] = self.ema(
            hist.get("spread_ema"),
            spread,
            0.08
        )

        # Store some values for debugging / future testing
        hist["last_position"] = position
        hist["last_spread"] = spread
        hist["last_mid_value"] = mid

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "best_bid_volume": best_bid_volume,
            "best_ask_volume": best_ask_volume,
            "mid": mid,
            "momentum": momentum,
            "momentum_ema": hist["momentum_ema"],
            "trend": trend,
            "spread_ema": hist["spread_ema"],
            "ticks": hist["ticks"]
        }

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

        # -------------------------
        # Parameters
        # -------------------------

        LIMIT = 200
        BASE_FAIR = 9990

        ALPHA = 0.015
        ANCHOR_WEIGHT = 0.02

        EDGE = 6
        ORDER_SIZE = 16
        INVENTORY_SKEW = 0.03

        # Historical signal parameters
        MOMENTUM_SKEW = 0.08

        TREND_THRESHOLD = 8
        DANGER_POSITION = 120
        STRONG_DANGER_POSITION = 160

        USE_DYNAMIC_EDGE = True

        # -------------------------
        # Historical data
        # -------------------------

        hist = self.update_hydrogel_history(
            product=product,
            order_depth=order_depth,
            position=position,
            data=data
        )

        best_bid = hist["best_bid"]
        best_ask = hist["best_ask"]

        mid = hist["mid"]
        momentum = hist["momentum"]
        momentum_ema = hist["momentum_ema"]
        trend = hist["trend"]
        spread_ema = hist["spread_ema"]

        # -------------------------
        # Fair value
        # Same as your original logic
        # -------------------------

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

        # -------------------------
        # Position limits
        # -------------------------

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # -------------------------
        # Historical momentum signal
        # -------------------------

        momentum_signal = 0.5 * momentum + 0.5 * momentum_ema

        adjusted_fair = (
            fair
            - INVENTORY_SKEW * position
            + MOMENTUM_SKEW * momentum_signal
        )

        # -------------------------
        # Dynamic edge using spread history
        # -------------------------

        if USE_DYNAMIC_EDGE:
            dynamic_edge = int(round(spread_ema / 2 - 1))
            dynamic_edge = max(5, min(7, dynamic_edge))
        else:
            dynamic_edge = EDGE

        # -------------------------
        # Passive market-making quotes
        # -------------------------

        bid_price = int(round(adjusted_fair - dynamic_edge))
        ask_price = int(round(adjusted_fair + dynamic_edge))

        # Avoid crossing too much
        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        # -------------------------
        # Soft inventory/trend sizing
        # -------------------------

        buy_size = ORDER_SIZE
        sell_size = ORDER_SIZE

        # Already long and price trend is down:
        # buy less, sell more.
        if position > DANGER_POSITION and trend < -TREND_THRESHOLD:
            buy_size = 8
            sell_size = 20

        if position > STRONG_DANGER_POSITION and trend < -TREND_THRESHOLD:
            buy_size = 0
            sell_size = 24

        # Already short and price trend is up:
        # sell less, buy more.
        if position < -DANGER_POSITION and trend > TREND_THRESHOLD:
            sell_size = 8
            buy_size = 20

        if position < -STRONG_DANGER_POSITION and trend > TREND_THRESHOLD:
            sell_size = 0
            buy_size = 24

        # -------------------------
        # Orders
        # -------------------------

        if buy_room > 0 and buy_size > 0:
            buy_qty = min(buy_size, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0 and sell_size > 0:
            sell_qty = min(sell_size, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        return orders
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
        # -------------------------

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

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData

    # ============================================================
    # Helper
    # ============================================================

    def ema(self, previous, value, alpha):
        if previous is None:
            return value

        return alpha * value + (1 - alpha) * previous

    # ============================================================
    # HYDROGEL HISTORY
    # ============================================================

    def update_hydrogel_history(
        self,
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
        hist["last_position"] = position
        hist["last_spread"] = spread
        hist["last_momentum"] = momentum

        # Stored historical values for later testing.
        # These do not currently affect Hydrogel trading.
        hist["momentum_ema"] = self.ema(
            hist.get("momentum_ema"),
            momentum,
            0.20
        )

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

        hist["trend"] = hist["fast_ema"] - hist["slow_ema"]

        hist["spread_ema"] = self.ema(
            hist.get("spread_ema"),
            spread,
            0.08
        )

        hist["absret_ema"] = self.ema(
            hist.get("absret_ema"),
            abs(momentum),
            0.08
        )

        total_top_volume = best_bid_volume + best_ask_volume

        if total_top_volume > 0:
            imbalance = (best_bid_volume - best_ask_volume) / total_top_volume
        else:
            imbalance = 0

        hist["imbalance_ema"] = self.ema(
            hist.get("imbalance_ema"),
            imbalance,
            0.10
        )

        if "mid_hist" not in hist:
            hist["mid_hist"] = []

        hist["mid_hist"].append(round(mid, 1))
        hist["mid_hist"] = hist["mid_hist"][-20:]

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "best_bid_volume": best_bid_volume,
            "best_ask_volume": best_ask_volume,
            "mid": mid
        }

    # ============================================================
    # HYDROGEL TRADING
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

        hist = self.update_hydrogel_history(
            order_depth=order_depth,
            position=position,
            data=data
        )

        best_bid = hist["best_bid"]
        best_ask = hist["best_ask"]
        mid = hist["mid"]

        # Parameters
        LIMIT = 200
        BASE_FAIR = 9990

        ALPHA = 0.015
        ANCHOR_WEIGHT = 0.02

        EDGE = 6
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
    # VELVETFRUIT HISTORY
    # ============================================================

    def update_velvetfruit_history(
        self,
        order_depth: OrderDepth,
        data: dict,
        base_fair: float,
        alpha: float,
        momentum_ema_alpha: float,
        momentum_current_weight: float,
        momentum_ema_weight: float,
        imbalance_ema_alpha: float,
        book_skew: float,
        max_book_adjustment: float
    ) -> dict:

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        # -------------------------
        # Fair value
        # Same as your original Velvetfruit logic
        # -------------------------

        if "fair" not in data:
            data["fair"] = base_fair

        fair = alpha * mid + (1 - alpha) * data["fair"]
        data["fair"] = fair

        # -------------------------
        # Momentum
        # Same as your original Velvetfruit logic
        # -------------------------

        if "last_mid" not in data:
            data["last_mid"] = mid

        momentum = mid - data["last_mid"]
        data["last_mid"] = mid

        # -------------------------
        # Historical momentum EMA
        # Same as your original Velvetfruit logic
        # -------------------------

        if "momentum_ema" not in data:
            data["momentum_ema"] = momentum
        else:
            data["momentum_ema"] = (
                momentum_ema_alpha * momentum
                + (1 - momentum_ema_alpha) * data["momentum_ema"]
            )

        momentum_ema = data["momentum_ema"]

        momentum_signal = (
            momentum_current_weight * momentum
            + momentum_ema_weight * momentum_ema
        )

        # -------------------------
        # Historical order book imbalance
        # Same as your original Velvetfruit logic
        # -------------------------

        total_top_volume = best_bid_volume + best_ask_volume

        if total_top_volume > 0:
            imbalance = (
                best_bid_volume - best_ask_volume
            ) / total_top_volume
        else:
            imbalance = 0

        if "imbalance_ema" not in data:
            data["imbalance_ema"] = imbalance
        else:
            data["imbalance_ema"] = (
                imbalance_ema_alpha * imbalance
                + (1 - imbalance_ema_alpha) * data["imbalance_ema"]
            )

        imbalance_ema = data["imbalance_ema"]

        book_adjustment = book_skew * imbalance_ema
        book_adjustment = max(
            -max_book_adjustment,
            min(max_book_adjustment, book_adjustment)
        )

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "best_bid_volume": best_bid_volume,
            "best_ask_volume": best_ask_volume,
            "mid": mid,
            "fair": fair,
            "momentum": momentum,
            "momentum_ema": momentum_ema,
            "momentum_signal": momentum_signal,
            "imbalance": imbalance,
            "imbalance_ema": imbalance_ema,
            "book_adjustment": book_adjustment
        }

    # ============================================================
    # VELVETFRUIT TRADING
    # ============================================================

    def trade_velvetfruit(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict,
        timestamp: int
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        LIMIT = 200

        BASE_FAIR = 5250
        ALPHA = 0.002

        PASSIVE_EDGE = 4
        PASSIVE_SIZE = 15

        TAKE_EDGE = 8
        TAKE_SIZE = 15

        INVENTORY_SKEW = 0.08
        MOMENTUM_SKEW = 0.1

        # Historical momentum
        MOMENTUM_EMA_ALPHA = 0.20
        MOMENTUM_CURRENT_WEIGHT = 0.50
        MOMENTUM_EMA_WEIGHT = 0.50

        # Historical imbalance signal
        IMBALANCE_EMA_ALPHA = 0.20
        BOOK_SKEW = 1.5
        MAX_BOOK_ADJUSTMENT = 2

        hist = self.update_velvetfruit_history(
            order_depth=order_depth,
            data=data,
            base_fair=BASE_FAIR,
            alpha=ALPHA,
            momentum_ema_alpha=MOMENTUM_EMA_ALPHA,
            momentum_current_weight=MOMENTUM_CURRENT_WEIGHT,
            momentum_ema_weight=MOMENTUM_EMA_WEIGHT,
            imbalance_ema_alpha=IMBALANCE_EMA_ALPHA,
            book_skew=BOOK_SKEW,
            max_book_adjustment=MAX_BOOK_ADJUSTMENT
        )

        best_bid = hist["best_bid"]
        best_ask = hist["best_ask"]

        best_bid_volume = hist["best_bid_volume"]
        best_ask_volume = hist["best_ask_volume"]

        fair = hist["fair"]
        momentum_signal = hist["momentum_signal"]
        book_adjustment = hist["book_adjustment"]

        # Warmup: update fair/momentum/imbalance but do not trade yet
        WARMUP_TIME = 5000

        if timestamp < WARMUP_TIME:
            return orders

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        adjusted_fair = (
            fair
            - INVENTORY_SKEW * position
            + MOMENTUM_SKEW * momentum_signal
            + book_adjustment
        )

        # Passive market-making quotes
        bid_price = int(round(adjusted_fair - PASSIVE_EDGE))
        ask_price = int(round(adjusted_fair + PASSIVE_EDGE))

        # Do not cross the spread with passive orders
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        if buy_room > 0:
            buy_qty = min(PASSIVE_SIZE, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(PASSIVE_SIZE, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        # Small aggressive fills
        if best_ask < adjusted_fair - TAKE_EDGE and buy_room > 0:
            qty = min(TAKE_SIZE, best_ask_volume, buy_room)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        if best_bid > adjusted_fair + TAKE_EDGE and sell_room > 0:
            qty = min(TAKE_SIZE, best_bid_volume, sell_room)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        return orders
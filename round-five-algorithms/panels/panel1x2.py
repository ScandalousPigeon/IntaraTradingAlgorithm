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

        self.trade_panel_1x2(state, result, data)

        return result, 0, json.dumps(data)

    def trade_panel_1x2(self, state: TradingState, result: dict, data: dict) -> None:
        product = "PANEL_1X2"

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = []

        # =====================
        # PARAMETERS
        # =====================

        LIMIT = 10

        PASSIVE_EDGE = 3
        MIN_EDGE = 1.5

        PASSIVE_SIZE = 3
        TAKE_SIZE = 4

        TAKE_EDGE = 6.5

        INVENTORY_SKEW = 0.75

        TREND_WEIGHT = 0.25
        FLOW_WEIGHT = 0.20

        EMA_ALPHA = 0.03
        TREND_ALPHA = 0.10
        FLOW_DECAY = 0.80

        # =====================
        # ORDER BOOK
        # =====================

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        position = state.position.get(product, 0)

        # =====================
        # STORED STATE
        # =====================

        if product not in data:
            data[product] = {}

        pdata = data[product]

        ema = pdata.get("ema", mid)
        last_mid = pdata.get("last_mid", mid)
        trend = pdata.get("trend", 0.0)
        flow = pdata.get("flow", 0.0)

        # Smooth fair value, but do NOT anchor to a fixed base price.
        ema = (1 - EMA_ALPHA) * ema + EMA_ALPHA * mid

        mid_change = mid - last_mid
        trend = (1 - TREND_ALPHA) * trend + TREND_ALPHA * mid_change

        # =====================
        # MARKET TRADE FLOW SIGNAL
        # =====================

        raw_flow = 0

        for trade in state.market_trades.get(product, []):
            if trade.price >= best_ask:
                raw_flow += trade.quantity
            elif trade.price <= best_bid:
                raw_flow -= trade.quantity
            elif trade.price > mid:
                raw_flow += trade.quantity
            elif trade.price < mid:
                raw_flow -= trade.quantity

        flow = FLOW_DECAY * flow + raw_flow

        # Main fair value:
        # mostly current mid, with small trend/order-flow adjustment,
        # then inventory skew to avoid getting stuck long/short.
        fair = mid
        fair += TREND_WEIGHT * trend
        fair += FLOW_WEIGHT * flow
        fair -= INVENTORY_SKEW * position

        # Save state
        pdata["ema"] = ema
        pdata["last_mid"] = mid
        pdata["trend"] = trend
        pdata["flow"] = flow

        # =====================
        # AGGRESSIVE TAKING
        # =====================

        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # Buy obviously cheap asks
        if buy_capacity > 0:
            for ask_price in sorted(order_depth.sell_orders.keys()):
                ask_volume = -order_depth.sell_orders[ask_price]

                if ask_price <= fair - TAKE_EDGE:
                    qty = min(ask_volume, buy_capacity, TAKE_SIZE)

                    if qty > 0:
                        orders.append(Order(product, ask_price, qty))
                        buy_capacity -= qty
                        position += qty

                if buy_capacity <= 0:
                    break

        # Sell obviously expensive bids
        if sell_capacity > 0:
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                bid_volume = order_depth.buy_orders[bid_price]

                if bid_price >= fair + TAKE_EDGE:
                    qty = min(bid_volume, sell_capacity, TAKE_SIZE)

                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty))
                        sell_capacity -= qty
                        position -= qty

                if sell_capacity <= 0:
                    break

        # Recalculate capacity after taking
        buy_capacity = LIMIT - position
        sell_capacity = LIMIT + position

        # =====================
        # PASSIVE MARKET MAKING
        # =====================

        if spread > 2:

            # Quote inside the spread, but only if the quote still has edge vs fair.
            buy_quote = min(best_ask - 1, max(best_bid, math.floor(fair - PASSIVE_EDGE)))
            sell_quote = max(best_bid + 1, min(best_ask, math.ceil(fair + PASSIVE_EDGE)))

            # Buy quote
            if buy_capacity > 0 and buy_quote <= fair - MIN_EDGE:
                buy_size = PASSIVE_SIZE

                # If short, buy a little more aggressively to flatten.
                if position < 0:
                    buy_size += min(2, abs(position) // 3)

                qty = min(buy_size, buy_capacity)

                if qty > 0:
                    orders.append(Order(product, buy_quote, qty))

            # Sell quote
            if sell_capacity > 0 and sell_quote >= fair + MIN_EDGE:
                sell_size = PASSIVE_SIZE

                # If long, sell a little more aggressively to flatten.
                if position > 0:
                    sell_size += min(2, position // 3)

                qty = min(sell_size, sell_capacity)

                if qty > 0:
                    orders.append(Order(product, sell_quote, -qty))

        result[product] = orders
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:

    def run(self, state: TradingState):

        result = {}

        if state.traderData:
            data = json.loads(state.traderData)
        else:
            data = {}

        product = "VELVETFRUIT_EXTRACT"
        orders: List[Order] = []

        if product in state.order_depths:

            order_depth: OrderDepth = state.order_depths[product]

            if order_depth.buy_orders and order_depth.sell_orders:

                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())

                mid = (best_bid + best_ask) / 2

                # =========================
                # MODEL PARAMETERS
                # =========================

                LIMIT = 200

                BASE_FAIR = 5250          # observed long-run average
                ALPHA = 0.003             # slow EMA for 10,000-step simulation
                EDGE = 6                  # quote distance from fair
                ORDER_SIZE = 12           # passive order size
                INVENTORY_SKEW = 0.04     # shifts quotes against inventory

                # =========================
                # FAIR VALUE MODEL
                # =========================

                if "velvet_fair" not in data:
                    data["velvet_fair"] = BASE_FAIR
                else:
                    data["velvet_fair"] = (
                        ALPHA * mid
                        + (1 - ALPHA) * data["velvet_fair"]
                    )

                fair = data["velvet_fair"]

                # Pull fair slightly back toward the known long-run centre
                fair = 0.9 * fair + 0.1 * BASE_FAIR
                data["velvet_fair"] = fair

                # =========================
                # POSITION / INVENTORY
                # =========================

                position = state.position.get(product, 0)

                buy_room = LIMIT - position
                sell_room = LIMIT + position

                # If long, lower fair to encourage selling.
                # If short, raise fair to encourage buying.
                adjusted_fair = fair - INVENTORY_SKEW * position

                # =========================
                # PASSIVE MARKET MAKING
                # =========================

                bid_price = int(round(adjusted_fair - EDGE))
                ask_price = int(round(adjusted_fair + EDGE))

                # Do not cross the spread.
                # We want to provide liquidity, not constantly take liquidity.
                bid_price = min(bid_price, best_bid + 1)
                ask_price = max(ask_price, best_ask - 1)

                if buy_room > 0:
                    buy_qty = min(ORDER_SIZE, buy_room)
                    orders.append(Order(product, bid_price, buy_qty))

                if sell_room > 0:
                    sell_qty = min(ORDER_SIZE, sell_room)
                    orders.append(Order(product, ask_price, -sell_qty))

                # =========================
                # AGGRESSIVE MEAN REVERSION
                # =========================
                # Only cross the spread when price is very far from fair.

                AGGRESSIVE_EDGE = 18

                if best_ask < adjusted_fair - AGGRESSIVE_EDGE and buy_room > 0:
                    available = -order_depth.sell_orders[best_ask]
                    qty = min(available, buy_room, 25)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))

                if best_bid > adjusted_fair + AGGRESSIVE_EDGE and sell_room > 0:
                    available = order_depth.buy_orders[best_bid]
                    qty = min(available, sell_room, 25)
                    if qty > 0:
                        orders.append(Order(product, best_bid, -qty))

        result[product] = orders

        traderData = json.dumps(data)

        conversions = 0

        return result, conversions, traderData
    
    # 1700 
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string

class Trader:

    def bid(self):
        # for round 2
        return 15
    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        # for debugging:
        # print("traderData: " + state.traderData)
        # print("Observations: " + str(state.observations))

        # Orders to be placed on exchange matching engine
        result = {}
        for product in state.order_depths:
            position = state.position.get(product, 0)
            modifier = 3 if position < -40 else -3 if position > 40 else 0
            order_depth: OrderDepth = state.order_depths[product] # order book
            # each OrderDepth contains two dicts: buy_orders and sell_orders, mapping price to quantity
            orders: List[Order] = []
            if product == "INTARIAN_PEPPER_ROOT":
                orders += self.trade_pepper(order_depth, state.traderData, position)
            else:
                orders += self.trade_osmium(order_depth, position, modifier)

            if state.traderData == "":
                iteration = 0
            else:
                iteration = int(state.traderData)
            
            result[product] = orders

        # You can place info you want to persist to the next TradingState in traderData, 
        # and access it from the next TradingState's traderData. It must be a string.
        # Although, idk what we would use it for
          # No state needed - we check position directly
        next_trader_data = str(iteration + 1)
        conversions = 0
        return result, conversions, next_trader_data
    
    def trade_osmium(self, order_depth, position, modifier):
        result = []
        LIMIT = 80

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        for price, qty in sorted(order_depth.buy_orders.items(), reverse=True):
            if sell_room <= 0:
                break

            if price >= 10001 + modifier:
                sell_qty = min(qty, sell_room)   # qty in buy_orders is positive
                result.append(Order("ASH_COATED_OSMIUM", price, -sell_qty))
                sell_room -= sell_qty

        for price, qty in sorted(order_depth.sell_orders.items()):
            if buy_room <= 0:
                break

            if price <= 9999 + modifier:
                ask_size = -qty                  # qty in sell_orders is negative
                buy_qty = min(ask_size, buy_room)
                result.append(Order("ASH_COATED_OSMIUM", price, buy_qty))
                buy_room -= buy_qty

        return result

    def trade_pepper(self, order_depth, iteration, position):
        result = []
        LIMIT = 80
            
        if iteration == "":
            buy_room = min(8, max(0, LIMIT - position))
            for price, qty in sorted(order_depth.sell_orders.items()):
                if buy_room <= 0:
                    break
                available = -qty
                buy_qty = min(available, buy_room)
                result.append(Order("INTARIAN_PEPPER_ROOT", price, buy_qty))
                buy_room -= buy_qty

        elif int(iteration) < 10:
            buy_room = min(8, max(0, LIMIT - position))
            for price, qty in sorted(order_depth.sell_orders.items()):
                if buy_room <= 0:
                    break
                available = -qty
                buy_qty = min(available, buy_room)
                result.append(Order("INTARIAN_PEPPER_ROOT", price, buy_qty))
                buy_room -= buy_qty

        elif int(iteration) >= 9990:
            sell_qty_left = min(8, max(position, 0))
            for price, qty in sorted(order_depth.buy_orders.items(), reverse=True):
                if sell_qty_left <= 0:
                    break
                sell_qty = min(qty, sell_qty_left)
                result.append(Order("INTARIAN_PEPPER_ROOT", price, -sell_qty))
                sell_qty_left -= sell_qty
            
        return result
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
                orders += self.trade_pepper(order_depth, state.traderData)
            else:
                orders += self.trade_osmium(order_depth, modifier)

            if state.traderData == "":
                iteration = 0
            else:
                iteration = int(state.traderData)

            
            """ Provided example code
            acceptable_price = 10  # Participant should calculate this value
            print("Acceptable price : " + str(acceptable_price))
            print("Buy Order depth : " + str(len(order_depth.buy_orders)) + ", Sell order depth : " + str(len(order_depth.sell_orders)))
    
            if len(order_depth.sell_orders) != 0:
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                if int(best_ask) < acceptable_price:
                    # print("BUY", str(-best_ask_amount) + "x", best_ask)
                    orders.append(Order(product, best_ask, -best_ask_amount))
    
            if len(order_depth.buy_orders) != 0:
                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                if int(best_bid) > acceptable_price:
                    # print("SELL", str(best_bid_amount) + "x", best_bid)
                    orders.append(Order(product, best_bid, -best_bid_amount))"""
            
            result[product] = orders

        # You can place info you want to persist to the next TradingState in traderData, 
        # and access it from the next TradingState's traderData. It must be a string.
        # Although, idk what we would use it for
          # No state needed - we check position directly
        next_trader_data = str(iteration + 1)
        conversions = 0
        return result, conversions, next_trader_data
    
    def trade_osmium(self, order_depth, modifier):
        """Helper method; to call inside run() when trading osmium."""
        result = []
        
        for price, qty in order_depth.buy_orders.items():
            
            if price >= 10001 + modifier:
                # order_depth.buy_orders[price]
                result.append(Order("ASH_COATED_OSMIUM", price, -qty))
                
        for price, qty in order_depth.sell_orders.items():
            
            if price <= 9999 + modifier:
                # order_depth.sell_orders[price]
                result.append(Order("ASH_COATED_OSMIUM", price, -qty))
        
        
            
        return result

    def trade_pepper(self, order_depth, iteration):
        result = []
        
        if iteration == "":
            buy_room = 8
            for price, qty in order_depth.sell_orders.items():
                if buy_room <= 0:
                    break
                available = -qty          # sell_orders qty is negative
                buy_qty = min(available, buy_room)
                result.append(Order("INTARIAN_PEPPER_ROOT", price, buy_qty))
                buy_room -= buy_qty

        elif int(iteration) < int("10"):
            buy_room = 8
            for price, qty in order_depth.sell_orders.items():
                if buy_room <= 0:
                    break
                available = -qty          # sell_orders qty is negative
                buy_qty = min(available, buy_room)
                result.append(Order("INTARIAN_PEPPER_ROOT", price, buy_qty)) # change to 10000
                buy_room -= buy_qty

        elif int(iteration) >= int("990"):
            sell_qty_left = 8
            for price, qty in order_depth.buy_orders.items():
                if sell_qty_left <= 0:
                    break
                sell_qty = min(qty, sell_qty_left)
                result.append(Order("INTARIAN_PEPPER_ROOT", price, -sell_qty))
                sell_qty_left -= sell_qty

        return result
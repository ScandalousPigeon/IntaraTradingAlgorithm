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
            # position = state.position[product]
            order_depth: OrderDepth = state.order_depths[product] # order book
            # each OrderDepth contains two dicts: buy_orders and sell_orders, mapping price to quantity
            orders: List[Order] = []
            if product == "INTARIAN_PEPPER_ROOT":
                orders += self.trade_pepper(order_depth)
            else:
                orders += self.trade_osmium(order_depth)


            
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
        traderData = ""  # No state needed - we check position directly
        conversions = 0
        return result, conversions, traderData
    
    def trade_osmium(self, order_depth):
        """Helper method; to call inside run() when trading osmium."""
        result = []
        
        
        
        for price in order_depth.buy_orders:
            
            if price >= 10001:
                # order_depth.buy_orders[price]
                result.append(Order("ASH_COATED_OSMIUM", price, -5))
                
        for price in order_depth.sell_orders:
            
            if price <= 9999:
                # order_depth.sell_orders[price]
                result.append(Order("ASH_COATED_OSMIUM", price, 5))
        
            
        return result

    def trade_pepper(self, order_depth):
        """Helper method; to call inside run() when trading pepper."""
        result = []
        for price in order_depth.buy_orders:
            pass

        for price in order_depth.sell_orders:
            pass
        return result
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
            
            
            
            
            orders: List[Order] = []
            if product == "HYDROGEL_PACK":
                orders += self.trade_hydrogel()
            elif product == "VELVETFRUIT_EXTRACT":
                orders += self.trade_velvetfruit()
            else:
                orders += self.voucher()

            if state.traderData == "":
                iteration = 0
            else:
                iteration = int(state.traderData)
            
            result[product] = orders

        # You can place info you want to persist to the next TradingState in traderData, 
        # and access it from the next TradingState's traderData. It must be a string.
        
          # No state needed - we check position directly
        next_trader_data = str(iteration + 1)
        conversions = 0
        return result, conversions, next_trader_data
    
    def trade_hydrogel(self):
        result = []
        return result
    
    def trade_velvetfruit(self):
        result = []
        return result
    
    def voucher(self):
        result = []
        return result
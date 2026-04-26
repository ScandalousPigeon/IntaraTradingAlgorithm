intrinsic_value = 920

highest_profit = [0,670]

for first_bid_price in range(670,919):
    profit = 0
    for reserve_price in range(51):
        reserve_price = reserve_price * 5 + 670
        if first_bid_price > reserve_price:
            profit += (intrinsic_value-first_bid_price)
        if profit > highest_profit[0]:
            highest_profit = [profit,first_bid_price]

print (highest_profit)
        
# first_bid_profit optimised at 791, 3225
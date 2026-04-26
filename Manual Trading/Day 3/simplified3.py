intrinsic_value = 920
average_bid_others = 836 # change as needed


highest_profit = [0,670]

for first_bid_price in range(670,921):
    for second_bid_price in range(first_bid_price, 921):
        profit = 0
        for reserve_price in range(51):
            reserve_price = reserve_price * 5 + 670
            if first_bid_price > reserve_price:
                profit += (intrinsic_value-first_bid_price)
            elif second_bid_price > reserve_price:
                    if second_bid_price >= average_bid_others:
                         profit += (intrinsic_value - second_bid_price)
                    else:
                         discount_factor = ((intrinsic_value - average_bid_others)/(intrinsic_value - second_bid_price)) ** 3
                
                         profit += (intrinsic_value - second_bid_price) * discount_factor
            if profit > highest_profit[0]:
                highest_profit = [profit,first_bid_price, second_bid_price]
            

print (highest_profit)
        
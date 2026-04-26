intrinsic_value = 920


profit_maximise = []
for average_bid_others in range(671,920):
    highest_profit = [average_bid_others,0,670, 671]
    for first_bid_price in range(670,921):
        for second_bid_price in range(first_bid_price + 1, 921):
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
            if profit > highest_profit[1]:
                highest_profit = [average_bid_others, profit, first_bid_price, second_bid_price]
    profit_maximise.append(highest_profit)
            
import matplotlib.pyplot as plt

x = [row[0] for row in profit_maximise]  # average_bid_others
y = [row[1] for row in profit_maximise]  # maximum profit

plt.figure(figsize=(10,6))
plt.plot(x, y)

plt.xlabel("Average Bid of Others")
plt.ylabel("Maximum Profit")
plt.title("Maximum Profit vs Average Bid of Others")

plt.grid(True)
plt.show()


first_bids = [row[2] for row in profit_maximise]
second_bids = [row[3] for row in profit_maximise]

plt.figure(figsize=(10,6))

plt.plot(x, first_bids, label="Optimal First Bid")
plt.plot(x, second_bids, label="Optimal Second Bid")

plt.xlabel("Average Bid of Others")
plt.ylabel("Bid Value")
plt.title("Optimal Bids vs Average Bid of Others")

plt.legend()
plt.grid(True)
plt.show()


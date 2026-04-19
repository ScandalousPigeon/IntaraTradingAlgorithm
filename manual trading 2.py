import numpy as np
max_profit = 0
profit_max_x = 0
for x in range(100):
    research = 200_000 * np.log(1 + x) / np.log(1 + 100)
    scale = (100-x)*0.07
    if (research * scale * 0.1) > max_profit:
        max_profit = research * scale /10
        profit_max_x = x
        
print(profit_max_x, max_profit)
        

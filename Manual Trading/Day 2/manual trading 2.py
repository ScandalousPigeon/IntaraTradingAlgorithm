import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

optimal_allocation = []
for allocation in range (101):
    max_profit = 0
    profit_max_x = 0
    for x in range(allocation+1):
        research = 200_000 * np.log(1 + x) / np.log(1 + 100)
        scale = (allocation-x) * 0.07
        if (research * scale * 0.1) > max_profit:
            max_profit = round(research * scale /10 
            profit_max_x = x
    optimal_allocation.append([allocation, profit_max_x, max_profit])

optimal_allocation = np.array(optimal_allocation)

plt.figure(figsize=(8, 5))
plt.plot(optimal_allocation[:, 0], optimal_allocation[:, 2])
plt.xlabel("Allocation")
plt.ylabel("Max Profit")
plt.title("Allocation vs Max Profit")
plt.grid(True)
plt.show()


df = pd.DataFrame(optimal_allocation, columns=["Allocation", "Best_Research", "Max_Profit"])

df.to_excel("optimal_allocation.xlsx", index=False)
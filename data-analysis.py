import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def plot_csv(csv_file):
    df = pd.read_csv(csv_file)

    print(df.columns)

    # df.plot(x="Month", y="Revenue", kind="bar")

    plt.title(csv_file.stem)
    plt.xlabel("Month")
    plt.ylabel("Revenue")
    plt.show()

folder = Path("historical-csvs/round3")

for csv_file in folder.glob("*.csv"):
    plot_csv(csv_file)
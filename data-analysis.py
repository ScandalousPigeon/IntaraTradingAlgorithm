import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def plot_prices(csv_file):

    df = pd.read_csv(csv_file, sep=";")

    df.plot(x="timestamp", y="mid_price", kind="line")

    plt.title(csv_file.stem)
    plt.xlabel("Timestamp")
    plt.ylabel("Mid Price")
    output_file = Path("graphs") / f"{csv_file.stem}.png"
    plt.savefig(output_file)
    plt.close()

def plot_trades(csv_file):
    
    df = pd.read_csv(csv_file, sep=";")

    print(df.columns)

    df.plot(x="timestamp", y="price", kind="line")

    plt.title(csv_file.stem)
    plt.xlabel("Time")
    plt.ylabel("Price")
    
    
    output_file = Path("graphs") / f"{csv_file.stem}.png"
    plt.savefig(output_file)
    plt.close()

folder = Path("historical-csvs/round3")

for csv_file in folder.glob("*.csv"):
    if "prices" in csv_file.name:
        plot_prices(csv_file)
    elif "trades" in csv_file.name:
        plot_trades(csv_file)
    else:
        raise ValueError("huh")
import pandas as pd
import numpy as np
import json
from typing import Dict, List
from pathlib import Path
import math

import matplotlib
matplotlib.use("Agg")  # Linux/headless safe: no GUI window
import matplotlib.pyplot as plt


# ==================================================
# CONFIG
# ==================================================

DATA_DIR = Path(
    "/home/mechanicalpigeon/Documents/Projects/VSCodeProjects/IMCProsperity/historical-csvs/round5"
)

PRICE_FILES = [
    "prices_round_5_day_2.csv",
    "prices_round_5_day_3.csv",
    "prices_round_5_day_4.csv",
]

OUTPUT_PNG = "local_backtest_pnl.png"


# ==================================================
# SIMPLE LOCAL DATAMODEL FALLBACK
# only use this if you are not importing datamodel
# ==================================================

class Order:
    def __init__(self, symbol: str, price: int, quantity: int):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity

    def __repr__(self):
        return f"Order({self.symbol}, {self.price}, {self.quantity})"


class OrderDepth:
    def __init__(self):
        self.buy_orders = {}
        self.sell_orders = {}


class TradingState:
    def __init__(
        self,
        traderData,
        timestamp,
        listings,
        order_depths,
        own_trades,
        market_trades,
        position,
        observations
    ):
        self.traderData = traderData
        self.timestamp = timestamp
        self.listings = listings
        self.order_depths = order_depths
        self.own_trades = own_trades
        self.market_trades = market_trades
        self.position = position
        self.observations = observations


# ==================================================
# LOAD PRICE DATA
# ==================================================

def load_price_data() -> pd.DataFrame:
    dfs = []

    for file_name in PRICE_FILES:
        path = DATA_DIR / file_name

        if not path.exists():
            raise FileNotFoundError(
                f"Could not find {path}\n"
                f"Check DATA_DIR near the top of this file."
            )

        dfs.append(pd.read_csv(path, sep=";"))

    df = pd.concat(dfs, ignore_index=True)
    df = df.sort_values(["day", "timestamp", "product"])

    return df


# ==================================================
# BUILD ORDER DEPTH FROM ONE TIMESTAMP
# ==================================================

def build_order_depth(row):
    depth = OrderDepth()

    for level in [1, 2, 3]:
        bid_price_col = f"bid_price_{level}"
        bid_volume_col = f"bid_volume_{level}"
        ask_price_col = f"ask_price_{level}"
        ask_volume_col = f"ask_volume_{level}"

        if bid_price_col in row and not pd.isna(row[bid_price_col]):
            price = int(row[bid_price_col])
            volume = int(row[bid_volume_col])

            if volume != 0:
                depth.buy_orders[price] = volume

        if ask_price_col in row and not pd.isna(row[ask_price_col]):
            price = int(row[ask_price_col])
            volume = int(row[ask_volume_col])

            if volume != 0:
                # IMC datamodel usually stores sell volumes as negative
                depth.sell_orders[price] = -abs(volume)

    return depth


def build_state(snapshot, timestamp, positions, trader_data):
    order_depths = {}

    for _, row in snapshot.iterrows():
        product = row["product"]
        order_depths[product] = build_order_depth(row)

    state = TradingState(
        traderData=trader_data,
        timestamp=timestamp,
        listings={},
        order_depths=order_depths,
        own_trades={},
        market_trades={},
        position=positions.copy(),
        observations={}
    )

    return state


# ==================================================
# EXECUTION MODEL
# ==================================================

def execute_orders(orders, order_depths, positions, cash):
    trade_log = []

    for product, product_orders in orders.items():
        if product not in order_depths:
            continue

        depth = order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            continue

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_volume = depth.buy_orders[best_bid]
        ask_volume = -depth.sell_orders[best_ask]

        for order in product_orders:
            qty = order.quantity
            price = order.price

            # BUY: only fill if order crosses ask
            if qty > 0:
                if price >= best_ask:
                    fill_qty = min(qty, ask_volume)

                    if fill_qty > 0:
                        positions[product] = positions.get(product, 0) + fill_qty
                        cash[product] = cash.get(product, 0) - fill_qty * best_ask

                        trade_log.append({
                            "product": product,
                            "side": "BUY",
                            "price": best_ask,
                            "qty": fill_qty,
                        })

            # SELL: only fill if order crosses bid
            elif qty < 0:
                sell_qty = -qty

                if price <= best_bid:
                    fill_qty = min(sell_qty, bid_volume)

                    if fill_qty > 0:
                        positions[product] = positions.get(product, 0) - fill_qty
                        cash[product] = cash.get(product, 0) + fill_qty * best_bid

                        trade_log.append({
                            "product": product,
                            "side": "SELL",
                            "price": best_bid,
                            "qty": fill_qty,
                        })

    return trade_log


# ==================================================
# MARK TO MARKET
# ==================================================

def mark_to_market(order_depths, positions, cash):
    total = 0

    for product in order_depths:
        depth = order_depths[product]

        if not depth.buy_orders or not depth.sell_orders:
            continue

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        pos = positions.get(product, 0)
        product_cash = cash.get(product, 0)

        total += product_cash + pos * mid

    return total


# ==================================================
# BACKTEST
# ==================================================

def run_backtest(trader, df):
    positions = {}
    cash = {}
    trader_data = ""

    pnl_curve = []
    trade_logs = []

    grouped = df.groupby(["day", "timestamp"], sort=True)

    for (day, timestamp), snapshot in grouped:
        state = build_state(
            snapshot=snapshot,
            timestamp=timestamp,
            positions=positions,
            trader_data=trader_data
        )

        result, conversions, trader_data = trader.run(state)

        logs = execute_orders(
            orders=result,
            order_depths=state.order_depths,
            positions=positions,
            cash=cash
        )

        for log in logs:
            log["day"] = day
            log["timestamp"] = timestamp
            trade_logs.append(log)

        pnl = mark_to_market(
            order_depths=state.order_depths,
            positions=positions,
            cash=cash
        )

        pnl_curve.append({
            "day": day,
            "timestamp": timestamp,
            "pnl": pnl,
            **{f"pos_{p}": positions.get(p, 0) for p in positions}
        })

    pnl_df = pd.DataFrame(pnl_curve)
    trades_df = pd.DataFrame(trade_logs)

    return pnl_df, trades_df, positions, cash


# ==================================================
# SAVE PNG GRAPH
# ==================================================

def save_pnl_graph(pnl_df, output_path=OUTPUT_PNG):
    plt.figure(figsize=(12, 5))
    plt.plot(pnl_df["pnl"])
    plt.title("Local Backtest PnL")
    plt.xlabel("Step")
    plt.ylabel("PnL")
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close()

    print(f"Saved PnL graph to: {output_path}")


# ==================================================
# PASTE THE ALGORITHM YOU WANT TO TEST BELOW
# Replace this whole Trader class each time.
# ==================================================


class Trader:
    PRODUCT = "GALAXY_SOUNDS_SOLAR_WINDS"

    LIMIT = 10

    # Trend-following EMAs.
    # Solar Winds tends to move in chunky directional waves,
    # so this version only trades when the fast trend separates strongly.
    FAST_ALPHA = 0.20
    SLOW_ALPHA = 0.01

    # Higher = fewer trades, safer.
    # Lower to 120 if this is still too inactive.
    ENTRY_SIGNAL = 150

    # Max amount to cross per tick.
    MAX_STEP = 5

    # Avoid weird/wide books.
    MAX_SPREAD = 18

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_solar_winds(state, result, data)

        return result, 0, json.dumps(data)

    def trade_solar_winds(self, state: TradingState, result: Dict[str, List[Order]], data: dict) -> None:
        product = self.PRODUCT

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        if best_bid >= best_ask:
            return

        spread = best_ask - best_bid

        if spread > self.MAX_SPREAD:
            return

        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        memory = data.get(product, {})

        fast = memory.get("fast", mid)
        slow = memory.get("slow", mid)

        # Update EMAs using current mid.
        fast = self.FAST_ALPHA * mid + (1 - self.FAST_ALPHA) * fast
        slow = self.SLOW_ALPHA * mid + (1 - self.SLOW_ALPHA) * slow

        signal = fast - slow

        memory["fast"] = fast
        memory["slow"] = slow
        memory["signal"] = signal
        data[product] = memory

        buy_capacity = self.LIMIT - position
        sell_capacity = self.LIMIT + position

        best_ask_volume = abs(order_depth.sell_orders[best_ask])
        best_bid_volume = abs(order_depth.buy_orders[best_bid])

        # =========================
        # AGGRESSIVE TREND FOLLOWING
        # =========================
        #
        # If fast EMA is far above slow EMA, momentum is up:
        # buy at the ask.
        #
        # If fast EMA is far below slow EMA, momentum is down:
        # sell at the bid.
        #
        # This crosses the spread, so it should actually produce fills.

        if signal > self.ENTRY_SIGNAL and buy_capacity > 0:
            qty = min(self.MAX_STEP, buy_capacity, best_ask_volume)

            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        elif signal < -self.ENTRY_SIGNAL and sell_capacity > 0:
            qty = min(self.MAX_STEP, sell_capacity, best_bid_volume)

            if qty > 0:
                orders.append(Order(product, best_bid, -qty))


# ==================================================
# RUN BACKTEST
# ==================================================

if __name__ == "__main__":
    df = load_price_data()

    trader = Trader()

    pnl_df, trades_df, final_positions, final_cash = run_backtest(trader, df)

    print("Final PnL:", pnl_df["pnl"].iloc[-1])
    print("Final positions:", final_positions)

    print()
    print("Trades:")
    print(trades_df.head(20))

    print()
    print("Trade count by product:")
    if len(trades_df) > 0:
        print(trades_df.groupby("product").size())
    else:
        print("No trades")

    save_pnl_graph(pnl_df)
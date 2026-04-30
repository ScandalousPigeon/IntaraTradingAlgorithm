import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import math


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
# Put trader code in here !!!!!!
# ==================================================
class Trader:
    PRODUCT = "SNACKPACK_RASPBERRY"
    HEDGE_PRODUCT = "SNACKPACK_PISTACHIO"

    LIMIT = 10

    # Historical fair model:
    # RASPBERRY fair ~= 14355.3001 - 0.450459 * PISTACHIO_mid
    PAIR_INTERCEPT = 14355.3001
    PAIR_BETA = -0.450459

    # Blend pair fair with own slow EMA
    PAIR_WEIGHT = 0.75
    EMA_ALPHA = 0.001

    WARMUP = 120

    # Only trade large dislocations because spread is often wide.
    ENTRY_EDGE = 120
    EXIT_EDGE = 3

    MAX_SPREAD = 14
    MAX_STEP = 10

    def run(self, state: TradingState):
        result = {product: [] for product in state.order_depths}

        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        self.trade_raspberry(state, result, data)

        return result, 0, json.dumps(data)

    def best_bid_ask(self, depth: OrderDepth):
        if not depth.buy_orders or not depth.sell_orders:
            return None

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_vol = depth.buy_orders[best_bid]
        ask_vol = abs(depth.sell_orders[best_ask])

        return best_bid, best_ask, bid_vol, ask_vol

    def mid_price(self, depth: OrderDepth):
        best = self.best_bid_ask(depth)
        if best is None:
            return None
        best_bid, best_ask, _, _ = best
        return (best_bid + best_ask) / 2

    def trade_raspberry(
        self,
        state: TradingState,
        result: Dict[str, List[Order]],
        data: dict,
    ) -> None:

        if self.PRODUCT not in state.order_depths:
            return

        depth = state.order_depths[self.PRODUCT]
        best = self.best_bid_ask(depth)
        if best is None:
            return

        best_bid, best_ask, bid_vol, ask_vol = best
        spread = best_ask - best_bid
        raspberry_mid = (best_bid + best_ask) / 2

        store = data.setdefault("snackpack_raspberry_v2", {})

        if "ema" not in store:
            store["ema"] = raspberry_mid
            store["n"] = 0

        store["ema"] = (
            self.EMA_ALPHA * raspberry_mid
            + (1 - self.EMA_ALPHA) * store["ema"]
        )
        store["n"] += 1

        if store["n"] < self.WARMUP:
            return

        # Pair fair from Pistachio if available
        pair_fair = None
        if self.HEDGE_PRODUCT in state.order_depths:
            pistachio_mid = self.mid_price(state.order_depths[self.HEDGE_PRODUCT])
            if pistachio_mid is not None:
                pair_fair = self.PAIR_INTERCEPT + self.PAIR_BETA * pistachio_mid

        # Fallback to own EMA if Pistachio is missing
        if pair_fair is None:
            fair = store["ema"]
        else:
            fair = self.PAIR_WEIGHT * pair_fair + (1 - self.PAIR_WEIGHT) * store["ema"]

        position = state.position.get(self.PRODUCT, 0)

        # Avoid donating edge in wide books
        if spread > self.MAX_SPREAD:
            return

        # Buy when Raspberry is much cheaper than relative fair
        if best_ask < fair - self.ENTRY_EDGE and position < self.LIMIT:
            qty = min(
                self.LIMIT - position,
                ask_vol,
                self.MAX_STEP,
            )
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_ask, qty))
                position += qty

        # Sell when Raspberry is much richer than relative fair
        elif best_bid > fair + self.ENTRY_EDGE and position > -self.LIMIT:
            qty = min(
                position + self.LIMIT,
                bid_vol,
                self.MAX_STEP,
            )
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_bid, -qty))
                position -= qty

        # Exit long when price has mean-reverted near fair
        if position > 0 and best_bid >= fair - self.EXIT_EDGE:
            qty = min(position, bid_vol, self.MAX_STEP)
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_bid, -qty))
                position -= qty

        # Exit short when price has mean-reverted near fair
        elif position < 0 and best_ask <= fair + self.EXIT_EDGE:
            qty = min(-position, ask_vol, self.MAX_STEP)
            if qty > 0:
                result[self.PRODUCT].append(Order(self.PRODUCT, best_ask, qty))
                position += qty


# ==================================================
# LOAD PRICE DATA
# ==================================================

import os

os.chdir(r"C:\Users\oscar\OneDrive\Python\IntaraTradingAlgorithm\historical-csvs\round5")

files = [
    "prices_round_5_day_2.csv",
    "prices_round_5_day_3.csv",
    "prices_round_5_day_4.csv",
]


df = pd.concat(
    [pd.read_csv(f, sep=";") for f in files],
    ignore_index=True
)

df = df.sort_values(["day", "timestamp", "product"])


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
                # datamodel usually stores sell volumes as negative
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
# RUN
# ==================================================

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

plt.figure(figsize=(12, 5))
plt.plot(pnl_df["pnl"])
plt.title("Local Backtest PnL")
plt.xlabel("Step")
plt.ylabel("PnL")
plt.grid(True)
plt.show()
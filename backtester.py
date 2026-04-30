import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt


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

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        pebbles = [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL",
        ]

        has_all = True

        for p in pebbles:
            if p not in state.order_depths:
                has_all = False

        if has_all:

            pebble_orders = self.trade_pebbles(
                state=state
            )

            for product in pebble_orders:
                result[product] = pebble_orders[product]

        return result, 0, json.dumps(data)

    def trade_pebbles(
        self,
        state: TradingState,
    ):

        orders = {}

        products = [
            "PEBBLES_XS",
            "PEBBLES_S",
            "PEBBLES_M",
            "PEBBLES_L",
            "PEBBLES_XL",
        ]

        mids = {}

        best_bids = {}
        best_asks = {}

        buy_volumes = {}
        sell_volumes = {}

        # =====================================
        # BUILD BOOK DATA
        # =====================================

        for product in products:

            orders[product] = []

            depth = state.order_depths[product]

            if not depth.buy_orders or not depth.sell_orders:
                return orders

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())

            best_bids[product] = best_bid
            best_asks[product] = best_ask

            mids[product] = (
                best_bid + best_ask
            ) / 2

            buy_volumes[product] = depth.buy_orders[best_bid]

            sell_volumes[product] = -depth.sell_orders[best_ask]

        # =====================================
        # PARAMETERS
        # =====================================

        LIMIT = 50

        ENTRY = 12
        EXIT = 1

        SIZE = 3

        MAX_ERROR = 80

        # =====================================
        # CHECK EACH PRODUCT
        # =====================================

        for target in products:

            others = []

            for p in products:
                if p != target:
                    others.append(p)

            fair = (
                50000
                - mids[others[0]]
                - mids[others[1]]
                - mids[others[2]]
                - mids[others[3]]
            )

            error = mids[target] - fair

            if abs(error) > MAX_ERROR:
                continue

            position = state.position.get(target, 0)

            # =====================================
            # OVERPRICED -> SELL
            # =====================================

            if error > ENTRY:

                if position > -LIMIT:

                    qty = min(
                        SIZE,
                        LIMIT + position,
                        buy_volumes[target]
                    )

                    if qty > 0:

                        orders[target].append(
                            Order(
                                target,
                                best_bids[target],
                                -qty
                            )
                        )

            # =====================================
            # UNDERPRICED -> BUY
            # =====================================

            elif error < -ENTRY:

                if position < LIMIT:

                    qty = min(
                        SIZE,
                        LIMIT - position,
                        sell_volumes[target]
                    )

                    if qty > 0:

                        orders[target].append(
                            Order(
                                target,
                                best_asks[target],
                                qty
                            )
                        )

            # =====================================
            # EXIT SHORT
            # =====================================

            elif position < 0 and error < EXIT:

                qty = min(
                    SIZE,
                    -position,
                    sell_volumes[target]
                )

                if qty > 0:

                    orders[target].append(
                        Order(
                            target,
                            best_asks[target],
                            qty
                        )
                    )

            # =====================================
            # EXIT LONG
            # =====================================

            elif position > 0 and error > -EXIT:

                qty = min(
                    SIZE,
                    position,
                    buy_volumes[target]
                )

                if qty > 0:

                    orders[target].append(
                        Order(
                            target,
                            best_bids[target],
                            -qty
                        )
                    )

        return orders
    

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
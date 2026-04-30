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

    def run(self, state: TradingState):
        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        self.trade_panel_2x4_v2(state, result, data)

        return result, 0, json.dumps(data)

    def trade_panel_2x4_v2(self, state: TradingState, result: dict, data: dict) -> None:
        product = "PANEL_2X4"
        LIMIT = 10

        if product not in state.order_depths:
            return

        order_depth: OrderDepth = state.order_depths[product]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        orders: List[Order] = result[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        position = state.position.get(product, 0)

        # =====================
        # MEMORY
        # =====================

        key = "panel_2x4_v2"

        if key not in data:
            data[key] = {}

        memory = data[key]

        # Reset memory if timestamp goes backwards, useful across separate tests/days.
        if "last_timestamp" in memory and state.timestamp < memory["last_timestamp"]:
            memory.clear()

        if "open_mid" not in memory:
            memory["open_mid"] = mid
            memory["fast"] = mid
            memory["slow"] = mid
            memory["previous_mid"] = mid
            memory["session_high"] = mid
            memory["session_low"] = mid
            memory["target"] = 0
            memory["tick"] = 0
            memory["last_switch_tick"] = -9999

        memory["tick"] += 1
        memory["last_timestamp"] = state.timestamp

        tick = memory["tick"]

        previous_mid = memory["previous_mid"]
        change = mid - previous_mid

        FAST_ALPHA = 0.15
        SLOW_ALPHA = 0.025

        fast = memory["fast"] + FAST_ALPHA * (mid - memory["fast"])
        slow = memory["slow"] + SLOW_ALPHA * (mid - memory["slow"])

        memory["fast"] = fast
        memory["slow"] = slow
        memory["previous_mid"] = mid

        memory["session_high"] = max(memory["session_high"], mid)
        memory["session_low"] = min(memory["session_low"], mid)

        open_mid = memory["open_mid"]
        session_high = memory["session_high"]
        session_low = memory["session_low"]

        momentum = fast - slow
        from_open = mid - open_mid
        bounce_from_low = mid - session_low
        pullback_from_high = session_high - mid

        # =====================
        # SIGNAL PARAMETERS
        # =====================

        WARMUP_TICKS = 8

        # How far from open before we trust a directional move.
        OPEN_ENTRY = 80

        # EMA trend threshold.
        MOMENTUM_ENTRY = 25

        # Recovery threshold from the day's low.
        RECOVERY_BOUNCE = 180

        # Breakdown threshold from the day's high.
        BREAKDOWN_PULLBACK = 140

        # Exit thresholds.
        MOMENTUM_EXIT = 8
        OPEN_EXIT = 25

        # Prevent constant flipping.
        COOLDOWN_TICKS = 8

        old_target = memory.get("target", 0)
        desired_target = old_target

        # =====================
        # TARGET POSITION LOGIC
        # =====================

        if tick < WARMUP_TICKS:
            desired_target = 0

        else:
            strong_downtrend = (
                from_open < -OPEN_ENTRY
                or momentum < -MOMENTUM_ENTRY
                or (pullback_from_high > BREAKDOWN_PULLBACK and momentum < 0)
            )

            strong_uptrend = (
                from_open > OPEN_ENTRY
                or momentum > MOMENTUM_ENTRY
                or (bounce_from_low > RECOVERY_BOUNCE and momentum > 0)
            )

            recovery_after_selloff = (
                old_target <= 0
                and bounce_from_low > RECOVERY_BOUNCE
                and momentum > MOMENTUM_EXIT
            )

            breakdown_after_rally = (
                old_target >= 0
                and pullback_from_high > BREAKDOWN_PULLBACK
                and momentum < -MOMENTUM_EXIT
            )

            # Main idea:
            # - short the kind of downtrend shown in your PnL graph
            # - only flip long after a real bounce from the low
            if recovery_after_selloff:
                desired_target = LIMIT

            elif breakdown_after_rally:
                desired_target = -LIMIT

            elif strong_downtrend and not recovery_after_selloff:
                desired_target = -LIMIT

            elif strong_uptrend:
                desired_target = LIMIT

            else:
                # If the signal weakens, flatten instead of blindly holding risk.
                if old_target > 0:
                    if momentum > MOMENTUM_EXIT or from_open > OPEN_EXIT:
                        desired_target = old_target
                    else:
                        desired_target = 0

                elif old_target < 0:
                    if momentum < -MOMENTUM_EXIT or from_open < -OPEN_EXIT:
                        desired_target = old_target
                    else:
                        desired_target = 0

                else:
                    desired_target = 0

        # Cooldown to avoid overtrading.
        last_switch_tick = memory.get("last_switch_tick", -9999)

        if desired_target != old_target:
            if tick - last_switch_tick >= COOLDOWN_TICKS:
                memory["target"] = desired_target
                memory["last_switch_tick"] = tick
            else:
                desired_target = old_target

        target_position = max(-LIMIT, min(LIMIT, memory["target"]))

        # =====================
        # EXECUTE TOWARDS TARGET
        # =====================

        # Need to buy.
        if position < target_position:
            buy_needed = target_position - position

            for ask_price in sorted(order_depth.sell_orders.keys()):
                if buy_needed <= 0:
                    break

                ask_volume = -order_depth.sell_orders[ask_price]

                if ask_volume <= 0:
                    continue

                qty = min(ask_volume, buy_needed, LIMIT - position)

                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    position += qty
                    buy_needed -= qty

            # Passive top-up if not fully filled.
            if position < target_position:
                passive_price = min(best_bid + 1, best_ask - 1)

                if passive_price < best_ask:
                    qty = min(target_position - position, LIMIT - position)

                    if qty > 0:
                        orders.append(Order(product, passive_price, qty))

        # Need to sell.
        elif position > target_position:
            sell_needed = position - target_position

            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if sell_needed <= 0:
                    break

                bid_volume = order_depth.buy_orders[bid_price]

                if bid_volume <= 0:
                    continue

                qty = min(bid_volume, sell_needed, LIMIT + position)

                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    position -= qty
                    sell_needed -= qty

            # Passive top-up if not fully filled.
            if position > target_position:
                passive_price = max(best_ask - 1, best_bid + 1)

                if passive_price > best_bid:
                    qty = min(position - target_position, LIMIT + position)

                    if qty > 0:
                        orders.append(Order(product, passive_price, -qty))

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
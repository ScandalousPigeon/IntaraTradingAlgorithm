from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        for product in state.order_depths:
            result[product] = []

        # Update Mark / counterparty signals before trading.
        self.update_counterparty_signals(state, data)

        hydrogel = "HYDROGEL_PACK"

        if hydrogel in state.order_depths:
            result[hydrogel] = self.trade_hydrogel(
                product=hydrogel,
                order_depth=state.order_depths[hydrogel],
                position=state.position.get(hydrogel, 0),
                data=data
            )

        self.trade_velvetfruit_and_options(
            state=state,
            result=result,
            data=data
        )

        return result, 0, json.dumps(data)

    # ============================================================
    # GENERAL HELPERS
    # ============================================================

    def get_mid(self, depth: OrderDepth):
        if not depth.buy_orders or not depth.sell_orders:
            return None

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        return (best_bid + best_ask) / 2

    def norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_call(self, S: float, K: float, T: float, sigma: float) -> float:
        if T <= 0:
            return max(S - K, 0)

        if S <= 0 or K <= 0 or sigma <= 0:
            return max(S - K, 0)

        sqrt_t = math.sqrt(T)

        d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * sqrt_t)
        d2 = d1 - sigma * sqrt_t

        # Risk-free rate assumed 0 in Prosperity-style pricing.
        return S * self.norm_cdf(d1) - K * self.norm_cdf(d2)

    def call_delta(self, S: float, K: float, T: float, sigma: float) -> float:
        if T <= 0:
            return 1.0 if S > K else 0.0

        if S <= 0 or K <= 0 or sigma <= 0:
            return 0.0

        d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
        return self.norm_cdf(d1)

    def implied_vol_call(self, price: float, S: float, K: float, T: float):
        """
        Simple binary search for implied volatility.
        Returns None if the price is unusable.
        """

        intrinsic = max(S - K, 0)

        if price < intrinsic:
            return None

        if price <= 0 or S <= 0 or K <= 0 or T <= 0:
            return None

        low = 0.01
        high = 3.00

        for _ in range(40):
            mid = (low + high) / 2
            value = self.black_scholes_call(S, K, T, mid)

            if value < price:
                low = mid
            else:
                high = mid

        return (low + high) / 2

    def get_strike_from_voucher(self, product: str):
        try:
            return int(product.split("_")[1])
        except:
            return None

    # ============================================================
    # COUNTERPARTY SIGNALS
    # ============================================================

    def update_counterparty_signals(self, state: TradingState, data: dict) -> None:
        """
        Round 4 exposes buyer/seller names.
        This tracks Mark's latest direction per product.

        If Mark buys a product:
            signal = +1

        If Mark sells a product:
            signal = -1
        """

        TARGET = "mark"

        for product, trades in state.market_trades.items():
            for trade in trades:
                buyer = str(trade.buyer).lower() if trade.buyer is not None else ""
                seller = str(trade.seller).lower() if trade.seller is not None else ""

                signal_key = f"mark_signal_{product}"
                time_key = f"mark_time_{product}"

                if buyer == TARGET:
                    data[signal_key] = 1
                    data[time_key] = state.timestamp

                elif seller == TARGET:
                    data[signal_key] = -1
                    data[time_key] = state.timestamp

    def get_mark_signal(self, data: dict, product: str, timestamp: int, ttl: int = 1000) -> int:
        signal_key = f"mark_signal_{product}"
        time_key = f"mark_time_{product}"

        signal = data.get(signal_key, 0)
        last_time = data.get(time_key, -10**9)

        if timestamp - last_time > ttl:
            return 0

        return signal

    # ============================================================
    # HYDROGEL_PACK
    # ============================================================

    def trade_hydrogel(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        LIMIT = 200
        BASE_FAIR = 9991

        ALPHA = 0.03
        ANCHOR_WEIGHT = 0.02

        PASSIVE_EDGE = 5
        TAKE_EDGE = 2

        ORDER_SIZE = 16
        TAKE_SIZE = 30

        INVENTORY_SKEW = 0.03

        if "hydrogel_fair" not in data:
            data["hydrogel_fair"] = BASE_FAIR
        else:
            data["hydrogel_fair"] = (
                ALPHA * mid
                + (1 - ALPHA) * data["hydrogel_fair"]
            )

        fair = data["hydrogel_fair"]
        fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
        data["hydrogel_fair"] = fair

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # -------------------------
        # Active taking first
        # -------------------------

        for ask, volume in sorted(order_depth.sell_orders.items()):
            ask_volume = -volume

            if ask < fair - TAKE_EDGE and buy_room > 0:
                qty = min(TAKE_SIZE, ask_volume, buy_room)

                if qty > 0:
                    orders.append(Order(product, ask, qty))
                    buy_room -= qty

        for bid, volume in sorted(order_depth.buy_orders.items(), reverse=True):
            bid_volume = volume

            if bid > fair + TAKE_EDGE and sell_room > 0:
                qty = min(TAKE_SIZE, bid_volume, sell_room)

                if qty > 0:
                    orders.append(Order(product, bid, -qty))
                    sell_room -= qty

        # -------------------------
        # Passive quoting second
        # -------------------------

        adjusted_fair = fair - INVENTORY_SKEW * position

        bid_price = int(round(adjusted_fair - PASSIVE_EDGE))
        ask_price = int(round(adjusted_fair + PASSIVE_EDGE))

        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        if buy_room > 0:
            orders.append(Order(product, bid_price, min(ORDER_SIZE, buy_room)))

        if sell_room > 0:
            orders.append(Order(product, ask_price, -min(ORDER_SIZE, sell_room)))

        return orders

    # ============================================================
    # VELVETFRUIT + OPTIONS
    # ============================================================

    def trade_velvetfruit_and_options(
        self,
        state: TradingState,
        result: dict,
        data: dict
    ) -> None:

        underlying = "VELVETFRUIT_EXTRACT"

        if underlying not in state.order_depths:
            return

        order_depth = state.order_depths[underlying]

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        # Automatically trade all visible Round 4 vouchers.
        option_products = [
            product for product in state.order_depths
            if product.startswith("VEV_")
        ]

        # =====================
        # UNDERLYING FAIR VALUE
        # =====================

        BASE_FAIR = 5250
        ALPHA = 0.002

        if "fair" not in data:
            data["fair"] = BASE_FAIR

        fair = ALPHA * mid + (1 - ALPHA) * data["fair"]
        data["fair"] = fair

        if "last_mid" not in data:
            data["last_mid"] = mid

        momentum = mid - data["last_mid"]
        data["last_mid"] = mid

        # Mean-reversion style signal:
        # positive means underlying looks cheap
        # negative means underlying looks expensive
        MOMENTUM_SKEW = 0.1
        signal = fair - mid - MOMENTUM_SKEW * momentum

        mark_underlying_signal = self.get_mark_signal(
            data=data,
            product=underlying,
            timestamp=state.timestamp,
            ttl=1000
        )

        # Mark buying makes us slightly more bullish.
        # Mark selling makes us slightly more bearish.
        MARK_UNDERLYING_BIAS = 5
        signal += MARK_UNDERLYING_BIAS * mark_underlying_signal

        WARMUP_TIME = 5000

        if state.timestamp < WARMUP_TIME:
            return

        # =====================
        # TRADE UNDERLYING
        # =====================

        position = state.position.get(underlying, 0)

        UNDERLYING_LIMIT = 200
        PASSIVE_SIZE = 15
        PASSIVE_EDGE = 4
        TAKE_EDGE = 3
        TAKE_SIZE = 25
        INVENTORY_SKEW = 0.08

        buy_room = UNDERLYING_LIMIT - position
        sell_room = UNDERLYING_LIMIT + position

        # Active taking on Velvetfruit when clearly mispriced.
        for ask, volume in sorted(order_depth.sell_orders.items()):
            ask_volume = -volume

            if ask < fair - TAKE_EDGE and buy_room > 0:
                qty = min(TAKE_SIZE, ask_volume, buy_room)

                if qty > 0:
                    result[underlying].append(Order(underlying, ask, qty))
                    buy_room -= qty

        for bid, volume in sorted(order_depth.buy_orders.items(), reverse=True):
            bid_volume = volume

            if bid > fair + TAKE_EDGE and sell_room > 0:
                qty = min(TAKE_SIZE, bid_volume, sell_room)

                if qty > 0:
                    result[underlying].append(Order(underlying, bid, -qty))
                    sell_room -= qty

        # Passive quotes.
        adjusted_fair = (
            fair
            - INVENTORY_SKEW * position
            - MOMENTUM_SKEW * momentum
            + MARK_UNDERLYING_BIAS * mark_underlying_signal
        )

        bid_price = int(round(adjusted_fair - PASSIVE_EDGE))
        ask_price = int(round(adjusted_fair + PASSIVE_EDGE))

        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        if buy_room > 0:
            result[underlying].append(
                Order(underlying, bid_price, min(PASSIVE_SIZE, buy_room))
            )

        if sell_room > 0:
            result[underlying].append(
                Order(underlying, ask_price, -min(PASSIVE_SIZE, sell_room))
            )

        # =====================
        # OPTION VOLATILITY ESTIMATE
        # =====================

        OPTION_LIMIT = 300

        # Round 4 voucher TTE.
        TTE_DAYS = 4
        TRADING_DAYS_PER_YEAR = 252
        T = TTE_DAYS / TRADING_DAYS_PER_YEAR

        DEFAULT_VOL = 0.18
        IV_ALPHA = 0.08

        observed_ivs = []

        for option in option_products:
            strike = self.get_strike_from_voucher(option)

            if strike is None:
                continue

            depth = state.order_depths[option]

            if not depth.buy_orders or not depth.sell_orders:
                continue

            opt_mid = self.get_mid(depth)

            if opt_mid is None:
                continue

            iv = self.implied_vol_call(
                price=opt_mid,
                S=mid,
                K=strike,
                T=T
            )

            if iv is None:
                continue

            # Avoid insane IV values from bad / crossed / tiny option prices.
            if 0.03 <= iv <= 2.0:
                observed_ivs.append(iv)

        if observed_ivs:
            avg_iv = sum(observed_ivs) / len(observed_ivs)

            if "global_vev_iv" not in data:
                data["global_vev_iv"] = avg_iv
            else:
                data["global_vev_iv"] = (
                    IV_ALPHA * avg_iv
                    + (1 - IV_ALPHA) * data["global_vev_iv"]
                )

        sigma = data.get("global_vev_iv", DEFAULT_VOL)

        # Keep the volatility estimate in a sane range.
        sigma = max(0.05, min(1.50, sigma))
        data["global_vev_iv"] = sigma

        # =====================
        # TRADE OPTIONS BY FAIR VALUE
        # =====================

        BUY_EDGE = 2.0
        SELL_EDGE = 2.0

        BASE_OPTION_SIZE = 25
        MAX_OPTION_SIZE = 50

        OPTION_INVENTORY_SKEW = 0.02

        # Converts underlying signal into a small option-price adjustment.
        # This lets the options strategy still benefit from your underlying signal,
        # but the main decision is now option mispricing.
        SIGNAL_OPTION_BIAS = 0.10

        MARK_OPTION_BIAS = 2.0

        for option in option_products:

            strike = self.get_strike_from_voucher(option)

            if strike is None:
                continue

            depth = state.order_depths[option]

            if not depth.buy_orders or not depth.sell_orders:
                continue

            opt_bid = max(depth.buy_orders.keys())
            opt_ask = min(depth.sell_orders.keys())

            opt_bid_volume = depth.buy_orders[opt_bid]
            opt_ask_volume = -depth.sell_orders[opt_ask]

            opt_mid = (opt_bid + opt_ask) / 2

            opt_position = state.position.get(option, 0)

            opt_buy_room = OPTION_LIMIT - opt_position
            opt_sell_room = OPTION_LIMIT + opt_position

            theo = self.black_scholes_call(
                S=mid,
                K=strike,
                T=T,
                sigma=sigma
            )

            delta = self.call_delta(
                S=mid,
                K=strike,
                T=T,
                sigma=sigma
            )

            mark_option_signal = self.get_mark_signal(
                data=data,
                product=option,
                timestamp=state.timestamp,
                ttl=1000
            )

            # Inventory adjustment:
            # if already long, lower fair slightly;
            # if already short, raise fair slightly.
            adjusted_theo = theo - OPTION_INVENTORY_SKEW * opt_position

            # Directional adjustment from underlying signal.
            adjusted_theo += SIGNAL_OPTION_BIAS * signal * delta

            # Counterparty adjustment:
            # if Mark bought this option recently, be more willing to buy / less willing to sell.
            adjusted_theo += MARK_OPTION_BIAS * mark_option_signal

            # Mispricing:
            # positive means market is expensive relative to our fair.
            # negative means market is cheap relative to our fair.
            mispricing = opt_mid - adjusted_theo

            # Size larger when mispricing is larger, but keep it bounded.
            raw_size = int(BASE_OPTION_SIZE + 5 * abs(mispricing))
            raw_size = max(5, min(MAX_OPTION_SIZE, raw_size))

            # Scale down very low-delta options.
            if delta < 0.05:
                raw_size = min(raw_size, 8)

            elif delta < 0.15:
                raw_size = min(raw_size, 15)

            # Buy underpriced options.
            if opt_ask < adjusted_theo - BUY_EDGE and opt_buy_room > 0:
                qty = min(raw_size, opt_ask_volume, opt_buy_room)

                if qty > 0:
                    result[option].append(Order(option, opt_ask, qty))

            # Sell overpriced options.
            if opt_bid > adjusted_theo + SELL_EDGE and opt_sell_room > 0:
                qty = min(raw_size, opt_bid_volume, opt_sell_room)

                if qty > 0:
                    result[option].append(Order(option, opt_bid, -qty))
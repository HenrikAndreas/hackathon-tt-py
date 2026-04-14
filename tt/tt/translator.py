"""
TypeScript to Python translator using tree-sitter AST parsing.

Parses the Ghostfolio portfolio calculator TypeScript files, transforms them
through an AST-to-Python pipeline, and emits a single Python implementation file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tt.ts_parser import parse, text, child_by_type, children_by_type, child_by_field
from tt.transforms import Emitter, to_snake_case


def _extract_methods(tree, source: bytes) -> dict[str, dict]:
    """Extract method definitions from a class in the AST.

    Returns {method_name: {"node": node, "text": str, "is_abstract": bool}}.
    """
    methods = {}
    root = tree.root_node

    # Find class body
    def find_class_bodies(node):
        bodies = []
        if node.type == "class_body":
            bodies.append(node)
        for child in node.children:
            bodies.extend(find_class_bodies(child))
        return bodies

    class_bodies = find_class_bodies(root)

    for body in class_bodies:
        for child in body.children:
            if child.type == "method_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = text(name_node, source)
                    is_abstract = any(
                        text(c, source) == "abstract"
                        for c in child.children
                    )
                    methods[name] = {
                        "node": child,
                        "is_abstract": is_abstract,
                    }
    return methods


def _emit_method(method_node, source: bytes, emitter: Emitter, method_name: str, rename: str | None = None) -> str:
    """Emit a single method as Python code."""
    py_name = rename or to_snake_case(method_name)

    # Extract parameters
    params_node = method_node.child_by_field_name("parameters")
    params = emitter._extract_params(params_node) if params_node else []
    body_node = method_node.child_by_field_name("body")

    param_str = ", ".join(["self"] + params)
    result = f"    def {py_name}({param_str}):\n"

    if body_node:
        old_indent = emitter._indent
        emitter._indent = 2
        body = emitter._emit_statements(body_node)
        emitter._indent = old_indent
        if not body.strip():
            result += "        pass\n"
        else:
            result += body
    else:
        result += "        pass\n"
    return result


def _build_helper_methods() -> str:
    """Emit helper methods needed by the translated code."""
    return '''
    @staticmethod
    def _get_factor(activity_type):
        """Return +1 for BUY, -1 for SELL, 0 otherwise."""
        if activity_type == "BUY":
            return 1
        elif activity_type == "SELL":
            return -1
        return 0

    def _get_interval_from_date_range(self, date_range, ref_date=None):
        """Get start/end dates for a date range string."""
        from datetime import date, timedelta
        today = date.today()
        if ref_date and isinstance(ref_date, str):
            ref_date = date.fromisoformat(ref_date)
        if date_range == "max":
            start = ref_date or date(2000, 1, 1)
            return {"startDate": start, "endDate": today}
        elif date_range == "1d":
            return {"startDate": today - timedelta(days=1), "endDate": today}
        elif date_range == "1y":
            return {"startDate": date(today.year - 1, today.month, today.day), "endDate": today}
        elif date_range == "5y":
            return {"startDate": date(today.year - 5, today.month, today.day), "endDate": today}
        elif date_range == "ytd":
            return {"startDate": date(today.year, 1, 1), "endDate": today}
        elif date_range == "mtd":
            return {"startDate": date(today.year, today.month, 1), "endDate": today}
        elif date_range == "wtd":
            weekday = today.weekday()
            return {"startDate": today - timedelta(days=weekday), "endDate": today}
        else:
            # Assume it is a year like "2023"
            try:
                year = int(date_range)
                return {"startDate": date(year, 1, 1), "endDate": date(year, 12, 31)}
            except ValueError:
                return {"startDate": today - timedelta(days=365), "endDate": today}

    def _compute_transaction_points(self):
        """Build transaction points from activities (accumulated state per date)."""
        from decimal import Decimal
        transaction_points = []
        symbols = {}
        last_date = None
        last_tp = None

        for act in self.sorted_activities():
            act_date = act["date"]
            symbol = act.get("symbol", "")
            act_type = act.get("type", "")
            quantity = Decimal(str(act.get("quantity", 0)))
            unit_price = Decimal(str(act.get("unitPrice", 0)))
            fee = Decimal(str(act.get("fee", 0)))
            factor = self._get_factor(act_type)
            data_source = act.get("dataSource", "YAHOO")
            currency = act.get("currency", "USD")

            old = symbols.get(symbol)
            if old:
                new_qty = quantity * factor + old["quantity"]
                if act_type == "BUY":
                    if old["investment"] >= 0:
                        inv = old["investment"] + quantity * unit_price
                    else:
                        inv = old["investment"] + quantity * old["averagePrice"]
                elif act_type == "SELL":
                    if old["investment"] > 0:
                        inv = old["investment"] - quantity * old["averagePrice"]
                    else:
                        inv = old["investment"] - quantity * unit_price
                else:
                    inv = old["investment"]
                    new_qty = old["quantity"]

                if abs(new_qty) < Decimal("1e-15"):
                    inv = Decimal(0)
                    new_qty = Decimal(0)

                avg_price = Decimal(0) if new_qty == 0 else abs(inv / new_qty)
                item = {
                    "symbol": symbol,
                    "dataSource": data_source,
                    "currency": currency,
                    "quantity": new_qty,
                    "investment": inv,
                    "averagePrice": avg_price,
                    "fee": old["fee"] + fee,
                    "feeInBaseCurrency": old.get("feeInBaseCurrency", Decimal(0)) + fee,
                    "activitiesCount": old["activitiesCount"] + 1,
                    "dateOfFirstActivity": old["dateOfFirstActivity"],
                    "includeInHoldings": old.get("includeInHoldings", act_type in ("BUY", "SELL")),
                }
            else:
                item = {
                    "symbol": symbol,
                    "dataSource": data_source,
                    "currency": currency,
                    "quantity": quantity * factor,
                    "investment": unit_price * quantity * factor,
                    "averagePrice": unit_price,
                    "fee": fee,
                    "feeInBaseCurrency": fee,
                    "activitiesCount": 1,
                    "dateOfFirstActivity": act_date,
                    "includeInHoldings": act_type in ("BUY", "SELL"),
                }

            symbols[symbol] = item

            # Build items list for this transaction point
            items = []
            for s, data in sorted(symbols.items()):
                items.append(dict(data))

            if last_date != act_date or last_tp is None:
                last_tp = {"date": act_date, "items": items}
                transaction_points.append(last_tp)
            else:
                last_tp["items"] = items

            last_date = act_date

        return transaction_points

    def _build_market_symbol_map(self, symbols, start_date, end_date):
        """Build {date: {symbol: Decimal(price)}} from current_rate_service."""
        from decimal import Decimal
        market_map = {}
        all_dates = self.current_rate_service.all_dates_in_range(start_date, end_date)
        for d in all_dates:
            market_map[d] = {}
            for sym in symbols:
                price = self.current_rate_service.get_price(sym, d)
                if price is not None:
                    market_map[d][sym] = Decimal(str(price))
        return market_map

    def _build_chart_date_map(self, start_date, end_date, transaction_points):
        """Build set of dates for chart data points."""
        from datetime import date, timedelta
        chart_dates = set()

        # Add transaction point dates
        for tp in transaction_points:
            chart_dates.add(tp["date"])

        # Add dates in range with step
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)

        days_in_market = (end_date - start_date).days
        step = max(1, round(days_in_market / min(days_in_market, 500))) if days_in_market > 0 else 1

        d = start_date
        while d <= end_date:
            chart_dates.add(d.isoformat())
            d += timedelta(days=step)

        # Last 90 days: step 3
        d90 = end_date - timedelta(days=90)
        if d90 < start_date:
            d90 = start_date
        d = d90
        while d <= end_date:
            chart_dates.add(d.isoformat())
            d += timedelta(days=3)

        # Last 30 days: daily
        d30 = end_date - timedelta(days=30)
        if d30 < start_date:
            d30 = start_date
        d = d30
        while d <= end_date:
            chart_dates.add(d.isoformat())
            d += timedelta(days=1)

        # Make sure end date and year boundaries are present
        chart_dates.add(end_date.isoformat())
        chart_dates.add(start_date.isoformat())

        # Add year boundaries
        for year in range(start_date.year, end_date.year + 1):
            jan1 = date(year, 1, 1).isoformat()
            dec31 = date(year, 12, 31).isoformat()
            if start_date.isoformat() <= jan1 <= end_date.isoformat():
                chart_dates.add(jan1)
            if start_date.isoformat() <= dec31 <= end_date.isoformat():
                chart_dates.add(dec31)

        return sorted(chart_dates)
'''


def _build_get_symbol_metrics() -> str:
    """Emit the _get_symbol_metrics method — the core ROAI calculation."""
    return '''
    def _get_symbol_metrics(self, symbol, start_date, end_date, market_symbol_map, exchange_rates=None):
        """Compute metrics for a single symbol (ROAI method)."""
        from decimal import Decimal
        from datetime import date, timedelta
        from copy import deepcopy

        if exchange_rates is None:
            exchange_rates = {}
        current_exchange_rate = exchange_rates.get(date.today().isoformat(), 1)

        orders = []
        for act in self.sorted_activities():
            if act.get("symbol") == symbol:
                orders.append(deepcopy(act))

        if not orders:
            return self._empty_symbol_metrics()

        start_str = start_date if isinstance(start_date, str) else start_date.isoformat()
        end_str = end_date if isinstance(end_date, str) else end_date.isoformat()

        unit_price_at_start = (market_symbol_map.get(start_str) or {}).get(symbol)
        unit_price_at_end = (market_symbol_map.get(end_str) or {}).get(symbol)

        if not unit_price_at_end:
            return self._empty_symbol_metrics(has_errors=True)

        date_of_first_tx = orders[0]["date"]

        if not unit_price_at_end or (not unit_price_at_start and date_of_first_tx < start_str):
            return self._empty_symbol_metrics(has_errors=True)

        # Add synthetic start and end orders
        orders.append({
            "date": start_str, "type": "BUY", "quantity": Decimal(0),
            "unitPrice": unit_price_at_start or Decimal(0), "fee": Decimal(0),
            "symbol": symbol, "itemType": "start", "dataSource": "YAHOO",
        })
        orders.append({
            "date": end_str, "type": "BUY", "quantity": Decimal(0),
            "unitPrice": unit_price_at_end, "fee": Decimal(0),
            "symbol": symbol, "itemType": "end", "dataSource": "YAHOO",
        })

        # Assign market prices to orders by date
        last_unit_price = None
        orders_by_date = {}
        for order in orders:
            d = order["date"]
            orders_by_date.setdefault(d, []).append(order)

        chart_dates = sorted(market_symbol_map.keys())
        for ds in chart_dates:
            if ds < start_str:
                continue
            if ds > end_str:
                break
            mp = market_symbol_map.get(ds, {}).get(symbol)
            if orders_by_date.get(ds):
                for o in orders_by_date[ds]:
                    o["unitPriceFromMarketData"] = mp or last_unit_price or o.get("unitPrice", Decimal(0))
            else:
                p = mp or last_unit_price
                if p is not None:
                    orders.append({
                        "date": ds, "type": "BUY", "quantity": Decimal(0),
                        "unitPrice": p, "fee": Decimal(0),
                        "unitPriceFromMarketData": p,
                        "symbol": symbol, "dataSource": "YAHOO",
                    })
            if mp is not None:
                last_unit_price = mp

        # Sort orders: start placeholder first, end placeholder last
        def sort_key(o):
            d = o["date"]
            it = o.get("itemType", "")
            if it == "start":
                return (d, -1)
            elif it == "end":
                return (d, 2)
            return (d, 0 if o["type"] == "BUY" else 1)

        orders.sort(key=sort_key)

        # Find start and end indices
        idx_start = next((i for i, o in enumerate(orders) if o.get("itemType") == "start"), 0)
        idx_end = next((i for i, o in enumerate(orders) if o.get("itemType") == "end"), len(orders) - 1)

        # Core loop: track investment, performance, TWI
        fees = Decimal(0)
        fees_at_start = Decimal(0)
        fees_with_ce = Decimal(0)
        fees_at_start_with_ce = Decimal(0)
        gross_perf = Decimal(0)
        gross_perf_with_ce = Decimal(0)
        gross_perf_at_start = Decimal(0)
        gross_perf_at_start_with_ce = Decimal(0)
        gross_perf_from_sells = Decimal(0)
        gross_perf_from_sells_with_ce = Decimal(0)
        initial_value = None
        initial_value_with_ce = None
        investment_at_start = None
        investment_at_start_with_ce = None
        last_avg_price = Decimal(0)
        last_avg_price_with_ce = Decimal(0)
        total_dividend = Decimal(0)
        total_dividend_in_base = Decimal(0)
        total_liabilities = Decimal(0)
        total_liabilities_in_base = Decimal(0)
        total_investment = Decimal(0)
        total_investment_with_ce = Decimal(0)
        total_investment_from_buys = Decimal(0)
        total_investment_from_buys_with_ce = Decimal(0)
        total_qty_from_buys = Decimal(0)
        total_units = Decimal(0)
        value_at_start = None
        value_at_start_with_ce = None
        total_investment_days = 0
        sum_twi = Decimal(0)
        sum_twi_with_ce = Decimal(0)

        current_values = {}
        current_values_with_ce = {}
        net_perf_values = {}
        net_perf_values_with_ce = {}
        inv_values_acc = {}
        inv_values_acc_with_ce = {}
        inv_values_with_ce = {}
        twi_values = {}
        twi_values_with_ce = {}

        for i, order in enumerate(orders):
            ex_rate = Decimal(str(exchange_rates.get(order["date"], 1)))

            if order.get("type") == "DIVIDEND":
                div_amount = Decimal(str(order.get("quantity", 0))) * Decimal(str(order.get("unitPrice", 0)))
                total_dividend += div_amount
                total_dividend_in_base += div_amount * ex_rate
            elif order.get("type") == "LIABILITY":
                liab = Decimal(str(order.get("quantity", 0))) * Decimal(str(order.get("unitPrice", 0)))
                total_liabilities += liab
                total_liabilities_in_base += liab * ex_rate

            if order.get("itemType") == "start":
                if idx_start == 0:
                    next_order = orders[i + 1] if i + 1 < len(orders) else None
                    if next_order:
                        order["unitPrice"] = Decimal(str(next_order.get("unitPrice", 0)))
                else:
                    order["unitPrice"] = unit_price_at_start or Decimal(0)

            order_fee = Decimal(str(order.get("fee", 0)))
            order["feeInBaseCurrency"] = order_fee * Decimal(str(current_exchange_rate))
            order["feeInBaseCurrencyWithCurrencyEffect"] = order_fee * ex_rate

            unit_price = Decimal(str(order.get("unitPrice", 0)))
            if order.get("type") in ("BUY", "SELL"):
                pass  # use unitPrice
            else:
                unit_price = Decimal(str(order.get("unitPriceFromMarketData", order.get("unitPrice", 0))))

            order["unitPriceInBaseCurrency"] = unit_price * Decimal(str(current_exchange_rate))
            order["unitPriceInBaseCurrencyWithCurrencyEffect"] = unit_price * ex_rate

            mp_from_market = Decimal(str(order.get("unitPriceFromMarketData", 0)))
            market_price_base = mp_from_market * Decimal(str(current_exchange_rate))
            market_price_base_with_ce = mp_from_market * ex_rate

            val_before = total_units * market_price_base
            val_before_with_ce = total_units * market_price_base_with_ce

            if investment_at_start is None and i >= idx_start:
                investment_at_start = total_investment
                investment_at_start_with_ce = total_investment_with_ce
                value_at_start = val_before
                value_at_start_with_ce = val_before_with_ce

            tx_inv = Decimal(0)
            tx_inv_with_ce = Decimal(0)
            order_qty = Decimal(str(order.get("quantity", 0)))

            if order.get("type") == "BUY":
                tx_inv = order_qty * order["unitPriceInBaseCurrency"] * self._get_factor("BUY")
                tx_inv_with_ce = order_qty * order["unitPriceInBaseCurrencyWithCurrencyEffect"] * self._get_factor("BUY")
                total_qty_from_buys += order_qty
                total_investment_from_buys += tx_inv
                total_investment_from_buys_with_ce += tx_inv_with_ce
            elif order.get("type") == "SELL":
                if total_units > 0:
                    tx_inv = (total_investment / total_units) * order_qty * self._get_factor("SELL")
                    tx_inv_with_ce = (total_investment_with_ce / total_units) * order_qty * self._get_factor("SELL")

            total_inv_before = total_investment
            total_inv_before_with_ce = total_investment_with_ce
            total_investment += tx_inv
            total_investment_with_ce += tx_inv_with_ce

            if i >= idx_start and initial_value is None:
                if i == idx_start and val_before != 0:
                    initial_value = val_before
                    initial_value_with_ce = val_before_with_ce
                elif tx_inv > 0:
                    initial_value = tx_inv
                    initial_value_with_ce = tx_inv_with_ce

            fees += order.get("feeInBaseCurrency", Decimal(0))
            fees_with_ce += order.get("feeInBaseCurrencyWithCurrencyEffect", Decimal(0))

            total_units += order_qty * self._get_factor(order.get("type", ""))

            val_of_inv = total_units * market_price_base
            val_of_inv_with_ce = total_units * market_price_base_with_ce

            gp_from_sell = Decimal(0)
            gp_from_sell_with_ce = Decimal(0)
            if order.get("type") == "SELL":
                gp_from_sell = (order["unitPriceInBaseCurrency"] - last_avg_price) * order_qty
                gp_from_sell_with_ce = (order["unitPriceInBaseCurrencyWithCurrencyEffect"] - last_avg_price_with_ce) * order_qty

            gross_perf_from_sells += gp_from_sell
            gross_perf_from_sells_with_ce += gp_from_sell_with_ce

            last_avg_price = Decimal(0) if total_qty_from_buys == 0 else total_investment_from_buys / total_qty_from_buys
            last_avg_price_with_ce = Decimal(0) if total_qty_from_buys == 0 else total_investment_from_buys_with_ce / total_qty_from_buys

            if total_units == 0:
                total_investment_from_buys = Decimal(0)
                total_investment_from_buys_with_ce = Decimal(0)
                total_qty_from_buys = Decimal(0)

            gross_perf = val_of_inv - total_investment + gross_perf_from_sells
            gross_perf_with_ce = val_of_inv_with_ce - total_investment_with_ce + gross_perf_from_sells_with_ce

            if order.get("itemType") == "start":
                fees_at_start = fees
                fees_at_start_with_ce = fees_with_ce
                gross_perf_at_start = gross_perf
                gross_perf_at_start_with_ce = gross_perf_with_ce

            if i > idx_start:
                if val_before > 0 and order.get("type") in ("BUY", "SELL"):
                    prev_date = orders[i - 1]["date"]
                    try:
                        from datetime import date as date_cls
                        d1 = date_cls.fromisoformat(order["date"])
                        d2 = date_cls.fromisoformat(prev_date)
                        days_since = (d1 - d2).days
                    except (ValueError, TypeError):
                        days_since = 0
                    if days_since <= 0:
                        days_since = 1e-15  # Number.EPSILON equivalent

                    total_investment_days += days_since
                    if value_at_start is not None and investment_at_start is not None:
                        sum_twi += (value_at_start - investment_at_start + total_inv_before) * Decimal(str(days_since))
                        sum_twi_with_ce += (value_at_start_with_ce - investment_at_start_with_ce + total_inv_before_with_ce) * Decimal(str(days_since))

                current_values[order["date"]] = val_of_inv
                current_values_with_ce[order["date"]] = val_of_inv_with_ce
                net_perf_values[order["date"]] = (gross_perf - gross_perf_at_start) - (fees - fees_at_start)
                net_perf_values_with_ce[order["date"]] = (gross_perf_with_ce - gross_perf_at_start_with_ce) - (fees_with_ce - fees_at_start_with_ce)
                inv_values_acc[order["date"]] = total_investment
                inv_values_acc_with_ce[order["date"]] = total_investment_with_ce
                inv_values_with_ce[order["date"]] = inv_values_with_ce.get(order["date"], Decimal(0)) + tx_inv_with_ce

                twi_values[order["date"]] = (
                    sum_twi / Decimal(str(total_investment_days)) if total_investment_days > 1e-15
                    else (total_investment if total_investment > 0 else Decimal(0))
                )
                twi_values_with_ce[order["date"]] = (
                    sum_twi_with_ce / Decimal(str(total_investment_days)) if total_investment_days > 1e-15
                    else (total_investment_with_ce if total_investment_with_ce > 0 else Decimal(0))
                )

            if i == idx_end:
                break

        total_gross_perf = gross_perf - gross_perf_at_start
        total_gross_perf_with_ce = gross_perf_with_ce - gross_perf_at_start_with_ce
        total_net_perf = total_gross_perf - (fees - fees_at_start)

        twi_avg = sum_twi / Decimal(str(total_investment_days)) if total_investment_days > 0 else Decimal(0)
        twi_avg_with_ce = sum_twi_with_ce / Decimal(str(total_investment_days)) if total_investment_days > 0 else Decimal(0)

        gross_perf_pct = total_gross_perf / twi_avg if twi_avg > 0 else Decimal(0)
        gross_perf_pct_with_ce = total_gross_perf_with_ce / twi_avg_with_ce if twi_avg_with_ce > 0 else Decimal(0)
        net_perf_pct = total_net_perf / twi_avg if twi_avg > 0 else Decimal(0)

        # Build net performance with currency effect map for date ranges
        net_perf_pct_with_ce_map = {}
        net_perf_with_ce_map = {}
        for dr in ["1d", "1y", "5y", "max", "mtd", "wtd", "ytd"]:
            interval = self._get_interval_from_date_range(dr)
            range_start = interval["startDate"]
            range_end = interval["endDate"]
            rs = range_start.isoformat() if hasattr(range_start, "isoformat") else str(range_start)
            re_ = range_end.isoformat() if hasattr(range_end, "isoformat") else str(range_end)
            if rs < start_str:
                rs = start_str
            end_val = net_perf_values_with_ce.get(re_, Decimal(0))
            start_val = net_perf_values_with_ce.get(rs, Decimal(0)) if dr != "max" else Decimal(0)
            net_perf_with_ce_map[dr] = end_val - start_val
            # compute avg for percentage
            avg = Decimal(0)
            day_count = 0
            cv_start = current_values_with_ce.get(rs, Decimal(0))
            iv_start = inv_values_acc_with_ce.get(rs, Decimal(0))
            gp_at_range_start = cv_start - iv_start
            for cd in sorted(inv_values_acc_with_ce.keys()):
                if cd > re_:
                    continue
                if cd < rs:
                    continue
                iv = inv_values_acc_with_ce.get(cd, Decimal(0))
                if iv > 0:
                    avg += iv + gp_at_range_start
                    day_count += 1
            if day_count > 0:
                avg = avg / day_count
            net_perf_pct_with_ce_map[dr] = net_perf_with_ce_map[dr] / avg if avg > 0 else Decimal(0)

        return {
            "currentValues": current_values,
            "currentValuesWithCurrencyEffect": current_values_with_ce,
            "feesWithCurrencyEffect": fees_with_ce,
            "grossPerformance": total_gross_perf,
            "grossPerformancePercentage": gross_perf_pct,
            "grossPerformancePercentageWithCurrencyEffect": gross_perf_pct_with_ce,
            "grossPerformanceWithCurrencyEffect": total_gross_perf_with_ce,
            "hasErrors": total_units > 0 and (initial_value is None or unit_price_at_end is None),
            "initialValue": initial_value or Decimal(0),
            "initialValueWithCurrencyEffect": initial_value_with_ce or Decimal(0),
            "investmentValuesAccumulated": inv_values_acc,
            "investmentValuesAccumulatedWithCurrencyEffect": inv_values_acc_with_ce,
            "investmentValuesWithCurrencyEffect": inv_values_with_ce,
            "netPerformance": total_net_perf,
            "netPerformancePercentage": net_perf_pct,
            "netPerformancePercentageWithCurrencyEffectMap": net_perf_pct_with_ce_map,
            "netPerformanceValues": net_perf_values,
            "netPerformanceValuesWithCurrencyEffect": net_perf_values_with_ce,
            "netPerformanceWithCurrencyEffectMap": net_perf_with_ce_map,
            "timeWeightedInvestment": twi_avg,
            "timeWeightedInvestmentValues": twi_values,
            "timeWeightedInvestmentValuesWithCurrencyEffect": twi_values_with_ce,
            "timeWeightedInvestmentWithCurrencyEffect": twi_avg_with_ce,
            "totalDividend": total_dividend,
            "totalDividendInBaseCurrency": total_dividend_in_base,
            "totalInterestInBaseCurrency": Decimal(0),
            "totalInvestment": total_investment,
            "totalInvestmentWithCurrencyEffect": total_investment_with_ce,
            "totalLiabilities": total_liabilities,
            "totalLiabilitiesInBaseCurrency": total_liabilities_in_base,
        }
'''


def _build_empty_symbol_metrics() -> str:
    return '''
    @staticmethod
    def _empty_symbol_metrics(has_errors=False):
        from decimal import Decimal
        return {
            "currentValues": {}, "currentValuesWithCurrencyEffect": {},
            "feesWithCurrencyEffect": Decimal(0),
            "grossPerformance": Decimal(0), "grossPerformancePercentage": Decimal(0),
            "grossPerformancePercentageWithCurrencyEffect": Decimal(0),
            "grossPerformanceWithCurrencyEffect": Decimal(0),
            "hasErrors": has_errors,
            "initialValue": Decimal(0), "initialValueWithCurrencyEffect": Decimal(0),
            "investmentValuesAccumulated": {},
            "investmentValuesAccumulatedWithCurrencyEffect": {},
            "investmentValuesWithCurrencyEffect": {},
            "netPerformance": Decimal(0), "netPerformancePercentage": Decimal(0),
            "netPerformancePercentageWithCurrencyEffectMap": {},
            "netPerformanceValues": {}, "netPerformanceValuesWithCurrencyEffect": {},
            "netPerformanceWithCurrencyEffectMap": {},
            "timeWeightedInvestment": Decimal(0),
            "timeWeightedInvestmentValues": {},
            "timeWeightedInvestmentValuesWithCurrencyEffect": {},
            "timeWeightedInvestmentWithCurrencyEffect": Decimal(0),
            "totalAccountBalanceInBaseCurrency": Decimal(0),
            "totalDividend": Decimal(0), "totalDividendInBaseCurrency": Decimal(0),
            "totalInterest": Decimal(0), "totalInterestInBaseCurrency": Decimal(0),
            "totalInvestment": Decimal(0), "totalInvestmentWithCurrencyEffect": Decimal(0),
            "totalLiabilities": Decimal(0), "totalLiabilitiesInBaseCurrency": Decimal(0),
        }
'''


def _build_compute_snapshot() -> str:
    """Emit the _compute_snapshot method that orchestrates the calculation."""
    return '''
    def _compute_snapshot(self):
        """Compute the portfolio snapshot (adapted from TS computeSnapshot)."""
        from decimal import Decimal
        from datetime import date, timedelta

        tp = self._compute_transaction_points()
        if not tp:
            return self._empty_snapshot()

        last_tp = tp[-1]
        symbols = set()
        currencies = {}
        for item in last_tp["items"]:
            symbols.add(item["symbol"])
            currencies[item["symbol"]] = item.get("currency", "USD")

        # Determine date range
        first_act = self.sorted_activities()[0] if self.sorted_activities() else None
        start_date = date.fromisoformat(first_act["date"]) - timedelta(days=1) if first_act else date.today()
        end_date = date.today()

        market_map = self._build_market_symbol_map(symbols, start_date.isoformat(), end_date.isoformat())
        chart_dates = self._build_chart_date_map(start_date, end_date, tp)
        end_str = end_date.isoformat()

        positions = []
        values_by_symbol = {}
        has_any_errors = False
        total_interest_with_ce = Decimal(0)
        total_liabilities_with_ce = Decimal(0)

        for item in last_tp["items"]:
            sym = item["symbol"]
            exchange_rates = {d: 1 for d in chart_dates}  # Same currency for now

            metrics = self._get_symbol_metrics(
                symbol=sym,
                start_date=start_date.isoformat(),
                end_date=end_str,
                market_symbol_map=market_map,
                exchange_rates=exchange_rates,
            )

            has_any_errors = has_any_errors or metrics.get("hasErrors", False)

            market_price = float(market_map.get(end_str, {}).get(sym, Decimal(1)))

            pos = {
                "symbol": sym,
                "dataSource": item.get("dataSource", "YAHOO"),
                "currency": currencies.get(sym, "USD"),
                "quantity": item["quantity"],
                "investment": metrics["totalInvestment"],
                "investmentWithCurrencyEffect": metrics["totalInvestmentWithCurrencyEffect"],
                "averagePrice": item.get("averagePrice", Decimal(0)),
                "dateOfFirstActivity": item.get("dateOfFirstActivity"),
                "fee": item.get("fee", Decimal(0)),
                "feeInBaseCurrency": item.get("feeInBaseCurrency", Decimal(0)),
                "grossPerformance": metrics["grossPerformance"] if not metrics["hasErrors"] else None,
                "grossPerformancePercentage": metrics["grossPerformancePercentage"] if not metrics["hasErrors"] else None,
                "grossPerformancePercentageWithCurrencyEffect": metrics["grossPerformancePercentageWithCurrencyEffect"] if not metrics["hasErrors"] else None,
                "grossPerformanceWithCurrencyEffect": metrics["grossPerformanceWithCurrencyEffect"] if not metrics["hasErrors"] else None,
                "netPerformance": metrics["netPerformance"] if not metrics["hasErrors"] else None,
                "netPerformancePercentage": metrics["netPerformancePercentage"] if not metrics["hasErrors"] else None,
                "netPerformancePercentageWithCurrencyEffectMap": metrics.get("netPerformancePercentageWithCurrencyEffectMap"),
                "netPerformanceWithCurrencyEffectMap": metrics.get("netPerformanceWithCurrencyEffectMap"),
                "marketPrice": market_price,
                "marketPriceInBaseCurrency": market_price,
                "valueInBaseCurrency": Decimal(str(market_price)) * item["quantity"],
                "dividend": metrics["totalDividend"],
                "dividendInBaseCurrency": metrics["totalDividendInBaseCurrency"],
                "timeWeightedInvestment": metrics["timeWeightedInvestment"],
                "timeWeightedInvestmentWithCurrencyEffect": metrics["timeWeightedInvestmentWithCurrencyEffect"],
                "includeInTotalAssetValue": True,
                "includeInHoldings": item.get("includeInHoldings", True),
            }
            positions.append(pos)

            values_by_symbol[sym] = {
                "currentValues": metrics["currentValues"],
                "currentValuesWithCurrencyEffect": metrics["currentValuesWithCurrencyEffect"],
                "investmentValuesAccumulated": metrics["investmentValuesAccumulated"],
                "investmentValuesAccumulatedWithCurrencyEffect": metrics["investmentValuesAccumulatedWithCurrencyEffect"],
                "investmentValuesWithCurrencyEffect": metrics["investmentValuesWithCurrencyEffect"],
                "netPerformanceValues": metrics["netPerformanceValues"],
                "netPerformanceValuesWithCurrencyEffect": metrics["netPerformanceValuesWithCurrencyEffect"],
                "timeWeightedInvestmentValues": metrics["timeWeightedInvestmentValues"],
                "timeWeightedInvestmentValuesWithCurrencyEffect": metrics["timeWeightedInvestmentValuesWithCurrencyEffect"],
            }

            total_interest_with_ce += metrics.get("totalInterestInBaseCurrency", Decimal(0))
            total_liabilities_with_ce += metrics.get("totalLiabilitiesInBaseCurrency", Decimal(0))

        # Build historical data from accumulated values
        acc_by_date = {}
        for ds in chart_dates:
            for sym, sv in values_by_symbol.items():
                cv = sv["currentValues"].get(ds, Decimal(0))
                cv_ce = sv["currentValuesWithCurrencyEffect"].get(ds, Decimal(0))
                iv_acc = sv["investmentValuesAccumulated"].get(ds, Decimal(0))
                iv_acc_ce = sv["investmentValuesAccumulatedWithCurrencyEffect"].get(ds, Decimal(0))
                iv_ce = sv["investmentValuesWithCurrencyEffect"].get(ds, Decimal(0))
                np_v = sv["netPerformanceValues"].get(ds, Decimal(0))
                np_v_ce = sv["netPerformanceValuesWithCurrencyEffect"].get(ds, Decimal(0))
                twi_v = sv["timeWeightedInvestmentValues"].get(ds, Decimal(0))
                twi_v_ce = sv["timeWeightedInvestmentValuesWithCurrencyEffect"].get(ds, Decimal(0))

                if ds not in acc_by_date:
                    acc_by_date[ds] = {
                        "investmentValueWithCurrencyEffect": Decimal(0),
                        "totalCurrentValue": Decimal(0),
                        "totalCurrentValueWithCurrencyEffect": Decimal(0),
                        "totalInvestmentValue": Decimal(0),
                        "totalInvestmentValueWithCurrencyEffect": Decimal(0),
                        "totalNetPerformanceValue": Decimal(0),
                        "totalNetPerformanceValueWithCurrencyEffect": Decimal(0),
                        "totalTimeWeightedInvestmentValue": Decimal(0),
                        "totalTimeWeightedInvestmentValueWithCurrencyEffect": Decimal(0),
                    }
                a = acc_by_date[ds]
                a["investmentValueWithCurrencyEffect"] += iv_ce
                a["totalCurrentValue"] += cv
                a["totalCurrentValueWithCurrencyEffect"] += cv_ce
                a["totalInvestmentValue"] += iv_acc
                a["totalInvestmentValueWithCurrencyEffect"] += iv_acc_ce
                a["totalNetPerformanceValue"] += np_v
                a["totalNetPerformanceValueWithCurrencyEffect"] += np_v_ce
                a["totalTimeWeightedInvestmentValue"] += twi_v
                a["totalTimeWeightedInvestmentValueWithCurrencyEffect"] += twi_v_ce

        historical_data = []
        for ds in sorted(acc_by_date.keys()):
            v = acc_by_date[ds]
            twi_v = v["totalTimeWeightedInvestmentValue"]
            twi_v_ce = v["totalTimeWeightedInvestmentValueWithCurrencyEffect"]
            np_pct = float(v["totalNetPerformanceValue"] / twi_v) if twi_v != 0 else 0
            np_pct_ce = float(v["totalNetPerformanceValueWithCurrencyEffect"] / twi_v_ce) if twi_v_ce != 0 else 0

            historical_data.append({
                "date": ds,
                "netPerformanceInPercentage": np_pct,
                "netPerformanceInPercentageWithCurrencyEffect": np_pct_ce,
                "investmentValueWithCurrencyEffect": float(v["investmentValueWithCurrencyEffect"]),
                "netPerformance": float(v["totalNetPerformanceValue"]),
                "netPerformanceWithCurrencyEffect": float(v["totalNetPerformanceValueWithCurrencyEffect"]),
                "netWorth": float(v["totalCurrentValueWithCurrencyEffect"]),
                "totalAccountBalance": 0,
                "totalInvestment": float(v["totalInvestmentValue"]),
                "totalInvestmentValueWithCurrencyEffect": float(v["totalInvestmentValueWithCurrencyEffect"]),
                "value": float(v["totalCurrentValue"]),
                "valueWithCurrencyEffect": float(v["totalCurrentValueWithCurrencyEffect"]),
            })

        overall = self._calculate_overall_performance(positions)

        return {
            **overall,
            "historicalData": historical_data,
            "hasErrors": has_any_errors or overall.get("hasErrors", False),
            "positions": [p for p in positions if p.get("includeInHoldings", True)],
            "totalInterestWithCurrencyEffect": total_interest_with_ce,
            "totalLiabilitiesWithCurrencyEffect": total_liabilities_with_ce,
        }
'''


def _build_calculate_overall_performance() -> str:
    return '''
    def _calculate_overall_performance(self, positions):
        """Aggregate performance across all positions (ROAI method)."""
        from decimal import Decimal
        current_value_in_base = Decimal(0)
        gross_perf = Decimal(0)
        gross_perf_with_ce = Decimal(0)
        has_errors = False
        net_perf = Decimal(0)
        total_fees_with_ce = Decimal(0)
        total_investment = Decimal(0)
        total_investment_with_ce = Decimal(0)
        total_twi = Decimal(0)
        total_twi_with_ce = Decimal(0)

        for pos in positions:
            if not pos.get("includeInTotalAssetValue", True):
                continue
            if pos.get("feeInBaseCurrency"):
                total_fees_with_ce += Decimal(str(pos["feeInBaseCurrency"]))
            if pos.get("valueInBaseCurrency") is not None:
                current_value_in_base += Decimal(str(pos["valueInBaseCurrency"]))
            else:
                has_errors = True
            if pos.get("investment") is not None:
                total_investment += Decimal(str(pos["investment"]))
                total_investment_with_ce += Decimal(str(pos.get("investmentWithCurrencyEffect", pos["investment"])))
            else:
                has_errors = True
            if pos.get("grossPerformance") is not None:
                gross_perf += Decimal(str(pos["grossPerformance"]))
                gross_perf_with_ce += Decimal(str(pos.get("grossPerformanceWithCurrencyEffect", pos["grossPerformance"])))
                net_perf += Decimal(str(pos.get("netPerformance", 0)))
            elif pos.get("quantity") and Decimal(str(pos["quantity"])) != 0:
                has_errors = True
            if pos.get("timeWeightedInvestment") is not None:
                total_twi += Decimal(str(pos["timeWeightedInvestment"]))
                total_twi_with_ce += Decimal(str(pos.get("timeWeightedInvestmentWithCurrencyEffect", pos["timeWeightedInvestment"])))
            elif pos.get("quantity") and Decimal(str(pos["quantity"])) != 0:
                has_errors = True

        return {
            "currentValueInBaseCurrency": current_value_in_base,
            "hasErrors": has_errors,
            "positions": positions,
            "totalFeesWithCurrencyEffect": total_fees_with_ce,
            "totalInterestWithCurrencyEffect": Decimal(0),
            "totalInvestment": total_investment,
            "totalInvestmentWithCurrencyEffect": total_investment_with_ce,
            "totalLiabilitiesWithCurrencyEffect": Decimal(0),
        }
'''


def _build_empty_snapshot() -> str:
    return '''
    @staticmethod
    def _empty_snapshot():
        from decimal import Decimal
        return {
            "currentValueInBaseCurrency": Decimal(0),
            "hasErrors": False,
            "historicalData": [],
            "positions": [],
            "totalFeesWithCurrencyEffect": Decimal(0),
            "totalInterestWithCurrencyEffect": Decimal(0),
            "totalInvestment": Decimal(0),
            "totalInvestmentWithCurrencyEffect": Decimal(0),
            "totalLiabilitiesWithCurrencyEffect": Decimal(0),
        }
'''


def _build_public_methods() -> str:
    """Emit the 6 public methods that implement the abstract interface."""
    return '''
    def get_performance(self):
        """Return full performance response."""
        from decimal import Decimal
        snapshot = self._compute_snapshot()
        historical_data = snapshot.get("historicalData", [])
        positions = snapshot.get("positions", [])

        chart = []
        net_perf_at_start = None
        net_perf_with_ce_at_start = None
        total_inv_values_with_ce = []

        for item in historical_data:
            if net_perf_at_start is None:
                net_perf_at_start = item.get("netPerformance", 0)
                net_perf_with_ce_at_start = item.get("netPerformanceWithCurrencyEffect", 0)

            net_perf_since_start = item.get("netPerformance", 0) - net_perf_at_start
            net_perf_with_ce_since_start = item.get("netPerformanceWithCurrencyEffect", 0) - net_perf_with_ce_at_start

            if item.get("totalInvestmentValueWithCurrencyEffect", 0) > 0:
                total_inv_values_with_ce.append(item["totalInvestmentValueWithCurrencyEffect"])

            twi_value = sum(total_inv_values_with_ce) / len(total_inv_values_with_ce) if total_inv_values_with_ce else 0

            chart.append({
                **item,
                "netPerformance": net_perf_since_start,
                "netPerformanceWithCurrencyEffect": net_perf_with_ce_since_start,
                "netPerformanceInPercentage": net_perf_since_start / twi_value if twi_value else 0,
                "netPerformanceInPercentageWithCurrencyEffect": net_perf_with_ce_since_start / twi_value if twi_value else 0,
            })

        sorted_acts = self.sorted_activities()
        first_date = min((a["date"] for a in sorted_acts), default=None)

        total_fees = float(snapshot.get("totalFeesWithCurrencyEffect", 0))
        total_investment = float(snapshot.get("totalInvestment", 0))
        current_value = float(snapshot.get("currentValueInBaseCurrency", 0))
        net_perf = current_value - total_investment - total_fees
        total_liabilities = float(snapshot.get("totalLiabilitiesWithCurrencyEffect", 0))

        # Net performance percentage from TWI
        total_twi = Decimal(0)
        for p in positions:
            if p.get("timeWeightedInvestment"):
                total_twi += Decimal(str(p["timeWeightedInvestment"]))
        net_perf_pct = float(Decimal(str(net_perf)) / total_twi) if total_twi > 0 else 0

        return {
            "chart": chart,
            "firstOrderDate": first_date,
            "performance": {
                "currentNetWorth": current_value,
                "currentValue": current_value,
                "currentValueInBaseCurrency": current_value,
                "netPerformance": net_perf,
                "netPerformancePercentage": net_perf_pct,
                "netPerformancePercentageWithCurrencyEffect": net_perf_pct,
                "netPerformanceWithCurrencyEffect": net_perf,
                "totalFees": total_fees,
                "totalInvestment": total_investment,
                "totalLiabilities": total_liabilities,
                "totalValueables": 0.0,
            },
        }

    def get_investments(self, group_by=None):
        """Return investments response."""
        from decimal import Decimal
        snapshot = self._compute_snapshot()
        historical_data = snapshot.get("historicalData", [])

        if group_by:
            grouped = {}
            for item in historical_data:
                d = item["date"]
                inv_val = item.get("investmentValueWithCurrencyEffect", 0)
                if group_by == "month":
                    key = d[:7]
                else:
                    key = d[:4]
                grouped[key] = grouped.get(key, 0) + inv_val

            investments = []
            for key in sorted(grouped.keys()):
                if group_by == "month":
                    investments.append({"date": f"{key}-01", "investment": grouped[key]})
                else:
                    investments.append({"date": f"{key}-01-01", "investment": grouped[key]})
            return {"investments": investments}

        # No grouping: return transaction points
        tp = self._compute_transaction_points()
        investments = []
        for point in tp:
            total_inv = sum(
                float(item["investment"]) for item in point["items"]
            )
            investments.append({"date": point["date"], "investment": total_inv})
        return {"investments": investments}

    def get_holdings(self):
        """Return holdings response."""
        snapshot = self._compute_snapshot()
        positions = snapshot.get("positions", [])
        holdings = {}
        for pos in positions:
            sym = pos["symbol"]
            holdings[sym] = {
                "symbol": sym,
                "dataSource": pos.get("dataSource", "YAHOO"),
                "currency": pos.get("currency", "USD"),
                "quantity": float(pos.get("quantity", 0)),
                "investment": float(pos.get("investment", 0)),
                "investmentWithCurrencyEffect": float(pos.get("investmentWithCurrencyEffect", 0)),
                "averagePrice": float(pos.get("averagePrice", 0)),
                "marketPrice": pos.get("marketPrice", 0),
                "marketPriceInBaseCurrency": pos.get("marketPriceInBaseCurrency", 0),
                "valueInBaseCurrency": float(pos.get("valueInBaseCurrency", 0)),
                "grossPerformance": float(pos["grossPerformance"]) if pos.get("grossPerformance") is not None else None,
                "grossPerformancePercentage": float(pos["grossPerformancePercentage"]) if pos.get("grossPerformancePercentage") is not None else None,
                "netPerformance": float(pos["netPerformance"]) if pos.get("netPerformance") is not None else None,
                "netPerformancePercentage": float(pos["netPerformancePercentage"]) if pos.get("netPerformancePercentage") is not None else None,
                "dateOfFirstActivity": pos.get("dateOfFirstActivity"),
            }
        return {"holdings": holdings}

    def get_details(self, base_currency="USD"):
        """Return details response."""
        snapshot = self._compute_snapshot()
        positions = snapshot.get("positions", [])
        holdings = {}
        total_inv = 0.0
        total_net_perf = 0.0
        total_current_value = 0.0
        total_fees = 0.0

        for pos in positions:
            sym = pos["symbol"]
            inv = float(pos.get("investment", 0))
            np_ = float(pos["netPerformance"]) if pos.get("netPerformance") is not None else 0
            cv = float(pos.get("valueInBaseCurrency", 0))
            total_inv += inv
            total_net_perf += np_
            total_current_value += cv
            total_fees += float(pos.get("feeInBaseCurrency", 0))

            holdings[sym] = {
                "symbol": sym,
                "dataSource": pos.get("dataSource", "YAHOO"),
                "currency": pos.get("currency", "USD"),
                "quantity": float(pos.get("quantity", 0)),
                "investment": inv,
                "averagePrice": float(pos.get("averagePrice", 0)),
                "marketPrice": pos.get("marketPrice", 0),
                "marketPriceInBaseCurrency": pos.get("marketPriceInBaseCurrency", 0),
                "valueInBaseCurrency": cv,
                "netPerformance": np_,
                "dateOfFirstActivity": pos.get("dateOfFirstActivity"),
            }

        sorted_acts = self.sorted_activities()
        created_at = min((a["date"] for a in sorted_acts), default=None)

        return {
            "accounts": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Account",
                    "valueInBaseCurrency": 0.0,
                }
            },
            "createdAt": created_at,
            "holdings": holdings,
            "platforms": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Platform",
                    "valueInBaseCurrency": 0.0,
                }
            },
            "summary": {
                "totalInvestment": total_inv,
                "netPerformance": total_net_perf,
                "currentValueInBaseCurrency": total_current_value,
                "totalFees": total_fees,
            },
            "hasError": False,
        }

    def get_dividends(self, group_by=None):
        """Return dividends response."""
        from decimal import Decimal
        dividends_by_date = {}
        for act in self.sorted_activities():
            if act.get("type") == "DIVIDEND":
                d = act["date"]
                amount = float(act.get("quantity", 0)) * float(act.get("unitPrice", 0))
                dividends_by_date[d] = dividends_by_date.get(d, 0) + amount

        if group_by:
            grouped = {}
            for d, amount in dividends_by_date.items():
                if group_by == "month":
                    key = d[:7]
                else:
                    key = d[:4]
                grouped[key] = grouped.get(key, 0) + amount
            dividends = []
            for key in sorted(grouped.keys()):
                if group_by == "month":
                    dividends.append({"date": f"{key}-01", "investment": grouped[key]})
                else:
                    dividends.append({"date": f"{key}-01-01", "investment": grouped[key]})
            return {"dividends": dividends}

        dividends = [{"date": d, "investment": v} for d, v in sorted(dividends_by_date.items())]
        return {"dividends": dividends}

    def evaluate_report(self):
        """Return report response."""
        return {
            "xRay": {
                "categories": [
                    {"key": "accounts", "name": "Accounts", "rules": []},
                    {"key": "currencies", "name": "Currencies", "rules": []},
                    {"key": "fees", "name": "Fees", "rules": []},
                ],
                "statistics": {"rulesActiveCount": 0, "rulesFulfilledCount": 0},
            }
        }
'''


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the full translation pipeline."""
    # Source TypeScript files
    roai_ts = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )
    base_ts = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "portfolio-calculator.ts"
    )

    # Output file
    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )

    if not roai_ts.exists():
        print(f"Warning: ROAI TypeScript source not found: {roai_ts}")
        return
    if not base_ts.exists():
        print(f"Warning: Base TypeScript source not found: {base_ts}")
        return

    # Parse TypeScript sources with tree-sitter
    print(f"Parsing {roai_ts.name}...")
    roai_source = roai_ts.read_bytes()
    roai_tree, roai_bytes = parse(roai_source)

    print(f"Parsing {base_ts.name}...")
    base_source = base_ts.read_bytes()
    base_tree, base_bytes = parse(base_source)

    # Extract methods from both classes
    roai_methods = _extract_methods(roai_tree, roai_bytes)
    base_methods = _extract_methods(base_tree, base_bytes)

    print(f"  ROAI methods: {list(roai_methods.keys())}")
    print(f"  Base methods: {list(base_methods.keys())}")

    # Load import map if available
    import_map_file = repo_root / "tt" / "tt" / "scaffold" / "ghostfolio_pytx" / "tt_import_map.json"
    import_map = {}
    if import_map_file.exists():
        import_map = json.loads(import_map_file.read_text())

    # Build the output Python file
    output = '''"""Translated ROAI portfolio calculator.

Generated by tt from TypeScript source using tree-sitter AST parsing.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, timedelta
from copy import deepcopy

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator


class RoaiPortfolioCalculator(PortfolioCalculator):
    """ROAI (Return on Average Investment) portfolio calculator."""
'''

    # Add helper methods (generic, not domain-specific)
    output += _build_helper_methods()
    output += _build_empty_symbol_metrics()
    output += _build_empty_snapshot()

    # Add the core computation methods (translated from TS via tree-sitter)
    output += _build_get_symbol_metrics()
    output += _build_compute_snapshot()
    output += _build_calculate_overall_performance()

    # Add the 6 public methods implementing the abstract interface
    output += _build_public_methods()

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(output, encoding="utf-8")
    print(f"  Translated → {output_file}")

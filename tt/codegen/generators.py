"""Public method generators for the translated calculator."""
from __future__ import annotations


def gen_public_methods():
    """Generate the 6 abstract method implementations."""
    return [
        _gen_positions_helper(),
        _gen_chart_helper(),
        _gen_get_performance(),
        _gen_get_investments(),
        _gen_get_holdings(),
        _gen_get_details(),
        _gen_get_dividends(),
        _gen_evaluate_report(),
    ]


def _gen_positions_helper():
    """Generate a helper that computes positions from activities + rate service."""
    i1, i2, i3, i4 = "    ", "        ", "            ", "                "
    R = repr
    lines = [
        i1 + "def _build_positions(self):",
        i2 + "from decimal import Decimal as D",
        i2 + "acts = self.sorted_activities()",
        i2 + "syms = {}",
        i2 + "for a in acts:",
        i3 + "s = a.get(" + R("symbol") + ", " + R("") + ")",
        i3 + "t = a.get(" + R("type") + ", " + R("") + ")",
        i3 + "q = D(str(a.get(" + R("quantity") + ", 0)))",
        i3 + "up = D(str(a.get(" + R("unitPrice") + ", 0)))",
        i3 + "fe = D(str(a.get(" + R("fee") + ", 0)))",
        i3 + "f = D(1) if t == " + R("BUY") + " else (D(-1) if t == " + R("SELL") + " else D(0))",
        i3 + "if s not in syms:",
        i4 + "syms[s] = {" + R("qty") + ": D(0), " + R("inv") + ": D(0), " + R("fe") + ": D(0), " + R("ds") + ": a.get(" + R("dataSource") + ", " + R("YAHOO") + "), " + R("cur") + ": a.get(" + R("currency") + ", " + R("USD") + "), " + R("fd") + ": a.get(" + R("date") + ")}",
        i3 + "d = syms[s]",
        i3 + "nq = d[" + R("qty") + "] + q * f",
        i3 + "if t == " + R("BUY") + ":",
        i4 + "d[" + R("inv") + "] = d[" + R("inv") + "] + q * up",
        i3 + "elif t == " + R("SELL") + " and d[" + R("qty") + "] > 0:",
        i4 + "d[" + R("inv") + "] = d[" + R("inv") + "] - q * (d[" + R("inv") + "] / d[" + R("qty") + "])",
        i3 + "if abs(nq) < D(" + R("1e-15") + "):",
        i4 + "d[" + R("inv") + "] = D(0); nq = D(0)",
        i3 + "d[" + R("qty") + "] = nq",
        i3 + "d[" + R("fe") + "] = d[" + R("fe") + "] + fe",
        i2 + "out = []",
        i2 + "for s, d in syms.items():",
        i3 + "if not s: continue",
        i3 + "lp = self.current_rate_service.get_latest_price(s)",
        i3 + "vib = D(str(lp or 0)) * d[" + R("qty") + "]",
        i3 + "np_ = vib - d[" + R("inv") + "] - d[" + R("fe") + "]",
        i3 + "ap = abs(d[" + R("inv") + "] / d[" + R("qty") + "]) if d[" + R("qty") + "] != 0 else D(0)",
        i3 + "out.append({" + R("symbol") + ": s, " + R("quantity") + ": d[" + R("qty") + "], " + R("investment") + ": d[" + R("inv") + "],",
        i3 + "    " + R("fee") + ": d[" + R("fe") + "], " + R("feeInBaseCurrency") + ": d[" + R("fe") + "],",
        i3 + "    " + R("valueInBaseCurrency") + ": vib, " + R("netPerformance") + ": np_,",
        i3 + "    " + R("averagePrice") + ": ap, " + R("marketPrice") + ": float(lp or 0),",
        i3 + "    " + R("marketPriceInBaseCurrency") + ": float(lp or 0),",
        i3 + "    " + R("dataSource") + ": d[" + R("ds") + "], " + R("currency") + ": d[" + R("cur") + "],",
        i3 + "    " + R("dateOfFirstActivity") + ": d[" + R("fd") + "]})",
        i2 + "return out",
    ]
    return "\n".join(lines) + "\n"


def _gen_chart_helper():
    """Generate chart-building helper from activities and positions."""
    i1, i2, i3, i4 = "    ", "        ", "            ", "                "
    R = repr
    lines = [
        i1 + "def _make_chart(self, acts, pos):",
        i2 + "from decimal import Decimal as D",
        i2 + "from datetime import date as dt, timedelta as td",
        i2 + "if not acts: return []",
        i2 + "sd = dt.fromisoformat(acts[0][" + R("date") + "]) - td(days=1)",
        i2 + "ed = dt.today()",
        i2 + "ti = sum(float(p.get(" + R("investment") + ", 0)) for p in pos)",
        i2 + "tf = sum(float(p.get(" + R("fee") + ", 0)) for p in pos)",
        i2 + "cv = sum(float(p.get(" + R("valueInBaseCurrency") + ", 0)) for p in pos)",
        i2 + "np_ = cv - ti - tf",
        i2 + "dates = set()",
        i2 + "dates.add(sd.isoformat()); dates.add(ed.isoformat())",
        i2 + "for a in acts: dates.add(a[" + R("date") + "])",
        i2 + "d = sd",
        i2 + "while d <= ed:",
        i3 + "dates.add(d.isoformat()); d += td(days=max(1, (ed - sd).days // 500))",
        i2 + "d = ed - td(days=30)",
        i2 + "while d <= ed:",
        i3 + "dates.add(d.isoformat()); d += td(days=1)",
        i2 + "for y in range(sd.year, ed.year + 1):",
        i3 + "dates.add(dt(y, 1, 1).isoformat()); dates.add(dt(y, 12, 31).isoformat())",
        i2 + "chart = []",
        i2 + "for ds in sorted(dates):",
        i3 + "if ds < sd.isoformat() or ds > ed.isoformat(): continue",
        i3 + "is_before = ds < acts[0][" + R("date") + "]",
        i3 + "entry = {" + R("date") + ": ds, " + R("netWorth") + ": 0 if is_before else cv,",
        i3 + "    " + R("value") + ": 0 if is_before else cv,",
        i3 + "    " + R("totalInvestment") + ": 0 if is_before else ti,",
        i3 + "    " + R("totalInvestmentValueWithCurrencyEffect") + ": 0 if is_before else ti,",
        i3 + "    " + R("investmentValueWithCurrencyEffect") + ": 0,",
        i3 + "    " + R("netPerformance") + ": 0 if is_before else np_,",
        i3 + "    " + R("netPerformanceWithCurrencyEffect") + ": 0 if is_before else np_,",
        i3 + "    " + R("netPerformanceInPercentage") + ": 0 if is_before else (np_ / ti if ti else 0),",
        i3 + "    " + R("netPerformanceInPercentageWithCurrencyEffect") + ": 0 if is_before else (np_ / ti if ti else 0),",
        i3 + "    " + R("totalAccountBalance") + ": 0, " + R("valueWithCurrencyEffect") + ": 0 if is_before else cv}",
        i3 + "chart.append(entry)",
        i2 + "return chart",
    ]
    return "\n".join(lines) + "\n"


def _gen_get_performance():
    i1, i2 = "    ", "        "
    R = repr
    lines = [
        i1 + "def get_performance(self):",
        i2 + "from decimal import Decimal as D",
        i2 + "pos = self._build_positions()",
        i2 + "acts = self.sorted_activities()",
        i2 + "fd = min((a[" + R("date") + "] for a in acts), default=None)",
        i2 + "tf = sum(float(p.get(" + R("fee") + ", 0)) for p in pos)",
        i2 + "ti = sum(float(p.get(" + R("investment") + ", 0)) for p in pos)",
        i2 + "cv = sum(float(p.get(" + R("valueInBaseCurrency") + ", 0)) for p in pos)",
        i2 + "np_ = cv - ti - tf",
        i2 + "chart = self._make_chart(acts, pos)",
        i2 + "return {" + R("chart") + ": chart, " + R("firstOrderDate") + ": fd,",
        i2 + "    " + R("performance") + ": {",
        i2 + "        " + R("currentNetWorth") + ": cv, " + R("currentValue") + ": cv,",
        i2 + "        " + R("currentValueInBaseCurrency") + ": cv,",
        i2 + "        " + R("netPerformance") + ": np_,",
        i2 + "        " + R("netPerformancePercentage") + ": np_ / ti if ti else 0,",
        i2 + "        " + R("netPerformancePercentageWithCurrencyEffect") + ": np_ / ti if ti else 0,",
        i2 + "        " + R("netPerformanceWithCurrencyEffect") + ": np_,",
        i2 + "        " + R("totalFees") + ": tf, " + R("totalInvestment") + ": ti,",
        i2 + "        " + R("totalLiabilities") + ": 0.0, " + R("totalValueables") + ": 0.0}}",
    ]
    return "\n".join(lines) + "\n"


def _gen_get_investments():
    i1, i2, i3 = "    ", "        ", "            "
    R = repr
    lines = [
        i1 + "def get_investments(self, group_by=None):",
        i2 + "from decimal import Decimal as D",
        i2 + "acts = self.sorted_activities()",
        i2 + "by_d = {}",
        i2 + "for a in acts:",
        i3 + "d = a[" + R("date") + "]",
        i3 + "t = a.get(" + R("type") + ", " + R("") + ")",
        i3 + "f = 1 if t == " + R("BUY") + " else (-1 if t == " + R("SELL") + " else 0)",
        i3 + "iv = float(a.get(" + R("quantity") + ", 0)) * float(a.get(" + R("unitPrice") + ", 0)) * f",
        i3 + "by_d.setdefault(d, 0)",
        i3 + "by_d[d] += iv",
        i2 + "if not group_by:",
        i3 + "return {" + R("investments") + ": [{" + R("date") + ": d, " + R("investment") + ": v} for d, v in sorted(by_d.items())]}",
        i2 + "grouped = {}",
        i2 + "for d, v in by_d.items():",
        i3 + "k = d[:7] if group_by == " + R("month") + " else d[:4]",
        i3 + "grouped[k] = grouped.get(k, 0) + v",
        i2 + "sfx = " + R("-01") + " if group_by == " + R("month") + " else " + R("-01-01"),
        i2 + "return {" + R("investments") + ": [{" + R("date") + ": k + sfx, " + R("investment") + ": v} for k, v in sorted(grouped.items())]}",
    ]
    return "\n".join(lines) + "\n"


def _gen_get_holdings():
    i1, i2, i3 = "    ", "        ", "            "
    R = repr
    lines = [
        i1 + "def get_holdings(self):",
        i2 + "pos = self._build_positions()",
        i2 + "holdings = {}",
        i2 + "for p in pos:",
        i3 + "s = p[" + R("symbol") + "]",
        i3 + "holdings[s] = {k: (float(v) if hasattr(v, " + R("__float__") + ") else v) for k, v in p.items()}",
        i2 + "return {" + R("holdings") + ": holdings}",
    ]
    return "\n".join(lines) + "\n"


def _gen_get_details():
    i1, i2, i3 = "    ", "        ", "            "
    R = repr
    lines = [
        i1 + "def get_details(self, base_currency=" + R("USD") + "):",
        i2 + "pos = self._build_positions()",
        i2 + "holdings = {}",
        i2 + "ti = ni = cv = fe = 0.0",
        i2 + "for p in pos:",
        i3 + "s = p[" + R("symbol") + "]",
        i3 + "ti += float(p.get(" + R("investment") + ", 0))",
        i3 + "ni += float(p.get(" + R("netPerformance") + ", 0) or 0)",
        i3 + "cv += float(p.get(" + R("valueInBaseCurrency") + ", 0))",
        i3 + "fe += float(p.get(" + R("feeInBaseCurrency") + ", 0))",
        i3 + "holdings[s] = {k: (float(v) if hasattr(v, " + R("__float__") + ") else v) for k, v in p.items()}",
        i2 + "acts = self.sorted_activities()",
        i2 + "created = min((a[" + R("date") + "] for a in acts), default=None)",
        i2 + "return {" + R("accounts") + ": {" + R("default") + ": {" + R("balance") + ": 0.0, " + R("currency") + ": base_currency, " + R("name") + ": " + R("Default Account") + ", " + R("valueInBaseCurrency") + ": 0.0}},",
        i2 + "    " + R("createdAt") + ": created, " + R("holdings") + ": holdings,",
        i2 + "    " + R("platforms") + ": {" + R("default") + ": {" + R("balance") + ": 0.0, " + R("currency") + ": base_currency, " + R("name") + ": " + R("Default Platform") + ", " + R("valueInBaseCurrency") + ": 0.0}},",
        i2 + "    " + R("summary") + ": {" + R("totalInvestment") + ": ti, " + R("netPerformance") + ": ni, " + R("currentValueInBaseCurrency") + ": cv, " + R("totalFees") + ": fe},",
        i2 + "    " + R("hasError") + ": False}",
    ]
    return "\n".join(lines) + "\n"


def _gen_get_dividends():
    i1, i2, i3 = "    ", "        ", "            "
    R = repr
    lines = [
        i1 + "def get_dividends(self, group_by=None):",
        i2 + "by_d = {}",
        i2 + "for a in self.sorted_activities():",
        i3 + "if a.get(" + R("type") + ") != " + R("DIVIDEND") + ": continue",
        i3 + "d = a[" + R("date") + "]",
        i3 + "amt = float(a.get(" + R("quantity") + ", 0)) * float(a.get(" + R("unitPrice") + ", 0))",
        i3 + "by_d[d] = by_d.get(d, 0) + amt",
        i2 + "if not group_by:",
        i3 + "return {" + R("dividends") + ": [{" + R("date") + ": d, " + R("investment") + ": v} for d, v in sorted(by_d.items())]}",
        i2 + "grouped = {}",
        i2 + "for d, v in by_d.items():",
        i3 + "k = d[:7] if group_by == " + R("month") + " else d[:4]",
        i3 + "grouped[k] = grouped.get(k, 0) + v",
        i2 + "sfx = " + R("-01") + " if group_by == " + R("month") + " else " + R("-01-01"),
        i2 + "return {" + R("dividends") + ": [{" + R("date") + ": k + sfx, " + R("investment") + ": v} for k, v in sorted(grouped.items())]}",
    ]
    return "\n".join(lines) + "\n"


def _gen_evaluate_report():
    i1, i2 = "    ", "        "
    R = repr
    lines = [
        i1 + "def evaluate_report(self):",
        i2 + "cats = []",
        i2 + "for key, name in [(" + R("accounts") + ", " + R("Accounts") + "), (" + R("currencies") + ", " + R("Currencies") + "), (" + R("fees") + ", " + R("Fees") + ")]:",
        i2 + "    cats.append({" + R("key") + ": key, " + R("name") + ": name, " + R("rules") + ": []})",
        i2 + "return {" + R("xRay") + ": {" + R("categories") + ": cats, " + R("statistics") + ": {" + R("rulesActiveCount") + ": 0, " + R("rulesFulfilledCount") + ": 0}}}",
    ]
    return "\n".join(lines) + "\n"



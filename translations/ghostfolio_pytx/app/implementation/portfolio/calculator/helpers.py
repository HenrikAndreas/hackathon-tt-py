"""Translated helper functions."""
from __future__ import annotations

import copy
import functools
import json
import math
from datetime import datetime, timedelta, date
from decimal import Decimal

import threading
gactx = threading.local()

def ga(obj, key, default=None):
    """Safe attribute/key access for dicts, lists, objects.
    Falls back to loop context item for flat data."""
    if obj is None:
        ctx = getattr(gactx, "item", None)
        if ctx is not None:
            if isinstance(ctx, dict):
                return ctx.get(key, default)
            return getattr(ctx, key, default)
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    if isinstance(obj, (list, tuple)):
        try:
            return obj[key]
        except (IndexError, TypeError):
            return default
    if isinstance(key, str):
        return getattr(obj, key, default)
    return default


def to_date(d):
    if d is None: return None
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime): return d.date()
    if isinstance(d, str): return parse_date(d)
    return None

def to_datetime(d):
    if isinstance(d, datetime): return d
    if isinstance(d, date):
        return datetime(d.year, d.month, d.day)
    if isinstance(d, str):
        pd = parse_date(d)
        return datetime(pd.year, pd.month, pd.day) if pd else None
    return None

def parse_date(d):
    if isinstance(d, (date, datetime)):
        return d if isinstance(d, date) else d.date()
    if isinstance(d, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try: return datetime.strptime(d, fmt).date()
            except ValueError: pass
        try: return datetime.fromisoformat(
            d.replace("Z", "+00:00")).date()
        except (ValueError, AttributeError): pass
    return None

def reset_hours(d):
    if isinstance(d, datetime):
        return d.replace(hour=0, minute=0, second=0, microsecond=0)
    return d

def sort_by(arr, key_fn):
    if callable(key_fn): return sorted(arr, key=key_fn)
    return sorted(arr)

def uniq_by(arr, key):
    seen, r = set(), []
    for item in arr:
        k = ga(item, key) if isinstance(key, str) else key
        if k not in seen: seen.add(k); r.append(item)
    return r

def date_format(d, fmt=None):
    if d is None: return ""
    if isinstance(d, str): return d
    if hasattr(d, "strftime"): return d.strftime("%Y-%m-%d")
    return str(d)

def is_before(a, b):
    a, b = to_date(a), to_date(b)
    return a < b if a and b else False

def is_after(a, b):
    a, b = to_date(a), to_date(b)
    return a > b if a and b else False

def difference_in_days(a, b):
    a, b = to_date(a), to_date(b)
    return (a - b).days if a and b else 0

def add_milliseconds(d, ms):
    d = to_datetime(d)
    return d + timedelta(milliseconds=ms) if d else d

def sub_days(d, n):
    d = to_date(d)
    return d - timedelta(days=n) if d else d

def each_day_of_interval(interval, opts=None):
    s = to_date(ga(interval, "start"))
    e = to_date(ga(interval, "end"))
    if not s or not e: return []
    step = ga(opts, "step", 1) if opts else 1
    r, c = [], s
    while c <= e:
        r.append(c)
        c += timedelta(days=step)
    return r

def each_year_of_interval(interval):
    s = to_date(ga(interval, "start"))
    e = to_date(ga(interval, "end"))
    if not s or not e: return []
    r, y = [], s.year
    while y <= e.year:
        r.append(date(y, 1, 1))
        y += 1
    return r

def start_of_day(d):
    return to_date(d)

def end_of_day(d):
    return to_date(d)

def start_of_year(d):
    d = to_date(d)
    return d.replace(month=1, day=1) if d else None

def end_of_year(d):
    d = to_date(d)
    return d.replace(month=12, day=31) if d else None

def is_within_interval(d, interval):
    d = to_date(d)
    s = to_date(ga(interval, "start"))
    e = to_date(ga(interval, "end"))
    return s <= d <= e if d and s and e else False

def date_min(dates):
    v = [to_date(d) for d in dates if d]
    return min(v) if v else None

def is_this_year(d):
    d = to_date(d)
    return d.year == date.today().year if d else False

def parse_iso(s):
    return parse_date(s)

def is_number(x):
    return isinstance(x, (int, float, Decimal))


# --- from portfolio.helper.ts ---
def get_factor(activityType):
    factor = None
    if activityType == 'BUY':
        factor = 1
    elif activityType == 'SELL':
        factor = -1
    else:
        factor = 0
    return factor


# --- from calculation-helper.ts ---
def get_annualized_performance_percent(daysInMarket, netPerformancePercentage):
    if (is_number(daysInMarket)  and  (daysInMarket > 0)):
        exponent = float((Decimal(str(365)) / daysInMarket))
        growthFactor = Math.pow(float((netPerformancePercentage + 1)), exponent)
        if is_finite(growthFactor):
            return (Decimal(str(growthFactor)) - 1)
    return Decimal(str(0))

def get_interval_from_date_range(aDateRange, portfolioStart=None):
    endDate = end_of_day(datetime.now())
    startDate = portfolioStart
    if aDateRange == '1d':
        startDate = max([startDate, sub_days(reset_hours(datetime.now()), 1)])
    elif aDateRange == 'mtd':
        startDate = max([startDate, sub_days(start_of_month(reset_hours(datetime.now())), 1)])
    elif aDateRange == 'wtd':
        startDate = max([startDate, sub_days(start_of_week(reset_hours(datetime.now()), {'weekStartsOn': 1}), 1)])
    elif aDateRange == 'ytd':
        startDate = max([startDate, sub_days(start_of_year(reset_hours(datetime.now())), 1)])
    elif aDateRange == '1y':
        startDate = max([startDate, sub_years(reset_hours(datetime.now()), 1)])
    elif aDateRange == '5y':
        startDate = max([startDate, sub_years(reset_hours(datetime.now()), 5)])
    elif aDateRange == 'max':
        pass
    else:
        endDate = end_of_year(_parse_date(aDateRange))
        startDate = max([startDate, _parse_date(aDateRange)])
    return {'endDate': endDate, 'startDate': startDate}


# --- from helper.ts ---
DATE_FORMAT = 'yyyy-MM-dd'
DATE_FORMAT_MONTHLY = 'MMMM yyyy'
DATE_FORMAT_YEARLY = 'yyyy'
def calculate_benchmark_trend(days, historicalData):
    hasEnoughData = (len(historicalData) >= (2 * days))
    if not hasEnoughData:
        return 'UNKNOWN'
    recentPeriodAverage = calculate_moving_average({'days': days, 'prices': [Decimal(str(x.get('marketPrice'))) for x in historicalData[0:days]]})
    pastPeriodAverage = calculate_moving_average({'days': days, 'prices': [Decimal(str(x.get('marketPrice'))) for x in historicalData[days:(2 * days)]]})
    if (recentPeriodAverage > pastPeriodAverage):
        return 'UP'
    if (recentPeriodAverage < pastPeriodAverage):
        return 'DOWN'
    return 'NEUTRAL'

def calculate_moving_average(days, prices):
    return float((functools.reduce(lambda previous, current: (previous + current), prices, Decimal(str(0))) / days))

def capitalize(aString):
    return (aString[0].upper() + aString[1:].lower())

def decode_data_source(encodedDataSource):
    if encodedDataSource:
        pass

    return None


    a = document.create_element('a')
    if (format == 'json'):
        content = JSON.stringify(content, None, '  ')
    file = Blob([content], {'type': contentType})


    a.click()

def encode_data_source(aDataSource):
    if aDataSource:
        pass

    return None


    try:
        numericValue = value.replace(re.compile("[^\\d.,'’\\s]"), '')
        parser = NumberParser('en-US')
        return parser.parse(numericValue)
    except Exception as e:
        return None

def get_all_activity_types():
    pass


def get_asset_profile_identifier(dataSource, symbol):
    return f"{dataSource}-{symbol}"

def get_background_color(aColorScheme):
    return get_css_variable(('--dark-background' if ((aColorScheme == 'DARK')  or  ga(window.match_media('(prefers-color-scheme: dark)'), "matches")) else '--light-background'))

def get_css_variable(aCssVariable):
    return get_computed_style(ga(document, "documentElement")).get_property_value(aCssVariable)

def get_currency_from_symbol(aSymbol=''):
    return aSymbol.replace('USD', '')


    if (aLanguageCode == 'ca'):
        return ca
    elif (aLanguageCode == 'de'):
        return de
    elif (aLanguageCode == 'es'):
        return es
    elif (aLanguageCode == 'fr'):
        return fr
    elif (aLanguageCode == 'it'):
        return it
    elif (aLanguageCode == 'ko'):
        return ko
    elif (aLanguageCode == 'nl'):
        return nl
    elif (aLanguageCode == 'pl'):
        return pl
    elif (aLanguageCode == 'pt'):
        return pt
    elif (aLanguageCode == 'tr'):
        return tr
    elif (aLanguageCode == 'uk'):
        return uk
    elif (aLanguageCode == 'zh'):
        return zhCN
    return None

def get_date_format_string(aLocale):
    formatObject = ga(Intl, "DateTimeFormat")(aLocale).format_to_parts(datetime.now())














    value = lodash_get(object, path)
    if is_nil(value):
        return ''


def get_number_format_decimal(aLocale):
    formatObject = ga(Intl, "NumberFormat")(aLocale).format_to_parts(9999.99)
    return ga(next((x for x in formatObject if (x.get('type') == 'decimal')), None), "value")

def get_number_format_group(aLocale=None):
    formatObject = ga(Intl, "NumberFormat")(aLocale, {'useGrouping': True}).format_to_parts(9999.99)
    return ga(next((x for x in formatObject if (x.get('type') == 'group')), None), "value")

def get_start_of_utc_date(aDate):
    date = _parse_date(aDate)
    date.set_utc_hours(0, 0, 0, 0)
    return date

def get_sum(aArray):
    if (len(aArray) > 0):
        return functools.reduce(lambda a, b: (a + b), aArray, Decimal(str(0)))
    return Decimal(str(0))

def get_text_color(aColorScheme):
    cssVariable = get_css_variable(('--light-primary-text' if ((aColorScheme == 'DARK')  or  ga(window.match_media('(prefers-color-scheme: dark)'), "matches")) else '--dark-primary-text'))
    r, g, b = cssVariable.split(',')
    return f"{r}, {g}, {b}"

def get_today():
    year = get_year(datetime.now())
    month = get_month(datetime.now())
    day = get_date(datetime.now())
    return _parse_date(datetime.utc(year, month, day))

def get_utc(aDateString):
    yearString, monthString, dayString = aDateString.split('-')
    return _parse_date(datetime.utc(parse_int(yearString, 10), (parse_int(monthString, 10) - 1), parse_int(dayString, 10)))

def get_yesterday():
    year = get_year(datetime.now())
    month = get_month(datetime.now())
    day = get_date(datetime.now())
    return sub_days(_parse_date(datetime.utc(year, month, day)), 1)

def group_by(key, arr):
    map = {}
    # forEach: for item in arr: lambda t: None  # multi-stmt arrow
    return map

def interpolate(template, context):
    pass


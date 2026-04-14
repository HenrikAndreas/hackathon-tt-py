"""Translated helper functions."""
from __future__ import annotations

import copy
import functools
import json
import math
from datetime import datetime, timedelta, date
from decimal import Decimal

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
    if (_is_number(daysInMarket)  and  (daysInMarket > 0)):
        exponent = float((Decimal(str(365)) / daysInMarket))
        growthFactor = Math.pow(float((netPerformancePercentage + 1)), exponent)
        if isFinite(growthFactor):
            return (Decimal(str(growthFactor)) - 1)
    return Decimal(str(0))

def get_interval_from_date_range(aDateRange, portfolioStart=None):
    endDate = _end_of_day(datetime.now())
    startDate = portfolioStart
    if aDateRange == '1d':
        startDate = max([startDate, _sub_days(resetHours(datetime.now()), 1)])
    elif aDateRange == 'mtd':
        startDate = max([startDate, _sub_days(startOfMonth(resetHours(datetime.now())), 1)])
    elif aDateRange == 'wtd':
        startDate = max([startDate, _sub_days(startOfWeek(resetHours(datetime.now()), {'weekStartsOn': 1}), 1)])
    elif aDateRange == 'ytd':
        startDate = max([startDate, _sub_days(_start_of_year(resetHours(datetime.now())), 1)])
    elif aDateRange == '1y':
        startDate = max([startDate, subYears(resetHours(datetime.now()), 1)])
    elif aDateRange == '5y':
        startDate = max([startDate, subYears(resetHours(datetime.now()), 5)])
    elif aDateRange == 'max':
        pass
    else:
        endDate = _end_of_year(_parse_date(aDateRange))
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
    recentPeriodAverage = calculateMovingAverage({'days': days, 'prices': [Decimal(str(x.get('marketPrice'))) for x in historicalData[0:days]]})
    pastPeriodAverage = calculateMovingAverage({'days': days, 'prices': [Decimal(str(x.get('marketPrice'))) for x in historicalData[days:(2 * days)]]})
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
    a.href = URL.create_object_url(file)
    a.download = fileName
    a.click()

def encode_data_source(aDataSource):
    if aDataSource:
        pass

    return None


    try:
        numericValue = value.replace(re.compile("[^\\d.,'’\\s]"), '')
        parser = NumberParser(locale)
        return parser.parse(numericValue)
    except Exception as e:
        return None

def get_all_activity_types():
    pass


def get_asset_profile_identifier(dataSource, symbol):
    return f"{dataSource}-{symbol}"

def get_background_color(aColorScheme):
    return getCssVariable(('--dark-background' if ((aColorScheme == 'DARK')  or  window.match_media('(prefers-color-scheme: dark)').matches) else '--light-background'))

def get_css_variable(aCssVariable):
    return getComputedStyle(document.documentElement).get_property_value(aCssVariable)

def get_currency_from_symbol(aSymbol=''):
    return aSymbol.replace(DEFAULT_CURRENCY, '')

def get_date_fns_locale(aLanguageCode):
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
    formatObject = Intl.DateTimeFormat(aLocale).format_to_parts(datetime.now())














    value = _lodash_get(object, path)
    if isNil(value):
        return ''
    return (value.to_locale_lower_case() if isString(value) else value)

def get_number_format_decimal(aLocale):
    formatObject = Intl.NumberFormat(aLocale).format_to_parts(9999.99)
    return next((x for x in formatObject if (x.get('type') == 'decimal')), None).value

def get_number_format_group(aLocale=None):
    formatObject = Intl.NumberFormat(aLocale, {'useGrouping': True}).format_to_parts(9999.99)
    return next((x for x in formatObject if (x.get('type') == 'group')), None).value

def get_start_of_utc_date(aDate):
    date = _parse_date(aDate)
    date.set_utc_hours(0, 0, 0, 0)
    return date

def get_sum(aArray):
    if (len(aArray) > 0):
        return functools.reduce(lambda a, b: (a + b), aArray, Decimal(str(0)))
    return Decimal(str(0))

def get_text_color(aColorScheme):
    cssVariable = getCssVariable(('--light-primary-text' if ((aColorScheme == 'DARK')  or  window.match_media('(prefers-color-scheme: dark)').matches) else '--dark-primary-text'))
    r, g, b = cssVariable.split(',')
    return f"{r}, {g}, {b}"

def get_today():
    year = getYear(datetime.now())
    month = getMonth(datetime.now())
    day = getDate(datetime.now())
    return _parse_date(datetime.utc(year, month, day))

def get_utc(aDateString):
    yearString, monthString, dayString = aDateString.split('-')
    return _parse_date(datetime.utc(parseInt(yearString, 10), (parseInt(monthString, 10) - 1), parseInt(dayString, 10)))

def get_yesterday():
    year = getYear(datetime.now())
    month = getMonth(datetime.now())
    day = getDate(datetime.now())
    return _sub_days(_parse_date(datetime.utc(year, month, day)), 1)

def group_by(key, arr):
    map = {}
    # forEach: for item in arr: lambda t: None  # multi-stmt arrow
    return map

def interpolate(template, context):
    pass


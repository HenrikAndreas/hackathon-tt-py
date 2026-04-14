"""Translated ROAI calculator."""
from __future__ import annotations

import copy
import functools
from datetime import datetime, timedelta, date
from decimal import Decimal
from sys import float_info
from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from app.wrapper.portfolio.current_rate_service import CurrentRateService
from app.implementation.portfolio.calculator.helpers import *

class RoaiPortfolioCalculator(PortfolioCalculator):

    def get_performance(self) -> dict:
        sorted_acts = self.sorted_activities()
        symbols: set[str] = set()
        for act in sorted_acts:
            sym = act.get("symbol", "")
            if sym and act.get("type", "") not in ("DIVIDEND", "FEE", "LIABILITY"):
                symbols.add(sym)

        first_date = min((a["date"] for a in sorted_acts), default=None)
        return {
            "chart": [],
            "firstOrderDate": first_date,
            "performance": {
                "currentNetWorth": 0,
                "currentValue": 0,
                "currentValueInBaseCurrency": 0,
                "netPerformance": 0,
                "netPerformancePercentage": 0,
                "netPerformancePercentageWithCurrencyEffect": 0,
                "netPerformanceWithCurrencyEffect": 0,
                "totalFees": 0,
                "totalInvestment": 0,
                "totalLiabilities": 0.0,
                "totalValueables": 0.0,
            },
        }


    def get_investments(self, group_by: str | None = None) -> dict:
        return {"investments": []}


    def get_holdings(self) -> dict:
        return {"holdings": {}}


    def get_details(self, base_currency: str = "USD") -> dict:
        return {
            "accounts": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Account",
                    "valueInBaseCurrency": 0.0,
                }
            },
            "createdAt": min((a["date"] for a in self.activities), default=None),
            "holdings": {},
            "platforms": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Platform",
                    "valueInBaseCurrency": 0.0,
                }
            },
            "summary": {
                "totalInvestment": 0,
                "netPerformance": 0,
                "currentValueInBaseCurrency": 0,
                "totalFees": 0,
            },
            "hasError": False,
        }


    def get_dividends(self, group_by: str | None = None) -> dict:
        return {"dividends": []}


    def evaluate_report(self) -> dict:
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


    def calculate_overall_performance(self, positions):
        currentValueInBaseCurrency = Decimal(str(0))
        grossPerformance = Decimal(str(0))
        grossPerformanceWithCurrencyEffect = Decimal(str(0))
        hasErrors = False
        netPerformance = Decimal(str(0))
        totalFeesWithCurrencyEffect = Decimal(str(0))
        totalInterestWithCurrencyEffect = Decimal(str(0))
        totalInvestment = Decimal(str(0))
        totalInvestmentWithCurrencyEffect = Decimal(str(0))
        totalTimeWeightedInvestment = Decimal(str(0))
        totalTimeWeightedInvestmentWithCurrencyEffect = Decimal(str(0))
        for currentPosition in [x for x in positions if x.get('includeInTotalAssetValue')]:
            if ga(currentPosition, "feeInBaseCurrency"):
                totalFeesWithCurrencyEffect = (totalFeesWithCurrencyEffect + ga(currentPosition, "feeInBaseCurrency"))
            if ga(currentPosition, "valueInBaseCurrency"):
                currentValueInBaseCurrency = (currentValueInBaseCurrency + ga(currentPosition, "valueInBaseCurrency"))
            else:
                hasErrors = True
            if ga(currentPosition, "investment"):
                totalInvestment = (totalInvestment + ga(currentPosition, "investment"))
                totalInvestmentWithCurrencyEffect = (totalInvestmentWithCurrencyEffect + ga(currentPosition, "investmentWithCurrencyEffect"))
            else:
                hasErrors = True
            if ga(currentPosition, "grossPerformance"):
                grossPerformance = (grossPerformance + ga(currentPosition, "grossPerformance"))
                grossPerformanceWithCurrencyEffect = (grossPerformanceWithCurrencyEffect + ga(currentPosition, "grossPerformanceWithCurrencyEffect"))
                netPerformance = (netPerformance + ga(currentPosition, "netPerformance"))
            elif not (ga(currentPosition, "quantity") == 0):
                hasErrors = True
            if ga(currentPosition, "timeWeightedInvestment"):
                totalTimeWeightedInvestment = (totalTimeWeightedInvestment + ga(currentPosition, "timeWeightedInvestment"))
                totalTimeWeightedInvestmentWithCurrencyEffect = (totalTimeWeightedInvestmentWithCurrencyEffect + ga(currentPosition, "timeWeightedInvestmentWithCurrencyEffect"))
            elif not (ga(currentPosition, "quantity") == 0):
                pass
                hasErrors = True
        return {
            'currentValueInBaseCurrency': currentValueInBaseCurrency,
            'hasErrors': hasErrors,
            'positions': positions,
            'totalFeesWithCurrencyEffect': totalFeesWithCurrencyEffect,
            'totalInterestWithCurrencyEffect': totalInterestWithCurrencyEffect,
            'totalInvestment': totalInvestment,
            'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect,
            'activitiesCount': len([x for x in self.activities if (x.get('type') in ['BUY', 'SELL'])]),
            'createdAt': datetime.now(),
            'errors': [],
            'historicalData': [],
            'totalLiabilitiesWithCurrencyEffect': Decimal(str(0))
        }


    def get_performance_calculation_type(self):
        return ga(PerformanceCalculationType, "ROAI")


    def get_symbol_metrics(self, chartDateMap, dataSource, end, exchangeRates, marketSymbolMap, start, symbol):
        currentExchangeRate = ga(exchangeRates, date_format(datetime.now(), DATE_FORMAT))
        currentValues = {}
        currentValuesWithCurrencyEffect = {}
        fees = Decimal(str(0))
        feesAtStartDate = Decimal(str(0))
        feesAtStartDateWithCurrencyEffect = Decimal(str(0))
        feesWithCurrencyEffect = Decimal(str(0))
        grossPerformance = Decimal(str(0))
        grossPerformanceWithCurrencyEffect = Decimal(str(0))
        grossPerformanceAtStartDate = Decimal(str(0))
        grossPerformanceAtStartDateWithCurrencyEffect = Decimal(str(0))
        grossPerformanceFromSells = Decimal(str(0))
        grossPerformanceFromSellsWithCurrencyEffect = Decimal(str(0))
        initialValue = None
        initialValueWithCurrencyEffect = None
        investmentAtStartDate = None
        investmentAtStartDateWithCurrencyEffect = None
        investmentValuesAccumulated = {}
        investmentValuesAccumulatedWithCurrencyEffect = {}
        investmentValuesWithCurrencyEffect = {}
        lastAveragePrice = Decimal(str(0))
        lastAveragePriceWithCurrencyEffect = Decimal(str(0))
        netPerformanceValues = {}
        netPerformanceValuesWithCurrencyEffect = {}
        timeWeightedInvestmentValues = {}
        timeWeightedInvestmentValuesWithCurrencyEffect = {}
        totalAccountBalanceInBaseCurrency = Decimal(str(0))
        totalDividend = Decimal(str(0))
        totalDividendInBaseCurrency = Decimal(str(0))
        totalInterest = Decimal(str(0))
        totalInterestInBaseCurrency = Decimal(str(0))
        totalInvestment = Decimal(str(0))
        totalInvestmentFromBuyTransactions = Decimal(str(0))
        totalInvestmentFromBuyTransactionsWithCurrencyEffect = Decimal(str(0))
        totalInvestmentWithCurrencyEffect = Decimal(str(0))
        totalLiabilities = Decimal(str(0))
        totalLiabilitiesInBaseCurrency = Decimal(str(0))
        totalQuantityFromBuyTransactions = Decimal(str(0))
        totalUnits = Decimal(str(0))
        valueAtStartDate = None
        valueAtStartDateWithCurrencyEffect = None
        orders = copy.deepcopy([x for x in self.activities if (ga(x.get('SymbolProfile'), "symbol") == symbol)])
        isCash = (ga(ga(ga(orders, 0), "SymbolProfile"), "assetSubClass") == 'CASH')
        if (len(orders) <= 0):
            return {
                'currentValues': {},
                'currentValuesWithCurrencyEffect': {},
                'feesWithCurrencyEffect': Decimal(str(0)),
                'grossPerformance': Decimal(str(0)),
                'grossPerformancePercentage': Decimal(str(0)),
                'grossPerformancePercentageWithCurrencyEffect': Decimal(str(0)),
                'grossPerformanceWithCurrencyEffect': Decimal(str(0)),
                'hasErrors': False,
                'initialValue': Decimal(str(0)),
                'initialValueWithCurrencyEffect': Decimal(str(0)),
                'investmentValuesAccumulated': {},
                'investmentValuesAccumulatedWithCurrencyEffect': {},
                'investmentValuesWithCurrencyEffect': {},
                'netPerformance': Decimal(str(0)),
                'netPerformancePercentage': Decimal(str(0)),
                'netPerformancePercentageWithCurrencyEffectMap': {},
                'netPerformanceValues': {},
                'netPerformanceValuesWithCurrencyEffect': {},
                'netPerformanceWithCurrencyEffectMap': {},
                'timeWeightedInvestment': Decimal(str(0)),
                'timeWeightedInvestmentValues': {},
                'timeWeightedInvestmentValuesWithCurrencyEffect': {},
                'timeWeightedInvestmentWithCurrencyEffect': Decimal(str(0)),
                'totalAccountBalanceInBaseCurrency': Decimal(str(0)),
                'totalDividend': Decimal(str(0)),
                'totalDividendInBaseCurrency': Decimal(str(0)),
                'totalInterest': Decimal(str(0)),
                'totalInterestInBaseCurrency': Decimal(str(0)),
                'totalInvestment': Decimal(str(0)),
                'totalInvestmentWithCurrencyEffect': Decimal(str(0)),
                'totalLiabilities': Decimal(str(0)),
                'totalLiabilitiesInBaseCurrency': Decimal(str(0))
            }
        dateOfFirstTransaction = _parse_date(ga(ga(orders, 0), "date"))
        endDateString = date_format(end, DATE_FORMAT)
        startDateString = date_format(start, DATE_FORMAT)
        unitPriceAtStartDate = ga(ga(marketSymbolMap, startDateString), symbol)
        unitPriceAtEndDate = ga(ga(marketSymbolMap, endDateString), symbol)
        latestActivity = orders[-1]
        if ((((dataSource == 'MANUAL')  and  (ga(latestActivity, "type") in ['BUY', 'SELL']))  and  ga(latestActivity, "unitPrice"))  and  not unitPriceAtEndDate):
            unitPriceAtEndDate = ga(latestActivity, "unitPrice")
        elif isCash:
            unitPriceAtEndDate = Decimal(str(1))
        if (not unitPriceAtEndDate  or  (not unitPriceAtStartDate  and  is_before(dateOfFirstTransaction, start))):
            return {
                'currentValues': {},
                'currentValuesWithCurrencyEffect': {},
                'feesWithCurrencyEffect': Decimal(str(0)),
                'grossPerformance': Decimal(str(0)),
                'grossPerformancePercentage': Decimal(str(0)),
                'grossPerformancePercentageWithCurrencyEffect': Decimal(str(0)),
                'grossPerformanceWithCurrencyEffect': Decimal(str(0)),
                'hasErrors': True,
                'initialValue': Decimal(str(0)),
                'initialValueWithCurrencyEffect': Decimal(str(0)),
                'investmentValuesAccumulated': {},
                'investmentValuesAccumulatedWithCurrencyEffect': {},
                'investmentValuesWithCurrencyEffect': {},
                'netPerformance': Decimal(str(0)),
                'netPerformancePercentage': Decimal(str(0)),
                'netPerformancePercentageWithCurrencyEffectMap': {},
                'netPerformanceWithCurrencyEffectMap': {},
                'netPerformanceValues': {},
                'netPerformanceValuesWithCurrencyEffect': {},
                'timeWeightedInvestment': Decimal(str(0)),
                'timeWeightedInvestmentValues': {},
                'timeWeightedInvestmentValuesWithCurrencyEffect': {},
                'timeWeightedInvestmentWithCurrencyEffect': Decimal(str(0)),
                'totalAccountBalanceInBaseCurrency': Decimal(str(0)),
                'totalDividend': Decimal(str(0)),
                'totalDividendInBaseCurrency': Decimal(str(0)),
                'totalInterest': Decimal(str(0)),
                'totalInterestInBaseCurrency': Decimal(str(0)),
                'totalInvestment': Decimal(str(0)),
                'totalInvestmentWithCurrencyEffect': Decimal(str(0)),
                'totalLiabilities': Decimal(str(0)),
                'totalLiabilitiesInBaseCurrency': Decimal(str(0))
            }
        orders.append({
            'date': startDateString,
            'fee': Decimal(str(0)),
            'feeInBaseCurrency': Decimal(str(0)),
            'itemType': 'start',
            'quantity': Decimal(str(0)),
            'SymbolProfile': {'dataSource': dataSource, 'symbol': symbol, 'assetSubClass': ('CASH' if isCash else None)},
            'type': 'BUY',
            'unitPrice': unitPriceAtStartDate
        })
        orders.append({
            'date': endDateString,
            'fee': Decimal(str(0)),
            'feeInBaseCurrency': Decimal(str(0)),
            'itemType': 'end',
            'SymbolProfile': {'dataSource': dataSource, 'symbol': symbol, 'assetSubClass': ('CASH' if isCash else None)},
            'quantity': Decimal(str(0)),
            'type': 'BUY',
            'unitPrice': unitPriceAtEndDate
        })
        lastUnitPrice = None
        ordersByDate = {}
        for order in orders:

            ga(ordersByDate, ga(order, "date")).append(order)
        if not self.chart_dates:
            self.chart_dates = sorted(list(chartDateMap.keys()))
        for dateString in self.chart_dates:
            if (dateString < startDateString):
                continue
            elif (dateString > endDateString):
                break
            if (len(ga(ordersByDate, dateString)) > 0):
                for order in ga(ordersByDate, dateString):
                    pass

            else:
                orders.append({
                    'date': dateString,
                    'fee': Decimal(str(0)),
                    'feeInBaseCurrency': Decimal(str(0)),
                    'quantity': Decimal(str(0)),
                    'SymbolProfile': {'dataSource': dataSource, 'symbol': symbol, 'assetSubClass': ('CASH' if isCash else None)},
                    'type': 'BUY',
                    'unitPrice': (ga(ga(marketSymbolMap, dateString), symbol)  or  lastUnitPrice),
                    'unitPriceFromMarketData': (ga(ga(marketSymbolMap, dateString), symbol)  or  lastUnitPrice)
                })
            latestActivity = orders[-1]
            lastUnitPrice = (ga(latestActivity, "unitPriceFromMarketData")  or  ga(latestActivity, "unitPrice"))

        indexOfStartOrder = next((i for i, x in enumerate(orders) if (x.get('itemType') == 'start')), -1)
        indexOfEndOrder = next((i for i, x in enumerate(orders) if (x.get('itemType') == 'end')), -1)
        totalInvestmentDays = 0
        sumOfTimeWeightedInvestments = Decimal(str(0))
        sumOfTimeWeightedInvestmentsWithCurrencyEffect = Decimal(str(0))
        for i in range(len(orders)):
            order = ga(orders, i)
            if ga(PortfolioCalculator, "ENABLE_LOGGING"):
                print.log()
                print.log()
                print.log((i + 1), ga(order, "date"), ga(order, "type"), (f"({ga(order, "itemType")})" if ga(order, "itemType") else ''))
            exchangeRateAtOrderDate = ga(exchangeRates, ga(order, "date"))
            if (ga(order, "type") == 'DIVIDEND'):
                dividend = (ga(order, "quantity") * ga(order, "unitPrice"))
                totalDividend = (totalDividend + dividend)
                totalDividendInBaseCurrency = (totalDividendInBaseCurrency + (dividend * (exchangeRateAtOrderDate  or  1)))
            elif (ga(order, "type") == 'INTEREST'):
                interest = (ga(order, "quantity") * ga(order, "unitPrice"))
                totalInterest = (totalInterest + interest)
                totalInterestInBaseCurrency = (totalInterestInBaseCurrency + (interest * (exchangeRateAtOrderDate  or  1)))
            elif (ga(order, "type") == 'LIABILITY'):
                liabilities = (ga(order, "quantity") * ga(order, "unitPrice"))
                totalLiabilities = (totalLiabilities + liabilities)
                totalLiabilitiesInBaseCurrency = (totalLiabilitiesInBaseCurrency + (liabilities * (exchangeRateAtOrderDate  or  1)))
            if (ga(order, "itemType") == 'start'):
                pass

            if ga(order, "fee"):
                pass


            unitPrice = (ga(order, "unitPrice") if (ga(order, "type") in ['BUY', 'SELL']) else ga(order, "unitPriceFromMarketData"))
            if unitPrice:
                pass


            marketPriceInBaseCurrency = ((ga(order, "unitPriceFromMarketData") * (currentExchangeRate  or  1))  or  Decimal(str(0)))
            marketPriceInBaseCurrencyWithCurrencyEffect = ((ga(order, "unitPriceFromMarketData") * (exchangeRateAtOrderDate  or  1))  or  Decimal(str(0)))
            valueOfInvestmentBeforeTransaction = (totalUnits * marketPriceInBaseCurrency)
            valueOfInvestmentBeforeTransactionWithCurrencyEffect = (totalUnits * marketPriceInBaseCurrencyWithCurrencyEffect)
            if (not investmentAtStartDate  and  (i >= indexOfStartOrder)):
                investmentAtStartDate = (totalInvestment  or  Decimal(str(0)))
                investmentAtStartDateWithCurrencyEffect = (totalInvestmentWithCurrencyEffect  or  Decimal(str(0)))
                valueAtStartDate = valueOfInvestmentBeforeTransaction
                valueAtStartDateWithCurrencyEffect = valueOfInvestmentBeforeTransactionWithCurrencyEffect
            transactionInvestment = Decimal(str(0))
            transactionInvestmentWithCurrencyEffect = Decimal(str(0))
            if (ga(order, "type") == 'BUY'):
                transactionInvestment = ((ga(order, "quantity") * ga(order, "unitPriceInBaseCurrency")) * get_factor(ga(order, "type")))
                transactionInvestmentWithCurrencyEffect = ((ga(order, "quantity") * ga(order, "unitPriceInBaseCurrencyWithCurrencyEffect")) * get_factor(ga(order, "type")))
                totalQuantityFromBuyTransactions = (totalQuantityFromBuyTransactions + ga(order, "quantity"))
                totalInvestmentFromBuyTransactions = (totalInvestmentFromBuyTransactions + transactionInvestment)
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = (totalInvestmentFromBuyTransactionsWithCurrencyEffect + transactionInvestmentWithCurrencyEffect)
            elif (ga(order, "type") == 'SELL'):
                if (totalUnits > 0):
                    transactionInvestment = (((totalInvestment / totalUnits) * ga(order, "quantity")) * get_factor(ga(order, "type")))
                    transactionInvestmentWithCurrencyEffect = (((totalInvestmentWithCurrencyEffect / totalUnits) * ga(order, "quantity")) * get_factor(ga(order, "type")))
            if ga(PortfolioCalculator, "ENABLE_LOGGING"):
                print.log('order.quantity', float(ga(order, "quantity")))
                print.log('transactionInvestment', float(transactionInvestment))
                print.log('transactionInvestmentWithCurrencyEffect', float(transactionInvestmentWithCurrencyEffect))
            totalInvestmentBeforeTransaction = totalInvestment
            totalInvestmentBeforeTransactionWithCurrencyEffect = totalInvestmentWithCurrencyEffect
            totalInvestment = (totalInvestment + transactionInvestment)
            totalInvestmentWithCurrencyEffect = (totalInvestmentWithCurrencyEffect + transactionInvestmentWithCurrencyEffect)
            if ((i >= indexOfStartOrder)  and  not initialValue):
                if ((i == indexOfStartOrder)  and  not (valueOfInvestmentBeforeTransaction == 0)):
                    initialValue = valueOfInvestmentBeforeTransaction
                    initialValueWithCurrencyEffect = valueOfInvestmentBeforeTransactionWithCurrencyEffect
                elif (transactionInvestment > 0):
                    initialValue = transactionInvestment
                    initialValueWithCurrencyEffect = transactionInvestmentWithCurrencyEffect
            fees = (fees + (ga(order, "feeInBaseCurrency")  or  0))
            feesWithCurrencyEffect = (feesWithCurrencyEffect + (ga(order, "feeInBaseCurrencyWithCurrencyEffect")  or  0))
            totalUnits = (totalUnits + (ga(order, "quantity") * get_factor(ga(order, "type"))))
            valueOfInvestment = (totalUnits * marketPriceInBaseCurrency)
            valueOfInvestmentWithCurrencyEffect = (totalUnits * marketPriceInBaseCurrencyWithCurrencyEffect)
            grossPerformanceFromSell = (((ga(order, "unitPriceInBaseCurrency") - lastAveragePrice) * ga(order, "quantity")) if (ga(order, "type") == 'SELL') else Decimal(str(0)))
            grossPerformanceFromSellWithCurrencyEffect = (((ga(order, "unitPriceInBaseCurrencyWithCurrencyEffect") - lastAveragePriceWithCurrencyEffect) * ga(order, "quantity")) if (ga(order, "type") == 'SELL') else Decimal(str(0)))
            grossPerformanceFromSells = (grossPerformanceFromSells + grossPerformanceFromSell)
            grossPerformanceFromSellsWithCurrencyEffect = (grossPerformanceFromSellsWithCurrencyEffect + grossPerformanceFromSellWithCurrencyEffect)
            lastAveragePrice = (Decimal(str(0)) if (totalQuantityFromBuyTransactions == 0) else (totalInvestmentFromBuyTransactions / totalQuantityFromBuyTransactions))
            lastAveragePriceWithCurrencyEffect = (Decimal(str(0)) if (totalQuantityFromBuyTransactions == 0) else (totalInvestmentFromBuyTransactionsWithCurrencyEffect / totalQuantityFromBuyTransactions))
            if (totalUnits == 0):
                totalInvestmentFromBuyTransactions = Decimal(str(0))
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = Decimal(str(0))
                totalQuantityFromBuyTransactions = Decimal(str(0))
            if ga(PortfolioCalculator, "ENABLE_LOGGING"):
                print.log('grossPerformanceFromSells', float(grossPerformanceFromSells))
                print.log('grossPerformanceFromSellWithCurrencyEffect', float(grossPerformanceFromSellWithCurrencyEffect))
            newGrossPerformance = ((valueOfInvestment - totalInvestment) + grossPerformanceFromSells)
            newGrossPerformanceWithCurrencyEffect = ((valueOfInvestmentWithCurrencyEffect - totalInvestmentWithCurrencyEffect) + grossPerformanceFromSellsWithCurrencyEffect)
            grossPerformance = newGrossPerformance
            grossPerformanceWithCurrencyEffect = newGrossPerformanceWithCurrencyEffect
            if (ga(order, "itemType") == 'start'):
                feesAtStartDate = fees
                feesAtStartDateWithCurrencyEffect = feesWithCurrencyEffect
                grossPerformanceAtStartDate = grossPerformance
                grossPerformanceAtStartDateWithCurrencyEffect = grossPerformanceWithCurrencyEffect
            if (i > indexOfStartOrder):
                if ((valueOfInvestmentBeforeTransaction > 0)  and  (ga(order, "type") in ['BUY', 'SELL'])):
                    orderDate = _parse_date(ga(order, "date"))
                    previousOrderDate = _parse_date(ga(ga(orders, (i - 1)), "date"))
                    daysSinceLastOrder = difference_in_days(orderDate, previousOrderDate)
                    if (daysSinceLastOrder <= 0):
                        daysSinceLastOrder = float_info.epsilon
                    totalInvestmentDays += daysSinceLastOrder
                    sumOfTimeWeightedInvestments = (sumOfTimeWeightedInvestments + (((valueAtStartDate - investmentAtStartDate) + totalInvestmentBeforeTransaction) * daysSinceLastOrder))
                    sumOfTimeWeightedInvestmentsWithCurrencyEffect = (sumOfTimeWeightedInvestmentsWithCurrencyEffect + (((valueAtStartDateWithCurrencyEffect - investmentAtStartDateWithCurrencyEffect) + totalInvestmentBeforeTransactionWithCurrencyEffect) * daysSinceLastOrder))









            if ga(PortfolioCalculator, "ENABLE_LOGGING"):
                print.log('totalInvestment', float(totalInvestment))
                print.log('totalInvestmentWithCurrencyEffect', float(totalInvestmentWithCurrencyEffect))
                print.log('totalGrossPerformance', float((grossPerformance - grossPerformanceAtStartDate)))
                print.log('totalGrossPerformanceWithCurrencyEffect', float((grossPerformanceWithCurrencyEffect - grossPerformanceAtStartDateWithCurrencyEffect)))
            if (i == indexOfEndOrder):
                break
        totalGrossPerformance = (grossPerformance - grossPerformanceAtStartDate)
        totalGrossPerformanceWithCurrencyEffect = (grossPerformanceWithCurrencyEffect - grossPerformanceAtStartDateWithCurrencyEffect)
        totalNetPerformance = ((grossPerformance - grossPerformanceAtStartDate) - (fees - feesAtStartDate))
        timeWeightedAverageInvestmentBetweenStartAndEndDate = ((sumOfTimeWeightedInvestments / totalInvestmentDays) if (totalInvestmentDays > 0) else Decimal(str(0)))
        timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect = ((sumOfTimeWeightedInvestmentsWithCurrencyEffect / totalInvestmentDays) if (totalInvestmentDays > 0) else Decimal(str(0)))
        grossPerformancePercentage = ((totalGrossPerformance / timeWeightedAverageInvestmentBetweenStartAndEndDate) if (timeWeightedAverageInvestmentBetweenStartAndEndDate > 0) else Decimal(str(0)))
        grossPerformancePercentageWithCurrencyEffect = ((totalGrossPerformanceWithCurrencyEffect / timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect) if (timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect > 0) else Decimal(str(0)))
        feesPerUnit = (((fees - feesAtStartDate) / totalUnits) if (totalUnits > 0) else Decimal(str(0)))
        feesPerUnitWithCurrencyEffect = (((feesWithCurrencyEffect - feesAtStartDateWithCurrencyEffect) / totalUnits) if (totalUnits > 0) else Decimal(str(0)))
        netPerformancePercentage = ((totalNetPerformance / timeWeightedAverageInvestmentBetweenStartAndEndDate) if (timeWeightedAverageInvestmentBetweenStartAndEndDate > 0) else Decimal(str(0)))
        netPerformancePercentageWithCurrencyEffectMap = {}
        netPerformanceWithCurrencyEffectMap = {}
        for dateRange in ['1d', '1y', '5y', 'max', 'mtd', 'wtd', 'ytd']:
            dateInterval = get_interval_from_date_range(dateRange)
            endDate = ga(dateInterval, "endDate")
            startDate = ga(dateInterval, "startDate")
            if is_before(startDate, start):
                startDate = start
            rangeEndDateString = date_format(endDate, DATE_FORMAT)
            rangeStartDateString = date_format(startDate, DATE_FORMAT)
            currentValuesAtDateRangeStartWithCurrencyEffect = (ga(currentValuesWithCurrencyEffect, rangeStartDateString)  or  Decimal(str(0)))
            investmentValuesAccumulatedAtStartDateWithCurrencyEffect = (ga(investmentValuesAccumulatedWithCurrencyEffect, rangeStartDateString)  or  Decimal(str(0)))
            grossPerformanceAtDateRangeStartWithCurrencyEffect = (currentValuesAtDateRangeStartWithCurrencyEffect - investmentValuesAccumulatedAtStartDateWithCurrencyEffect)
            average = Decimal(str(0))
            dayCount = 0
            i = (len(self.chart_dates) - 1)
            while (i >= 0):
                date = self.chart_dates[i]
                if (date > rangeEndDateString):
                    continue
                elif (date < rangeStartDateString):
                    break
                if (isinstance(ga(investmentValuesAccumulatedWithCurrencyEffect, date), Big)  and  (ga(investmentValuesAccumulatedWithCurrencyEffect, date) > 0)):
                    average = (average + (ga(investmentValuesAccumulatedWithCurrencyEffect, date) + grossPerformanceAtDateRangeStartWithCurrencyEffect))
                    dayCount += 1
                i -= 1
            if (dayCount > 0):
                average = (average / dayCount)


        if ga(PortfolioCalculator, "ENABLE_LOGGING"):
            pass

        {symbol}












        return {
            'currentValues': currentValues,
            'currentValuesWithCurrencyEffect': currentValuesWithCurrencyEffect,
            'feesWithCurrencyEffect': feesWithCurrencyEffect,
            'grossPerformancePercentage': grossPerformancePercentage,
            'grossPerformancePercentageWithCurrencyEffect': grossPerformancePercentageWithCurrencyEffect,
            'initialValue': initialValue,
            'initialValueWithCurrencyEffect': initialValueWithCurrencyEffect,
            'investmentValuesAccumulated': investmentValuesAccumulated,
            'investmentValuesAccumulatedWithCurrencyEffect': investmentValuesAccumulatedWithCurrencyEffect,
            'investmentValuesWithCurrencyEffect': investmentValuesWithCurrencyEffect,
            'netPerformancePercentage': netPerformancePercentage,
            'netPerformancePercentageWithCurrencyEffectMap': netPerformancePercentageWithCurrencyEffectMap,
            'netPerformanceValues': netPerformanceValues,
            'netPerformanceValuesWithCurrencyEffect': netPerformanceValuesWithCurrencyEffect,
            'netPerformanceWithCurrencyEffectMap': netPerformanceWithCurrencyEffectMap,
            'timeWeightedInvestmentValues': timeWeightedInvestmentValues,
            'timeWeightedInvestmentValuesWithCurrencyEffect': timeWeightedInvestmentValuesWithCurrencyEffect,
            'totalAccountBalanceInBaseCurrency': totalAccountBalanceInBaseCurrency,
            'totalDividend': totalDividend,
            'totalDividendInBaseCurrency': totalDividendInBaseCurrency,
            'totalInterest': totalInterest,
            'totalInterestInBaseCurrency': totalInterestInBaseCurrency,
            'totalInvestment': totalInvestment,
            'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect,
            'totalLiabilities': totalLiabilities,
            'totalLiabilitiesInBaseCurrency': totalLiabilitiesInBaseCurrency,
            'grossPerformance': totalGrossPerformance,
            'grossPerformanceWithCurrencyEffect': totalGrossPerformanceWithCurrencyEffect,
            'hasErrors': ((totalUnits > 0)  and  (not initialValue  or  not unitPriceAtEndDate)),
            'netPerformance': totalNetPerformance,
            'timeWeightedInvestment': timeWeightedAverageInvestmentBetweenStartAndEndDate,
            'timeWeightedInvestmentWithCurrencyEffect': timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect
        }


    def compute_snapshot(self):
        if not hasattr(self, 'transaction_points'):
            self.compute_transaction_points()

        lastTransactionPoint = self.transaction_points[-1]
        transactionPoints = [x for x in self.transaction_points if is_before(parse_date(x.get('date')), self.end_date)]
        if not len(transactionPoints):
            return {
                'activitiesCount': 0,
                'createdAt': datetime.now(),
                'currentValueInBaseCurrency': Decimal(str(0)),
                'errors': [],
                'hasErrors': False,
                'historicalData': [],
                'positions': [],
                'totalFeesWithCurrencyEffect': Decimal(str(0)),
                'totalInterestWithCurrencyEffect': Decimal(str(0)),
                'totalInvestment': Decimal(str(0)),
                'totalInvestmentWithCurrencyEffect': Decimal(str(0)),
                'totalLiabilitiesWithCurrencyEffect': Decimal(str(0))
            }
        currencies = {}
        dataGatheringItems = []
        firstIndex = len(transactionPoints)
        firstTransactionPoint = None
        totalInterestWithCurrencyEffect = Decimal(str(0))
        totalLiabilitiesWithCurrencyEffect = Decimal(str(0))
        for _item in ga(ga(transactionPoints, (firstIndex - 1)), "items"):
            gactx.item = _item
            assetSubClass = ga(_item, 'assetSubClass')
            currency = ga(_item, 'currency')
            dataSource = ga(_item, 'dataSource')
            symbol = ga(_item, 'symbol')
            if (assetSubClass != 'CASH'):
                dataGatheringItems.append({'dataSource': dataSource, 'symbol': symbol})

        for i in range(len(transactionPoints)):
            if (not is_before(parse_date(ga(ga(transactionPoints, i), "date")), self.start_date)  and  (firstTransactionPoint == None)):
                firstTransactionPoint = ga(transactionPoints, i)
                firstIndex = i
        exchangeRatesByCurrency = self.exchange_rate_data_service.get_exchange_rates_by_currency({

            'endDate': self.end_date,
            'startDate': self.start_date,
            'targetCurrency': self.currency
        })
        dataProviderInfos, currentRateErrors, marketSymbols = self.current_rate_service.get_values({'dataGatheringItems': dataGatheringItems, 'dateQuery': {'gte': self.start_date, 'lt': self.end_date}})
        self.data_provider_infos = dataProviderInfos
        marketSymbolMap = {}
        for marketSymbol in marketSymbols:
            date = date_format(ga(marketSymbol, "date"), DATE_FORMAT)
            if not ga(marketSymbolMap, date):
                pass

            if ga(marketSymbol, "marketPrice"):
                pass

        endDateString = date_format(self.end_date, DATE_FORMAT)
        daysInMarket = difference_in_days(self.end_date, self.start_date)
        chartDateMap = self.get_chart_date_map({'endDate': self.end_date, 'startDate': self.start_date, 'step': Math.round((daysInMarket / date_min(daysInMarket, self.configuration_service.get('MAX_CHART_ITEMS'))))})
        for accountBalanceItem in self.account_balance_items:
            pass

        chartDates = sort_by(list(chartDateMap.keys()), lambda chartDate: chartDate)
        if (firstIndex > 0):
            firstIndex -= 1
        errors = []
        hasAnySymbolMetricsErrors = False
        positions = []
        accumulatedValuesByDate = {}
        valuesBySymbol = {}
        for item in ga(lastTransactionPoint, "items"):
            marketPriceInBaseCurrency = ((ga(ga(marketSymbolMap, endDateString), ga(item, "symbol"))  or  ga(item, "averagePrice")) * (ga(ga(exchangeRatesByCurrency, f"{ga(item, "currency")}{self.currency}"), endDateString)  or  1))
            currentValues, currentValuesWithCurrencyEffect, grossPerformance, grossPerformancePercentage, grossPerformancePercentageWithCurrencyEffect, grossPerformanceWithCurrencyEffect, hasErrors, investmentValuesAccumulated, investmentValuesAccumulatedWithCurrencyEffect, investmentValuesWithCurrencyEffect, netPerformance, netPerformancePercentage, netPerformancePercentageWithCurrencyEffectMap, netPerformanceValues, netPerformanceValuesWithCurrencyEffect, netPerformanceWithCurrencyEffectMap, timeWeightedInvestment, timeWeightedInvestmentValues, timeWeightedInvestmentValuesWithCurrencyEffect, timeWeightedInvestmentWithCurrencyEffect, totalDividend, totalDividendInBaseCurrency, totalInterestInBaseCurrency, totalInvestment, totalInvestmentWithCurrencyEffect, totalLiabilitiesInBaseCurrency = self.get_symbol_metrics({
                'chartDateMap': chartDateMap,
                'marketSymbolMap': marketSymbolMap,
                'dataSource': ga(item, "dataSource"),
                'end': self.end_date,
                'exchangeRates': ga(exchangeRatesByCurrency, f"{ga(item, "currency")}{self.currency}"),
                'start': self.start_date,
                'symbol': ga(item, "symbol")
            })
            hasAnySymbolMetricsErrors = (hasAnySymbolMetricsErrors  or  hasErrors)
            includeInTotalAssetValue = (ga(item, "assetSubClass") != ga(AssetSubClass, "CASH"))
            if includeInTotalAssetValue:
                pass











            positions.append({
                'includeInTotalAssetValue': includeInTotalAssetValue,
                'timeWeightedInvestment': timeWeightedInvestment,
                'timeWeightedInvestmentWithCurrencyEffect': timeWeightedInvestmentWithCurrencyEffect,
                'activitiesCount': ga(item, "activitiesCount"),
                'averagePrice': ga(item, "averagePrice"),
                'currency': ga(item, "currency"),
                'dataSource': ga(item, "dataSource"),
                'dateOfFirstActivity': ga(item, "dateOfFirstActivity"),
                'dividend': totalDividend,
                'dividendInBaseCurrency': totalDividendInBaseCurrency,
                'fee': ga(item, "fee"),
                'feeInBaseCurrency': ga(item, "feeInBaseCurrency"),
                'grossPerformance': ((grossPerformance  or  None) if not hasErrors else None),
                'grossPerformancePercentage': ((grossPerformancePercentage  or  None) if not hasErrors else None),
                'grossPerformancePercentageWithCurrencyEffect': ((grossPerformancePercentageWithCurrencyEffect  or  None) if not hasErrors else None),
                'grossPerformanceWithCurrencyEffect': ((grossPerformanceWithCurrencyEffect  or  None) if not hasErrors else None),
                'includeInHoldings': ga(item, "includeInHoldings"),
                'investment': totalInvestment,
                'investmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect,
                'marketPrice': (float(ga(ga(marketSymbolMap, endDateString), ga(item, "symbol")))  or  1),
                'marketPriceInBaseCurrency': (float(marketPriceInBaseCurrency)  or  1),
                'netPerformance': ((netPerformance  or  None) if not hasErrors else None),
                'netPerformancePercentage': ((netPerformancePercentage  or  None) if not hasErrors else None),
                'netPerformancePercentageWithCurrencyEffectMap': ((netPerformancePercentageWithCurrencyEffectMap  or  None) if not hasErrors else None),
                'netPerformanceWithCurrencyEffectMap': ((netPerformanceWithCurrencyEffectMap  or  None) if not hasErrors else None),
                'quantity': ga(item, "quantity"),
                'symbol': ga(item, "symbol"),
                'tags': ga(item, "tags"),
                'valueInBaseCurrency': (Decimal(str(marketPriceInBaseCurrency)) * ga(item, "quantity"))
            })
            totalInterestWithCurrencyEffect = (totalInterestWithCurrencyEffect + totalInterestInBaseCurrency)
            totalLiabilitiesWithCurrencyEffect = (totalLiabilitiesWithCurrencyEffect + totalLiabilitiesInBaseCurrency)
            if (((hasErrors  or  next((x for x in currentRateErrors if ((x.get('dataSource') == ga(item, "dataSource"))  and  (x.get('symbol') == ga(item, "symbol")))), None))  and  (ga(item, "investment") > 0))  and  (ga(item, "skipErrors") == False)):
                errors.append({'dataSource': ga(item, "dataSource"), 'symbol': ga(item, "symbol")})

        accountBalanceMap = {}
        lastKnownBalance = Decimal(str(0))
        for dateString in chartDates:
            if (ga(accountBalanceItemsMap, dateString) != None):
                lastKnownBalance = ga(accountBalanceItemsMap, dateString)

            for symbol in list(valuesBySymbol.keys()):
                symbolValues = ga(valuesBySymbol, symbol)
                currentValue = (ga(ga(symbolValues, "currentValues"), dateString)  or  Decimal(str(0)))
                currentValueWithCurrencyEffect = (ga(ga(symbolValues, "currentValuesWithCurrencyEffect"), dateString)  or  Decimal(str(0)))
                investmentValueAccumulated = (ga(ga(symbolValues, "investmentValuesAccumulated"), dateString)  or  Decimal(str(0)))
                investmentValueAccumulatedWithCurrencyEffect = (ga(ga(symbolValues, "investmentValuesAccumulatedWithCurrencyEffect"), dateString)  or  Decimal(str(0)))
                investmentValueWithCurrencyEffect = (ga(ga(symbolValues, "investmentValuesWithCurrencyEffect"), dateString)  or  Decimal(str(0)))
                netPerformanceValue = (ga(ga(symbolValues, "netPerformanceValues"), dateString)  or  Decimal(str(0)))
                netPerformanceValueWithCurrencyEffect = (ga(ga(symbolValues, "netPerformanceValuesWithCurrencyEffect"), dateString)  or  Decimal(str(0)))
                timeWeightedInvestmentValue = (ga(ga(symbolValues, "timeWeightedInvestmentValues"), dateString)  or  Decimal(str(0)))
                timeWeightedInvestmentValueWithCurrencyEffect = (ga(ga(symbolValues, "timeWeightedInvestmentValuesWithCurrencyEffect"), dateString)  or  Decimal(str(0)))













        overall = self.calculate_overall_performance(positions)
        positionsIncludedInHoldings = [rest for x in [x for x in positions if x.get('includeInHoldings')]]
        return {
            **overall,
            'errors': errors,
            'historicalData': historicalData,
            'totalInterestWithCurrencyEffect': totalInterestWithCurrencyEffect,
            'totalLiabilitiesWithCurrencyEffect': totalLiabilitiesWithCurrencyEffect,
            'hasErrors': (hasAnySymbolMetricsErrors  or  ga(overall, "hasErrors")),
            'positions': positionsIncludedInHoldings
        }



    def get_investments_by_group(self, data, groupBy):
        groupedData = {}
        for _item in data:
            gactx.item = _item
            date = ga(_item, 'date')
            investmentValueWithCurrencyEffect = ga(_item, 'investmentValueWithCurrencyEffect')
            dateGroup = (date[0:7] if (groupBy == 'month') else date[0:4])

        return [{'date': (f"{x}-01" if (groupBy == 'month') else f"{x}-01-01"), 'investment': float(ga(groupedData, x))} for x in list(groupedData.keys())]



    def get_snapshot(self):
        self.snapshot_promise
        return self.snapshot



    def get_start_date(self):
        firstAccountBalanceDate = None
        firstActivityDate = None
        try:
            firstAccountBalanceDateString = self.account_balance_items[0].date
            firstAccountBalanceDate = (parse_date(firstAccountBalanceDateString) if firstAccountBalanceDateString else datetime.now())
        except Exception as error:
            firstAccountBalanceDate = datetime.now()
        try:
            firstActivityDateString = self.transaction_points[0].date
            firstActivityDate = (parse_date(firstActivityDateString) if firstActivityDateString else datetime.now())
        except Exception as error:
            firstActivityDate = datetime.now()
        return date_min([firstAccountBalanceDate, firstActivityDate])



    def get_transaction_points(self):
        return self.transaction_points



    def get_chart_date_map(self, endDate, startDate, step):

        for date in each_day_of_interval({'end': endDate, 'start': startDate}, {'step': step}):
            pass

        if (step > 1):
            for date in each_day_of_interval({'end': endDate, 'start': sub_days(endDate, 90)}, {'step': 3}):
                pass

            for date in each_day_of_interval({'end': endDate, 'start': sub_days(endDate, 30)}, {'step': 1}):
                pass


        for dateRange in ['1d', '1y', '5y', 'max', 'mtd', 'wtd', 'ytd']:
            dateRangeEnd, dateRangeStart = get_interval_from_date_range(dateRange)
            if (not is_before(dateRangeStart, startDate)  and  not is_after(dateRangeStart, endDate)):
                pass

            if (not is_before(dateRangeEnd, startDate)  and  not is_after(dateRangeEnd, endDate)):
                pass

        interval = {'start': startDate, 'end': endDate}
        for date in each_year_of_interval(interval):
            yearStart = start_of_year(date)
            yearEnd = end_of_year(date)
            if is_within_interval(yearStart, interval):
                pass

            if is_within_interval(yearEnd, interval):
                pass

        return chartDateMap



    def compute_transaction_points(self):
        self.transaction_points = []
        symbols = {}
        lastDate = None
        lastTransactionPoint = None
        for _item in self.activities:
            gactx.item = _item
            date = ga(_item, 'date')
            fee = ga(_item, 'fee')
            feeInBaseCurrency = ga(_item, 'feeInBaseCurrency')
            quantity = ga(_item, 'quantity')
            SymbolProfile = ga(_item, 'SymbolProfile')
            tags = ga(_item, 'tags')
            type = ga(_item, 'type')
            unitPrice = ga(_item, 'unitPrice')
            currentTransactionPointItem = None
            assetSubClass = ga(SymbolProfile, "assetSubClass")
            currency = ga(SymbolProfile, "currency")
            dataSource = ga(SymbolProfile, "dataSource")
            factor = get_factor(type)
            skipErrors = not not ga(SymbolProfile, "userId")
            symbol = ga(SymbolProfile, "symbol")
            oldAccumulatedSymbol = ga(symbols, symbol)
            if oldAccumulatedSymbol:
                investment = ga(oldAccumulatedSymbol, "investment")
                newQuantity = ((quantity * factor) + ga(oldAccumulatedSymbol, "quantity"))
                if (type == 'BUY'):
                    if (ga(oldAccumulatedSymbol, "investment") >= 0):
                        investment = (ga(oldAccumulatedSymbol, "investment") + (quantity * unitPrice))
                    else:
                        investment = (ga(oldAccumulatedSymbol, "investment") + (quantity * ga(oldAccumulatedSymbol, "averagePrice")))
                elif (type == 'SELL'):
                    if (ga(oldAccumulatedSymbol, "investment") > 0):
                        investment = (ga(oldAccumulatedSymbol, "investment") - (quantity * ga(oldAccumulatedSymbol, "averagePrice")))
                    else:
                        investment = (ga(oldAccumulatedSymbol, "investment") - (quantity * unitPrice))
                if (abs(newQuantity) < float_info.epsilon):
                    investment = Decimal(str(0))
                    newQuantity = Decimal(str(0))
                currentTransactionPointItem = {
                    'assetSubClass': assetSubClass,
                    'currency': currency,
                    'dataSource': dataSource,
                    'investment': investment,
                    'skipErrors': skipErrors,
                    'symbol': symbol,
                    'activitiesCount': (ga(oldAccumulatedSymbol, "activitiesCount") + 1),
                    'averagePrice': (Decimal(str(0)) if (newQuantity == 0) else abs((investment / newQuantity))),
                    'dateOfFirstActivity': ga(oldAccumulatedSymbol, "dateOfFirstActivity"),
                    'dividend': Decimal(str(0)),
                    'fee': (ga(oldAccumulatedSymbol, "fee") + fee),
                    'feeInBaseCurrency': (ga(oldAccumulatedSymbol, "feeInBaseCurrency") + feeInBaseCurrency),
                    'includeInHoldings': ga(oldAccumulatedSymbol, "includeInHoldings"),
                    'quantity': newQuantity,
                    'tags': [*ga(oldAccumulatedSymbol, "tags"), *tags]
                }
            else:
                currentTransactionPointItem = {
                    'assetSubClass': assetSubClass,
                    'currency': currency,
                    'dataSource': dataSource,
                    'fee': fee,
                    'feeInBaseCurrency': feeInBaseCurrency,
                    'skipErrors': skipErrors,
                    'symbol': symbol,
                    'tags': tags,
                    'activitiesCount': 1,
                    'averagePrice': unitPrice,
                    'dateOfFirstActivity': date,
                    'dividend': Decimal(str(0)),
                    'includeInHoldings': (type in ['BUY', 'DIVIDEND', 'SELL']),
                    'investment': ((unitPrice * quantity) * factor),
                    'quantity': (quantity * factor)
                }


            items = (ga(lastTransactionPoint, "items")  or  [])
            newItems = [x for x in items if (x.get('symbol') != ga(SymbolProfile, "symbol"))]
            newItems.append(currentTransactionPointItem)
            sorted(newItems, key=functools.cmp_to_key(lambda a, b: ((ga(a, "symbol") > ga(b, "symbol")) - (ga(a, "symbol") < ga(b, "symbol")))))
            fees = Decimal(str(0))
            if (type == 'FEE'):
                fees = fee
            interest = Decimal(str(0))
            if (type == 'INTEREST'):
                interest = (quantity * unitPrice)
            liabilities = Decimal(str(0))
            if (type == 'LIABILITY'):
                liabilities = (quantity * unitPrice)
            if ((lastDate != date)  or  (lastTransactionPoint == None)):
                lastTransactionPoint = {
                    'date': date,
                    'fees': fees,
                    'interest': interest,
                    'liabilities': liabilities,
                    'items': newItems
                }
                self.transaction_points.append(lastTransactionPoint)
            else:
                pass




            lastDate = date

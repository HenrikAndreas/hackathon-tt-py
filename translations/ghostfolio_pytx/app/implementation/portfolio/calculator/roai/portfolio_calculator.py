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
            if _ga(currentPosition, "feeInBaseCurrency"):
                totalFeesWithCurrencyEffect = (totalFeesWithCurrencyEffect + _ga(currentPosition, "feeInBaseCurrency"))
            if _ga(currentPosition, "valueInBaseCurrency"):
                currentValueInBaseCurrency = (currentValueInBaseCurrency + _ga(currentPosition, "valueInBaseCurrency"))
            else:
                hasErrors = True
            if _ga(currentPosition, "investment"):
                totalInvestment = (totalInvestment + _ga(currentPosition, "investment"))
                totalInvestmentWithCurrencyEffect = (totalInvestmentWithCurrencyEffect + _ga(currentPosition, "investmentWithCurrencyEffect"))
            else:
                hasErrors = True
            if _ga(currentPosition, "grossPerformance"):
                grossPerformance = (grossPerformance + _ga(currentPosition, "grossPerformance"))
                grossPerformanceWithCurrencyEffect = (grossPerformanceWithCurrencyEffect + _ga(currentPosition, "grossPerformanceWithCurrencyEffect"))
                netPerformance = (netPerformance + _ga(currentPosition, "netPerformance"))
            elif not (_ga(currentPosition, "quantity") == 0):
                hasErrors = True
            if _ga(currentPosition, "timeWeightedInvestment"):
                totalTimeWeightedInvestment = (totalTimeWeightedInvestment + _ga(currentPosition, "timeWeightedInvestment"))
                totalTimeWeightedInvestmentWithCurrencyEffect = (totalTimeWeightedInvestmentWithCurrencyEffect + _ga(currentPosition, "timeWeightedInvestmentWithCurrencyEffect"))
            elif not (_ga(currentPosition, "quantity") == 0):
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
        return "ROAI"


    def get_symbol_metrics(self, chartDateMap, dataSource, end, exchangeRates, marketSymbolMap, start, symbol):
        currentExchangeRate = exchangeRates[_date_format(datetime.now(), DATE_FORMAT)]
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
        orders = copy.deepcopy([x for x in self.activities if (_ga(x.get('SymbolProfile'), "symbol") == symbol)])
        isCash = (_ga(_ga(orders[0], "SymbolProfile"), "assetSubClass") == 'CASH')
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
        dateOfFirstTransaction = _parse_date(_ga(orders[0], "date"))
        endDateString = _date_format(end, DATE_FORMAT)
        startDateString = _date_format(start, DATE_FORMAT)
        unitPriceAtStartDate = marketSymbolMap[startDateString][symbol]
        unitPriceAtEndDate = marketSymbolMap[endDateString][symbol]
        latestActivity = orders[-1]
        if ((((dataSource == 'MANUAL')  and  (_ga(latestActivity, "type") in ['BUY', 'SELL']))  and  _ga(latestActivity, "unitPrice"))  and  not unitPriceAtEndDate):
            unitPriceAtEndDate = _ga(latestActivity, "unitPrice")
        elif isCash:
            unitPriceAtEndDate = Decimal(str(1))
        if (not unitPriceAtEndDate  or  (not unitPriceAtStartDate  and  _is_before(dateOfFirstTransaction, start))):
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
            ordersByDate[_ga(order, "date")] = (ordersByDate[_ga(order, "date")]  or  [])
            ordersByDate[_ga(order, "date")].append(order)
        if not self.chart_dates:
            self.chart_dates = sorted(list(chartDateMap.keys()))
        for dateString in self.chart_dates:
            if (dateString < startDateString):
                continue
            elif (dateString > endDateString):
                break
            if (len(ordersByDate[dateString]) > 0):
                for order in ordersByDate[dateString]:
                    pass

            else:
                orders.append({
                    'date': dateString,
                    'fee': Decimal(str(0)),
                    'feeInBaseCurrency': Decimal(str(0)),
                    'quantity': Decimal(str(0)),
                    'SymbolProfile': {'dataSource': dataSource, 'symbol': symbol, 'assetSubClass': ('CASH' if isCash else None)},
                    'type': 'BUY',
                    'unitPrice': (marketSymbolMap[dateString][symbol]  or  lastUnitPrice),
                    'unitPriceFromMarketData': (marketSymbolMap[dateString][symbol]  or  lastUnitPrice)
                })
            latestActivity = orders[-1]
            lastUnitPrice = (_ga(latestActivity, "unitPriceFromMarketData")  or  _ga(latestActivity, "unitPrice"))

        indexOfStartOrder = next((i for i, x in enumerate(orders) if (x.get('itemType') == 'start')), -1)
        indexOfEndOrder = next((i for i, x in enumerate(orders) if (x.get('itemType') == 'end')), -1)
        totalInvestmentDays = 0
        sumOfTimeWeightedInvestments = Decimal(str(0))
        sumOfTimeWeightedInvestmentsWithCurrencyEffect = Decimal(str(0))
        for i in range(len(orders)):
            order = orders[i]
            if PortfolioCalculator.ENABLE_LOGGING:
                print.log()
                print.log()
                print.log((i + 1), _ga(order, "date"), _ga(order, "type"), (f"({_ga(order, "itemType")})" if _ga(order, "itemType") else ''))
            exchangeRateAtOrderDate = exchangeRates[_ga(order, "date")]
            if (_ga(order, "type") == 'DIVIDEND'):
                dividend = (_ga(order, "quantity") * _ga(order, "unitPrice"))
                totalDividend = (totalDividend + dividend)
                totalDividendInBaseCurrency = (totalDividendInBaseCurrency + (dividend * (exchangeRateAtOrderDate  or  1)))
            elif (_ga(order, "type") == 'INTEREST'):
                interest = (_ga(order, "quantity") * _ga(order, "unitPrice"))
                totalInterest = (totalInterest + interest)
                totalInterestInBaseCurrency = (totalInterestInBaseCurrency + (interest * (exchangeRateAtOrderDate  or  1)))
            elif (_ga(order, "type") == 'LIABILITY'):
                liabilities = (_ga(order, "quantity") * _ga(order, "unitPrice"))
                totalLiabilities = (totalLiabilities + liabilities)
                totalLiabilitiesInBaseCurrency = (totalLiabilitiesInBaseCurrency + (liabilities * (exchangeRateAtOrderDate  or  1)))
            if (_ga(order, "itemType") == 'start'):
                pass

            if _ga(order, "fee"):
                pass


            unitPrice = (_ga(order, "unitPrice") if (_ga(order, "type") in ['BUY', 'SELL']) else _ga(order, "unitPriceFromMarketData"))
            if unitPrice:
                pass


            marketPriceInBaseCurrency = ((_ga(order, "unitPriceFromMarketData") * (currentExchangeRate  or  1))  or  Decimal(str(0)))
            marketPriceInBaseCurrencyWithCurrencyEffect = ((_ga(order, "unitPriceFromMarketData") * (exchangeRateAtOrderDate  or  1))  or  Decimal(str(0)))
            valueOfInvestmentBeforeTransaction = (totalUnits * marketPriceInBaseCurrency)
            valueOfInvestmentBeforeTransactionWithCurrencyEffect = (totalUnits * marketPriceInBaseCurrencyWithCurrencyEffect)
            if (not investmentAtStartDate  and  (i >= indexOfStartOrder)):
                investmentAtStartDate = (totalInvestment  or  Decimal(str(0)))
                investmentAtStartDateWithCurrencyEffect = (totalInvestmentWithCurrencyEffect  or  Decimal(str(0)))
                valueAtStartDate = valueOfInvestmentBeforeTransaction
                valueAtStartDateWithCurrencyEffect = valueOfInvestmentBeforeTransactionWithCurrencyEffect
            transactionInvestment = Decimal(str(0))
            transactionInvestmentWithCurrencyEffect = Decimal(str(0))
            if (_ga(order, "type") == 'BUY'):
                transactionInvestment = ((_ga(order, "quantity") * _ga(order, "unitPriceInBaseCurrency")) * getFactor(_ga(order, "type")))
                transactionInvestmentWithCurrencyEffect = ((_ga(order, "quantity") * _ga(order, "unitPriceInBaseCurrencyWithCurrencyEffect")) * getFactor(_ga(order, "type")))
                totalQuantityFromBuyTransactions = (totalQuantityFromBuyTransactions + _ga(order, "quantity"))
                totalInvestmentFromBuyTransactions = (totalInvestmentFromBuyTransactions + transactionInvestment)
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = (totalInvestmentFromBuyTransactionsWithCurrencyEffect + transactionInvestmentWithCurrencyEffect)
            elif (_ga(order, "type") == 'SELL'):
                if (totalUnits > 0):
                    transactionInvestment = (((totalInvestment / totalUnits) * _ga(order, "quantity")) * getFactor(_ga(order, "type")))
                    transactionInvestmentWithCurrencyEffect = (((totalInvestmentWithCurrencyEffect / totalUnits) * _ga(order, "quantity")) * getFactor(_ga(order, "type")))
            if PortfolioCalculator.ENABLE_LOGGING:
                print.log('order.quantity', float(_ga(order, "quantity")))
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
            fees = (fees + (_ga(order, "feeInBaseCurrency")  or  0))
            feesWithCurrencyEffect = (feesWithCurrencyEffect + (_ga(order, "feeInBaseCurrencyWithCurrencyEffect")  or  0))
            totalUnits = (totalUnits + (_ga(order, "quantity") * getFactor(_ga(order, "type"))))
            valueOfInvestment = (totalUnits * marketPriceInBaseCurrency)
            valueOfInvestmentWithCurrencyEffect = (totalUnits * marketPriceInBaseCurrencyWithCurrencyEffect)
            grossPerformanceFromSell = (((_ga(order, "unitPriceInBaseCurrency") - lastAveragePrice) * _ga(order, "quantity")) if (_ga(order, "type") == 'SELL') else Decimal(str(0)))
            grossPerformanceFromSellWithCurrencyEffect = (((_ga(order, "unitPriceInBaseCurrencyWithCurrencyEffect") - lastAveragePriceWithCurrencyEffect) * _ga(order, "quantity")) if (_ga(order, "type") == 'SELL') else Decimal(str(0)))
            grossPerformanceFromSells = (grossPerformanceFromSells + grossPerformanceFromSell)
            grossPerformanceFromSellsWithCurrencyEffect = (grossPerformanceFromSellsWithCurrencyEffect + grossPerformanceFromSellWithCurrencyEffect)
            lastAveragePrice = (Decimal(str(0)) if (totalQuantityFromBuyTransactions == 0) else (totalInvestmentFromBuyTransactions / totalQuantityFromBuyTransactions))
            lastAveragePriceWithCurrencyEffect = (Decimal(str(0)) if (totalQuantityFromBuyTransactions == 0) else (totalInvestmentFromBuyTransactionsWithCurrencyEffect / totalQuantityFromBuyTransactions))
            if (totalUnits == 0):
                totalInvestmentFromBuyTransactions = Decimal(str(0))
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = Decimal(str(0))
                totalQuantityFromBuyTransactions = Decimal(str(0))
            if PortfolioCalculator.ENABLE_LOGGING:
                print.log('grossPerformanceFromSells', float(grossPerformanceFromSells))
                print.log('grossPerformanceFromSellWithCurrencyEffect', float(grossPerformanceFromSellWithCurrencyEffect))
            newGrossPerformance = ((valueOfInvestment - totalInvestment) + grossPerformanceFromSells)
            newGrossPerformanceWithCurrencyEffect = ((valueOfInvestmentWithCurrencyEffect - totalInvestmentWithCurrencyEffect) + grossPerformanceFromSellsWithCurrencyEffect)
            grossPerformance = newGrossPerformance
            grossPerformanceWithCurrencyEffect = newGrossPerformanceWithCurrencyEffect
            if (_ga(order, "itemType") == 'start'):
                feesAtStartDate = fees
                feesAtStartDateWithCurrencyEffect = feesWithCurrencyEffect
                grossPerformanceAtStartDate = grossPerformance
                grossPerformanceAtStartDateWithCurrencyEffect = grossPerformanceWithCurrencyEffect
            if (i > indexOfStartOrder):
                if ((valueOfInvestmentBeforeTransaction > 0)  and  (_ga(order, "type") in ['BUY', 'SELL'])):
                    orderDate = _parse_date(_ga(order, "date"))
                    previousOrderDate = _parse_date(_ga(orders[(i - 1)], "date"))
                    daysSinceLastOrder = _difference_in_days(orderDate, previousOrderDate)
                    if (daysSinceLastOrder <= 0):
                        daysSinceLastOrder = float_info.epsilon
                    totalInvestmentDays += daysSinceLastOrder
                    sumOfTimeWeightedInvestments = (sumOfTimeWeightedInvestments + (((valueAtStartDate - investmentAtStartDate) + totalInvestmentBeforeTransaction) * daysSinceLastOrder))
                    sumOfTimeWeightedInvestmentsWithCurrencyEffect = (sumOfTimeWeightedInvestmentsWithCurrencyEffect + (((valueAtStartDateWithCurrencyEffect - investmentAtStartDateWithCurrencyEffect) + totalInvestmentBeforeTransactionWithCurrencyEffect) * daysSinceLastOrder))
                currentValues[_ga(order, "date")] = valueOfInvestment
                currentValuesWithCurrencyEffect[_ga(order, "date")] = valueOfInvestmentWithCurrencyEffect
                netPerformanceValues[_ga(order, "date")] = ((grossPerformance - grossPerformanceAtStartDate) - (fees - feesAtStartDate))
                netPerformanceValuesWithCurrencyEffect[_ga(order, "date")] = ((grossPerformanceWithCurrencyEffect - grossPerformanceAtStartDateWithCurrencyEffect) - (feesWithCurrencyEffect - feesAtStartDateWithCurrencyEffect))
                investmentValuesAccumulated[_ga(order, "date")] = totalInvestment
                investmentValuesAccumulatedWithCurrencyEffect[_ga(order, "date")] = totalInvestmentWithCurrencyEffect
                investmentValuesWithCurrencyEffect[_ga(order, "date")] = ((investmentValuesWithCurrencyEffect[_ga(order, "date")]  or  Decimal(str(0))) + transactionInvestmentWithCurrencyEffect)
                timeWeightedInvestmentValues[_ga(order, "date")] = ((sumOfTimeWeightedInvestments / totalInvestmentDays) if (totalInvestmentDays > float_info.epsilon) else (totalInvestment if (totalInvestment > 0) else Decimal(str(0))))
                timeWeightedInvestmentValuesWithCurrencyEffect[_ga(order, "date")] = ((sumOfTimeWeightedInvestmentsWithCurrencyEffect / totalInvestmentDays) if (totalInvestmentDays > float_info.epsilon) else (totalInvestmentWithCurrencyEffect if (totalInvestmentWithCurrencyEffect > 0) else Decimal(str(0))))
            if PortfolioCalculator.ENABLE_LOGGING:
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
            dateInterval = getIntervalFromDateRange(dateRange)
            endDate = _ga(dateInterval, "endDate")
            startDate = _ga(dateInterval, "startDate")
            if _is_before(startDate, start):
                startDate = start
            rangeEndDateString = _date_format(endDate, DATE_FORMAT)
            rangeStartDateString = _date_format(startDate, DATE_FORMAT)
            currentValuesAtDateRangeStartWithCurrencyEffect = (currentValuesWithCurrencyEffect[rangeStartDateString]  or  Decimal(str(0)))
            investmentValuesAccumulatedAtStartDateWithCurrencyEffect = (investmentValuesAccumulatedWithCurrencyEffect[rangeStartDateString]  or  Decimal(str(0)))
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
                if (isinstance(investmentValuesAccumulatedWithCurrencyEffect[date], Big)  and  (investmentValuesAccumulatedWithCurrencyEffect[date] > 0)):
                    average = (average + (investmentValuesAccumulatedWithCurrencyEffect[date] + grossPerformanceAtDateRangeStartWithCurrencyEffect))
                    dayCount += 1
                i -= 1
            if (dayCount > 0):
                average = (average / dayCount)
            netPerformanceWithCurrencyEffectMap[dateRange] = ((netPerformanceValuesWithCurrencyEffect[rangeEndDateString] - (Decimal(str(0)) if (dateRange == 'max') else (netPerformanceValuesWithCurrencyEffect[rangeStartDateString]  or  Decimal(str(0)))))  or  Decimal(str(0)))
            netPerformancePercentageWithCurrencyEffectMap[dateRange] = ((netPerformanceWithCurrencyEffectMap[dateRange] / average) if (average > 0) else Decimal(str(0)))
        if PortfolioCalculator.ENABLE_LOGGING:
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
        transactionPoints = [x for x in self.transaction_points if _is_before(parseDate(x.get('date')), self.end_date)]
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
        for _item in _ga(transactionPoints[(firstIndex - 1)], "items"):
            assetSubClass = _item.get('assetSubClass') if isinstance(_item, dict) else getattr(_item, 'assetSubClass', None)
            currency = _item.get('currency') if isinstance(_item, dict) else getattr(_item, 'currency', None)
            dataSource = _item.get('dataSource') if isinstance(_item, dict) else getattr(_item, 'dataSource', None)
            symbol = _item.get('symbol') if isinstance(_item, dict) else getattr(_item, 'symbol', None)
            if (assetSubClass != 'CASH'):
                dataGatheringItems.append({'dataSource': dataSource, 'symbol': symbol})
            currencies[symbol] = currency
        for i in range(len(transactionPoints)):
            if (not _is_before(parseDate(_ga(transactionPoints[i], "date")), self.start_date)  and  (firstTransactionPoint == None)):
                firstTransactionPoint = transactionPoints[i]
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
            date = _date_format(_ga(marketSymbol, "date"), DATE_FORMAT)
            if not marketSymbolMap[date]:
                marketSymbolMap[date] = {}
            if _ga(marketSymbol, "marketPrice"):
                marketSymbolMap[date][_ga(marketSymbol, "symbol")] = Decimal(str(_ga(marketSymbol, "marketPrice")))
        endDateString = _date_format(self.end_date, DATE_FORMAT)
        daysInMarket = _difference_in_days(self.end_date, self.start_date)
        chartDateMap = self.get_chart_date_map({'endDate': self.end_date, 'startDate': self.start_date, 'step': Math.round((daysInMarket / _date_min(daysInMarket, self.configuration_service.get('MAX_CHART_ITEMS'))))})
        for accountBalanceItem in self.account_balance_items:
            chartDateMap[_ga(accountBalanceItem, "date")] = True
        chartDates = _sort_by(list(chartDateMap.keys()), lambda chartDate: chartDate)
        if (firstIndex > 0):
            firstIndex -= 1
        errors = []
        hasAnySymbolMetricsErrors = False
        positions = []
        accumulatedValuesByDate = {}
        valuesBySymbol = {}
        for item in _ga(lastTransactionPoint, "items"):
            marketPriceInBaseCurrency = ((marketSymbolMap[endDateString][_ga(item, "symbol")]  or  _ga(item, "averagePrice")) * (exchangeRatesByCurrency[f"{_ga(item, "currency")}{self.currency}"][endDateString]  or  1))
            currentValues, currentValuesWithCurrencyEffect, grossPerformance, grossPerformancePercentage, grossPerformancePercentageWithCurrencyEffect, grossPerformanceWithCurrencyEffect, hasErrors, investmentValuesAccumulated, investmentValuesAccumulatedWithCurrencyEffect, investmentValuesWithCurrencyEffect, netPerformance, netPerformancePercentage, netPerformancePercentageWithCurrencyEffectMap, netPerformanceValues, netPerformanceValuesWithCurrencyEffect, netPerformanceWithCurrencyEffectMap, timeWeightedInvestment, timeWeightedInvestmentValues, timeWeightedInvestmentValuesWithCurrencyEffect, timeWeightedInvestmentWithCurrencyEffect, totalDividend, totalDividendInBaseCurrency, totalInterestInBaseCurrency, totalInvestment, totalInvestmentWithCurrencyEffect, totalLiabilitiesInBaseCurrency = self.get_symbol_metrics({
                'chartDateMap': chartDateMap,
                'marketSymbolMap': marketSymbolMap,
                'dataSource': _ga(item, "dataSource"),
                'end': self.end_date,
                'exchangeRates': exchangeRatesByCurrency[f"{_ga(item, "currency")}{self.currency}"],
                'start': self.start_date,
                'symbol': _ga(item, "symbol")
            })
            hasAnySymbolMetricsErrors = (hasAnySymbolMetricsErrors  or  hasErrors)
            includeInTotalAssetValue = (_ga(item, "assetSubClass") != "CASH")
            if includeInTotalAssetValue:
                valuesBySymbol[_ga(item, "symbol")] = {
                    'currentValues': currentValues,
                    'currentValuesWithCurrencyEffect': currentValuesWithCurrencyEffect,
                    'investmentValuesAccumulated': investmentValuesAccumulated,
                    'investmentValuesAccumulatedWithCurrencyEffect': investmentValuesAccumulatedWithCurrencyEffect,
                    'investmentValuesWithCurrencyEffect': investmentValuesWithCurrencyEffect,
                    'netPerformanceValues': netPerformanceValues,
                    'netPerformanceValuesWithCurrencyEffect': netPerformanceValuesWithCurrencyEffect,
                    'timeWeightedInvestmentValues': timeWeightedInvestmentValues,
                    'timeWeightedInvestmentValuesWithCurrencyEffect': timeWeightedInvestmentValuesWithCurrencyEffect
                }
            positions.append({
                'includeInTotalAssetValue': includeInTotalAssetValue,
                'timeWeightedInvestment': timeWeightedInvestment,
                'timeWeightedInvestmentWithCurrencyEffect': timeWeightedInvestmentWithCurrencyEffect,
                'activitiesCount': _ga(item, "activitiesCount"),
                'averagePrice': _ga(item, "averagePrice"),
                'currency': _ga(item, "currency"),
                'dataSource': _ga(item, "dataSource"),
                'dateOfFirstActivity': _ga(item, "dateOfFirstActivity"),
                'dividend': totalDividend,
                'dividendInBaseCurrency': totalDividendInBaseCurrency,
                'fee': _ga(item, "fee"),
                'feeInBaseCurrency': _ga(item, "feeInBaseCurrency"),
                'grossPerformance': ((grossPerformance  or  None) if not hasErrors else None),
                'grossPerformancePercentage': ((grossPerformancePercentage  or  None) if not hasErrors else None),
                'grossPerformancePercentageWithCurrencyEffect': ((grossPerformancePercentageWithCurrencyEffect  or  None) if not hasErrors else None),
                'grossPerformanceWithCurrencyEffect': ((grossPerformanceWithCurrencyEffect  or  None) if not hasErrors else None),
                'includeInHoldings': _ga(item, "includeInHoldings"),
                'investment': totalInvestment,
                'investmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect,
                'marketPrice': (float(marketSymbolMap[endDateString][_ga(item, "symbol")])  or  1),
                'marketPriceInBaseCurrency': (float(marketPriceInBaseCurrency)  or  1),
                'netPerformance': ((netPerformance  or  None) if not hasErrors else None),
                'netPerformancePercentage': ((netPerformancePercentage  or  None) if not hasErrors else None),
                'netPerformancePercentageWithCurrencyEffectMap': ((netPerformancePercentageWithCurrencyEffectMap  or  None) if not hasErrors else None),
                'netPerformanceWithCurrencyEffectMap': ((netPerformanceWithCurrencyEffectMap  or  None) if not hasErrors else None),
                'quantity': _ga(item, "quantity"),
                'symbol': _ga(item, "symbol"),
                'tags': _ga(item, "tags"),
                'valueInBaseCurrency': (Decimal(str(marketPriceInBaseCurrency)) * _ga(item, "quantity"))
            })
            totalInterestWithCurrencyEffect = (totalInterestWithCurrencyEffect + totalInterestInBaseCurrency)
            totalLiabilitiesWithCurrencyEffect = (totalLiabilitiesWithCurrencyEffect + totalLiabilitiesInBaseCurrency)
            if (((hasErrors  or  next((x for x in currentRateErrors if ((x.get('dataSource') == _ga(item, "dataSource"))  and  (x.get('symbol') == _ga(item, "symbol")))), None))  and  (_ga(item, "investment") > 0))  and  (_ga(item, "skipErrors") == False)):
                errors.append({'dataSource': _ga(item, "dataSource"), 'symbol': _ga(item, "symbol")})

        accountBalanceMap = {}
        lastKnownBalance = Decimal(str(0))
        for dateString in chartDates:
            if (accountBalanceItemsMap[dateString] != None):
                lastKnownBalance = accountBalanceItemsMap[dateString]
            accountBalanceMap[dateString] = lastKnownBalance
            for symbol in list(valuesBySymbol.keys()):
                symbolValues = valuesBySymbol[symbol]
                currentValue = (_ga(symbolValues, "currentValues")[dateString]  or  Decimal(str(0)))
                currentValueWithCurrencyEffect = (_ga(symbolValues, "currentValuesWithCurrencyEffect")[dateString]  or  Decimal(str(0)))
                investmentValueAccumulated = (_ga(symbolValues, "investmentValuesAccumulated")[dateString]  or  Decimal(str(0)))
                investmentValueAccumulatedWithCurrencyEffect = (_ga(symbolValues, "investmentValuesAccumulatedWithCurrencyEffect")[dateString]  or  Decimal(str(0)))
                investmentValueWithCurrencyEffect = (_ga(symbolValues, "investmentValuesWithCurrencyEffect")[dateString]  or  Decimal(str(0)))
                netPerformanceValue = (_ga(symbolValues, "netPerformanceValues")[dateString]  or  Decimal(str(0)))
                netPerformanceValueWithCurrencyEffect = (_ga(symbolValues, "netPerformanceValuesWithCurrencyEffect")[dateString]  or  Decimal(str(0)))
                timeWeightedInvestmentValue = (_ga(symbolValues, "timeWeightedInvestmentValues")[dateString]  or  Decimal(str(0)))
                timeWeightedInvestmentValueWithCurrencyEffect = (_ga(symbolValues, "timeWeightedInvestmentValuesWithCurrencyEffect")[dateString]  or  Decimal(str(0)))
                accumulatedValuesByDate[dateString] = {
                    'investmentValueWithCurrencyEffect': ((_ga(accumulatedValuesByDate[dateString], "investmentValueWithCurrencyEffect")  or  Decimal(str(0))) + investmentValueWithCurrencyEffect),
                    'totalAccountBalanceWithCurrencyEffect': accountBalanceMap[dateString],
                    'totalCurrentValue': ((_ga(accumulatedValuesByDate[dateString], "totalCurrentValue")  or  Decimal(str(0))) + currentValue),
                    'totalCurrentValueWithCurrencyEffect': ((_ga(accumulatedValuesByDate[dateString], "totalCurrentValueWithCurrencyEffect")  or  Decimal(str(0))) + currentValueWithCurrencyEffect),
                    'totalInvestmentValue': ((_ga(accumulatedValuesByDate[dateString], "totalInvestmentValue")  or  Decimal(str(0))) + investmentValueAccumulated),
                    'totalInvestmentValueWithCurrencyEffect': ((_ga(accumulatedValuesByDate[dateString], "totalInvestmentValueWithCurrencyEffect")  or  Decimal(str(0))) + investmentValueAccumulatedWithCurrencyEffect),
                    'totalNetPerformanceValue': ((_ga(accumulatedValuesByDate[dateString], "totalNetPerformanceValue")  or  Decimal(str(0))) + netPerformanceValue),
                    'totalNetPerformanceValueWithCurrencyEffect': ((_ga(accumulatedValuesByDate[dateString], "totalNetPerformanceValueWithCurrencyEffect")  or  Decimal(str(0))) + netPerformanceValueWithCurrencyEffect),
                    'totalTimeWeightedInvestmentValue': ((_ga(accumulatedValuesByDate[dateString], "totalTimeWeightedInvestmentValue")  or  Decimal(str(0))) + timeWeightedInvestmentValue),
                    'totalTimeWeightedInvestmentValueWithCurrencyEffect': ((_ga(accumulatedValuesByDate[dateString], "totalTimeWeightedInvestmentValueWithCurrencyEffect")  or  Decimal(str(0))) + timeWeightedInvestmentValueWithCurrencyEffect)
                }

        overall = self.calculate_overall_performance(positions)
        positionsIncludedInHoldings = [rest for x in [x for x in positions if x.get('includeInHoldings')]]
        return {
            **overall,
            'errors': errors,
            'historicalData': historicalData,
            'totalInterestWithCurrencyEffect': totalInterestWithCurrencyEffect,
            'totalLiabilitiesWithCurrencyEffect': totalLiabilitiesWithCurrencyEffect,
            'hasErrors': (hasAnySymbolMetricsErrors  or  _ga(overall, "hasErrors")),
            'positions': positionsIncludedInHoldings
        }



    def get_investments_by_group(self, data, groupBy):
        groupedData = {}
        for _item in data:
            date = _item.get('date') if isinstance(_item, dict) else getattr(_item, 'date', None)
            investmentValueWithCurrencyEffect = _item.get('investmentValueWithCurrencyEffect') if isinstance(_item, dict) else getattr(_item, 'investmentValueWithCurrencyEffect', None)
            dateGroup = (date[0:7] if (groupBy == 'month') else date[0:4])
            groupedData[dateGroup] = ((groupedData[dateGroup]  or  Decimal(str(0))) + investmentValueWithCurrencyEffect)
        return [{'date': (f"{x}-01" if (groupBy == 'month') else f"{x}-01-01"), 'investment': float(groupedData[x])} for x in list(groupedData.keys())]



    def get_snapshot(self):
        self.snapshot_promise
        return self.snapshot



    def get_start_date(self):
        firstAccountBalanceDate = None
        firstActivityDate = None
        try:
            firstAccountBalanceDateString = self.account_balance_items[0].date
            firstAccountBalanceDate = (parseDate(firstAccountBalanceDateString) if firstAccountBalanceDateString else datetime.now())
        except Exception as error:
            firstAccountBalanceDate = datetime.now()
        try:
            firstActivityDateString = self.transaction_points[0].date
            firstActivityDate = (parseDate(firstActivityDateString) if firstActivityDateString else datetime.now())
        except Exception as error:
            firstActivityDate = datetime.now()
        return _date_min([firstAccountBalanceDate, firstActivityDate])



    def get_transaction_points(self):
        return self.transaction_points



    def get_chart_date_map(self, endDate, startDate, step):

        for date in _each_day_of_interval({'end': endDate, 'start': startDate}, {'step': step}):
            chartDateMap[_date_format(date, DATE_FORMAT)] = True
        if (step > 1):
            for date in _each_day_of_interval({'end': endDate, 'start': _sub_days(endDate, 90)}, {'step': 3}):
                chartDateMap[_date_format(date, DATE_FORMAT)] = True
            for date in _each_day_of_interval({'end': endDate, 'start': _sub_days(endDate, 30)}, {'step': 1}):
                chartDateMap[_date_format(date, DATE_FORMAT)] = True
        chartDateMap[_date_format(endDate, DATE_FORMAT)] = True
        for dateRange in ['1d', '1y', '5y', 'max', 'mtd', 'wtd', 'ytd']:
            dateRangeEnd, dateRangeStart = getIntervalFromDateRange(dateRange)
            if (not _is_before(dateRangeStart, startDate)  and  not _is_after(dateRangeStart, endDate)):
                chartDateMap[_date_format(dateRangeStart, DATE_FORMAT)] = True
            if (not _is_before(dateRangeEnd, startDate)  and  not _is_after(dateRangeEnd, endDate)):
                chartDateMap[_date_format(dateRangeEnd, DATE_FORMAT)] = True
        interval = {'start': startDate, 'end': endDate}
        for date in _each_year_of_interval(interval):
            yearStart = _start_of_year(date)
            yearEnd = _end_of_year(date)
            if _is_within_interval(yearStart, interval):
                chartDateMap[_date_format(yearStart, DATE_FORMAT)] = True
            if _is_within_interval(yearEnd, interval):
                chartDateMap[_date_format(yearEnd, DATE_FORMAT)] = True
        return chartDateMap



    def compute_transaction_points(self):
        self.transaction_points = []
        symbols = {}
        lastDate = None
        lastTransactionPoint = None
        for _item in self.activities:
            date = _item.get('date') if isinstance(_item, dict) else getattr(_item, 'date', None)
            fee = _item.get('fee') if isinstance(_item, dict) else getattr(_item, 'fee', None)
            feeInBaseCurrency = _item.get('feeInBaseCurrency') if isinstance(_item, dict) else getattr(_item, 'feeInBaseCurrency', None)
            quantity = _item.get('quantity') if isinstance(_item, dict) else getattr(_item, 'quantity', None)
            SymbolProfile = _item.get('SymbolProfile') if isinstance(_item, dict) else getattr(_item, 'SymbolProfile', None)
            tags = _item.get('tags') if isinstance(_item, dict) else getattr(_item, 'tags', None)
            type = _item.get('type') if isinstance(_item, dict) else getattr(_item, 'type', None)
            unitPrice = _item.get('unitPrice') if isinstance(_item, dict) else getattr(_item, 'unitPrice', None)
            currentTransactionPointItem = None
            assetSubClass = SymbolProfile.assetSubClass
            currency = SymbolProfile.currency
            dataSource = SymbolProfile.dataSource
            factor = getFactor(type)
            skipErrors = not not SymbolProfile.userId
            symbol = SymbolProfile.symbol
            oldAccumulatedSymbol = symbols[symbol]
            if oldAccumulatedSymbol:
                investment = _ga(oldAccumulatedSymbol, "investment")
                newQuantity = ((quantity * factor) + _ga(oldAccumulatedSymbol, "quantity"))
                if (type == 'BUY'):
                    if (_ga(oldAccumulatedSymbol, "investment") >= 0):
                        investment = (_ga(oldAccumulatedSymbol, "investment") + (quantity * unitPrice))
                    else:
                        investment = (_ga(oldAccumulatedSymbol, "investment") + (quantity * _ga(oldAccumulatedSymbol, "averagePrice")))
                elif (type == 'SELL'):
                    if (_ga(oldAccumulatedSymbol, "investment") > 0):
                        investment = (_ga(oldAccumulatedSymbol, "investment") - (quantity * _ga(oldAccumulatedSymbol, "averagePrice")))
                    else:
                        investment = (_ga(oldAccumulatedSymbol, "investment") - (quantity * unitPrice))
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
                    'activitiesCount': (_ga(oldAccumulatedSymbol, "activitiesCount") + 1),
                    'averagePrice': (Decimal(str(0)) if (newQuantity == 0) else abs((investment / newQuantity))),
                    'dateOfFirstActivity': _ga(oldAccumulatedSymbol, "dateOfFirstActivity"),
                    'dividend': Decimal(str(0)),
                    'fee': (_ga(oldAccumulatedSymbol, "fee") + fee),
                    'feeInBaseCurrency': (_ga(oldAccumulatedSymbol, "feeInBaseCurrency") + feeInBaseCurrency),
                    'includeInHoldings': _ga(oldAccumulatedSymbol, "includeInHoldings"),
                    'quantity': newQuantity,
                    'tags': [*_ga(oldAccumulatedSymbol, "tags"), *tags]
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
                    'includeInHoldings': (type in INVESTMENT_ACTIVITY_TYPES),
                    'investment': ((unitPrice * quantity) * factor),
                    'quantity': (quantity * factor)
                }

            symbols[SymbolProfile.symbol] = currentTransactionPointItem
            items = (_ga(lastTransactionPoint, "items")  or  [])
            newItems = [x for x in items if (x.get('symbol') != SymbolProfile.symbol)]
            newItems.append(currentTransactionPointItem)
            sorted(newItems, key=functools.cmp_to_key(lambda a, b: ((_ga(a, "symbol") > _ga(b, "symbol")) - (_ga(a, "symbol") < _ga(b, "symbol")))))
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

#coding=utf-8
#加载必要的库
# import numpy as np
# import pandas as pd
from __future__ import print_function
from datetime import datetime
import time
import math
import json, requests
import sys, traceback
import importlib
import asyncio
import logging
import logging.config
import motor.motor_asyncio
import etcd
from functools import reduce

from finance.currency import Currency, CurrencyPair, currencyPair2Currency
from finance.order import OrderState, OrderDirection, ORDER_ID_FILLED_IMMEDIATELY
from exchange.exception import ApiErrorException
from sms.ali_sms import AliSms
from strategy import StragetyBase

waterLogger = logging.getLogger("water")
tradeLogger = logging.getLogger("trade")

class MarketMakingStrategy(StragetyBase):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.smsClient = AliSms(config['sms'])
        self.exchanges = {}
        exchanges = self.config['arbitrage']['exchanges']
        logging.info("initilizing %d exchange: %s", len(exchanges), exchanges)
        for exch in exchanges:
            exchConfig = list(filter(lambda x: x['name'] == exch, config['exchange']))[0]
            logging.info("initilizing exchange %s, config: %s", exch, exchConfig)
            e = importlib.import_module("exchange.%s"%exch).Exchange(exchConfig)
            self.exchanges.update({exch: e})
        self.mongoHost = config['db']['mongo']['host']
        self.mongoPort = config['db']['mongo']['port']
        logging.info("initilizing mongo client, host = %s, port = %s", self.mongoHost, self.mongoPort)
        # self.mongoClient = motor.motor_asyncio.AsyncIOMotorClient('localhost', 27017)
        self.etcdHost = config['etcd']['host']
        self.etcdPort = config['etcd']['port']
        logging.info("initilizing etcd client, host = %s, port = %s", self.etcdHost, self.etcdPort)
        self.etcdClient = etcd.Client(host = self.etcdHost, port = self.etcdPort)

    def determineGainTarget(self, currencyPair, buyExchangeCoinAmount, sellExchangeCoinAmount):
        balanceRatio = self.config['arbitrage'][currencyPair]['balance_ratio']
        if buyExchangeCoinAmount / sellExchangeCoinAmount < balanceRatio:
            return self.config['arbitrage'][currencyPair]['balance_target_gain']
        else:
            return self.config['arbitrage'][currencyPair]['arbitrage_target_gain']

    def _floor(self, num, precision = 3):
        multiplier = math.pow(10.0, precision)
        return math.floor(num * multiplier) / multiplier

    # return order_id if successes, None if order failed
    async def orderWithRetry(self, currencyPair, exchangeName, price, amount, isSell, maxRetryNum):
        logging.debug("orderWithRetry: currencyPair %s, exchangeName %s, price %s, amount %s, isSell %s, maxRetryNum %s",
                    currencyPair, exchangeName, price, amount, isSell, maxRetryNum)
        if isSell:
            orderFunc = self.exchanges[exchangeName].sellAsync
        else:
            orderFunc = self.exchanges[exchangeName].buyAsync

        orderSuccess = False
        orderId = None
        for i in range(maxRetryNum):
            try:
                orderId = await orderFunc(currencyPair, price = price, amount = amount)
                orderSuccess = True
                break
            except Exception as e:
                logging.warn("%s order in exchange %s(%f,%f) failed: %s, will try again[%d/%d]",
                            'sell' if isSell else 'buy',
                            exchangeName, price, amount, e, i+1, maxRetryNum)
        if orderSuccess:
            logging.info("%s order in exchange %s(%f,%f) success", 'sell' if isSell else 'buy', exchangeName, price, amount)
            return orderId
        else:
            logging.error("%s order in exchange %s(%f,%f) failed, reach maximum retry.",
                        'sell' if isSell else 'buy',
                        exchangeName, price, amount)
            return None

    # return True if successes, False if failed
    async def cancelOrderWithRetry(self, currencyPair, exchangeName, id, maxRetryNum):
        logging.debug("cancelOrderWithRetry: currencyPair %s, exchangeName %s, id %s, maxRetryNum %s",
                     currencyPair, exchangeName, id, maxRetryNum)
        cancelSuccess = False
        for i in range(maxRetryNum):
            try:
                cancelSuccess = await self.exchanges[exchangeName].cancelOrderAsync(currencyPair = currencyPair, id = id)
                break
            except Exception as e:
                if exchangeName == "chbtc" and isinstance(e, ApiErrorException) and int(e.code) == 3001:
                    return True
                logging.warn("cancel order in exchange %s(order_id: %s) failed: %s, will try again[%d/%d]",
                            exchangeName, id, e, i+1, maxRetryNum)
        if not cancelSuccess:
            logging.error("cancel order in exchange %s(order_id: %s) failed, reach maximum retry.",
                        exchangeName, id)
            return False
        return True

    # return order info
    async def queryOrderWithRetry(self, currencyPair, exchangeName, id, maxRetryNum):
        logging.debug("queryOrderWithRetry: currencyPair %s, exchangeName %s, id %s, maxRetryNum %s",
                     currencyPair, exchangeName, id, maxRetryNum)

        orderInfo = None
        for i in range(maxRetryNum):
            try:
                orderInfo = await self.exchanges[exchangeName].getOrderAsync(currencyPair = currencyPair, id = id)
                break
            except Exception as e:
                logging.warn("query order in exchange %s(order_id: %s) failed: %s, will try again[%d/%d]",
                            exchangeName, id, e, i+1, maxRetryNum)
        if not orderInfo:
            logging.error("query order in exchange %s(order_id: %s) failed, reach maximum retry.",
                        exchangeName, id)
            return None
        return orderInfo

    async def isBull(self, lastTrades):
        return False

    async def isBear(self, lastTrades):
        return False

    #return all orderInfo
    async def doBalance(self, exchangeName, currencyPair, targetAmount):
        remainAmount = targetAmount
        maxOrderRetry = filter(lambda x: x['name'] == exchangeName, 
                                self.config['exchange']).__next__()['max_order_retry']
        maxCancelOrderRetry = filter(lambda x: x['name'] == exchangeName, 
                                self.config['exchange']).__next__()['max_cancel_order_retry']
        orderInfos = []
        while (abs(remainAmount) > 0.002):
            try:
                orderBook = await self.exchanges[exchangeName].getQuotes(currencyPair)
                bid1 = orderBook.getBids()[0].price
                ask1 = orderBook.getAsks()[0].price
                if remainAmount < 0:
                    orderId = await self.orderWithRetry(currencyPair = currencyPair, exchangeName = exchangeName, price = bid1, 
                                        amount = remainAmount * -1, isSell = True, maxRetryNum = maxOrderRetry)
                else:
                    orderId = await self.orderWithRetry(currencyPair = currencyPair, exchangeName = exchangeName, price = ask1, 
                                        amount = remainAmount, isSell = False, maxRetryNum = maxOrderRetry)
                logging.debug("doBalance %d: orderId = %s", len(orderInfos) + 1, orderId)
                await asyncio.sleep(1.0)
                await self.cancelOrderWithRetry(currencyPair, exchangeName, orderId, maxCancelOrderRetry)
                orderInfo = await self.queryOrderWithRetry(currencyPair = currencyPair, exchangeName = exchangeName, id = orderId, maxRetryNum = 5)
                logging.debug("doBalance %d: orderInfo = %s", len(orderInfos) + 1, orderInfo)
                orderInfos.append(orderInfo)
                filledAmount = orderInfo.filledAmount
                if remainAmount > 0:
                    remainAmount -= filledAmount
                else:
                    remainAmount += filledAmount
            except Exception as e:
                logging.warn("doBalance error: %s", e)    

        return orderInfos

    # return order state
    async def waitOrderToBeFilled(self, currencyPair, exchangeName, id, waitOrderFilledSecond):
        queryOrderStateIntervalMs = self.config['arbitrage']['query_order_state_interval_ms']
        if id == ORDER_ID_FILLED_IMMEDIATELY:
            return OrderState.FILLED

        state = OrderState.INITIAL
        end_time = time.time() + waitOrderFilledSecond
        while time.time() < end_time:
            try:
                order = await self.exchanges[exchangeName].getOrderAsync(currencyPair, id)
                # 特殊逻辑，BTC38对于已经完成的订单是查不到的，还有聚币网有时居然也查不到订单
                if order is None:
                    return OrderState.FILLED
                state = order.state
                if order.state == OrderState.FILLED or order.state == OrderState.CANCELLED:
                    break
            except Exception as e:
                logging.warn("waitOrderToBeFilled error: %s(%s, %s, %s) ", e, currencyPair, exchangeName, id)
            await asyncio.sleep(queryOrderStateIntervalMs/1000.)
        return state

    async def check(self, currencyPair):
        currency = currencyPair2Currency(currencyPair)

        exchangeName = self.config['market_making'][str(currencyPair)]['exchange']
        gapMinPerc = self.config['market_making'][str(currencyPair)]['bid_ask_signal_gap_min_perc']
        gapMaxPerc = self.config['market_making'][str(currencyPair)]['bid_ask_signal_gap_max_perc']
        makerFee = self.config['market_making'][str(currencyPair)]['maker_fee']
        takerFee = self.config['market_making'][str(currencyPair)]['taker_fee']
        tradeMinAmount = self.config['market_making'][str(currencyPair)]['trade_min_amount']
        tradeMaxAmount = self.config['market_making'][str(currencyPair)]['trade_max_amount']
        targetGain = self.config['market_making'][str(currencyPair)]['target_gain']
        waitOrderSeconds = self.config['market_making']['wait_order_filled_second']
        sms_money_threshold = self.config['market_making']['sms_money_threshold']
        logging.info("run market making strategy for %s, in exchange %s", currencyPair, exchangeName)

        #先update账户信息
        await self.exchanges[exchangeName].updateAccountInfo()
        cash = self.exchanges[exchangeName].accountInfo['balances'][Currency.CNY]
        coinAmount = self.exchanges[exchangeName].accountInfo['balances'][currency]
        logging.info("[%s]cash %f, coinAmount %f", exchangeName, cash, coinAmount)

        #获取order book
        orderBook = await self.exchanges[exchangeName].getQuotes(currencyPair)
        ticker = await self.exchanges[exchangeName].getTicker(currencyPair)

        #获取trades
        
        #判断是否存在趋势，是则不交易
        
        #计算价格，判断信号
        bid1 = orderBook.getBids()[0].price
        bid1Amount = orderBook.getBids()[0].amount
        ask1 = orderBook.getAsks()[0].price
        ask1Amount = orderBook.getAsks()[0].amount
        #有些交易所偶尔会返回错误的信息，这里先过滤一遍
        if ask1 <= bid1:
            logging.warn("risk!!!%s qoutes maybe wrong, ask %f, bid %f, skip", exchangeName, ask1, bid1)
            return

        bidAskGapPerc = (ask1 - bid1) / bid1
        if bidAskGapPerc < gapMinPerc or bidAskGapPerc > gapMaxPerc:
            logging.info("bidAskGapPerc(%s) not in market marking signal range(%s, %s), skip", 
                         bidAskGapPerc, gapMinPerc, gapMaxPerc)
            return

        lastPrice = float(ticker['last'])
        bidPrice = bid1 * 0.618 + ask1 * 0.382
        askPrice = ask1 * 0.618 + bid1 * 0.382
        # bidPrice2 = bid1 * 0.5 + float(ticker['last']) * 0.5
        # askPrice2 = ask1 * 0.5 + float(ticker['last']) * 0.5
        
        # if bidPrice < lastPrice:
        #     bidPrice = (bidPrice + lastPrice) / 2.0
        # if askPrice > lastPrice:
        #     askPrice = (askPrice + lastPrice) / 2.0
        # logging.info("bidPrice = %s, askPrice = %s", bidPrice, askPrice)
        # if askPrice > ask1 or bidPrice < bid1:
        #     return
            
        # bidPrice = (bid1 + ask1) / 2.0 * (1 - targetGain - makerFee)
        # askPrice = (bid1 + ask1) / 2.0 * (1 + targetGain + makerFee)
        tradeAmount = min(bid1Amount, ask1Amount) * 0.8
        tradeAmount = min(tradeAmount, coinAmount)
        tradeAmount = min(tradeAmount, cash / (bidPrice * makerFee))
        tradeAmount = min(tradeAmount, tradeMaxAmount)
        if tradeAmount < tradeMinAmount:
            logging.info("tradeAmount(%s) < trade_min_amount(%s), skip", tradeAmount, tradeMinAmount)
            return

        #不存在利润则不操作
        buyValue = bidPrice * tradeAmount
        sellValue = askPrice * tradeAmount
        tradeFee = (buyValue + sellValue) * makerFee
        alpha = (sellValue - buyValue - tradeFee) / buyValue
        logging.info("tradeAmount: %s, buyValue: %s, sellValue: %s, tradeFee: %s, alpha: %s",
                    tradeAmount, buyValue, sellValue, tradeFee, alpha)
        if alpha < targetGain:
            logging.info("alpha(%s) <= targetGain(%s), skip", alpha, targetGain)
            return

        # get retry config
        maxOrderRetry = filter(lambda x: x['name'] == exchangeName, 
                                self.config['exchange']).__next__()['max_order_retry']
        maxCancelOrderRetry = filter(lambda x: x['name'] == exchangeName, 
                                self.config['exchange']).__next__()['max_cancel_order_retry']

        #双向下单
        logging.info("placing buy order (%s, %s) and sell order (%s, %s) for %s in %s",
                    bidPrice, tradeAmount, askPrice, tradeAmount, currencyPair, exchangeName)
        # buyOrderId = "201707229505504"
        # sellOrderId = "201707229479967"
        (buyOrderId, sellOrderId) = await asyncio.gather(
            self.orderWithRetry(currencyPair = currencyPair, exchangeName = exchangeName, price = bidPrice, 
                                amount = tradeAmount, isSell = False, maxRetryNum = maxOrderRetry),
            self.orderWithRetry(currencyPair = currencyPair, exchangeName = exchangeName, price = askPrice, 
                                amount = tradeAmount, isSell = True, maxRetryNum = maxOrderRetry),
            return_exceptions = True)
        logging.debug("buyOrderId: %s, sellOrderId: %s", buyOrderId, sellOrderId)

        # sleep for a while than cancel order and balance portfolio
        if not isinstance(buyOrderId, Exception) and not isinstance(sellOrderId, Exception):
            # 特殊逻辑，短暂sleep 500毫秒一下，防止太快查不到订单（主要是jubi网)
            await asyncio.sleep(0.5)
            (buyOrderState, sellOrderState) = await asyncio.gather(
                self.waitOrderToBeFilled(currencyPair, exchangeName, buyOrderId, waitOrderSeconds),
                self.waitOrderToBeFilled(currencyPair, exchangeName, sellOrderId, waitOrderSeconds))
            logging.info("buyOrderState %s, sellOrderState %s", buyOrderState, sellOrderState)

        tasks = []
        if isinstance(buyOrderId, Exception):
            logging.error("place buy order error with retry: %s", buyOrderId)
            # sendSms
        else:
            tasks.append(self.cancelOrderWithRetry(currencyPair, exchangeName, buyOrderId, maxCancelOrderRetry))

        if isinstance(sellOrderId, Exception):
            logging.error("place sell order error with retry: %s", sellOrderId)
            # sendSms
        else:
            tasks.append(self.cancelOrderWithRetry(currencyPair, exchangeName, sellOrderId, maxCancelOrderRetry))
        cancelResults = await asyncio.gather(*tasks, return_exceptions = True)
        logging.debug("cancelResults: %s", cancelResults)


        (buyOrderInfo, sellOrderInfo) = await asyncio.gather(
            self.queryOrderWithRetry(currencyPair = currencyPair, exchangeName = exchangeName, id = buyOrderId, maxRetryNum = 5),
            self.queryOrderWithRetry(currencyPair = currencyPair, exchangeName = exchangeName, id = sellOrderId, maxRetryNum = 5)
            )
        logging.debug("buyOrderInfo: %s", buyOrderInfo)
        logging.debug("sellOrderInfo: %s", sellOrderInfo)
        if buyOrderInfo is None or sellOrderInfo is None:
            logging.error("queryOrderWithRetry for %s or %s error", buyOrderId, sellOrderId)
            return

        # 保存trade流水
        tradeLogger.info("%s", buyOrderInfo)
        tradeLogger.info("%s", sellOrderInfo)

        # 计算成交部分，如果有未成交的则马上补仓（有可能造成亏损）
        buyFilledAmount = buyOrderInfo.filledAmount
        sellFilledAmount = sellOrderInfo.filledAmount
        if buyFilledAmount == 0 and sellFilledAmount == 0:
            return

        balanceOrderInfos = []
        hasBalance = False
        if abs(buyFilledAmount - sellFilledAmount) > 0.002:
            logging.info("buyFilledAmount(%s), sellFilledAmount(%s), need balance", buyFilledAmount, sellFilledAmount)
            hasBalance = True
            balanceOrderInfos = await self.doBalance(exchangeName, currencyPair, sellFilledAmount - buyFilledAmount)
            [tradeLogger.info("%s", orderInfo) for orderInfo in balanceOrderInfos]

        #计算收益，保存流水
        totalBuyValue = 0.0
        totalSellValue = 0.0
        totalTradeFee = 0.0
        totalTradeAmount = max(buyFilledAmount, sellFilledAmount)
        if buyFilledAmount > 0.0:
            totalBuyValue = buyOrderInfo.filledPrice * buyOrderInfo.filledAmount
            totalTradeFee += totalBuyValue * makerFee
        if sellFilledAmount > 0.0:
            totalSellValue = sellOrderInfo.filledPrice * sellOrderInfo.filledAmount
            totalTradeFee += totalSellValue * makerFee

        for orderInfo in balanceOrderInfos:
            if orderInfo.buyOrSell == OrderDirection.BUY and orderInfo.filledAmount > 0.0:
                totalBuyValue += orderInfo.filledPrice * orderInfo.filledAmount
                totalTradeFee += orderInfo.filledPrice * orderInfo.filledAmount * takerFee
            if orderInfo.buyOrSell == OrderDirection.SELL and orderInfo.filledAmount > 0.0:
                totalSellValue += orderInfo.filledPrice * orderInfo.filledAmount
                totalTradeFee += orderInfo.filledPrice * orderInfo.filledAmount * takerFee

        alphaFlat = totalSellValue - totalBuyValue - totalTradeFee
        alpha = alphaFlat / totalBuyValue
        balanceTime = len(balanceOrderInfos)
        water = {"time": datetime.now(),
                 "totalSellValue": totalSellValue,
                 "totalBuyValue": totalBuyValue,
                 "totalTradeAmount": totalTradeAmount,
                 "hasBalance": hasBalance,
                 "balanceTime": balanceTime,
                 "tradeCost": totalTradeFee,
                 "alphaFlat": alphaFlat,
                 "alpha": alpha}
        waterLogger.info("%s", water)
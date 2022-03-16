import logging
import time
from threading import Thread
from src.config import CONFIG
from src.events import CREATE_LIMIT_ORDER, CREATE_MARKET_ORDER, GRID_INIT, GRID_RESET, GRID_UPDATE, ORDERS, POSITION, REMOVE_ALL_LIMIT_ORDERS, REMOVE_LIMIT_ORDER, REMOVE_MARKET_ORDER, fire_event, fire_event_asap
from src.sessions import get_session


class GridWorker:

    def start(self, executions, events):
        t = Thread(target=self._run, args=(executions, events))
        t.start()
    
    def _run(self, executions, events):
        market = CONFIG['market']
        gridSize = CONFIG['gridSize']
        buyQty = CONFIG['buyQty']
        sellQty = CONFIG['sellQty']
        ticker = get_session().fetchTicker(market)
        minOrderSize = float(ticker['info']['minProvideSize'])
        position = {}
        amount = 0
        interval = 0
        margin = 0
        lastOrder = None
        while True:
            if (len(events)):
                event = events.popleft()
                eventType = event[0]
                if (eventType == ORDERS):
                    orders = event[1]
                    if (position and 'longOrderSize' in position and 'shortOrderSize' in position):
                        # Refresh current orders state
                        buys = []
                        sells = []
                        for order in orders:
                            if ('info' in order and 'side' in order['info']):
                                if (order['info']['side'] == 'buy'):
                                    buys.append(order['info'])
                                elif (order['info']['side'] == 'sell'):
                                    sells.append(order['info'])
                        if (len(buys) < 1 or len(sells) < 1):
                            fire_event_asap(executions, (GRID_RESET, market))
                        else:
                            # Handle buy orders
                            buys.sort(key=lambda k: float(k['price']))
                            minBuy = buys[0]
                            
                            if ('price' in minBuy and lastOrder and 'price' in lastOrder and lastOrder['price']):
                                minBuyPrice = float(minBuy['price'])
                                # Adding extreme buy orders
                                if (len(buys) < gridSize):
                                    for i in range(gridSize - len(buys)):
                                        orderPrice = minBuyPrice - (interval * (i + 1))
                                        logging.info(f'Adding minimum {market} buy order at {orderPrice} $')
                                        fire_event(executions, (CREATE_LIMIT_ORDER, market, 'buy', buyQty, orderPrice))
                                # Removing extreme buy orders
                                elif (len(buys) > gridSize and 'id' in minBuy):
                                    for i in range(len(buys) - gridSize):
                                        logging.info(f'Removing minimum {market} buy order at {buys[i]["price"]} $')
                                        fire_event(executions, (REMOVE_LIMIT_ORDER, buys[i]['id']))
                                lastBuy = None
                                for bo in buys:
                                    if lastBuy:
                                        lastBuyPrice = float(lastBuy['price'])
                                        diff = float(bo['price']) - lastBuyPrice
                                        # Filling buy orders gaps
                                        if (diff > interval + margin):
                                            orderPrice = lastBuyPrice + interval
                                            logging.info(f'Adding missing {market} buy order at {orderPrice} $')
                                            fire_event(executions, (CREATE_LIMIT_ORDER, market, 'buy', buyQty, orderPrice))
                                        # Removing duplicated buy orders
                                        elif (diff < interval - margin):
                                            logging.info(f'Removing misplaced {market} buy order at {lastBuyPrice} $')
                                            fire_event(executions, (REMOVE_LIMIT_ORDER, bo['id']))
                                    lastBuy = bo
                            # Handle sell orders
                            sells.sort(key=lambda k: float(k['price']))
                            maxSell = sells[len(sells) - 1]
                            if ('price' in maxSell and lastOrder and 'price' in lastOrder and lastOrder['price']):
                                maxSellPrice = float(maxSell['price'])
                                # Adding extreme sell orders
                                if (len(sells) < gridSize):
                                    for i in range(gridSize - len(sells)):
                                        orderPrice = maxSellPrice + ((interval) * (i + 1))
                                        logging.info(f'Adding maximum {market} sell order at {orderPrice} $')
                                        fire_event(executions, (CREATE_LIMIT_ORDER, market, 'sell', sellQty, orderPrice))
                                # Removing extreme sell orders
                                elif (len(sells) > gridSize and 'id' in maxSell):
                                    for i in range(len(sells) - gridSize):
                                        logging.info(f'Removing maximum {market} sell order at {sells[i]["price"]} $')
                                        fire_event(executions, (REMOVE_LIMIT_ORDER, maxSell['id']))
                                lastSell = None
                                for so in sells:
                                    if lastSell:
                                        lastSellPrice = float(lastSell['price'])
                                        diff = float(so['price']) - lastSellPrice
                                        # Filling sell orders gaps
                                        if (diff > interval + margin):
                                            orderPrice = float(so['price']) - interval
                                            logging.info(f'Adding missing {market} sell order at {orderPrice} $')
                                            fire_event(executions, (CREATE_LIMIT_ORDER, market, 'sell', sellQty, orderPrice))
                                        # Removing duplicated sell orders
                                        elif (diff < interval - margin):
                                            logging.info(f'Removing misplaced {market} sell order at {lastSellPrice} $')
                                            fire_event(executions, (REMOVE_LIMIT_ORDER, so['id']))
                                    lastSell = so

                        # Adding missing close orders
                        # maxBuy = buys[len(buys) - 1]
                        # minSell = sells[0]
                        # if ('price' in maxBuy and 'price' in minSell):
                        #     diff = minSell - maxBuy
                        #     if (diff > interval * 2 + margin):
                        #         print(f'A close order is missing {diff}')
                        #         if ('ask' in ticker and 'bid' in ticker):
                        #             price = (ticker['ask'] + ticker['bid']) / 2
                        #             if (minSell['price'] - price > price - maxBuy['price']):
                        #                 print('Adding missing sell order')
                        #                 fire_event_asap(executions, (CREATE_LIMIT_ORDER, market, 'sell', sellQty, minSell['price'] - interval))
                        #             else:
                        #                 print('Adding missing buy order')
                        #                 fire_event_asap(executions, (CREATE_LIMIT_ORDER, market, 'buy', buyQty, maxBuy['price'] + interval))

                elif (eventType == CREATE_MARKET_ORDER):
                    if ('amount' in event[1]):
                        amount = amount + event[1]['amount']
                        lastOrder = event[1]
                elif (eventType == POSITION):
                    position = event[1]
                    if not position or ('side' in position and position['side'] == 'sell') or ('netSize' in position and float(position['netSize']) < minOrderSize):
                        fire_event_asap(executions, (GRID_INIT, market))
                    else:
                        netSize = float(position['netSize'])
                        if (amount != netSize):
                            logging.info(f'Updating current {market} position from {amount} to {netSize} {market}')
                            amount = netSize
                elif (eventType == GRID_UPDATE):
                    order = event[1]
                    if ('type' in order and 'side' in order and 'price' in order and 'status' in order and 'filledSize' in order and order['type'] == 'limit' and order['status'] == 'closed' and order['filledSize'] != 0):
                        lastOrder = order
                        if (amount < minOrderSize):
                            logging.info(f'Current {market} position is under minimum contract size ({minOrderSize} {market})')
                            fire_event_asap(executions, (GRID_INIT, market))
                        else:
                            filledSize = order['filledSize']
                            orderPrice = order['price']
                            if (order['side'] == 'buy'):
                                amount = amount + filledSize
                                logging.info(f'Bought {filledSize} {market} at {orderPrice} $, current position is {amount} {market}')
                                executions.appendleft((CREATE_LIMIT_ORDER, market, 'sell', sellQty, orderPrice + interval))
                            elif (order['side'] == 'sell'):
                                amount = amount - filledSize
                                logging.info(f'Sold {filledSize} {market} at {orderPrice} $, current position is {amount} {market}')
                                executions.appendleft((CREATE_LIMIT_ORDER, market, 'buy', buyQty, orderPrice - interval))
                elif (eventType == GRID_INIT):
                    logging.info(f'Initializing {market} grid')
                    ticker = event[1]
                    position = event[2]
                    events.clear()
                    executions.clear()
                    if ('ask' in ticker and 'bid' in ticker):
                        executions.appendleft((REMOVE_ALL_LIMIT_ORDERS, market))
                        if len(event) == 3:
                            if (position and 'netSize' in position and float(position["netSize"]) > 0):
                                logging.info(f'Market selling {position["netSize"]} {market}')
                            executions.appendleft((REMOVE_MARKET_ORDER, market))
                        time.sleep(3)  # Let FTX remove all pending orders
                        # TODO improve
                        if (position and 'netSize' in position):
                            amount = float(position['netSize'])
                        else:
                            amount = 0
                        lastOrder = None
                        price = (ticker['ask'] + ticker['bid']) / 2
                        if len(event) == 3:
                            logging.info(f'Market buying {buyQty} {market} around {price} $')
                            executions.append((CREATE_MARKET_ORDER, market, 'buy', buyQty))
                        interval = price / 100 * CONFIG['gridStep']
                        margin = interval * 0.1
                        for i in range(1, gridSize + 1):
                            executions.append((CREATE_LIMIT_ORDER, market, 'buy', buyQty, price - (interval * i)))
                            executions.append((CREATE_LIMIT_ORDER, market, 'sell', sellQty, price + (interval * i)))
            time.sleep(0.05)
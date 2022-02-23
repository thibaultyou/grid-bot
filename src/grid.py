import logging
import time
from threading import Thread
from src.log import format_log
from src.config import CONFIG
from src.events import CREATE_LIMIT_ORDER, CREATE_MARKET_ORDER, GRID_INIT, GRID_INIT_COMPLETED, GRID_RESET, GRID_UPDATE, ORDERS, POSITION, REMOVE_ALL_LIMIT_ORDERS, REMOVE_LIMIT_ORDER, REMOVE_MARKET_ORDER
from src.sessions import get_session


class GridWorker:

    def start(self, exec_queue, event_queue):
        t = Thread(target=self._run, args=(exec_queue, event_queue))
        t.start()
    
    def _run(self, exec_queue, event_queue):
        ticker = get_session().fetchTicker(CONFIG['market'])
        minContractSize = float(ticker['info']['minProvideSize'])
        position = {}
        amount = 0
        margin = 0
        lastOrder = None
        while True:
            if (len(event_queue)):
                event = event_queue.popleft()
                if (event[0] == ORDERS):
                    if (position and 'longOrderSize' in position and 'shortOrderSize' in position):
                        # Get current orders state
                        buyOrders = []
                        sellOrders = []
                        for order in event[1]:
                            if ('info' in order and 'side' in order['info']):
                                if (order['info']['side'] == 'buy'):
                                    buyOrders.append(order['info'])
                                elif (order['info']['side'] == 'sell'):
                                    sellOrders.append(order['info'])
                        buyOrdersCount = len(buyOrders)
                        sellOrdersCount = len(sellOrders)
                        if (buyOrdersCount < 1 or sellOrdersCount < 1):
                            exec_queue.appendleft((GRID_RESET, CONFIG['market']))
                        else:
                            # Handle buy orders
                            buyOrders.sort(key=lambda k: k['price'])
                            minBuy = buyOrders[0]
                            if ('price' in minBuy and lastOrder and 'price' in lastOrder and lastOrder['price']):
                                minBuyOrderPrice = float(minBuy['price'])
                                # Adding extreme buy orders
                                if (buyOrdersCount < CONFIG['gridSize']):
                                    for i in range(CONFIG['gridSize'] - buyOrdersCount):
                                        price = minBuyOrderPrice - ((CONFIG['interval']) * (i + 1))
                                        logging.info(f'Adding minimum {CONFIG["market"]} buy order at {price} $')
                                        exec = (CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], price)
                                        if (exec not in exec_queue):
                                            exec_queue.append(exec)
                                # Removing extreme buy orders
                                elif (buyOrdersCount > CONFIG['gridSize'] and 'id' in minBuy):
                                    for i in range(buyOrdersCount - CONFIG['gridSize']):
                                        logging.info(f'Removing minimum {CONFIG["market"]} buy order at {buyOrders[i]["price"]} $')
                                        exec = (REMOVE_LIMIT_ORDER, buyOrders[i]['id'])
                                        if (exec not in exec_queue):
                                            exec_queue.append(exec)
                                lastSeenBuyOrder = None
                                for bo in buyOrders:
                                    if lastSeenBuyOrder:
                                        lastBuyOrderPrice = float(lastSeenBuyOrder['price'])
                                        diff = float(bo['price']) - lastBuyOrderPrice
                                        # Filling buy orders gaps
                                        if (diff > CONFIG['interval'] + margin):
                                            price = lastBuyOrderPrice + CONFIG['interval']
                                            logging.info(f'Adding missing {CONFIG["market"]} buy order at {price} $')
                                            exec = (CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], price)
                                            if (exec not in exec_queue):
                                                exec_queue.append(exec)
                                        # Removing duplicated buy orders
                                        elif (diff < CONFIG['interval'] - margin):
                                            logging.info(f'Removing misplaced {CONFIG["market"]} buy order at {lastBuyOrderPrice} $')
                                            exec = (REMOVE_LIMIT_ORDER, bo['id'])
                                            if (exec not in exec_queue):
                                                exec_queue.append(exec)
                                    lastSeenBuyOrder = bo
                            # Handle sell orders
                            sellOrders.sort(key=lambda k: k['price'])
                            maxSell = sellOrders[sellOrdersCount - 1]
                            if ('price' in maxSell and lastOrder and 'price' in lastOrder and lastOrder['price']):
                                maxSellOrderPrice = float(maxSell['price'])
                                # Adding extreme sell orders
                                if (sellOrdersCount < CONFIG['gridSize']):
                                    for i in range(CONFIG['gridSize'] - sellOrdersCount):
                                        price = maxSellOrderPrice + ((CONFIG['interval']) * (i + 1))
                                        logging.info(f'Adding maximum {CONFIG["market"]} sell order at {price} $')
                                        exec = (CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], price)
                                        if (exec not in exec_queue):
                                            exec_queue.append(exec)
                                # Removing extreme sell orders
                                elif (sellOrdersCount > CONFIG['gridSize'] and 'id' in maxSell):
                                    for i in range(sellOrdersCount - CONFIG['gridSize']):
                                        logging.info(f'Removing maximum {CONFIG["market"]} sell order at {sellOrders[i]["price"]} $')
                                        exec = (REMOVE_LIMIT_ORDER, maxSell['id'])
                                        if (exec not in exec_queue):
                                            exec_queue.append(exec)
                                lastSeenSellOrder = None
                                for so in sellOrders:
                                    if lastSeenSellOrder:
                                        lastSellOrderPrice = float(lastSeenSellOrder['price'])
                                        diff = float(so['price']) - lastSellOrderPrice
                                        # Filling sell orders gaps
                                        if (diff > CONFIG['interval'] + margin):
                                            price = float(so['price']) - CONFIG['interval']
                                            logging.info(f'Adding missing {CONFIG["market"]} sell order at {price} $')
                                            exec = (CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], price)
                                            if (exec not in exec_queue):
                                                exec_queue.append(exec)
                                        # Removing duplicated sell orders
                                        elif (diff < CONFIG['interval'] - margin):
                                            logging.info(f'Removing misplaced {CONFIG["market"]} sell order at {lastSellOrderPrice} $')
                                            exec = (REMOVE_LIMIT_ORDER, so['id'])
                                            if (exec not in exec_queue):
                                                exec_queue.append(exec)
                                    lastSeenSellOrder = so
                elif (event[0] == CREATE_MARKET_ORDER):
                    if ('amount' in event[1]):
                        amount = amount + event[1]['amount']
                        lastOrder = event[1]
                elif (event[0] == POSITION):
                    # print(f'Current position {format_log(event[1])}')
                    if not event[1] or ('side' in event[1] and event[1]['side'] == 'sell') or ('netSize' in event[1] and float(event[1]['netSize']) < minContractSize):
                        exec = (GRID_INIT, CONFIG['market'])
                        if (exec not in exec_queue):
                            exec_queue.appendleft(exec)
                    else:
                        position = event[1]
                        net = float(event[1]['netSize'])
                        if (amount != net):
                            logging.info(f'Updating current {CONFIG["market"]} position from {amount} to {net} {CONFIG["market"]}')
                            amount = net
                elif (event[0] == GRID_UPDATE):
                    if ('type' in event[1] and 'side' in event[1] and 'status' in event[1] and 'filledSize' in event[1] and event[1]['type'] == 'limit' and event[1]['status'] == 'closed' and event[1]['filledSize'] != 0):
                        # print(f'Event from websocket {format_log(event[1])}, {amount}, {minContractSize}')
                        lastOrder = event[1]
                        if (amount < minContractSize):
                            logging.info(f'Current {CONFIG["market"]} position is under minimum contract size ({minContractSize} {CONFIG["market"]})')
                            exec = (GRID_INIT, CONFIG['market'])
                            if (exec not in exec_queue):
                                exec_queue.appendleft(exec)
                        else:
                            if (event[1]['side'] == 'buy'):
                                amount = amount + event[1]['filledSize']
                                logging.info(f'Bought {CONFIG["market"]} at {event[1]["price"]} $, current position is {amount} {CONFIG["market"]}')
                                exec_queue.appendleft((CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], event[1]['price'] + CONFIG['interval']))
                            elif (event[1]['side'] == 'sell'):
                                amount = amount - event[1]['filledSize']
                                logging.info(f'Sold {CONFIG["market"]} at {event[1]["price"]} $, current position is {amount} {CONFIG["market"]}')
                                exec_queue.appendleft((CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], event[1]['price'] - CONFIG['interval']))
                elif (event[0] == GRID_INIT):
                    logging.info(f'{CONFIG["market"]} grid init')
                    event_queue.clear()
                    exec_queue.clear()
                    if ('ask' in event[1] and 'bid' in event[1]):
                        # print(f'Ticker {formatLog(event[1])}')
                        exec_queue.append((REMOVE_ALL_LIMIT_ORDERS, CONFIG['market']))
                        if len(event) == 3:
                            exec_queue.append((REMOVE_MARKET_ORDER, CONFIG['market']))
                        time.sleep(2)  # Let FTX remove all pending orders
                        
                        # TODO improve
                        if (event[2] and 'netSize' in event[2]):
                            amount = float(event[2]['netSize'])
                        else:
                            amount = 0

                        lastOrder = None
                        if len(event) == 3:
                            exec_queue.append((CREATE_MARKET_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty']))
                        price = (event[1]['ask'] + event[1]['bid']) / 2
                        CONFIG['interval'] = price / 100 * CONFIG['gridStep']
                        margin = CONFIG['interval'] * 0.05
                        for i in range(1, CONFIG['gridSize'] + 1):
                            exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], price - (CONFIG['interval'] * i)))
                            exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], price + (CONFIG['interval'] * i)))
            time.sleep(0.05)
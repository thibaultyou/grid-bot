from threading import Thread
import time
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
        isInitComplete = True
        while True:
            if (len(event_queue)):
                event = event_queue.popleft()
                if (event[0] == GRID_INIT_COMPLETED):
                    print('grid init completed')
                    isInitComplete = True
                elif (event[0] == ORDERS):
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
                            exec_queue.append((GRID_RESET, CONFIG['market']))
                        else:
                            # Handle buy orders
                            buyOrders.sort(key=lambda k: k['price'])
                            minBuy = buyOrders[0]
                            if ('price' in minBuy and lastOrder and 'price' in lastOrder and lastOrder['price']):
                                minBuyOrderPrice = float(minBuy['price'])
                                # TODO improve
                                # if (isInitComplete):
                                # Adding extreme buy orders
                                if (buyOrdersCount < CONFIG['gridSize']):
                                    for i in range(CONFIG['gridSize'] - buyOrdersCount):
                                        print('+ + added min buy')
                                        exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], minBuyOrderPrice - (CONFIG['interval']) * (i + 1)))
                                # Removing extreme buy orders
                                elif (buyOrdersCount > CONFIG['gridSize'] and 'id' in minBuy):
                                    for i in range(buyOrdersCount - CONFIG['gridSize']):
                                        print('- + removed min buy')
                                        exec_queue.append((REMOVE_LIMIT_ORDER, buyOrders[i]['id']))
                                lastSeenBuyOrder = None
                                for bo in buyOrders:
                                    if lastSeenBuyOrder:
                                        lastBuyOrderPrice = float(lastSeenBuyOrder['price'])
                                        diff = float(bo['price']) - lastBuyOrderPrice
                                        # Filling buy orders gaps # TODO loop ?
                                        if (diff > CONFIG['interval'] + margin):
                                            print('+ + filled buy gap')
                                            exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], lastBuyOrderPrice + CONFIG['interval']))
                                        # Removing duplicated buy orders
                                        elif (diff < CONFIG['interval'] - margin):
                                            print('x + removed misplaced buy')
                                            exec_queue.append((REMOVE_LIMIT_ORDER, bo['id']))
                                    lastSeenBuyOrder = bo
                            # Handle sell orders
                            sellOrders.sort(key=lambda k: k['price'])
                            maxSell = sellOrders[sellOrdersCount - 1]
                            if ('price' in maxSell and lastOrder and 'price' in lastOrder and lastOrder['price']):
                                maxSellOrderPrice = float(maxSell['price'])
                                # TODO improve
                                # if (isInitComplete):
                                # Adding extreme sell orders
                                if (sellOrdersCount < CONFIG['gridSize']):
                                    for i in range(CONFIG['gridSize'] - sellOrdersCount):
                                        print('+ - added max sell')
                                        exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], maxSellOrderPrice + (CONFIG['interval']) * (i + 1)))
                                # Removing extreme sell orders
                                elif (sellOrdersCount > CONFIG['gridSize'] and 'id' in maxSell):
                                    for i in range(sellOrdersCount - CONFIG['gridSize']):
                                        print('- - remove max sell')
                                        exec_queue.append((REMOVE_LIMIT_ORDER, maxSell['id']))
                                lastSeenSellOrder = None
                                for so in sellOrders:
                                    if lastSeenSellOrder:
                                        lastSellOrderPrice = float(lastSeenSellOrder['price'])
                                        diff = float(so['price']) - lastSellOrderPrice
                                        # Filling sell orders gaps
                                        if (diff > CONFIG['interval'] + margin):
                                            print('- - filled sell gap')
                                            exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], float(so['price']) - CONFIG['interval']))
                                        # Removing duplicated sell orders
                                        elif (diff < CONFIG['interval'] - margin):
                                            print('x + removed misplaced sell')
                                            exec_queue.append((REMOVE_LIMIT_ORDER, so['id']))
                                    lastSeenSellOrder = so
                elif (event[0] == CREATE_MARKET_ORDER):
                    if ('amount' in event[1]):
                        amount = amount + event[1]['amount']
                        lastOrder = event[1]
                elif (event[0] == POSITION):
                    # print(f'Current position {format_log(event[1])}')
                    if not event[1] or ('side' in event[1] and event[1]['side'] == 'sell') or ('netSize' in event[1] and float(event[1]['netSize']) < minContractSize):
                        exec_queue.appendleft((GRID_INIT, CONFIG['market']))
                    else:
                        position = event[1]
                        net = float(event[1]['netSize'])
                        if (amount != net):
                            print(f'updating current amount ({amount} -> {net})')
                            amount = net
                        # print(position)
                elif (event[0] == GRID_UPDATE):
                    # print(f'Event from websocket {formatLog(event[1])}')
                    if ('type' in event[1] and 'side' in event[1] and 'status' in event[1] and 'filledSize' in event[1] and event[1]['type'] == 'limit' and event[1]['status'] == 'closed' and event[1]['filledSize'] != 0):
                        lastOrder = event[1]
                        if (event[1]['side'] == 'buy'):
                            print('+ bought')
                            amount = amount + event[1]['filledSize']
                            exec_queue.appendleft((CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], event[1]['price'] + CONFIG['interval']))
                        elif (event[1]['side'] == 'sell'):
                            print('- sold')
                            amount = amount - event[1]['filledSize']
                            if (amount < minContractSize):
                                exec_queue.appendleft((GRID_INIT, CONFIG['market']))
                            else:
                                exec_queue.appendleft((CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], event[1]['price'] - CONFIG['interval']))
                elif (event[0] == GRID_INIT):
                    if (isInitComplete):
                        print('grid init')
                        isInitComplete = False
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
                                amount = CONFIG['buyQty']

                            lastOrder = None
                            if len(event) == 3:
                                exec_queue.append((CREATE_MARKET_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty']))
                            price = (event[1]['ask'] + event[1]['bid']) / 2
                            CONFIG['interval'] = price / 100 * CONFIG['gridStep']
                            margin = CONFIG['interval'] * 0.05
                            for i in range(1, CONFIG['gridSize'] + 1):
                                exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'buy', CONFIG['buyQty'], price - (CONFIG['interval'] * i)))
                                exec_queue.append((CREATE_LIMIT_ORDER, CONFIG['market'], 'sell', CONFIG['sellQty'], price + (CONFIG['interval'] * i)))
                            exec_queue.append((GRID_INIT_COMPLETED, CONFIG['market']))
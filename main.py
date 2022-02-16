import collections, json, os, time, hmac
import ccxt
from websocket import WebSocketApp
from threading import Thread, Lock
from dotenv import load_dotenv

# Config
load_dotenv()

config = {
    'market': os.getenv('MARKET'),
    'gridSize': int(os.getenv('GRID_SIZE')),
    'buyQty': int(os.getenv('BASE_ORDER_SIZE')) * float(os.getenv('BUYING_RATIO')),
    'sellQty': int(os.getenv('BASE_ORDER_SIZE')) * float(os.getenv('SELLING_RATIO')),
    'gridStep': float(os.getenv('GRID_STEP'))
}

# Events
ORDERS = 'orders'
POSITION = 'position'
CREATE_MARKET_ORDER = 'create_market_order'
REMOVE_MARKET_ORDER = 'remove_market_order'
CREATE_LIMIT_ORDER = 'create_limit_order'
REMOVE_LIMIT_ORDER = 'remove_limit_order'
REMOVE_ALL_LIMIT_ORDERS = 'remove_all_limit_orders'
GRID_UPDATE = 'grid_update'
GRID_INIT = 'grid_init'

# Workers
exec_queue = collections.deque()
event_queue = collections.deque()

lastIdUsed = 0
lock = Lock()
sessions = [ccxt.ftx({
    'apiKey': os.getenv('FTX_KEY'),
    'secret': os.getenv('FTX_SECRET'),
    'headers': { 'FTX-SUBACCOUNT': os.getenv('FTX_SUBACCOUNT') },
})]

def getSession():
    global lastIdUsed
    if not lastIdUsed:
        lastIdUsed = 0
    with lock:
        if (lastIdUsed == len(sessions) - 1):
            lastIdUsed = 0
            return sessions[lastIdUsed]
        else:
            lastIdUsed = lastIdUsed + 1
            return sessions[lastIdUsed]

def ftxRestWorker(exec_queue, event_queue):
    while True:
        if (len(exec_queue)):
            ex = exec_queue.popleft()
            try:
                if (len(ex) == 2 and ex[0] == ORDERS):
                    orders = getSession().fetchOpenOrders(ex[1])
                    event_queue.append((ORDERS, orders))
                elif (len(ex) == 2 and ex[0] == POSITION):
                    positions = getSession().fetchPositions()
                    for position in positions:
                        if ('info' in position and 'future' in position['info'] and position['info']['future'] == ex[1]):
                            event_queue.append((POSITION, position['info']))
                elif (len(ex) == 4 and ex[0] == CREATE_MARKET_ORDER):
                    order = getSession().createOrder(ex[1], 'market', ex[2], ex[3])
                    event_queue.append((CREATE_MARKET_ORDER, order))
                elif (len(ex) == 5 and ex[0] == CREATE_LIMIT_ORDER):
                    order = getSession().createOrder(ex[1], 'limit', ex[2], ex[3], ex[4])
                    event_queue.append((CREATE_LIMIT_ORDER, order))
                elif (len(ex) == 2 and ex[0] == GRID_INIT):
                    ticker = getSession().fetchTicker(ex[1])
                    event_queue.append((GRID_INIT, ticker))
                elif (len(ex) == 2 and ex[0] == REMOVE_MARKET_ORDER):
                    positions = getSession().fetchPositions()
                    for position in positions:
                        if ('info' in position and 'side' in position['info'] and 'size' in position['info'] and 'future' in position['info'] and position['info']['future'] == ex[1]):
                            side = 'buy' if position['info']['side'] == 'sell' else 'sell'
                            getSession().createOrder(ex[1], 'market', side, position['info']['size'])
                    event_queue.append((REMOVE_MARKET_ORDER))
                elif (len(ex) == 2 and ex[0] == REMOVE_LIMIT_ORDER):
                    getSession().cancelOrder(ex[1])
                    event_queue.append((REMOVE_LIMIT_ORDER))
                elif (len(ex) == 2 and ex[0] == REMOVE_ALL_LIMIT_ORDERS):
                    getSession().cancelAllOrders(ex[1])
                    event_queue.append((REMOVE_ALL_LIMIT_ORDERS))
                time.sleep(0.25 / len(sessions))
            except Exception as e:
                print(f'FtxRestWorker exception : {e}')

def gridWorker(exec_queue, event_queue):
    ticker = getSession().fetchTicker(config['market'])
    minContractSize = float(ticker['info']['minProvideSize'])
    position = {}
    amount = 0
    lastOrder = None
    while True:
        if (len(event_queue)):
            event = event_queue.popleft()
            # if (len(event) == 2):
            if (event[0] == ORDERS):

                # TODO if no more buy / sell orders -> reset grid

                # TODO if minSell - maxBuy > 2 * interval for N iterations -> add one order

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
                    # Handle buy orders
                    if (buyOrdersCount > 0):
                        buyOrders.sort(key=lambda k : k['price'])
                        minBuy = buyOrders[0]
                        if ('price' in minBuy and lastOrder and 'price' in lastOrder and lastOrder['price']): # lastOrder['price'] can be None with market order
                            expectedMinBuyOrderPrice = lastOrder['price'] - (config['gridSize'] * config['interval'])
                            minBuyOrderPrice = float(minBuy['price'])
                            # TODO replace by a loop if many orders are missing ?
                            if (expectedMinBuyOrderPrice < minBuyOrderPrice and minBuyOrderPrice - expectedMinBuyOrderPrice > config['interval'] + (config['interval'] * 0.05)):
                                print('+ + added min buy order')
                                exec_queue.append((CREATE_LIMIT_ORDER, config['market'], 'buy', config['buyQty'], minBuyOrderPrice - config['interval']))
                            # TODO improve
                            elif (buyOrdersCount > config['gridSize'] and 'id' in minBuy):
                                print('- + removed min buy order')
                                exec_queue.append((REMOVE_LIMIT_ORDER, minBuy['id']))
                            lastSeenBuyOrder = None
                            for bo in buyOrders:
                                if lastSeenBuyOrder:
                                    diff = float(bo['price']) - float(lastSeenBuyOrder['price'])
                                    margin = config['interval'] - (config['interval'] * 0.05)
                                    if (diff < margin):
                                        print('x + Removing misplaced / duplicated buy order')
                                        exec_queue.append((REMOVE_LIMIT_ORDER, bo['id']))
                                    # TODO add missing orders
                                lastSeenBuyOrder = bo
                    # Handle sell orders
                    if (sellOrdersCount > 0):
                        sellOrders.sort(key=lambda k : k['price'])
                        maxSell = sellOrders[sellOrdersCount - 1]
                        if ('price' in maxSell and lastOrder and 'price' in lastOrder and lastOrder['price']):
                            expectedMaxSellOrderPrice = lastOrder['price'] + (config['gridSize'] * config['interval'])
                            maxSellOrderPrice = float(maxSell['price'])
                            # TODO replace by a loop if many orders are missing ?
                            if (expectedMaxSellOrderPrice > maxSellOrderPrice and expectedMaxSellOrderPrice - maxSellOrderPrice > config['interval'] + (config['interval'] * 0.05)):
                                print('+ - added max sell order')
                                exec_queue.append((CREATE_LIMIT_ORDER, config['market'], 'sell', config['sellQty'], maxSellOrderPrice + config['interval']))
                            # TODO improve
                            elif (sellOrdersCount > config['gridSize'] and 'id' in maxSell):
                                print('- - remove max sell order')
                                exec_queue.append((REMOVE_LIMIT_ORDER, maxSell['id']))
                            lastSeenSellOrder = None
                            for so in sellOrders:
                                if lastSeenSellOrder:
                                    diff = float(so['price']) - float(lastSeenSellOrder['price'])
                                    margin = config['interval'] + (config['interval'] * 0.05)
                                    if (diff > margin):
                                        print('x + Removing misplaced / duplicated sell order')
                                        exec_queue.append((REMOVE_LIMIT_ORDER, bo['id']))
                                    # TODO add missing orders
                                lastSeenSellOrder = so
            elif (event[0] == CREATE_MARKET_ORDER):
                if ('amount' in event[1]):
                    amount = amount + event[1]['amount']
                    lastOrder = event[1]
            elif (event[0] == POSITION):
                # print(f'Current position {formatLog(event[1])}')
                if not event[1] or ('side' in event[1] and event[1]['side'] == 'sell') or ('netSize' in event[1] and float(event[1]['netSize']) < minContractSize):
                    exec_queue.appendleft((GRID_INIT, config['market']))
                else:
                    position = event[1]
                    net = float(event[1]['netSize'])
                    if (amount != net):
                        amount = net
                        print('diff between amount and live position')
                    # print(position)
            elif (event[0] == GRID_UPDATE):
                # print(f'Event from websocket {formatLog(event[1])}')
                if ('type' in event[1] and 'side' in event[1] and 'status' in event[1] and 'filledSize' in event[1] and event[1]['type'] == 'limit' and event[1]['status'] == 'closed' and event[1]['filledSize'] != 0):
                    lastOrder = event[1]
                    if (event[1]['side'] == 'buy'):
                        print('+ bought')
                        amount = amount + event[1]['filledSize']
                        exec_queue.appendleft((CREATE_LIMIT_ORDER, config['market'], 'sell', config['sellQty'], event[1]['price'] + config['interval']))
                    elif (event[1]['side'] == 'sell'):
                        print('- sold')
                        amount = amount - event[1]['filledSize']
                        if (amount < minContractSize):
                            exec_queue.appendleft((GRID_INIT, config['market']))
                        else:
                            exec_queue.appendleft((CREATE_LIMIT_ORDER, config['market'], 'buy', config['buyQty'], event[1]['price'] - config['interval']))
            elif (event[0] == GRID_INIT):
                print('grid reset')
                event_queue.clear()
                exec_queue.clear()
                if ('ask' in event[1] and 'bid' in event[1]):
                    # print(f'Ticker {formatLog(event[1])}')
                    exec_queue.append((REMOVE_ALL_LIMIT_ORDERS, config['market']))
                    exec_queue.append((REMOVE_MARKET_ORDER, config['market']))
                    time.sleep(3) # Let FTX remove all pending orders
                    amount = 0
                    lastOrder = None
                    exec_queue.append((CREATE_MARKET_ORDER, config['market'], 'buy', config['buyQty']))
                    price = (event[1]['ask'] + event[1]['bid']) / 2
                    config['interval'] = price / 100 * config['gridStep']
                    for i in range(1, config['gridSize'] + 1):
                        exec_queue.append((CREATE_LIMIT_ORDER, config['market'], 'buy', config['buyQty'], price - (config['interval'] * i)))
                        exec_queue.append((CREATE_LIMIT_ORDER, config['market'], 'sell', config['sellQty'], price + (config['interval'] * i)))

def formatLog(obj):
    return json.dumps(obj, indent=4, sort_keys=True)

def on_open(ws):
    print('Socket opened')
    ts = int(time.time() * 1000)
    ws.send(json.dumps({ 
        'op': 'login',
        'args': {
            'key': os.getenv('FTX_KEY'),
            'sign': hmac.new(
                os.getenv('FTX_SECRET').encode(), f'{ts}websocket_login'.encode(), 'sha256').hexdigest(),
            'time': ts,
            'subaccount': os.getenv('FTX_SUBACCOUNT')
        }
    }))
    ws.send(json.dumps({ 'op': 'subscribe', 'channel': 'orders' }))

def on_message(ws, raw):
    message = json.loads(raw)
    if (message['channel'] == 'orders' and message['type'] != 'subscribed'):
        event_queue.append((GRID_UPDATE, message['data']))

def on_error(ws, error):
    print(error)
    ftxWebsocketWorker(ws)

def on_close(ws, close_status_code, close_msg):
    print("Socket closed")

def ftxWebsocketWorker(ws):
    try:
        ws.run_forever(ping_interval=15, ping_timeout=14, ping_payload=json.dumps({ 'op': 'ping' }))
    except Exception as e:
        print(f'FtxSocketWorker exception : {e}')

def positionStateWorker(exec_queue):
    while True:
        exec_queue.append((POSITION, config['market']))
        time.sleep(5)

def ordersStateWorker(exec_queue):
    while True:
        exec_queue.append((ORDERS, config['market']))
        time.sleep(5)

if __name__ == '__main__':

    print(f'Starting service with following config :\n{formatLog(config)}')

    ws = WebSocketApp('wss://ftx.com/ws/',
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error)
    wst = Thread(target = ftxWebsocketWorker, args=(ws, ))
    wst.daemon = True
    rwt = Thread(target = ftxRestWorker)
    pwt = Thread(target = positionStateWorker)
    owt = Thread(target = ordersStateWorker)
    gwt = Thread(target = gridWorker)
    wst.start()
    rwt.start()
    pwt.start()
    owt.start()
    gwt.start()
    exec_queue.append((REMOVE_ALL_LIMIT_ORDERS, config['market']))
    exec_queue.append((REMOVE_MARKET_ORDER, config['market']))
    while True:
        pass
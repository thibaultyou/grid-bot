import json, os, time, hmac
import ccxt
from websocket import WebSocketApp
from threading import Thread
from queue import Queue
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
exec_queue = Queue()
event_queue = Queue()

session = ccxt.ftx({
    'apiKey': os.getenv('FTX_KEY'),
    'secret': os.getenv('FTX_SECRET'),
    'headers': { 'FTX-SUBACCOUNT': os.getenv('FTX_SUBACCOUNT') }, # TODO test if subaccount
})

def ftxRestWorker(exec_queue, event_queue):
    while True:
        ex = exec_queue.get()
        try:
            if (len(ex) == 2 and ex[0] == ORDERS):
                orders = session.fetchOpenOrders(ex[1])
                event_queue.put((ORDERS, orders))
            elif (len(ex) == 2 and ex[0] == POSITION):
                positions = session.fetchPositions()
                for position in positions:
                    if ('info' in position and 'future' in position['info'] and position['info']['future'] == ex[1]):
                        event_queue.put((POSITION, position['info']))
            elif (len(ex) == 4 and ex[0] == CREATE_MARKET_ORDER):
                order = session.createOrder(ex[1], 'market', ex[2], ex[3])
                event_queue.put((CREATE_MARKET_ORDER, order))
            elif (len(ex) == 5 and ex[0] == CREATE_LIMIT_ORDER):
                order = session.createOrder(ex[1], 'limit', ex[2], ex[3], ex[4])
                event_queue.put((CREATE_LIMIT_ORDER, order))
            elif (len(ex) == 2 and ex[0] == GRID_INIT):
                ticker = session.fetchTicker(ex[1])
                event_queue.put((GRID_INIT, ticker))
            elif (len(ex) == 2 and ex[0] == REMOVE_MARKET_ORDER):
                positions = session.fetchPositions()
                for position in positions:
                    if ('info' in position and 'side' in position['info'] and 'size' in position['info'] and 'future' in position['info'] and position['info']['future'] == ex[1]):
                        side = 'buy' if position['info']['side'] == 'sell' else 'sell'
                        session.createOrder(ex[1], 'market', side, position['info']['size'])
                event_queue.put((REMOVE_MARKET_ORDER))
            elif (len(ex) == 2 and ex[0] == REMOVE_LIMIT_ORDER):
                session.cancelOrder(ex[1])
                event_queue.put((REMOVE_LIMIT_ORDER))
            elif (len(ex) == 2 and ex[0] == REMOVE_ALL_LIMIT_ORDERS):
                session.cancelAllOrders(ex[1])
                event_queue.put((REMOVE_ALL_LIMIT_ORDERS))
            time.sleep(0.25)
        except Exception as e:
            print(f'FtxRestWorker exception : {e}')

def gridWorker(exec_queue, event_queue):
    ticker = session.fetchTicker(config['market'])
    minContractSize = float(ticker['info']['minProvideSize'])
    position = {}
    while True:
        event = event_queue.get()
        # if (len(event) == 2):
        if (event[0] == ORDERS):
            if (position and 'longOrderSize' in position and 'shortOrderSize' in position):
                buyOrdersCount = float(position['longOrderSize']) / config['buyQty']
                sellOrdersCount = float(position['shortOrderSize']) / config['sellQty']
                minBuy = { 'price': float("inf") }
                maxSell = { 'price': 0 }
                for order in event[1]:
                    if ('info' in order and 'side' in order['info'] and 'price' in order['info']):
                        if ('price' in minBuy and order['info']['side'] == 'buy' and float(order['info']['price']) < float(minBuy['price'])):
                            minBuy = order['info']
                        elif ('price' in maxSell and order['info']['side'] == 'sell' and float(order['info']['price']) > float(maxSell['price'])):
                            maxSell = order['info']
                if (buyOrdersCount > 0):
                    if (buyOrdersCount < config['gridSize'] and 'price' in minBuy):
                        print('+ +')
                        exec_queue.put((CREATE_LIMIT_ORDER, config['market'], 'buy', config['buyQty'], float(minBuy['price']) - config['interval']))
                    elif (buyOrdersCount > config['gridSize'] and 'id' in minBuy):
                        print('- +')
                        exec_queue.put((REMOVE_LIMIT_ORDER, minBuy['id']))
                if (sellOrdersCount > 0):
                    if (sellOrdersCount < config['gridSize'] and 'price' in maxSell):
                        print('+ -')
                        exec_queue.put((CREATE_LIMIT_ORDER, config['market'], 'sell', config['sellQty'], float(maxSell['price']) + config['interval']))
                    elif (sellOrdersCount > config['gridSize'] and 'id' in maxSell):
                        print('- -')
                        exec_queue.put((REMOVE_LIMIT_ORDER, maxSell['id']))
        elif (event[0] == POSITION):
            # print(f'Current position {formatLog(event[1])}')
            if not event[1] or ('side' in event[1] and event[1]['side'] == 'sell') or ('netSize' in event[1] and float(event[1]['netSize']) < minContractSize):
                exec_queue.put((GRID_INIT, config['market']))
            else:
                position = event[1]
                # print(position)
        elif (event[0] == GRID_UPDATE):
            # print(f'Event from websocket {formatLog(event[1])}')
            if ('type' in event[1] and 'side' in event[1] and 'status' in event[1] and 'filledSize' in event[1] and event[1]['type'] == 'limit' and event[1]['status'] == 'closed' and event[1]['filledSize'] != 0):
                # print(event[1])
                if (event[1]['side'] == 'buy'):
                    print('+')
                    exec_queue.put((CREATE_LIMIT_ORDER, config['market'], 'sell', config['sellQty'], event[1]['price'] + config['interval']))
                elif (event[1]['side'] == 'sell'):
                    print('-')
                    exec_queue.put((CREATE_LIMIT_ORDER, config['market'], 'buy', config['buyQty'], event[1]['price'] - config['interval']))
        elif (event[0] == GRID_INIT):
            print('reset')
            # FIXME TESTING #
            if ('ask' in event[1] and 'bid' in event[1]):
                # with exec_queue.mutex:
                exec_queue.queue.clear()
                # print(f'Ticker {formatLog(event[1])}')
                exec_queue.put((REMOVE_ALL_LIMIT_ORDERS, config['market']))
                exec_queue.put((REMOVE_MARKET_ORDER, config['market']))
                time.sleep(3) # Let FTX remove all pending orders
                exec_queue.put((CREATE_MARKET_ORDER, config['market'], 'buy', config['buyQty']))
                price = (event[1]['ask'] + event[1]['bid']) / 2
                config['interval'] = price / 100 * config['gridStep']
                for i in range(1, config['gridSize'] + 1):
                    exec_queue.put((CREATE_LIMIT_ORDER, config['market'], 'buy', config['buyQty'], price - (config['interval'] * i)))
                    exec_queue.put((CREATE_LIMIT_ORDER, config['market'], 'sell', config['sellQty'], price + (config['interval'] * i)))

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
        event_queue.put((GRID_UPDATE, message['data']))

def on_error(ws, error):
    print(error)
    connect_websocket(ws)

def on_close(ws, close_status_code, close_msg):
    print("Socket closed")

def run_forever(ws):
    try:
        ws.run_forever(ping_interval=15, ping_timeout=14, ping_payload=json.dumps({ 'op': 'ping' }))
    except Exception as e:
        print(f'FtxSocketWorker exception : {e}')

def connect_websocket(event_queue):
    ws = WebSocketApp('wss://ftx.com/ws/',
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error)
    wst = Thread(target=run_forever, args=(ws, ))
    wst.daemon = True
    wst.start()

if __name__ == '__main__':

    print(f'Starting service with following config :\n{formatLog(config)}')
    connect_websocket(event_queue)
    # ws = Thread(target = ftxWsWorker, args=(event_queue, ))
    # ws.daemon = True
    # ws.start()
    rest = Thread(target = ftxRestWorker, args=(exec_queue, event_queue, ))
    rest.start()
    grid = Thread(target = gridWorker, args=(exec_queue, event_queue, ))
    grid.start()
    exec_queue.put((REMOVE_ALL_LIMIT_ORDERS, config['market']))
    exec_queue.put((REMOVE_MARKET_ORDER, config['market']))
    while True:
        time.sleep(1)
        exec_queue.put((POSITION, config['market']))
        exec_queue.put((ORDERS, config['market']))
        pass
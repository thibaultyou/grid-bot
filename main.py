import json, os, time, hmac, websocket, copy
import ccxt
from threading import Thread, Lock
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
session = ccxt.ftx({
    'apiKey': os.getenv('FTX_KEY'),
    'secret': os.getenv('FTX_SECRET'),
    'headers': { 'FTX-SUBACCOUNT': os.getenv('FTX_SUBACCOUNT') }, # TODO test if subaccount
})

def ftxRestWorker(exec_queue, event_queue):
    while True:
        ex = exec_queue.get()
        try:
            if (ex[0] == ORDERS):
                orders = session.fetchOpenOrders(ex[1])
                event_queue.put((ORDERS, orders))
            elif (ex[0] == POSITION):
                positions = session.fetchPositions()
                for position in positions:
                    if (position['info']['future'] == ex[1]):
                        event_queue.put((POSITION, position['info']))
            elif (ex[0] == CREATE_MARKET_ORDER):
                order = session.createOrder(ex[1], 'market', ex[2], ex[3])
                event_queue.put((CREATE_MARKET_ORDER, order))
            elif (ex[0] == CREATE_LIMIT_ORDER):
                order = session.createOrder(ex[1], 'limit', ex[2], ex[3], ex[4])
                event_queue.put((CREATE_LIMIT_ORDER, order))
            elif (ex[0] == GRID_INIT):
                ticker = session.fetchTicker(ex[1])
                event_queue.put((GRID_INIT, ticker))
            elif (ex[0] == REMOVE_MARKET_ORDER):
                positions = session.fetchPositions()
                for position in positions:
                    if (position['info']['future'] == ex[1]):
                        side = 'buy' if position['info']['side'] == 'sell' else 'sell'
                        session.createOrder(ex[1], 'market', side, position['info']['size'])
                event_queue.put((REMOVE_MARKET_ORDER))
            elif (ex[0] == REMOVE_LIMIT_ORDER):
                # TODO
                event_queue.put((REMOVE_LIMIT_ORDER))
            elif (ex[0] == REMOVE_ALL_LIMIT_ORDERS):
                session.cancelAllOrders(ex[1])
                event_queue.put((REMOVE_ALL_LIMIT_ORDERS))
            time.sleep(0.3)
        except Exception as e:
            print(f'An exception occurred : {e}')

def gridWorker(exec_queue, event_queue):
    orders = []
    position = {}
    while True:
        event = event_queue.get()
        if (event[0] == ORDERS):
            orders = event[1]
            # TODO something with ordersc
        elif (event[0] == POSITION):
            # print(f'Current position {formatLog(event[1])}')
            if not event[1] or event[1]['side'] == 'sell' or float(event[1]['netSize']) < config['buyQty']:
                exec_queue.put((GRID_INIT, config['market']))
            else:
                position = event[1]
                print(position)
            # if (position['netSize'] != event[1]['netSize']):
            #     position = event[1]
            #     print(json.dumps(position, indent=4, sort_keys=True))
            #     print('Grid update needed')
        # elif (event[0] == LIMIT_ORDER):
            # print(f'Limit order placed {formatLog(event[1])}')
        # elif (event[0] == MARKET_ORDER):
            # print(f'Market bought {formatLog(event[1])}')
        elif (event[0] == GRID_UPDATE):
            print(f'Event from websocket {formatLog(event[1])}')
        elif (event[0] == GRID_INIT):
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
        # print(orders)

def formatLog(obj):
    return json.dumps(obj, indent=4, sort_keys=True)

class FtxWebsocket:
    def __init__(self, event_queue):
        self.ws = None
        self.event_queue = event_queue;

    def _wrap_callback(self, f):
        def wrapped_f(ws, *args, **kwargs):
            if ws is self.ws:
                try:
                    f(ws, *args, **kwargs)
                except Exception as e:
                    raise Exception(f'Error running websocket callback: {e}')
        return wrapped_f

    def connect(self):
        self.ws = websocket.WebSocketApp('wss://ftx.com/ws/',
        on_open=self._wrap_callback(self.on_open),
        on_message=self._wrap_callback(self.on_message),
        on_close=self._wrap_callback(self.on_close),
        on_error=self._wrap_callback(self.on_error),
        on_ping=self._wrap_callback(self.on_ping),
        on_pong=self._wrap_callback(self.on_pong))
        self.ws.run_forever(ping_interval=60, ping_timeout=10, ping_payload="ping")

    def login(self):
        ts = int(time.time() * 1000)
        self.send({ 
            'op': 'login',
            'args': {
                'key': os.getenv('FTX_KEY'),
                'sign': hmac.new(
                    os.getenv('FTX_SECRET').encode(), f'{ts}websocket_login'.encode(), 'sha256').hexdigest(),
                'time': ts,
                'subaccount': os.getenv('FTX_SUBACCOUNT')
            }
        })
        self.send({ 'op': 'subscribe', 'channel': 'orders' })

    def reconnect(self, ws):
        print('Reconnecting socket')
        assert ws is not None, '_reconnect should only be called with an existing ws'
        if ws is self.ws:
            self.ws = None
            ws.close()
            self.connect()

    def on_message(self, ws, raw):
        message = json.loads(raw)
        if (message['channel'] == 'orders' and message['type'] != 'subscribed'):
            self.event_queue.put((GRID_UPDATE, message['data']))

    def on_error(self, ws, error):
        print(error)
        self.reconnect(ws)

    def on_close(self, ws, close_status_code, close_msg):
        print("Socket closed")
        self.reconnect(ws)

    def on_open(self, ws):
        print('Socket opened')
        self.login()

    def on_ping(self, ws, message):
        print("Ping !")

    def on_pong(self, ws, message):
        print("Pong !")

    def send_json(self, message):
        self.ws.send(json.dumps(message))

    def send(self, message):
        # self.connect()
        self.send_json(message)

def ftxWsWorker(event_queue):
    # websocket.enableTrace(True)
    ws = FtxWebsocket(event_queue)
    ws.connect()

if __name__ == '__main__':

    print(f'Starting service with following config :\n{formatLog(config)}')

    exec_queue = Queue()
    event_queue = Queue()
    ws = Thread(target = ftxWsWorker, args=(event_queue, ))
    ws.daemon = True
    ws.start()
    rest = Thread(target = ftxRestWorker, args=(exec_queue, event_queue, ))
    rest.start()
    grid = Thread(target = gridWorker, args=(exec_queue, event_queue, ))
    grid.start()
    while True:
        # exec_exec_queue.put((ORDERS, config['market']))
        exec_queue.put((POSITION, config['market']))
        time.sleep(5)
        pass
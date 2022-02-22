import json
import os
import time
import hmac
from collections import deque
from threading import Thread, Lock
from websocket import WebSocketApp
from src.config import CONFIG
from src.events import GRID_UPDATE

# Credits here https://github.com/ftexchange/ftx/tree/master/websocket
class WebsocketWorker:
    _CONNECT_TIMEOUT_S = 5

    def __init__(self):
        self.connect_lock = Lock()
        self.ws = None

    def send(self, message):
        self.connect()
        self.ws.send(message)

    def send_json(self, message):
        self.send(json.dumps(message))

    def _connect(self, event_queue):
        assert not self.ws, "ws should be closed before attempting to connect"

        self.ws = WebSocketApp(
            'wss://ftx.com/ws/',
            on_open=self._wrap_callback(self.on_open),
            on_message=self._wrap_callback(self._on_message, event_queue),
            on_close=self._wrap_callback(self._on_close),
            on_error=self._wrap_callback(self._on_error),
        )

        wst = Thread(target=self._run_websocket, args=(self.ws,))
        wst.daemon = True
        wst.start()

        # Wait for socket to connect
        ts = time.time()
        while self.ws and (not self.ws.sock or not self.ws.sock.connected):
            if time.time() - ts > self._CONNECT_TIMEOUT_S:
                self.ws = None
                return
            time.sleep(0.1)

    def _wrap_callback(self, f, optional = None):
        def wrapped_f(ws, *args, **kwargs):
            if ws is self.ws:
                try:
                    if type(optional) is deque:
                        f(ws, *args, optional, **kwargs)
                    else:
                        f(ws, *args, **kwargs)
                except Exception as e:
                    raise Exception(f'Error running websocket callback: {e}')
        return wrapped_f

    def _run_websocket(self, ws):
        try:
            ws.run_forever(ping_interval=15, ping_timeout=14,
                    ping_payload=json.dumps({'op': 'ping'}))
        except Exception as e:
            raise Exception(f'Unexpected error while running websocket: {e}')
        finally:
            self._reconnect(ws)

    def _reconnect(self, ws):
        assert ws is not None, '_reconnect should only be called with an existing ws'
        if ws is self.ws:
            self.ws = None
            ws.close()
            self.connect()

    def start(self, event_queue):
        if self.ws:
            return
        with self.connect_lock:
            while not self.ws:
                self._connect(event_queue)
                if self.ws:
                    return

    def on_open(self, ws):
        print('Socket opened')
        ts = int(time.time() * 1000)
        ws.send(json.dumps({
            'op': 'login',
            'args': {
                'key': os.getenv('FTX_KEY_1'),
                'sign': hmac.new(
                    os.getenv('FTX_SECRET_1').encode(), f'{ts}websocket_login'.encode(), 'sha256').hexdigest(),
                'time': ts,
                'subaccount': os.getenv('FTX_SUBACCOUNT')
            }
        }))
        ws.send(json.dumps({'op': 'subscribe', 'channel': 'orders'}))

    def _on_message(self, ws, raw, event_queue):
        message = json.loads(raw)
        if (message['channel'] == 'orders' and message['type'] != 'subscribed' and message['data']['market'] == CONFIG['market']):
            event_queue.append((GRID_UPDATE, message['data']))

    def _on_close(self, ws):
        print('Socket closed')
        self._reconnect(ws)

    def _on_error(self, ws, error):
        print(f'Socket error : {error}')
        self._reconnect(ws)

    def reconnect(self) -> None:
        if self.ws is not None:
            self._reconnect(self.ws)
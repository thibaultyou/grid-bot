import collections
from src.config import CONFIG
from src.events import REMOVE_ALL_LIMIT_ORDERS
from src.log import format_log
from src.grid import GridWorker
from src.rest import RestWorker
from src.ws import WebsocketWorker
from src.orders import OrdersWorker
from src.positions import PositionsWorker

# Working queues
global exec_queue
exec_queue = collections.deque()
global event_queue
event_queue = collections.deque()

if __name__ == '__main__':
    print(f'Starting service with following config :\n{format_log(CONFIG)}')
    # Workers
    ws = WebsocketWorker()
    rw = RestWorker()
    gw = GridWorker()
    pw = PositionsWorker()
    ow = OrdersWorker()
    gw.start(exec_queue, event_queue)
    ws.start(event_queue)
    rw.start(exec_queue, event_queue)
    pw.start(exec_queue)
    ow.start(exec_queue)
    # Reset grid on init without closing current position
    exec_queue.append((REMOVE_ALL_LIMIT_ORDERS, CONFIG['market']))
    while True:
        pass

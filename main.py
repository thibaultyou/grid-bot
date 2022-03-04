import collections
import logging
import time
import sys
from src.config import CONFIG
from src.events import REMOVE_ALL_LIMIT_ORDERS
from src.log import format_log
from src.grid import GridWorker
from src.rest import RestWorker
from src.ws import WebsocketWorker
from src.orders import OrdersWorker
from src.positions import PositionsWorker


global executions
global events
executions = collections.deque()
events = collections.deque()

if __name__ == '__main__':
    logging.basicConfig(handlers=[logging.FileHandler(filename=f'./logs/{CONFIG["market"]}.log', encoding='utf-8', mode='a')], format='%(asctime)s %(message)s', level=logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    logging.info(f'Starting service with following config:\n{format_log(CONFIG)}')
    # Workers
    ws = WebsocketWorker()
    rw = RestWorker()
    gw = GridWorker()
    pw = PositionsWorker()
    ow = OrdersWorker()
    gw.start(executions, events)
    ws.connect(events)
    rw.start(executions, events)
    pw.start(executions)
    ow.start(executions)

    executions.append((REMOVE_ALL_LIMIT_ORDERS, CONFIG['market']))
    while True:
        time.sleep(0.05)
        pass

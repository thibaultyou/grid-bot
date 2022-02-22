from threading import Thread
import time
from src.config import CONFIG
from src.events import ORDERS


class OrdersWorker:

    def start(self, exec_queue):
        t = Thread(target=self._run, args=(exec_queue,))
        t.start()
    
    def _run(self, exec_queue):
        while True:
            exec_queue.append((ORDERS, CONFIG['market']))
            time.sleep(10)
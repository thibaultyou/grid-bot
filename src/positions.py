from threading import Thread
import time
from src.config import CONFIG
from src.events import POSITION


class PositionsWorker:

    def start(self, exec_queue):
        t = Thread(target=self._run, args=(exec_queue,))
        t.start()
    
    def _run(self, exec_queue):
        exec = (POSITION, CONFIG['market'])
        while True:
            if (exec not in exec_queue):
                exec_queue.append(exec)
            time.sleep(5)
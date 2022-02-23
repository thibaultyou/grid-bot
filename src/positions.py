from threading import Thread
import time
from src.config import CONFIG
from src.events import POSITION, fire_event


class PositionsWorker:

    def start(self, executions):
        t = Thread(target=self._run, args=(executions,))
        t.start()
    
    def _run(self, executions):
        while True:
            fire_event(executions, (POSITION, CONFIG['market']))
            time.sleep(5)
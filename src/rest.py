import logging
import time
from threading import Thread
from src.events import CREATE_LIMIT_ORDER, CREATE_MARKET_ORDER, GRID_INIT, GRID_RESET, ORDERS, POSITION, REMOVE_ALL_LIMIT_ORDERS, REMOVE_LIMIT_ORDER, REMOVE_MARKET_ORDER
from src.sessions import SESSIONS, get_session


class RestWorker:

    def start(self, executions, events):
        t = Thread(target=self._run, args=(executions, events))
        t.start()
    
    # TODO improve
    def _run(self, executions, events):
        while True:
            if (len(executions)):
                # print(executions)
                ex = executions.popleft()
                try:
                    if (len(ex) == 2 and ex[0] == ORDERS):
                        orders = get_session().fetchOpenOrders(ex[1])
                        events.append((ORDERS, orders))
                    elif (len(ex) == 2 and ex[0] == POSITION):
                        positions = get_session().fetchPositions()
                        for position in positions:
                            if ('info' in position and 'future' in position['info'] and position['info']['future'] == ex[1]):
                                events.append((POSITION, position['info']))
                        if (len(positions) == 0):
                            events.append((POSITION, None))
                    elif (len(ex) == 4 and ex[0] == CREATE_MARKET_ORDER):
                        order = get_session().createOrder(
                            ex[1], 'market', ex[2], ex[3])
                        events.append((CREATE_MARKET_ORDER, order))
                    elif (len(ex) == 5 and ex[0] == CREATE_LIMIT_ORDER):
                        order = get_session().createOrder(
                            ex[1], 'limit', ex[2], ex[3], ex[4])
                        events.append((CREATE_LIMIT_ORDER, order))
                    elif (len(ex) == 2 and (ex[0] == GRID_INIT or ex[0] == GRID_RESET)):
                        positions = get_session().fetchPositions()
                        position = None
                        # TODO improve
                        for p in positions:
                            if ('info' in p and 'future' in p['info'] and p['info']['future'] == ex[1]):
                                position = p['info']
                        time.sleep(0.25 / len(SESSIONS))
                        ticker = get_session().fetchTicker(ex[1])
                        if (ex[0] == GRID_RESET):
                            events.append((GRID_INIT, ticker, position, True))
                        else:
                            events.append((GRID_INIT, ticker, position))
                    elif (len(ex) == 2 and ex[0] == REMOVE_MARKET_ORDER):
                        positions = get_session().fetchPositions()
                        for position in positions:
                            if ('info' in position and 'side' in position['info'] and 'size' in position['info'] and 'future' in position['info'] and position['info']['future'] == ex[1]):
                                side = 'buy' if position['info']['side'] == 'sell' else 'sell'
                                get_session().createOrder(
                                    ex[1], 'market', side, position['info']['size'])
                        events.append((REMOVE_MARKET_ORDER))
                    elif (len(ex) == 2 and ex[0] == REMOVE_LIMIT_ORDER):
                        get_session().cancelOrder(ex[1])
                        events.append((REMOVE_LIMIT_ORDER))
                    elif (len(ex) == 2 and ex[0] == REMOVE_ALL_LIMIT_ORDERS):
                        get_session().cancelAllOrders(ex[1])
                        events.append((REMOVE_ALL_LIMIT_ORDERS))
                    time.sleep(0.25 / len(SESSIONS))
                except Exception as e:
                    logging.error(f'FtxRestWorker exception: {e}')
            time.sleep(0.05)
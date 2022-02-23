import os
from threading import Lock
import ccxt

lock = Lock()

SESSIONS = [ccxt.ftx({
    'apiKey': os.getenv('FTX_KEY_1'),
    'secret': os.getenv('FTX_SECRET_1'),
    'headers': {'FTX-SUBACCOUNT': os.getenv('FTX_SUBACCOUNT')},
}), ccxt.ftx({
    'apiKey': os.getenv('FTX_KEY_2'),
    'secret': os.getenv('FTX_SECRET_2'),
    'headers': {'FTX-SUBACCOUNT': os.getenv('FTX_SUBACCOUNT')},
}), ccxt.ftx({
    'apiKey': os.getenv('FTX_KEY_3'),
    'secret': os.getenv('FTX_SECRET_3'),
    'headers': {'FTX-SUBACCOUNT': os.getenv('FTX_SUBACCOUNT')},
}), ccxt.ftx({
    'apiKey': os.getenv('FTX_KEY_4'),
    'secret': os.getenv('FTX_SECRET_4'),
    'headers': {'FTX-SUBACCOUNT': os.getenv('FTX_SUBACCOUNT')},
})]

lastIdUsed = 0

def get_session():
    global lastIdUsed
    with lock:
        if (lastIdUsed == len(SESSIONS) - 1):
            lastIdUsed = 0
            return SESSIONS[lastIdUsed]
        else:
            lastIdUsed = lastIdUsed + 1
            return SESSIONS[lastIdUsed]
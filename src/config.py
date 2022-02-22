import os
from dotenv import load_dotenv

load_dotenv()

global CONFIG
CONFIG = {
    'market': os.getenv('MARKET'),
    'gridSize': int(os.getenv('GRID_SIZE')),
    'buyQty': int(os.getenv('BASE_ORDER_SIZE')) * float(os.getenv('BUYING_RATIO')),
    'sellQty': int(os.getenv('BASE_ORDER_SIZE')) * float(os.getenv('SELLING_RATIO')),
    'gridStep': float(os.getenv('GRID_STEP'))
}
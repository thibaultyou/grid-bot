ORDERS = 'orders'
POSITION = 'position'
CREATE_MARKET_ORDER = 'create_market_order'
REMOVE_MARKET_ORDER = 'remove_market_order'
CREATE_LIMIT_ORDER = 'create_limit_order'
REMOVE_LIMIT_ORDER = 'remove_limit_order'
REMOVE_ALL_LIMIT_ORDERS = 'remove_all_limit_orders'
GRID_UPDATE = 'grid_update'
GRID_INIT = 'grid_init'
GRID_RESET = 'grid_reset'

def fire_event_asap(deque, event):
    if (event not in deque):
        deque.appendleft(event)

def fire_event(deque, event):
    if (event not in deque):
        deque.append(event)
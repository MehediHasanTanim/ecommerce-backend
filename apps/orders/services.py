from common.uow import UnitOfWork

def place_order(order_data, cart_data):
    with UnitOfWork(action_name="place_order"):
        order = create_order(order_data)
        create_order_items(order, cart_data)
        reserve_stock(order)
        create_payment_record(order, order_data)
        clear_cart(cart_data)
        create_audit_log("order_placed", order)

    return order

def create_order(order_data):
    pass

def create_order_items(order, cart_data):
    pass

def reserve_stock(order):
    pass

def create_payment_record(order, order_data):
    pass

def clear_cart(cart_data):
    pass

def create_audit_log(action, instance):
    pass

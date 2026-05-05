from common.uow import UnitOfWork

def reserve_stock_flow(variant_id, quantity):
    with UnitOfWork(action_name="reserve_stock"):
        decrement_variant_stock(variant_id, quantity)
        create_inventory_log(variant_id, quantity, "reserved")

def decrement_variant_stock(variant_id, quantity):
    pass

def create_inventory_log(variant_id, quantity, action):
    pass

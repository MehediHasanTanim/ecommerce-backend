from common.uow import UnitOfWork

def process_refund(refund_data):
    with UnitOfWork(action_name="process_refund"):
        create_refund_record(refund_data)
        update_payment_refund_status(refund_data)
        update_order_status(refund_data)
        create_audit_log("refund_processed", refund_data)

def approve_return(return_data):
    with UnitOfWork(action_name="approve_return"):
        approve_return_request(return_data)
        restore_stock_if_required(return_data)
        update_order_item_status(return_data)
        trigger_refund_if_required(return_data)
        create_audit_log("return_approved", return_data)

def create_refund_record(data):
    pass

def update_payment_refund_status(data):
    pass

def update_order_status(data):
    pass

def approve_return_request(data):
    pass

def restore_stock_if_required(data):
    pass

def update_order_item_status(data):
    pass

def trigger_refund_if_required(data):
    pass

def create_audit_log(action, instance):
    pass

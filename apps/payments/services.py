from common.uow import UnitOfWork

def confirm_payment(payment_id, status_data):
    if is_payment_already_confirmed(payment_id):
        return  # Idempotent
        
    with UnitOfWork(action_name="confirm_payment"):
        update_payment_status(payment_id, status_data)
        update_order_payment_status(payment_id, status_data)
        create_audit_log("payment_confirmed", payment_id)

def is_payment_already_confirmed(payment_id):
    return False

def update_payment_status(payment_id, status_data):
    pass

def update_order_payment_status(payment_id, status_data):
    pass

def create_audit_log(action, instance):
    pass

from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class UnitOfWork:
    """
    Lightweight Unit of Work wrapper around Django transaction.atomic().

    Use only for complex business flows where multiple model updates
    must commit or rollback together.
    """
    def __init__(self, using="default", action_name="unknown"):
        self.using = using
        self.action_name = action_name

    def __enter__(self):
        self._atomic = transaction.atomic(using=self.using)
        self._atomic.__enter__()
        logger.info("transaction_started", extra={"using": self.using, "action": self.action_name})
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self._atomic.__exit__(exc_type, exc_value, traceback)
            if exc_type is None:
                logger.info("transaction_committed", extra={"using": self.using, "action": self.action_name})
            else:
                logger.info("transaction_rolled_back", extra={"using": self.using, "action": self.action_name, "error": str(exc_value)})
        except Exception as e:
            logger.info("transaction_rolled_back", extra={"using": self.using, "action": self.action_name, "error": str(e)})
            raise

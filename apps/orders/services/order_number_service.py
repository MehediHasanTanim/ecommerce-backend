"""OrderNumberService – generates unique, human-readable, thread-safe order numbers.

Format: ORD-YYYYMMDD-NNNNNN
Example: ORD-20260611-000001
"""
import logging
import threading
from datetime import date

from django.db import transaction, connection

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class OrderNumberService:
    """
    Generates unique order numbers.

    Uses database-sequence-backed counter per day to ensure uniqueness
    even across multiple app server instances.
    """

    @staticmethod
    def generate() -> str:
        """Return a unique order number for today.

        Thread-safe via Python lock + database-level atomic counter.
        """
        with _lock:
            today_str = date.today().strftime('%Y%m%d')

            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Use PostgreSQL advisory lock for cross-process safety
                    cursor.execute("SELECT pg_advisory_xact_lock(42)")
                    cursor.execute(
                        """
                        INSERT INTO orders_ordernumbercounter (date_str, last_sequence)
                        VALUES (%s, 1)
                        ON CONFLICT (date_str)
                        DO UPDATE SET last_sequence = orders_ordernumbercounter.last_sequence + 1
                        RETURNING last_sequence
                        """,
                        [today_str],
                    )
                    seq = cursor.fetchone()[0]

            order_number = f"ORD-{today_str}-{seq:06d}"
            logger.info(
                "Order number generated: %s",
                order_number,
                extra={"order_number": order_number},
            )
            return order_number

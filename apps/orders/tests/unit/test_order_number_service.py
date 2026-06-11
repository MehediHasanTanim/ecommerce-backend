"""Unit tests for OrderNumberService – format, uniqueness, sequential, thread-safety.

Covers:
- Correct format: ORD-YYYYMMDD-NNNNNN
- Uniqueness across 1000 generations
- Sequential increment
- Thread safety (concurrent generation)
- Date-based prefix
"""
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from freezegun import freeze_time

from apps.orders.services.order_number_service import OrderNumberService


# ---------------------------------------------------------------------------
# Format Validation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderNumberFormat:

    def test_starts_with_ord(self):
        num = OrderNumberService.generate()
        assert num.startswith('ORD-')

    def test_matches_expected_pattern(self):
        """Format: ORD-YYYYMMDD-NNNNNN"""
        num = OrderNumberService.generate()
        pattern = r'^ORD-\d{8}-\d{6}$'
        assert re.match(pattern, num), f"'{num}' does not match pattern {pattern}"

    def test_date_part_is_valid(self):
        """Date part must be parseable as YYYYMMDD."""
        num = OrderNumberService.generate()
        date_part = num.split('-')[1]
        from datetime import datetime
        parsed = datetime.strptime(date_part, '%Y%m%d')
        assert parsed is not None

    def test_sequence_part_is_six_digits(self):
        """Sequence is zero-padded to 6 digits."""
        num = OrderNumberService.generate()
        seq_part = num.split('-')[2]
        assert len(seq_part) == 6
        assert seq_part.isdigit()

    @freeze_time('2026-06-11')
    def test_date_matches_frozen_time(self):
        """Date part reflects the actual generation date."""
        num = OrderNumberService.generate()
        assert num.startswith('ORD-20260611-')


# ---------------------------------------------------------------------------
# Uniqueness
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderNumberUniqueness:

    def test_two_numbers_different(self):
        num1 = OrderNumberService.generate()
        num2 = OrderNumberService.generate()
        assert num1 != num2

    def test_bulk_uniqueness(self):
        """1000 numbers generated — all unique."""
        count = 1000
        numbers = {OrderNumberService.generate() for _ in range(count)}
        assert len(numbers) == count

    @freeze_time('2026-06-11')
    def test_uniqueness_within_same_day(self):
        """All numbers on the same day are unique."""
        numbers = {OrderNumberService.generate() for _ in range(100)}
        assert len(numbers) == 100


# ---------------------------------------------------------------------------
# Sequential Increment
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderNumberSequential:

    def test_consecutive_numbers_increment(self):
        num1 = OrderNumberService.generate()
        num2 = OrderNumberService.generate()
        num3 = OrderNumberService.generate()

        seq1 = int(num1.split('-')[-1])
        seq2 = int(num2.split('-')[-1])
        seq3 = int(num3.split('-')[-1])

        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1

    def test_first_number_starts_at_one(self):
        """First number of a new day should be 000001."""
        # Use a unique date to ensure no prior entries
        with freeze_time('2025-01-15'):
            num = OrderNumberService.generate()
            seq = num.split('-')[-1]
            assert seq == '000001'

    @freeze_time('2026-06-11')
    def test_sequential_across_multiple_calls(self):
        """10 calls produce sequence 1 through 10."""
        numbers = [OrderNumberService.generate() for _ in range(10)]
        sequences = [int(n.split('-')[-1]) for n in numbers]
        assert sequences == list(range(1, 11))

    @freeze_time('2026-06-11', as_kwarg='frozen_dt')
    def test_different_days_have_independent_counters(self, frozen_dt):
        """Each day starts counting from 1."""
        num_day1 = OrderNumberService.generate()
        seq_day1 = int(num_day1.split('-')[-1])
        assert seq_day1 == 1

        # Move to next day
        frozen_dt.move_to('2026-06-12')
        num_day2 = OrderNumberService.generate()
        seq_day2 = int(num_day2.split('-')[-1])
        assert seq_day2 == 1


# ---------------------------------------------------------------------------
# Thread Safety
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderNumberThreadSafety:

    def test_concurrent_generation_no_duplicates(self):
        """Concurrent threads produce unique numbers."""
        count = 50
        num_threads = 10

        results = []
        lock = threading.Lock()

        def generate_batch(batch_size):
            batch = [OrderNumberService.generate() for _ in range(batch_size)]
            with lock:
                results.extend(batch)

        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=generate_batch, args=(count // num_threads,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(results) == count
        assert len(set(results)) == count  # All unique

    def test_concurrent_with_executor(self):
        """ThreadPoolExecutor — all numbers unique."""
        count = 100

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(OrderNumberService.generate) for _ in range(count)]
            numbers = [f.result() for f in as_completed(futures)]

        assert len(numbers) == count
        assert len(set(numbers)) == count


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderNumberEdgeCases:

    @freeze_time('2026-12-31')
    def test_year_end_boundary(self):
        """Works correctly at year boundary."""
        num = OrderNumberService.generate()
        assert num.startswith('ORD-20261231-')

    @freeze_time('2026-01-01')
    def test_year_start_boundary(self):
        """Works correctly at year start."""
        num = OrderNumberService.generate()
        assert num.startswith('ORD-20260101-')

    @freeze_time('2026-02-29')  # Leap year
    def test_leap_year_date(self):
        """Works correctly on leap day."""
        num = OrderNumberService.generate()
        assert num.startswith('ORD-20260229-')

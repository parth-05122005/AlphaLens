from contextlib import contextmanager

from django.core.cache import cache


@contextmanager
def redis_lock(key: str, timeout: int = 300):
    """Yield True if we got the lock, False if someone else holds it.

    cache.add is atomic in Redis (SET NX), so only one process wins. The timeout
    guarantees the lock is released even if the holder crashes.
    """
    acquired = cache.add(key, "1", timeout)
    try:
        yield acquired
    finally:
        if acquired:
            cache.delete(key)

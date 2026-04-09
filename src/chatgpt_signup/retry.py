import asyncio
import functools
import time

from .config import get_logger

log = get_logger("retry")


def retry(max_attempts: int = 3, delay: float = 2.0, backoff: float = 2.0,
          exceptions: tuple = (Exception,)):
    """
    Retry decorator for sync functions.

    Args:
        max_attempts: Maximum number of attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        log.error("'%s' failed after %d attempts: %s",
                                  func.__name__, max_attempts, e)
                        raise
                    log.warning("'%s' attempt %d/%d failed: %s — retrying in %.1fs",
                                func.__name__, attempt, max_attempts, e, current_delay)
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc  # unreachable, but satisfies type checkers
        return wrapper
    return decorator


def async_retry(max_attempts: int = 3, delay: float = 2.0, backoff: float = 2.0,
                exceptions: tuple = (Exception,)):
    """
    Retry decorator for async functions.

    Args:
        max_attempts: Maximum number of attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        log.error("'%s' failed after %d attempts: %s",
                                  func.__name__, max_attempts, e)
                        raise
                    log.warning("'%s' attempt %d/%d failed: %s — retrying in %.1fs",
                                func.__name__, attempt, max_attempts, e, current_delay)
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc
        return wrapper
    return decorator

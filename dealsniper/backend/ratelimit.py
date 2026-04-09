"""No-op stub for the `ratelimit` package.

The `fli` library (pip install flights) depends on `ratelimit` at import time,
but that package often fails to build on modern Python/setuptools. This stub
provides the two symbols fli actually imports so everything loads cleanly.

Our own rate limiting is handled by time.sleep(2) between calls in searcher.py.
"""


def limits(calls=1, period=1):
    """Decorator that does nothing — real rate limiting is in searcher.py."""
    def decorator(func):
        return func
    return decorator


def sleep_and_retry(func):
    """Decorator that does nothing — real rate limiting is in searcher.py."""
    return func

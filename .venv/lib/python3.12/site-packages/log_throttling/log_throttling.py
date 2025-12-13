import inspect
import logging
import time
from abc import ABC
from abc import abstractmethod


class _ThrottlingStrategy(ABC):
    @abstractmethod
    def __eq__(self, other):
        pass

    @abstractmethod
    def filter(self) -> bool:
        pass


class _ThrottlingByTime(_ThrottlingStrategy):
    def __init__(self, interval: float):
        self.interval = interval
        self._last_print = float("-inf")

    def __eq__(self, other):
        return type(self) == type(other) and self.interval == other.interval

    def filter(self) -> bool:
        now = time.monotonic()
        if now - self._last_print < self.interval:
            return False
        else:
            self._last_print = now
            return True


class _ThrottlingByCount(_ThrottlingStrategy):
    def __init__(self, once_every: int):
        self.once_every = once_every
        self._counter = -1

    def __eq__(self, other):
        return type(self) == type(other) and self.once_every == other.once_every

    def filter(self) -> bool:
        self._counter = (self._counter + 1) % self.once_every
        if self._counter == 0:
            return True
        else:
            return False


class _ThrottlingFilter(logging.Filter):
    @classmethod
    def caller_key(cls, pathname: str, lineno: int) -> str:
        return f"{pathname}:{lineno}"

    @classmethod
    def filter(cls, record: logging.LogRecord) -> bool:
        logger = logging.getLogger(record.name)
        caller = cls.caller_key(record.pathname, record.lineno)
        throttling_strategy = getattr(logger, "throttling_config")[caller]
        return throttling_strategy.filter()


def _by_custom_strategy(logger: logging.Logger, strategy: _ThrottlingStrategy) -> logging.Logger:
    logger = logger.getChild("throttled")

    if not hasattr(logger, "throttling_config"):
        setattr(logger, "throttling_config", {})
        logger.addFilter(_ThrottlingFilter())

    frame = inspect.stack()[2]
    caller = _ThrottlingFilter.caller_key(frame.filename, frame.lineno)

    throttling_config = getattr(logger, "throttling_config")
    if throttling_config.get(caller) != strategy:
        throttling_config[caller] = strategy

    return logger


def by_time(logger: logging.Logger, interval: float) -> logging.Logger:
    """
    The returned logger will only permit at most one print every `interval` seconds from the code
    line this function was called from.

    Usage example::

        start = time.monotonic()
        while time.monotonic() - start < 10:
            log_throttling.by_time(logger, interval=1).info(
                "This line will be logged once every second."
            )
            time.sleep(0.01)

    **Notes**:
        \\1. Throttling is configured per code line that this function is called from.
        Changing the parameter from that used previously for that line will reset the throttling
        counter for the line.

        \\2. Throttling does not nest. e.g.::

            log_throttling.by_time(log_throttling.by_count(logger, 10), 1).info("...")

        Will simply ignore the nested `by_count`.


    :param logger: A `logging.Logger` object to "wrap". The return value from this function can be used
        just like a normal logger.
    :param interval: The interval, in seconds as a floating point number, between allowed throttled logs.
        Everything except the first print in an `interval` seconds interval will be black-holed.
    :return: A throttled `logging.Logger`-like object.
    """

    strategy = _ThrottlingByTime(interval)
    return _by_custom_strategy(logger, strategy)


def by_count(logger: logging.Logger, once_every: int) -> logging.Logger:
    """
    The returned logger will only permit at most one print every `once_every` logging calls from the code
    line this function was called from.

    Usage example::

        for i in range(100):
            log_throttling.by_count(logger, once_every=10).info(
                "This line will only log values that are multiples of 10: %s", i
            )

    **Notes**:
        \\1. Throttling is configured per code line that this function is called from.
        Changing the parameter from that used previously for that line will reset the throttling
        counter for the line.

        \\2. Throttling does not nest. e.g.::

            log_throttling.by_time(log_throttling.by_count(logger, 10), 1).info("...")

        Will simply ignore the nested `by_count`.

    :param logger: A `logging.Logger` object to "wrap". The return value from this function can be used
        just like a normal logger.
    :param once_every: The number of logging calls for which a single call is allowed to be written.
    :return: A throttled `logging.Logger`-like object.
    """

    strategy = _ThrottlingByCount(once_every)
    return _by_custom_strategy(logger, strategy)

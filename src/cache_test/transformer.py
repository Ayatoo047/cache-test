import time
from collections.abc import Callable

type Transformer = Callable[[str], str]


class TransformerError(Exception):
    """Raised when the transformer cannot produce a result for an input."""


class SimulatedTransformer:
    """Upper-cases its input after an artificial delay.

    The delay models the round trip to a real external service, which is the
    cost the caching layer exists to avoid.
    """

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self._delay_seconds = delay_seconds

    def __call__(self, value: str) -> str:
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        return value.upper()

from collections.abc import Callable
from threading import Lock
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def singleton(cls: Callable[P, T]) -> Callable[P, T]:
    instances: dict[Callable[P, T], T] = {}
    lock = Lock()

    def get_instance(*args: P.args, **kwargs: P.kwargs) -> T:
        with lock:
            if cls not in instances:
                instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance

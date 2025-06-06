from collections.abc import Callable
from threading import Lock
from typing import Any, TypeVar

T = TypeVar("T")


def singleton(cls: type[T]) -> Callable[..., T]:
    instances: dict[type[T], T] = {}
    lock = Lock()

    def get_instance(*args: Any, **kwargs: Any) -> T:
        with lock:
            if cls not in instances:
                instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance

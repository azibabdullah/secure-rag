"""Cooperative cancellation shared by the desktop worker and local services."""
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Event
from typing import Callable


class CancelledError(RuntimeError):
    pass


@dataclass
class Operation:
    cancelled: Event = field(default_factory=Event)
    notify: Callable[[str], None] = lambda _: None

    def check(self):
        if self.cancelled.is_set():
            raise CancelledError("Cancelled. No partial answer was saved.")


current_operation = ContextVar("operation", default=None)


def checkpoint(phase=None):
    operation = current_operation.get()
    if operation:
        operation.check()
        if phase:
            operation.notify(phase)


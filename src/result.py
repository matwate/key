from dataclasses import dataclass
from typing import Callable, Generic, NoReturn, Type, TypeVar, Union

# Define generic types for Value (T) and Error (E)
T = TypeVar("T")
E = TypeVar("E")
O = TypeVar("O")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        # We must raise an exception here to simulate a panic/crash
        raise ValueError(f"Called unwrap on an Err: {self.error}")

    def unwrap_or(self, default: O) -> O:
        return default


# The Result Type is a Union of Ok and Err
Result = Union[Ok[T], Err[E]]

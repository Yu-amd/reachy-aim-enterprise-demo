from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any

class RobotAdapter(ABC):
    @abstractmethod
    def health(self) -> bool: ...

    @abstractmethod
    def get_state(self) -> Dict[str, Any]: ...

    @abstractmethod
    def gesture(self, name: str) -> None: ...

    @abstractmethod
    def speak(self, text: str) -> None: ...

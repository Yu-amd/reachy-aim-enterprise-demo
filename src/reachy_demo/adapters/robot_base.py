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
    def speak(self, text: str) -> float: 
        """Speak text and return audio duration in seconds."""
        ...

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def calibrate_home(self) -> None: ...
    
    def thinking_pose(self) -> None:
        """Turn body to the side to indicate thinking. Optional - can be overridden."""
        pass
    
    def return_from_thinking(self) -> None:
        """Return body from thinking pose to neutral. Optional - can be overridden."""
        pass

from __future__ import annotations
from pydantic import BaseModel
from typing import Any, List, Dict, Optional

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: float = 0.2
    max_tokens: int = 180
    stream: bool = False

class ChatCompletionResponse(BaseModel):
    text: str
    raw: Dict[str, Any]
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

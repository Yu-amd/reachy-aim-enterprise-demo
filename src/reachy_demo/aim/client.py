from __future__ import annotations

import time
from typing import Dict, List, Optional
import requests

from .errors import AIMHTTPError, AIMTimeout
from .models import Message, ChatCompletionRequest, ChatCompletionResponse

class AIMClient:
    def __init__(
        self,
        base_url: str,
        chat_path: str = "/v1/chat/completions",
        api_key: Optional[str] = None,
        timeout_ms: int = 2200,
        max_retries: int = 1,
    ):
        self.base_url = base_url.rstrip("/")
        self.chat_path = chat_path if chat_path.startswith("/") else "/" + chat_path
        self.api_key = api_key.strip() if api_key else None
        self.timeout_s = max(0.1, timeout_ms / 1000.0)
        self.max_retries = max(0, int(max_retries))

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 180,
        stream: bool = False,
    ) -> ChatCompletionResponse:
        req = ChatCompletionRequest(
            model=model,
            messages=[Message(**m) for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        url = f"{self.base_url}{self.chat_path}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = req.model_dump()
        last_err: Exception | None = None

        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=self.timeout_s)
                dt_ms = (time.perf_counter() - t0) * 1000.0
                if r.status_code >= 400:
                    raise AIMHTTPError(r.status_code, r.text[:500])
                raw = r.json()
                try:
                    text = raw["choices"][0]["message"]["content"]
                except Exception:
                    text = str(raw)[:500]

                usage = raw.get("usage", {}) if isinstance(raw, dict) else {}
                return ChatCompletionResponse(
                    text=text,
                    raw={"latency_ms": dt_ms, "response": raw},
                    model=raw.get("model") if isinstance(raw, dict) else None,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                )
            except requests.Timeout as e:
                last_err = e
            except AIMHTTPError as e:
                last_err = e
                if 400 <= e.status_code < 500:
                    break
            except Exception as e:
                last_err = e

            # minimal backoff
            if attempt < self.max_retries:
                time.sleep(0.15)

        raise AIMTimeout(f"AIM request failed after retries: {last_err}")

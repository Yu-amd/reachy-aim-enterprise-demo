import pytest
from reachy_demo.config import load_settings

def test_load_settings_requires_base_url(monkeypatch):
    monkeypatch.delenv("AIM_BASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()

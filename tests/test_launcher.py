from __future__ import annotations

from pathlib import Path

import launcher


def test_user_data_dir_uses_local_app_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    data_dir = launcher._user_data_dir()
    assert data_dir == tmp_path / launcher.APP_NAME
    assert data_dir.is_dir()


def test_configured_port_is_respected(monkeypatch) -> None:
    monkeypatch.setenv("CLINIC_ANALYTICS_PORT", "8765")
    assert launcher._available_port() == 8765


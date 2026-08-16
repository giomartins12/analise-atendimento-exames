from __future__ import annotations

from pathlib import Path
import logging

import launcher


def test_user_data_dir_uses_local_app_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    data_dir = launcher._user_data_dir()
    assert data_dir == tmp_path / launcher.APP_NAME
    assert data_dir.is_dir()


def test_configured_port_is_respected(monkeypatch) -> None:
    monkeypatch.setenv("CLINIC_ANALYTICS_PORT", "8765")
    assert launcher._available_port() == 8765


def test_packaged_streamlit_runs_in_production_mode(tmp_path: Path) -> None:
    arguments = launcher._streamlit_arguments(tmp_path / "app.py", 8765, "true")
    assert "--global.developmentMode=false" in arguments
    assert "--server.port=8765" in arguments
    assert "--server.headless=true" in arguments


def test_diagnostics_are_written_before_streamlit_import(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    log_path = launcher._configure_diagnostics(launcher._user_data_dir())
    logging.shutdown()
    contents = log_path.read_text(encoding="utf-8")
    assert "Inicialização do aplicativo" in contents
    assert launcher.APP_VERSION in contents


def test_nonzero_system_exit_is_captured(monkeypatch) -> None:
    monkeypatch.setattr(launcher, "main", lambda: (_ for _ in ()).throw(SystemExit(-1)))
    monkeypatch.setattr(launcher, "_report_startup_failure", lambda _error: None)
    assert launcher._run() == -1

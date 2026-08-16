from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
from pathlib import Path

from streamlit.web import cli as streamlit_cli


APP_NAME = "AnaliseAtendimentoExames"


def _user_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _available_port() -> int:
    configured = os.environ.get("CLINIC_ANALYTICS_PORT")
    if configured:
        return int(configured)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


def _show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, "Análise de Atendimento e Exames", 0x10)


def main() -> None:
    data_dir = _user_data_dir()
    logging.basicConfig(
        filename=data_dir / "application.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    app_path = bundle_dir / "app.py"
    if not app_path.exists():
        raise FileNotFoundError(f"Arquivo da aplicação não encontrado: {app_path}")

    os.environ["CLINIC_ANALYTICS_DATA_DIR"] = str(data_dir)
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    port = _available_port()
    headless = os.environ.get("CLINIC_ANALYTICS_HEADLESS", "false").lower()
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        f"--server.headless={headless}",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
    ]
    streamlit_cli.main()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        logging.exception("Falha ao iniciar a aplicação")
        _show_error(
            "Não foi possível iniciar a aplicação.\n\n"
            f"Detalhe: {error}\n\n"
            f"Consulte o log em: {_user_data_dir() / 'application.log'}"
        )
        raise


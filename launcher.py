from __future__ import annotations

import faulthandler
import logging
import os
import platform
import socket
import sys
import traceback
from pathlib import Path


APP_NAME = "AnaliseAtendimentoExames"
APP_VERSION = "0.1.1"
_fault_log_handle = None
_console_log_handle = None
_stdin_handle = None


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
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, message, "Análise de Atendimento e Exames", 0x10)


def _streamlit_arguments(app_path: Path, port: int, headless: str) -> list[str]:
    return [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        f"--server.headless={headless}",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
    ]


def _configure_diagnostics(data_dir: Path) -> Path:
    global _console_log_handle, _fault_log_handle, _stdin_handle

    log_path = data_dir / "application.log"
    if sys.stdout is None or sys.stderr is None:
        _console_log_handle = (data_dir / "console.log").open(
            "a", encoding="utf-8", buffering=1
        )
        if sys.stdout is None:
            sys.stdout = _console_log_handle
        if sys.stderr is None:
            sys.stderr = _console_log_handle
    if sys.stdin is None:
        _stdin_handle = open(os.devnull, "r", encoding="utf-8")
        sys.stdin = _stdin_handle
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    _fault_log_handle = (data_dir / "native-crash.log").open("a", encoding="utf-8")
    faulthandler.enable(file=_fault_log_handle, all_threads=True)
    logging.info(
        "Inicialização do aplicativo versão %s | Windows=%s | Python=%s | frozen=%s | executable=%s",
        APP_VERSION,
        platform.platform(),
        sys.version.replace("\n", " "),
        bool(getattr(sys, "frozen", False)),
        sys.executable,
    )
    return log_path


def main() -> None:
    data_dir = _user_data_dir()
    _configure_diagnostics(data_dir)
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    app_path = bundle_dir / "app.py"
    logging.info("Diretório do pacote=%s | app=%s", bundle_dir, app_path)
    if not app_path.exists():
        raise FileNotFoundError(f"Arquivo da aplicação não encontrado: {app_path}")

    os.environ["CLINIC_ANALYTICS_DATA_DIR"] = str(data_dir)
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    port = _available_port()
    headless = os.environ.get("CLINIC_ANALYTICS_HEADLESS", "false").lower()
    sys.argv = _streamlit_arguments(app_path, port, headless)
    logging.info("Importando Streamlit")
    from streamlit.web import cli as streamlit_cli

    logging.info("Iniciando Streamlit em 127.0.0.1:%s", port)
    streamlit_cli.main()


def _run() -> int:
    try:
        main()
        return 0
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 1
        if code in (0, None):
            logging.info("Aplicativo encerrado normalmente")
            return 0
        logging.exception("Streamlit encerrou a inicialização com código %s", code)
        traceback.print_exc()
        _report_startup_failure(error)
        return code
    except BaseException as error:
        logging.exception("Falha ao iniciar a aplicação")
        traceback.print_exc()
        _report_startup_failure(error)
        return 1


def _report_startup_failure(error: BaseException) -> None:
    if os.environ.get("CLINIC_ANALYTICS_HEADLESS", "false").lower() == "true":
        return
    detail = str(error).strip() or repr(error)
    try:
        _show_error(
            "Não foi possível iniciar a aplicação.\n\n"
            f"Detalhe: {detail}\n\n"
            f"Consulte os logs em: {_user_data_dir()}"
        )
    except Exception:
        logging.exception("Também não foi possível exibir a mensagem de erro")


if __name__ == "__main__":
    sys.exit(_run())

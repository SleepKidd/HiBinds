from __future__ import annotations

import importlib
import subprocess
import sys


REQUIRED = ["customtkinter>=5.2.2"]


def ensure_dependencies() -> None:
    missing = []
    try:
        importlib.import_module("customtkinter")
    except ImportError:
        missing.append(REQUIRED[0])

    if not missing:
        return

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--user", *missing]
        )
    except Exception as exc:
        raise RuntimeError(
            "Не удалось автоматически установить компоненты интерфейса. "
            "Проверь интернет-соединение или установи зависимости вручную."
        ) from exc

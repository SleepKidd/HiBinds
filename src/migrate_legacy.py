from __future__ import annotations
import json
import shutil
from pathlib import Path

LEGACY_NAMES = ["HIBinds.json", "HIbinds.json"]


def migrate(folder: Path, target: Path) -> tuple[bool, str]:
    if target.exists():
        return False, "Новая база уже существует."
    for name in LEGACY_NAMES:
        p = folder / name
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8") or "{}")
                if not isinstance(data, dict):
                    continue
                target.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
                return True, f"Мигрирована база: {p.name}"
            except Exception as exc:
                shutil.copy2(p, p.with_suffix(".broken.json"))
                return False, f"Не удалось мигрировать {p.name}: {exc}"
    return False, "Старая база не найдена."

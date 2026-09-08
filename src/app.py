from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib.parse import urlparse

try:
    import tkinter as tk
    import customtkinter as ctk
except ImportError:
    from bootstrap import ensure_dependencies
    ensure_dependencies()
    import tkinter as tk
    import customtkinter as ctk

APP_NAME = "HiBinds"
DB_NAME = "HIBinds.json"
SETTINGS_NAME = "settings.json"
EXPORT_VERSION = 1

ACCENT = "#20D8D2"
ACCENT_HOVER = "#49E7E1"
SUCCESS = "#2FBF71"
WARNING = "#F2A93B"
DANGER = "#EF5B6B"
BG_DARK = "#050607"
CARD_DARK = "#0B0E11"
CARD_DARK_2 = "#10151A"
TEXT_DARK = "#F5FAFA"
MUTED_DARK = "#AAB7BC"
BG_LIGHT = "#111417"
CARD_LIGHT = "#161B1F"
TEXT_LIGHT = "#F5FAFA"
MUTED_LIGHT = "#AAB7BC"


def app_data_dir() -> Path:
    base = os.getenv("APPDATA")
    path = (Path(base) / APP_NAME) if base else (Path.home() / f".{APP_NAME.lower()}")
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = app_data_dir()
DB_FILE = DATA_DIR / DB_NAME
SETTINGS_FILE = DATA_DIR / SETTINGS_NAME


def load_settings() -> dict:
    defaults = {"appearance": "Dark", "autostart": False}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    result = {**defaults, **data}
    return result


def save_settings(data: dict) -> None:
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(SETTINGS_FILE)


def legacy_candidates() -> list[Path]:
    candidates = []
    locations = [DATA_DIR, Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()]
    for base in locations:
        for name in ("HIBinds.json", "HIbinds.json"):
            p = base / name
            if p not in candidates:
                candidates.append(p)
    return candidates


def ensure_db() -> None:
    if DB_FILE.exists():
        return
    for legacy in legacy_candidates():
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8") or "{}")
                if isinstance(data, dict):
                    DB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    return
            except Exception:
                pass
    DB_FILE.write_text("{}", encoding="utf-8")


def load_binds() -> dict:
    ensure_db()
    try:
        data = json.loads(DB_FILE.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("Корень базы должен быть объектом.")
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        backup = DB_FILE.with_name(f"HIBinds.broken_{int(time.time())}.json")
        try:
            shutil.copy2(DB_FILE, backup)
        except OSError:
            pass
        DB_FILE.write_text("{}", encoding="utf-8")
        return {}


def save_binds(data: dict) -> None:
    tmp = DB_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DB_FILE)


def normalize_target(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if value.lower().startswith("file:///"):
        value = value[8:]
    return os.path.expandvars(os.path.expanduser(value))


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def valid_hotkey(value: str) -> bool:
    if not value:
        return True
    parts = [x.strip() for x in re.split(r"\+", value) if x.strip()]
    if not parts:
        return False
    modifiers = {"CTRL", "ALT", "SHIFT", "WIN", "CMD"}
    base = parts[-1].upper()
    if any(p.upper() not in modifiers for p in parts[:-1]):
        return False
    if base in modifiers:
        return False
    valid_base = bool(re.fullmatch(r"F(?:[1-9]|1[0-9]|2[0-4])", base)) or bool(re.fullmatch(r"[A-Z0-9]", base))
    valid_base = valid_base or base in {"ENTER", "ESC", "TAB", "SPACE", "BACKSPACE", "DELETE", "HOME", "END", "UP", "DOWN", "LEFT", "RIGHT", "INSERT", "PAGEUP", "PAGEDOWN"}
    return valid_base


def validate_binds(data: dict) -> tuple[int, list[dict]]:
    issues: list[dict] = []
    if not isinstance(data, dict):
        return 0, [{"level": "error", "bind": "База", "message": "Корень базы должен быть объектом."}]

    hotkeys: dict[str, str] = {}
    working = 0
    for name, info in data.items():
        bind_ok = True
        if not isinstance(name, str) or not name.strip():
            issues.append({"level": "error", "bind": str(name), "message": "Пустое или некорректное название."})
            bind_ok = False
        if not isinstance(info, dict):
            issues.append({"level": "error", "bind": str(name), "message": "Данные бинда повреждены."})
            continue

        hotkey = str(info.get("hotkey", "")).strip()
        if hotkey:
            if not valid_hotkey(hotkey):
                issues.append({"level": "warning", "bind": name, "message": f"Некорректная горячая клавиша: {hotkey}"})
                bind_ok = False
            key = hotkey.upper().replace(" ", "")
            if key in hotkeys:
                issues.append({"level": "warning", "bind": name, "message": f"Дубликат горячей клавиши с «{hotkeys[key]}»."})
                bind_ok = False
            else:
                hotkeys[key] = name

        actions = info.get("actions")
        if not isinstance(actions, list) or not actions:
            issues.append({"level": "error", "bind": name, "message": "Нет действий."})
            continue

        seen_targets: set[tuple[str, str]] = set()
        for index, action in enumerate(actions, 1):
            if not isinstance(action, dict):
                issues.append({"level": "error", "bind": name, "message": f"Шаг {index}: повреждён."})
                bind_ok = False
                continue
            action_type = action.get("type")
            target = normalize_target(str(action.get("action", "")))
            delay = action.get("delay_ms", 0)
            try:
                delay_value = int(delay)
                if delay_value < 0 or delay_value > 86_400_000:
                    raise ValueError
            except (TypeError, ValueError):
                issues.append({"level": "error", "bind": name, "message": f"Шаг {index}: некорректная задержка."})
                bind_ok = False
                delay_value = 0

            key = (str(action_type), target.lower())
            if key in seen_targets:
                issues.append({"level": "warning", "bind": name, "message": f"Шаг {index}: дублирующееся действие."})
                bind_ok = False
            seen_targets.add(key)

            if action_type == "url":
                if not is_url(target):
                    issues.append({"level": "error", "bind": name, "message": f"Шаг {index}: URL некорректен."})
                    bind_ok = False
            elif action_type == "app":
                if not os.path.isfile(target):
                    issues.append({"level": "warning", "bind": name, "message": f"Шаг {index}: файл не найден."})
                    bind_ok = False
            else:
                issues.append({"level": "error", "bind": name, "message": f"Шаг {index}: неизвестный тип действия."})
                bind_ok = False
            _ = delay_value

        if bind_ok:
            working += 1
    return working, issues


def set_windows_autostart(enabled: bool) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Автозапуск Windows доступен только на Windows."
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            value = str(Path(sys.executable).resolve()) if getattr(sys, "frozen", False) else f'"{sys.executable}" "{Path(__file__).resolve()}"'
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True, ""
    except OSError as exc:
        return False, str(exc)


class HiBindsApp(ctk.CTk):
    def __init__(self):
        self.settings = load_settings()
        ctk.set_appearance_mode(self.settings.get("appearance", "Dark"))
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("HiBinds — Command Center")
        self.geometry("1280x820")
        self.minsize(1100, 740)
        self.configure(fg_color=BG_DARK)

        self.binds = load_binds()
        self.new_actions: list[dict] = []
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.running = False
        self.stop_event = threading.Event()
        self.current_view = "dashboard"
        self.validation = validate_binds(self.binds)

        self._build_shell()
        self.show_dashboard()
        self.after(100, self._drain_logs)
        self.after(250, self._animate_glow)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI shell ----------
    def _font(self, size: int, weight: str = "normal"):
        return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)

    def _panel(self, parent, **kwargs):
        return ctk.CTkFrame(
            parent,
            corner_radius=18,
            fg_color=(CARD_LIGHT, CARD_DARK),
            border_width=1,
            border_color=("#263036", "#20282D"),
            **kwargs,
        )

    def _build_shell(self):
        self.grid_columnconfigure(0, weight=0, minsize=230)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Permanent animated background. It is never destroyed by page changes.
        self.bg_canvas = tk.Canvas(self, bg=BG_DARK, highlightthickness=0, bd=0)
        self.bg_canvas.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self._stars = []
        self._orbs = []
        self._shooters = []
        self._star_phase = 0.0
        self._build_starfield()

        self.sidebar = ctk.CTkFrame(
            self,
            width=210,
            corner_radius=20,
            fg_color=("#0C0F12", "#090C0F"),
            border_width=1,
            border_color=("#283136", "#20272C"),
        )
        self.sidebar.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Brand
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=16, pady=(18, 16), sticky="ew")
        brand.grid_columnconfigure(1, weight=1)
        mark = ctk.CTkLabel(
            brand, text="HB", width=42, height=42, corner_radius=12,
            fg_color=ACCENT, text_color="#041112", font=self._font(17, "bold")
        )
        mark.grid(row=0, column=0, padx=(0, 10))
        ctk.CTkLabel(brand, text="HiBinds", font=self._font(22, "bold"), text_color=TEXT_DARK).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(brand, text="рабочая область", font=self._font(11), text_color=MUTED_DARK).grid(row=1, column=1, sticky="w", pady=(0, 1))

        ctk.CTkLabel(self.sidebar, text="НАВИГАЦИЯ", font=self._font(10, "bold"), text_color="#6E7C82").grid(row=1, column=0, padx=18, sticky="w")
        self.nav_dashboard = self._nav_button("Обзор", 2, self.show_dashboard)
        self.nav_binds = self._nav_button("Мои бинды", 3, self.show_run_view)
        self.nav_create = self._nav_button("Создать бинд", 4, self.show_create_view)
        self.nav_settings = self._nav_button("Настройки", 5, self.show_settings)

        quick = ctk.CTkFrame(self.sidebar, fg_color="#0B1013", corner_radius=14, border_width=1, border_color="#1D282C")
        quick.grid(row=7, column=0, padx=12, pady=(8, 12), sticky="sew")
        ctk.CTkLabel(quick, text="БЫСТРО", font=self._font(10, "bold"), text_color="#6E7C82").pack(anchor="w", padx=12, pady=(11, 7))
        ctk.CTkButton(quick, text="+  Новый бинд", height=40, corner_radius=11, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      text_color="#041112", font=self._font(14, "bold"), command=self.show_create_view).pack(fill="x", padx=10, pady=(0, 7))
        ctk.CTkButton(quick, text="Проверить конфигурацию", height=36, corner_radius=10, fg_color="#151B1F", hover_color="#1E272C",
                      border_width=1, border_color="#2B383D", text_color=TEXT_DARK, font=self._font(12, "bold"), command=self.run_validation).pack(fill="x", padx=10, pady=(0, 10))

        self.sidebar_status = ctk.CTkLabel(self.sidebar, text="● Готово", anchor="w", font=self._font(12, "bold"), text_color="#4EE39A")
        self.sidebar_status.grid(row=8, column=0, padx=18, pady=(0, 4), sticky="w")
        ctk.CTkLabel(self.sidebar, text="Данные сохраняются автоматически", font=self._font(10), text_color="#647177").grid(row=9, column=0, padx=18, pady=(0, 16), sticky="w")

        # Main surface: intentionally flat and calm, with stars visible around it.
        self.main = ctk.CTkFrame(self, corner_radius=20, fg_color="transparent", border_width=1, border_color="#20292E")
        self.main.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        topbar = ctk.CTkFrame(self.main, height=64, corner_radius=16, fg_color="#0D1114", border_width=1, border_color="#1C252A")
        topbar.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        topbar.grid_columnconfigure(0, weight=1)
        self.top_title = ctk.CTkLabel(topbar, text="Обзор", font=self._font(19, "bold"), text_color=TEXT_DARK)
        self.top_title.grid(row=0, column=0, padx=18, pady=(10, 0), sticky="w")
        self.top_subtitle = ctk.CTkLabel(topbar, text="Центр управления HiBinds", font=self._font(10), text_color="#78878E")
        self.top_subtitle.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")
        ctk.CTkButton(topbar, text="Проверить", width=104, height=36, corner_radius=11, fg_color="#12191D", hover_color="#1A2327",
                      border_width=1, border_color="#2D393E", text_color=TEXT_DARK, font=self._font(12, "bold"), command=self.run_validation).grid(row=0, column=1, rowspan=2, padx=5)
        ctk.CTkButton(topbar, text="+ Бинд", width=88, height=36, corner_radius=11, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      text_color="#041112", font=self._font(12, "bold"), command=self.show_create_view).grid(row=0, column=2, rowspan=2, padx=(5, 10))

        self.content_host = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content_host.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

        self.sidebar.lift()
        self.main.lift()

    def _build_starfield(self):
        import random, math
        self.bg_canvas.create_rectangle(0, 0, 5000, 5000, fill="#050607", outline="")
        # Very subtle glow clouds.
        self._orbs.append(self.bg_canvas.create_oval(-280, 120, 220, 620, fill="#0B2427", outline=""))
        self._orbs.append(self.bg_canvas.create_oval(1050, -250, 1550, 260, fill="#071D20", outline=""))
        self._orbs.append(self.bg_canvas.create_oval(1250, 620, 1800, 1170, fill="#081619", outline=""))
        self._stars.clear()
        for _ in range(95):
            x = random.uniform(0, 1500)
            y = random.uniform(0, 900)
            r = random.choice([1, 1, 1, 1.4, 1.8, 2.2])
            c = random.choice(["#E9FFFF", "#B7D8D8", "#8BA7A8", "#5D7678"])
            item = self.bg_canvas.create_oval(x-r, y-r, x+r, y+r, fill=c, outline="")
            self._stars.append({"id": item, "x": x, "y": y, "r": r, "base": c, "phase": random.random() * math.tau})
        # A few larger stars with cross-like glow.
        for _ in range(14):
            x = random.uniform(250, 1450)
            y = random.uniform(40, 820)
            size = random.choice([3, 4, 5])
            self.bg_canvas.create_line(x-size, y, x+size, y, fill="#78A5A6", width=1)
            self.bg_canvas.create_line(x, y-size, x, y+size, fill="#78A5A6", width=1)

        # Slow shooting stars add motion without turning the background into visual noise.
        for _ in range(4):
            x = random.uniform(0, 1200)
            y = random.uniform(40, 820)
            vx = random.uniform(3.5, 5.5)
            vy = random.uniform(1.4, 2.4)
            tail = random.uniform(20, 34)
            line = self.bg_canvas.create_line(x, y, x-tail, y-tail*0.38, fill="#5E8587", width=1)
            dot = self.bg_canvas.create_oval(x-1.8, y-1.8, x+1.8, y+1.8, fill="#B8E8E7", outline="")
            self._shooters.append({"line": line, "dot": dot, "x": x, "y": y, "vx": vx, "vy": vy, "tail": tail})

    def _nav_button(self, text: str, row: int, command):
        btn = ctk.CTkButton(self.sidebar, text=text, height=44, corner_radius=11, anchor="w", fg_color="#0C1114",
                            hover_color="#151D21", border_width=1, border_color="#1B2428", text_color=TEXT_DARK,
                            font=self._font(13, "bold"), command=command)
        btn.grid(row=row, column=0, padx=12, pady=3, sticky="ew")
        return btn

    def _animate_glow(self):
        import math, random
        if not getattr(self, "winfo_exists", lambda: False)():
            return
        try:
            self._star_phase += 0.055
            for i, st in enumerate(self._stars):
                tw = 0.5 + 0.5 * math.sin(self._star_phase * (1.0 + (i % 4) * 0.15) + st["phase"])
                radius = st["r"] * (0.85 + 0.35 * tw)
                x, y = st["x"], st["y"]
                self.bg_canvas.coords(st["id"], x-radius, y-radius, x+radius, y+radius)
            shift = 22 * math.sin(self._star_phase * 0.42)
            self.bg_canvas.coords(self._orbs[0], -280 + shift, 120, 220 + shift, 620)
            self.bg_canvas.coords(self._orbs[1], 1050 - shift/2, -250, 1550 - shift/2, 260)
            self.bg_canvas.coords(self._orbs[2], 1250 + shift/3, 620, 1800 + shift/3, 1170)
            w = max(900, self.winfo_width())
            h = max(700, self.winfo_height())
            for shot in self._shooters:
                shot["x"] += shot["vx"]
                shot["y"] += shot["vy"]
                if shot["x"] > w + 40 or shot["y"] > h + 40:
                    shot["x"] = -random.uniform(20, 220)
                    shot["y"] = random.uniform(30, max(80, h * 0.35))
                tx = shot["x"] - shot["tail"]
                ty = shot["y"] - shot["tail"] * 0.38
                self.bg_canvas.coords(shot["line"], shot["x"], shot["y"], tx, ty)
                r = 1.8
                self.bg_canvas.coords(shot["dot"], shot["x"]-r, shot["y"]-r, shot["x"]+r, shot["y"]+r)
        except tk.TclError:
            pass
        self.after(80, self._animate_glow)

    def _set_top(self, title: str, subtitle: str):
        if hasattr(self, "top_title") and self.top_title.winfo_exists():
            self.top_title.configure(text=title)
            self.top_subtitle.configure(text=subtitle)

    def clear_main(self):
        if hasattr(self, "content_host") and self.content_host.winfo_exists():
            for child in self.content_host.winfo_children():
                child.destroy()

    # ---------- dashboard ----------
    def show_dashboard(self):
        self.current_view = "dashboard"
        self.clear_main()
        self._set_top("Обзор", "Состояние системы и быстрый доступ к биндам")
        self.validation = validate_binds(self.binds)
        working, issues = self.validation

        body = ctk.CTkFrame(self.content_host, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform="stats")
        body.grid_columnconfigure(0, weight=2)
        body.grid_rowconfigure(2, weight=1)

        # Welcome block
        welcome = self._panel(body)
        welcome.grid(row=0, column=0, columnspan=3, padx=4, pady=(4, 10), sticky="ew")
        welcome.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(welcome, text="Запускай без лишних движений.", font=self._font(29, "bold"), text_color=TEXT_DARK).grid(row=0, column=0, padx=22, pady=(20, 4), sticky="w")
        ctk.CTkLabel(welcome, text="Создай бинд один раз — потом запускай его одним нажатием.", font=self._font(14), text_color=MUTED_DARK).grid(row=1, column=0, padx=22, pady=(0, 18), sticky="w")
        ctk.CTkButton(welcome, text="+ Создать первый бинд" if not self.binds else "+ Создать новый бинд", width=190, height=42, corner_radius=12,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#041112", font=self._font(13, "bold"), command=self.show_create_view).grid(row=0, column=1, rowspan=2, padx=20)

        self._stat_card(body, 0, "Бинды", str(len(self.binds)), "сохранено")
        self._stat_card(body, 1, "Готовы", str(working), "прошли проверку")
        self._stat_card(body, 2, "Проблемы", str(len(issues)), "нужно внимание")

        left = self._panel(body)
        left.grid(row=2, column=0, columnspan=2, padx=(4, 6), pady=(10, 4), sticky="nsew")
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Состояние", font=self._font(20, "bold"), text_color=TEXT_DARK).grid(row=0, column=0, padx=20, pady=(18, 2), sticky="w")
        ok = not issues
        ctk.CTkLabel(left, text="Все готово к запуску" if ok else f"Найдено проблем: {len(issues)}",
                     font=self._font(15, "bold"), text_color="#55E5A3" if ok else "#FFBE5C").grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        scroll = ctk.CTkScrollableFrame(left, corner_radius=12, fg_color="#090D10", border_width=1, border_color="#1B252A")
        scroll.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="nsew")
        if not issues:
            ctk.CTkLabel(scroll, text="Пути, URL, задержки и структура базы выглядят нормально.", font=self._font(13), text_color=MUTED_DARK).pack(anchor="w", padx=14, pady=18)
        else:
            for item in issues[:40]:
                row = ctk.CTkFrame(scroll, fg_color="#0D1317", corner_radius=10, border_width=1, border_color="#1B252A")
                row.pack(fill="x", padx=8, pady=5)
                icon = "×" if item["level"] == "error" else "!"
                color = DANGER if item["level"] == "error" else WARNING
                ctk.CTkLabel(row, text=icon, width=24, font=self._font(14, "bold"), text_color=color).pack(side="left", padx=(10, 3), pady=10)
                ctk.CTkLabel(row, text=f"{item['bind']}: {item['message']}", anchor="w", justify="left", wraplength=640,
                             font=self._font(12), text_color=TEXT_DARK).pack(side="left", fill="x", expand=True, padx=(2, 10), pady=10)

        right = self._panel(body)
        right.grid(row=2, column=2, padx=(6, 4), pady=(10, 4), sticky="nsew")
        ctk.CTkLabel(right, text="Быстрые действия", font=self._font(20, "bold"), text_color=TEXT_DARK).pack(anchor="w", padx=18, pady=(18, 12))
        for text, command in [
            ("Мои бинды", self.show_run_view),
            ("Создать бинд", self.show_create_view),
            ("Экспортировать", self.export_binds),
            ("Импортировать", self.import_binds),
            ("Проверить всё", self.run_validation),
        ]:
            ctk.CTkButton(right, text=text, height=44, corner_radius=11, anchor="w", fg_color="#0E1418", hover_color="#172126",
                          border_width=1, border_color="#263239", text_color=TEXT_DARK, font=self._font(12, "bold"), command=command).pack(fill="x", padx=14, pady=5)

    def _stat_card(self, parent, col: int, title: str, value: str, sub: str):
        card = self._panel(parent)
        card.grid(row=1, column=col, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(card, text=value, font=self._font(31, "bold"), text_color=TEXT_DARK).pack(anchor="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(card, text=title, font=self._font(13, "bold"), text_color=TEXT_DARK).pack(anchor="w", padx=18, pady=(0, 1))
        ctk.CTkLabel(card, text=sub, font=self._font(11), text_color="#6F7D83").pack(anchor="w", padx=18, pady=(0, 14))

    # ---------- bind list ----------
    def show_run_view(self):
        self.current_view = "binds"
        self.clear_main()
        self._set_top("Мои бинды", "Выбирай сценарий и запускай его в один клик")
        body = ctk.CTkFrame(self.content_host, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(body, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=4, pady=(4, 10), sticky="ew")
        toolbar.grid_columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        search = ctk.CTkEntry(toolbar, height=42, corner_radius=12, textvariable=self.search_var, placeholder_text="Поиск бинда…",
                               font=self._font(13), fg_color="#0C1114", border_color="#253137")
        search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        search.bind("<KeyRelease>", lambda _e: self.refresh_bind_list())
        ctk.CTkButton(toolbar, text="Обновить", width=105, height=42, corner_radius=12, fg_color="#0F1519", hover_color="#182126",
                      border_width=1, border_color="#27343A", text_color=TEXT_DARK, font=self._font(12, "bold"), command=self.refresh_bind_list).grid(row=0, column=1, padx=4)
        ctk.CTkButton(toolbar, text="+ Новый", width=100, height=42, corner_radius=12, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      text_color="#041112", font=self._font(12, "bold"), command=self.show_create_view).grid(row=0, column=2, padx=(4, 0))

        self.bind_scroll = ctk.CTkScrollableFrame(body, corner_radius=14, fg_color="#080C0F", border_width=1, border_color="#1F292E")
        self.bind_scroll.grid(row=1, column=0, padx=4, pady=(0, 10), sticky="nsew")
        self.bind_scroll.grid_columnconfigure(0, weight=1)
        self.refresh_bind_list()

        bottom = ctk.CTkFrame(body, fg_color="#0A0F12", corner_radius=14, border_width=1, border_color="#202A2F")
        bottom.grid(row=2, column=0, padx=4, pady=(0, 4), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        self.console = ctk.CTkTextbox(bottom, height=82, corner_radius=12, font=self._font(11), fg_color="#070A0C", border_width=0)
        self.console.grid(row=0, column=0, padx=(10, 8), pady=10, sticky="ew")
        self.console.configure(state="disabled")
        self.stop_button = ctk.CTkButton(bottom, text="Остановить", width=120, height=38, corner_radius=11, fg_color=DANGER, hover_color="#D84D5B",
                                         text_color="#17090B", font=self._font(12, "bold"), command=self.stop_running)
        self.stop_button.grid(row=0, column=1, padx=(0, 10), pady=10)

    def refresh_bind_list(self):
        self.binds = load_binds()
        self.validation = validate_binds(self.binds)
        if not hasattr(self, "bind_scroll") or not self.bind_scroll.winfo_exists():
            return
        for child in self.bind_scroll.winfo_children():
            child.destroy()
        query = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        rows = [(name, info) for name, info in self.binds.items() if not query or query in name.lower()]
        if not rows:
            empty = ctk.CTkFrame(self.bind_scroll, fg_color="#0C1114", corner_radius=14, border_width=1, border_color="#1D282D")
            empty.grid(row=0, column=0, padx=20, pady=30, sticky="ew")
            ctk.CTkLabel(empty, text="Биндов пока нет", font=self._font(20, "bold"), text_color=TEXT_DARK).pack(pady=(24, 4))
            ctk.CTkLabel(empty, text="Создай первый сценарий — он появится здесь.", font=self._font(13), text_color=MUTED_DARK).pack(pady=(0, 20))
            return
        for index, (name, info) in enumerate(rows):
            actions = info.get("actions", []) if isinstance(info, dict) else []
            hotkey = str(info.get("hotkey", "")) if isinstance(info, dict) else ""
            card = ctk.CTkFrame(self.bind_scroll, corner_radius=14, fg_color="#0D1317", border_width=1, border_color="#233037")
            card.grid(row=index, column=0, padx=8, pady=6, sticky="ew")
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text="●", font=self._font(20, "bold"), text_color="#55E5A3").grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=12)
            ctk.CTkLabel(card, text=name, font=self._font(16, "bold"), anchor="w", text_color=TEXT_DARK).grid(row=0, column=1, padx=4, pady=(10, 1), sticky="w")
            meta = f"{len(actions)} действий"
            if hotkey:
                meta += f"   ·   {hotkey}"
            ctk.CTkLabel(card, text=meta, font=self._font(11), text_color=MUTED_DARK, anchor="w").grid(row=1, column=1, padx=4, pady=(0, 11), sticky="w")
            ctk.CTkButton(card, text="Запустить", width=94, height=36, corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          text_color="#041112", font=self._font(11, "bold"), command=lambda n=name: self.start_bind(n)).grid(row=0, column=2, rowspan=2, padx=4)
            ctk.CTkButton(card, text="Удалить", width=78, height=36, corner_radius=10, fg_color="transparent", border_width=1, border_color="#334047",
                          text_color=TEXT_DARK, hover_color="#29171A", font=self._font(11, "bold"), command=lambda n=name: self.delete_bind(n)).grid(row=0, column=3, rowspan=2, padx=(4, 12))

    # ---------- create ----------
    def show_create_view(self):
        self.current_view = "create"
        self.clear_main()
        self._set_top("Создать бинд", "Собери цепочку действий и сохрани её как один сценарий")
        outer = ctk.CTkFrame(self.content_host, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(1, weight=1)

        left = self._panel(outer)
        left.grid(row=0, column=0, rowspan=2, padx=(4, 6), pady=4, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Основные данные", font=self._font(20, "bold"), text_color=TEXT_DARK).grid(row=0, column=0, padx=20, pady=(20, 14), sticky="w")
        ctk.CTkLabel(left, text="Название", font=self._font(12, "bold"), text_color=TEXT_DARK).grid(row=1, column=0, padx=20, pady=(0, 5), sticky="w")
        self.name_entry = ctk.CTkEntry(left, height=44, corner_radius=11, placeholder_text="Например: Мой рабочий набор", font=self._font(13), fg_color="#090D10", border_color="#253137")
        self.name_entry.grid(row=2, column=0, padx=20, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(left, text="Горячая клавиша", font=self._font(12, "bold"), text_color=TEXT_DARK).grid(row=3, column=0, padx=20, pady=(0, 5), sticky="w")
        self.hotkey_entry = ctk.CTkEntry(left, height=44, corner_radius=11, placeholder_text="Например: Ctrl+Shift+B", font=self._font(13), fg_color="#090D10", border_color="#253137")
        self.hotkey_entry.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="ew")

        ctk.CTkLabel(left, text="Новое действие", font=self._font(18, "bold"), text_color=TEXT_DARK).grid(row=5, column=0, padx=20, pady=(6, 12), sticky="w")
        self.target_entry = ctk.CTkEntry(left, height=44, corner_radius=11, placeholder_text="C:\\Program Files\\App\\app.exe или https://site.com", font=self._font(12), fg_color="#090D10", border_color="#253137")
        self.target_entry.grid(row=6, column=0, padx=20, pady=(0, 9), sticky="ew")
        file_row = ctk.CTkFrame(left, fg_color="transparent")
        file_row.grid(row=7, column=0, padx=20, pady=(0, 10), sticky="ew")
        file_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(file_row, text="Задержка перед шагом, мс", font=self._font(11), text_color=MUTED_DARK).grid(row=0, column=0, sticky="w")
        self.delay_entry = ctk.CTkEntry(file_row, width=130, height=40, corner_radius=10, font=self._font(12), fg_color="#090D10", border_color="#253137")
        self.delay_entry.insert(0, "500")
        self.delay_entry.grid(row=0, column=1, padx=(10, 0))
        ctk.CTkButton(file_row, text="Выбрать файл", width=118, height=40, corner_radius=10, fg_color="#12191D", hover_color="#1B252A",
                      border_width=1, border_color="#2A373D", text_color=TEXT_DARK, font=self._font(11, "bold"), command=self.pick_file).grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(left, text="+ Добавить действие", height=44, corner_radius=11, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      text_color="#041112", font=self._font(12, "bold"), command=self.add_action).grid(row=8, column=0, padx=20, pady=(0, 20), sticky="ew")

        right = self._panel(outer)
        right.grid(row=0, column=1, padx=(6, 4), pady=4, sticky="nsew")
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="Сценарий", font=self._font(20, "bold"), text_color=TEXT_DARK).grid(row=0, column=0, padx=18, pady=(20, 2), sticky="w")
        ctk.CTkLabel(right, text="Порядок действий будет сохранён именно так, как показано ниже.", font=self._font(11), text_color=MUTED_DARK).grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")
        self.actions_box = ctk.CTkTextbox(right, corner_radius=12, font=self._font(12), fg_color="#080C0F", border_width=1, border_color="#202B30")
        self.actions_box.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.actions_box.configure(state="disabled")
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=3, column=0, padx=14, pady=(0, 14), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions, text="Очистить", width=100, height=40, corner_radius=10, fg_color="transparent", border_width=1, border_color="#303C42",
                      text_color=TEXT_DARK, font=self._font(11, "bold"), command=self.clear_actions).grid(row=0, column=1, padx=(6, 0))
        ctk.CTkButton(actions, text="Сохранить бинд", width=150, height=40, corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      text_color="#041112", font=self._font(11, "bold"), command=self.save_bind).grid(row=0, column=2, padx=(6, 0))
        self.new_actions = []
        self._render_actions()

    # ---------- settings ----------
    def show_settings(self):
        self.current_view = "settings"
        self.clear_main()
        self._set_top("Настройки", "Параметры запуска и внешний вид")
        card = self._panel(self.content_host)
        card.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        ctk.CTkLabel(card, text="Параметры", font=self._font(22, "bold"), text_color=TEXT_DARK).pack(anchor="w", padx=22, pady=(22, 12))

        auto_row = ctk.CTkFrame(card, corner_radius=14, fg_color="#0D1317", border_width=1, border_color="#202B30")
        auto_row.pack(fill="x", padx=18, pady=7)
        text = ctk.CTkFrame(auto_row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=14, pady=13)
        ctk.CTkLabel(text, text="Запускать HiBinds вместе с Windows", font=self._font(14, "bold"), text_color=TEXT_DARK).pack(anchor="w")
        ctk.CTkLabel(text, text="Запускать приложение автоматически после входа в систему.", font=self._font(11), text_color=MUTED_DARK).pack(anchor="w", pady=(2, 0))
        self.autostart_var = tk.BooleanVar(value=bool(self.settings.get("autostart", False)))
        self.autostart_switch = ctk.CTkSwitch(auto_row, text="", variable=self.autostart_var, command=self.toggle_autostart, progress_color=ACCENT,
                                              button_color="#F4FFFF", button_hover_color="#F4FFFF")
        self.autostart_switch.pack(side="right", padx=16)

        theme_row = ctk.CTkFrame(card, corner_radius=14, fg_color="#0D1317", border_width=1, border_color="#202B30")
        theme_row.pack(fill="x", padx=18, pady=7)
        text2 = ctk.CTkFrame(theme_row, fg_color="transparent")
        text2.pack(side="left", fill="x", expand=True, padx=14, pady=13)
        ctk.CTkLabel(text2, text="Тема интерфейса", font=self._font(14, "bold"), text_color=TEXT_DARK).pack(anchor="w")
        ctk.CTkLabel(text2, text="Тёмная тема рекомендуется для нового оформления.", font=self._font(11), text_color=MUTED_DARK).pack(anchor="w", pady=(2, 0))
        self.theme_menu = ctk.CTkOptionMenu(theme_row, values=["Dark", "Light", "System"], command=self.change_appearance, width=150, height=38, corner_radius=10,
                                            fg_color="#12191D", button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                                            font=self._font(11, "bold"), dropdown_font=self._font(11))
        self.theme_menu.set(self.settings.get("appearance", "Dark"))
        self.theme_menu.pack(side="right", padx=16)

        ctk.CTkLabel(card, text="Локальные файлы", font=self._font(17, "bold"), text_color=TEXT_DARK).pack(anchor="w", padx=22, pady=(22, 8))
        ctk.CTkLabel(card, text=f"База: {DB_FILE}", wraplength=760, justify="left", font=self._font(11), text_color=MUTED_DARK).pack(anchor="w", padx=22, pady=(0, 3))
        ctk.CTkLabel(card, text=f"Настройки: {SETTINGS_FILE}", wraplength=760, justify="left", font=self._font(11), text_color=MUTED_DARK).pack(anchor="w", padx=22, pady=(0, 22))

    # ---------- actions ----------
    def pick_file(self):
        path = filedialog.askopenfilename(title="Выбери программу или файл", filetypes=[("Исполняемые файлы", "*.exe"), ("Все файлы", "*.*")])
        if path:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, path)

    def add_action(self):
        target = normalize_target(self.target_entry.get())
        if not target:
            messagebox.showwarning("Нет действия", "Укажи путь к файлу или URL.")
            return
        action_type = "url" if is_url(target) else "app"
        try:
            delay = int(self.delay_entry.get().strip() or "0")
            if delay < 0 or delay > 86_400_000:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Некорректная задержка", "Укажи целое число от 0 до 86400000 мс.")
            return
        if action_type == "app" and not os.path.isfile(target):
            messagebox.showwarning("Файл не найден", "Проверь путь к программе.")
            return
        self.new_actions.append({"type": action_type, "action": target, "delay_ms": delay})
        self._render_actions()
        self.target_entry.delete(0, "end")

    def _render_actions(self):
        if not hasattr(self, "actions_box") or not self.actions_box.winfo_exists():
            return
        self.actions_box.configure(state="normal")
        self.actions_box.delete("1.0", "end")
        for i, action in enumerate(self.new_actions, 1):
            kind = "URL" if action["type"] == "url" else "APP"
            self.actions_box.insert("end", f"{i}. [{kind}] {action['action']}   •   {action['delay_ms']} мс\n")
        self.actions_box.configure(state="disabled")

    def clear_actions(self):
        self.new_actions.clear()
        self._render_actions()

    def save_bind(self):
        name = self.name_entry.get().strip()
        hotkey = self.hotkey_entry.get().strip()
        if not name:
            messagebox.showwarning("Нет названия", "Введи название бинда.")
            return
        if hotkey and not valid_hotkey(hotkey):
            messagebox.showwarning("Некорректная клавиша", "Пример формата: Ctrl+Shift+B, F6 или Alt+Enter.")
            return
        if not self.new_actions:
            messagebox.showwarning("Нет действий", "Добавь хотя бы одно действие.")
            return
        replacing = name in self.binds
        if replacing and not messagebox.askyesno("Бинд существует", f"Заменить существующий бинд «{name}»?"):
            return
        self.binds[name] = {"hotkey": hotkey, "actions": list(self.new_actions)}
        try:
            save_binds(self.binds)
        except OSError as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))
            return
        self.log(f"Сохранён бинд: {name}")
        self.new_actions.clear()
        self.name_entry.delete(0, "end")
        self.hotkey_entry.delete(0, "end")
        self.show_run_view()

    def delete_bind(self, name: str):
        if not messagebox.askyesno("Удаление", f"Удалить бинд «{name}»?"):
            return
        self.binds.pop(name, None)
        try:
            save_binds(self.binds)
        except OSError as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))
            return
        self.log(f"Удалён бинд: {name}")
        self.refresh_bind_list()

    # ---------- import / export ----------
    def export_binds(self):
        if not self.binds:
            messagebox.showinfo("Экспорт", "В базе пока нет биндов.")
            return
        path = filedialog.asksaveasfilename(title="Экспорт биндов", defaultextension=".hibinds", filetypes=[("HiBinds package", "*.hibinds")], initialfile="HiBinds_backup.hibinds")
        if not path:
            return
        payload = {"format": "hibinds", "version": EXPORT_VERSION, "app": APP_NAME, "exported_at": datetime.now().isoformat(timespec="seconds"), "binds": self.binds}
        try:
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.log(f"Экспорт: {path}")
            messagebox.showinfo("Экспорт готов", f"Файл сохранён:\n{path}")
        except OSError as exc:
            messagebox.showerror("Ошибка экспорта", str(exc))

    def import_binds(self):
        path = filedialog.askopenfilename(title="Импорт биндов", filetypes=[("HiBinds package", "*.hibinds"), ("JSON", "*.json"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            imported = payload.get("binds") if isinstance(payload, dict) and payload.get("format") == "hibinds" else payload
            if not isinstance(imported, dict):
                raise ValueError("Файл не содержит корректной базы биндов.")
            _, issues = validate_binds(imported)
            if issues and not messagebox.askyesno("Есть предупреждения", f"После импорта найдено проблем: {len(issues)}.\n\nИмпортировать всё равно?"):
                return
            if self.binds and not messagebox.askyesno("Импорт", "Заменить текущие бинды импортированными?"):
                return
            self.binds = imported
            save_binds(self.binds)
            self.run_validation(show_message=False)
            self.log(f"Импортировано биндов: {len(imported)}")
            self.show_dashboard()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Ошибка импорта", str(exc))

    # ---------- validation ----------
    def run_validation(self, show_message: bool = True):
        self.binds = load_binds()
        working, issues = validate_binds(self.binds)
        self.validation = (working, issues)
        if hasattr(self, "sidebar_status"):
            if issues:
                self.sidebar_status.configure(text=f"⚠  Требуют внимания: {len(issues)}", text_color=("#A96309", "#FFC05F"))
            else:
                self.sidebar_status.configure(text="●  Система готова", text_color=("#168B4C", "#59D68E"))
        if show_message:
            if issues:
                preview = "\n".join(f"• {i['bind']}: {i['message']}" for i in issues[:8])
                extra = f"\n… и ещё {len(issues)-8}" if len(issues) > 8 else ""
                messagebox.showwarning("Проверка завершена", f"Работают: {working}\nПроблем: {len(issues)}\n\n{preview}{extra}")
            else:
                messagebox.showinfo("Проверка завершена", f"✓ Всё в порядке\n\nРабочих биндов: {working}")
        if self.current_view == "dashboard":
            self.show_dashboard()
        elif self.current_view == "binds":
            self.refresh_bind_list()

    # ---------- runner ----------
    def start_bind(self, name: str):
        if self.running:
            messagebox.showinfo("HiBinds занят", "Дождись завершения текущего бинда или нажми «Остановить».")
            return
        if name not in self.binds:
            messagebox.showerror("Ошибка", "Бинд больше не существует.")
            self.refresh_bind_list()
            return
        self.running = True
        self.stop_event.clear()
        self.sidebar_status.configure(text=f"●  Выполняется: {name}", text_color=("#A96309", "#FFC05F"))
        threading.Thread(target=self._run_bind_worker, args=(name,), daemon=True).start()

    def stop_running(self):
        if self.running:
            self.stop_event.set()
            self.log("Запрос остановки отправлен…")

    def _run_bind_worker(self, name: str):
        try:
            info = self.binds.get(name, {})
            actions = info.get("actions", [])
            self.log(f"▶ Запуск: {name}")
            for index, action in enumerate(actions, 1):
                if self.stop_event.is_set():
                    self.log("■ Выполнение остановлено пользователем.")
                    break
                try:
                    delay_ms = int(action.get("delay_ms", 0))
                except (TypeError, ValueError):
                    delay_ms = 0
                self.log(f"Шаг {index}/{len(actions)}: ожидание {delay_ms} мс")
                remaining = max(0, delay_ms) / 1000
                while remaining > 0 and not self.stop_event.is_set():
                    pause = min(0.1, remaining)
                    time.sleep(pause)
                    remaining -= pause
                if self.stop_event.is_set():
                    self.log("■ Выполнение остановлено.")
                    break

                target = normalize_target(str(action.get("action", "")))
                action_type = action.get("type")
                if action_type == "url":
                    if not is_url(target):
                        self.log(f"⚠ Пропущено: некорректный URL")
                        continue
                    webbrowser.open(target, new=2)
                    self.log(f"🌐 Открыто: {target}")
                elif action_type == "app":
                    if not os.path.isfile(target):
                        self.log(f"⚠ Пропущено: файл не найден — {target}")
                        continue
                    try:
                        subprocess.Popen([target], cwd=os.path.dirname(target) or None)
                        self.log(f"▶ Запущено: {target}")
                    except OSError as exc:
                        self.log(f"✕ Не удалось запустить: {exc}")
                else:
                    self.log(f"⚠ Неизвестный тип действия: {action_type!r}")
            else:
                self.log(f"✓ Бинд завершён: {name}")
        except Exception as exc:
            self.log(f"✕ Ошибка выполнения: {exc}")
        finally:
            self.after(0, self._worker_finished)

    def _worker_finished(self):
        self.running = False
        self.run_validation(show_message=False)

    def log(self, message: str):
        self.log_queue.put(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _drain_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if hasattr(self, "console") and self.console.winfo_exists():
                    self.console.configure(state="normal")
                    self.console.insert("end", msg + "\n")
                    self.console.see("end")
                    self.console.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_logs)

    # ---------- settings / shutdown ----------
    def toggle_autostart(self):
        enabled = bool(self.autostart_var.get())
        ok, error = set_windows_autostart(enabled)
        if not ok:
            self.autostart_var.set(False)
            self.settings["autostart"] = False
            save_settings(self.settings)
            messagebox.showerror("Автозапуск", error)
            return
        self.settings["autostart"] = enabled
        save_settings(self.settings)
        self.log("Автозапуск Windows включён." if enabled else "Автозапуск Windows выключен.")

    def change_appearance(self, value: str):
        ctk.set_appearance_mode(value)
        self.settings["appearance"] = value
        save_settings(self.settings)
        self.configure(fg_color=(BG_LIGHT, BG_DARK))

    def _on_close(self):
        self.stop_event.set()
        self.destroy()


if __name__ == "__main__":
    ensure_db()
    app = HiBindsApp()
    app.mainloop()

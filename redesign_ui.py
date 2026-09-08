from pathlib import Path
p = Path('/mnt/data/hibinds_redesign/src/app.py')
s = p.read_text(encoding='utf-8')
# Palette
s = s.replace('ACCENT = "#6C63FF"\nACCENT_HOVER = "#8179FF"', 'ACCENT = "#20D8D2"\nACCENT_HOVER = "#49E7E1"')
s = s.replace('BG_DARK = "#0D1018"\nCARD_DARK = "#151A26"\nCARD_DARK_2 = "#1B2130"\nTEXT_DARK = "#F4F6FA"\nMUTED_DARK = "#9AA4B5"', 'BG_DARK = "#050607"\nCARD_DARK = "#0B0E11"\nCARD_DARK_2 = "#10151A"\nTEXT_DARK = "#F5FAFA"\nMUTED_DARK = "#AAB7BC"')
s = s.replace('BG_LIGHT = "#F4F6FB"\nCARD_LIGHT = "#FFFFFF"\nTEXT_LIGHT = "#171B26"\nMUTED_LIGHT = "#6B7280"', 'BG_LIGHT = "#111417"\nCARD_LIGHT = "#161B1F"\nTEXT_LIGHT = "#F5FAFA"\nMUTED_LIGHT = "#AAB7BC"')
start = s.index('    # ---------- UI shell ----------')
end = s.index('    # ---------- actions ----------')
new = r'''    # ---------- UI shell ----------
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
        self.main = ctk.CTkFrame(self, corner_radius=20, fg_color="#080B0D", border_width=1, border_color="#20292E")
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
        # A few larger stars with cross-like glow made from 2 tiny lines.
        for _ in range(14):
            x = random.uniform(250, 1450)
            y = random.uniform(40, 820)
            size = random.choice([3, 4, 5])
            self.bg_canvas.create_line(x-size, y, x+size, y, fill="#78A5A6", width=1)
            self.bg_canvas.create_line(x, y-size, x, y+size, fill="#78A5A6", width=1)

    def _nav_button(self, text: str, row: int, command):
        btn = ctk.CTkButton(self.sidebar, text=text, height=44, corner_radius=11, anchor="w", fg_color="#0C1114",
                            hover_color="#151D21", border_width=1, border_color="#1B2428", text_color=TEXT_DARK,
                            font=self._font(13, "bold"), command=command)
        btn.grid(row=row, column=0, padx=12, pady=3, sticky="ew")
        return btn

    def _animate_glow(self):
        import math
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

'''
s = s[:start] + new + s[end:]
# Fix root animation startup already uses _animate_glow; okay. Remove old title lines? replace initial window settings and background configure.
s = s.replace('self.geometry("1180x760")\n        self.minsize(980, 680)\n        self.configure(fg_color=(BG_LIGHT, BG_DARK))', 'self.geometry("1280x820")\n        self.minsize(1100, 740)\n        self.configure(fg_color=BG_DARK)')
p.write_text(s, encoding='utf-8')

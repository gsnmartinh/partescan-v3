# -*- coding: utf-8 -*-
"""
PartesTeclea - interfaz.  Lista los partes de partes-para-tecleo.json, marca cuales ya se ingresaron,
permite reintentar uno solo, quitar los ya ingresados, editar datos y teclear en el sistema del Juzgado.
Nunca presiona Aceptar: tu revisas y aceptas cada parte.

Requiere teclea_contextual.py en la misma carpeta y:  pip install pywinauto
"""
import ctypes
import json
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import teclea_contextual as T

try:                       # tema "Sun Valley": aspecto de Windows 11 para ttk
    import sv_ttk
except Exception:          # sin el paquete: se usa un tema ttk normal
    sv_ttk = None

if not hasattr(T, "procesar_lote"):
    raise SystemExit("teclea_contextual.py es una version antigua: reemplazalo por el ultimo que te envie "
                     "(debe estar en la misma carpeta que teclea_gui.py).")

ESTADO_TXT = {
    "pendiente": "Pendiente", "tecleando": "Tecleando...", "tecleado": "Tecleado: falta aceptar",
    "ingresado": "Ingresado", "interrumpido": "Interrumpido", "cancelado": "Sin ingresar (cancelado)",
}
ESTADO_COLOR = {    # (tema claro, tema oscuro)
    "pendiente": ("#1b1b1b", "#e8e8e8"), "tecleando": ("#0b5ed7", "#6cb2ff"), "tecleado": ("#b45f06", "#f0b060"),
    "ingresado": ("#1a7f37", "#5fd48a"), "interrumpido": ("#c00000", "#ff7b72"), "cancelado": ("#c00000", "#ff7b72"),
}
ORIGINAL = {"pausa_tecla": T.PAUSA_TECLA, "espera_inicio": T.ESPERA_INICIO}
PERFIL = T.perfil
VELOCIDADES = {"Rapida": 0.01, "Normal": 0.02, "Lenta": 0.05}
TEMAS = ("Automatico (como Windows)", "Claro", "Oscuro")
COLUMNAS_ANCHAS = ("estado", "n", "parte", "fecha", "oficina", "rut", "placa", "inf", "avisos")
COLUMNAS_ANGOSTAS = ("estado", "parte", "placa", "inf", "avisos")      # media pantalla


def _config_ruta():
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "PartesTeclea" / "config.json"


def _cargar_config():
    try:
        return json.loads(_config_ruta().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _guardar_config(c):
    try:
        _config_ruta().parent.mkdir(parents=True, exist_ok=True)
        _config_ruta().write_text(json.dumps(c, indent=1), encoding="utf-8")
    except Exception:
        pass


def migrar_ajustes_antiguos(cfg):
    """Las actuarias y el reparto por Rol ahora viven en el perfil del juzgado (lo comparte ParteScan)."""
    if "actuarios" in cfg or "rol_actuario" in cfg:
        p = PERFIL.cargar()
        if "actuarios" in cfg:
            p["actuarios"] = {k.upper(): str(v) for k, v in cfg.pop("actuarios").items()}
        if "rol_actuario" in cfg:
            p["rol_actuario"] = {str(d): n.upper() for d, n in cfg.pop("rol_actuario").items()}
        PERFIL.guardar(p)
        _guardar_config(cfg)


def aplicar_ajustes(cfg):
    """Pasa al motor el perfil del juzgado (actuarias, reparto por Rol, oficinas, pantalla) y la velocidad elegida."""
    T.cargar_perfil()
    T.PAUSA_TECLA = float(cfg.get("pausa_tecla", ORIGINAL["pausa_tecla"]))
    T.ESPERA_INICIO = int(float(cfg.get("espera_inicio", ORIGINAL["espera_inicio"])))


def _windows_oscuro():
    """True si Windows esta en modo oscuro para las aplicaciones."""
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        return False


def _dpi_nitido():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _barra_titulo(ventana, oscuro):
    """Barra de titulo oscura/clara acorde al tema (Windows 10 1809+ / 11)."""
    try:
        ventana.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(ventana.winfo_id()) or ventana.winfo_id()
        v = ctypes.c_int(1 if oscuro else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), 4)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(v), 4)
    except Exception:
        pass


def _area_trabajo(root):
    """(x, y, ancho, alto) del area util de la pantalla (sin la barra de tareas)."""
    try:
        import ctypes.wintypes as wt
        r = wt.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        return r.left, r.top, r.right - r.left, r.bottom - r.top
    except Exception:
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48
CAMPOS_EDITABLES = [
    ("n_parte", "N Parte"), ("boleta", "Boleta (Bol/N.Parte)"), ("fecha_parte", "Fecha parte"),
    ("fecha_citacion", "Fecha citacion"), ("hora", "Hora"), ("oficina", "Oficina emisora"),
    ("descripcion", "Descripcion"), ("lugar", "Lugar"), ("rut", "RUT"), ("nombre", "Nombre"),
    ("direccion", "Direccion"), ("comuna", "Comuna"), ("placa", "Placa"),
    ("tipo_vehiculo", "Tipo vehiculo"), ("marca", "Marca"), ("infracciones", "Infracciones (separadas por coma)"),
]


class Salida:
    """Reemplaza sys.stdout mientras corre el motor: manda el texto a la interfaz."""
    def __init__(self, q):
        self.q = q

    def write(self, t):
        if not t or t.strip("\r ") == "":
            return
        if "Empiezo en" in t:
            self.q.put(("estado_txt", t.strip()))
        else:
            self.q.put(("log", t))

    def flush(self):
        pass


class App:
    def __init__(self):
        _dpi_nitido()
        self.cfg = _cargar_config()
        migrar_ajustes_antiguos(self.cfg)
        aplicar_ajustes(self.cfg)
        self.root = tk.Tk()
        self.root.title("PartesTeclea v" + getattr(T, "VERSION", "?"))
        self.oscuro = self._tema_oscuro()
        if sv_ttk:
            sv_ttk.set_theme("dark" if self.oscuro else "light")
        else:
            ttk.Style().theme_use("clam")
        est = ttk.Style()
        est.configure("Treeview", rowheight=int(self.root.winfo_fpixels("1i") / 96 * 28))
        est.configure("Titulo.TLabel", font=("Segoe UI Semibold", 15))
        est.configure("Tenue.TLabel", foreground="#8a8a8a")
        self.root.minsize(520, 460)
        self.q = queue.Queue()
        self.partes = []
        self.ruta = None
        self.quitados = set()
        self.ediciones = {}
        self.hilo = None
        self.var_top = tk.BooleanVar(value=bool(self.cfg.get("siempre_visible", False)))
        self.var_log = tk.BooleanVar(value=bool(self.cfg.get("ver_registro", True)))
        self._ui()
        self._ubicar(self.cfg.get("lado", "libre"), inicio=True)
        _barra_titulo(self.root, self.oscuro)
        self.root.after(100, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.root.bind("<Configure>", self._al_cambiar_tamano)

    def _tema_oscuro(self):
        t = self.cfg.get("tema", TEMAS[0])
        return True if t == "Oscuro" else (False if t == "Claro" else _windows_oscuro())

    # ------------------------------------------------------------------ interfaz
    def _ui(self):
        r = self.root
        r.columnconfigure(0, weight=1)
        r.rowconfigure(3, weight=1)

        # Encabezado: titulo + acoplar a un lado (para usar junto al sistema)
        cab = ttk.Frame(r, padding=(14, 12, 14, 4))
        cab.grid(row=0, column=0, sticky="ew")
        cab.columnconfigure(1, weight=1)
        ttk.Label(cab, text="PartesTeclea", style="Titulo.TLabel").grid(row=0, column=0, sticky="w")
        self.lbl_juz = ttk.Label(cab, text=PERFIL.cargar()["juzgado"] + "  \u00B7  v" + getattr(T, "VERSION", "?"), style="Tenue.TLabel")
        self.lbl_juz.grid(row=0, column=1, sticky="sw", padx=8, pady=(0, 3))
        lado = ttk.Frame(cab)
        lado.grid(row=0, column=2, sticky="e")
        ttk.Label(lado, text="Acoplar:", style="Tenue.TLabel").pack(side="left", padx=(0, 6))
        ttk.Button(lado, text="\u25E7 Izq.", width=7, command=lambda: self._ubicar("izq")).pack(side="left", padx=2)
        ttk.Button(lado, text="Der. \u25E8", width=7, command=lambda: self._ubicar("der")).pack(side="left", padx=2)
        ttk.Button(lado, text="\u25AD", width=3, command=lambda: self._ubicar("libre")).pack(side="left", padx=2)
        ttk.Button(lado, text="\u2699", width=3, command=self.ajustes).pack(side="left", padx=(10, 0))

        # Archivo y opciones
        arch = ttk.Frame(r, padding=(14, 6, 14, 2))
        arch.grid(row=1, column=0, sticky="ew")
        arch.columnconfigure(1, weight=1)
        ttk.Button(arch, text="Abrir archivo\u2026", command=self.abrir).grid(row=0, column=0, sticky="w")
        self.lbl_ruta = ttk.Label(arch, text="(sin archivo)", style="Tenue.TLabel")
        self.lbl_ruta.grid(row=0, column=1, sticky="w", padx=10)
        self.var_auto = tk.BooleanVar(value=bool(self.cfg.get("aceptar_auto", False)))
        ttk.Checkbutton(arch, text="Aceptar cada parte automaticamente", variable=self.var_auto,
                        style="Switch.TCheckbutton").grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        fa = ttk.Frame(arch)
        fa.grid(row=1, column=2, sticky="e", pady=(10, 0))
        ttk.Label(fa, text="Actuario").pack(side="left", padx=(18, 6))
        self.var_act = tk.StringVar(value="Automatico (segun el Rol)")
        self.cb_act = ttk.Combobox(fa, textvariable=self.var_act, width=22, state="readonly",
                                   values=self._lista_actuarios())
        self.cb_act.pack(side="left")

        # Avance
        av = ttk.Frame(r, padding=(14, 8, 14, 4))
        av.grid(row=2, column=0, sticky="ew")
        av.columnconfigure(0, weight=1)
        self.lbl_resumen = ttk.Label(av, text="Sin partes cargadas")
        self.lbl_resumen.grid(row=0, column=0, sticky="w")
        self.barra = ttk.Progressbar(av, mode="determinate", maximum=1)
        self.barra.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # Lista
        tf = ttk.Frame(r, padding=(14, 4))
        tf.grid(row=3, column=0, sticky="nsew")
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tf, columns=COLUMNAS_ANCHAS, show="headings", selectmode="extended", height=8)
        for c, t, w, st in (("estado", "Estado", 175, False), ("n", "#", 36, False), ("parte", "N Parte", 70, False),
                            ("fecha", "Fecha parte", 86, False), ("oficina", "Oficina", 150, False),
                            ("rut", "RUT", 96, False), ("placa", "Placa", 70, False), ("inf", "Infraccion", 80, False),
                            ("avisos", "Avisos", 260, True)):
            self.tree.heading(c, text=t, anchor="w")
            self.tree.column(c, width=w, minwidth=30, anchor="w", stretch=st)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self._colores_estado()
        self.tree.bind("<Double-1>", lambda e: self.editar())
        self.tree.bind("<Button-3>", self._menu_contextual)

        # Acciones
        ac = ttk.Frame(r, padding=(14, 8, 14, 4))
        ac.grid(row=4, column=0, sticky="ew")
        ttk.Button(ac, text="\u25B6  Teclear pendientes", style="Accent.TButton",
                   command=self.teclear_pendientes).pack(side="left")
        ttk.Button(ac, text="\u25A0  Detener", command=self.detener).pack(side="left", padx=6)
        ttk.Button(ac, text="Seguir igual", command=lambda: T.SALTAR.set()).pack(side="left")
        mb = ttk.Menubutton(ac, text="Mas acciones \u25BE")
        mb.pack(side="right")
        self.menu = self._crear_menu(mb)
        mb["menu"] = self.menu

        # Estado y registro
        self.lbl_estado = ttk.Label(r, text="Listo.", padding=(14, 4, 14, 2))
        self.lbl_estado.grid(row=5, column=0, sticky="ew")
        pie = ttk.Frame(r, padding=(14, 0, 14, 10))
        pie.grid(row=6, column=0, sticky="ew")
        pie.columnconfigure(0, weight=1)
        ttk.Checkbutton(pie, text="Mostrar registro", variable=self.var_log, style="Switch.TCheckbutton",
                        command=self._ver_registro).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(pie, text="Siempre visible", variable=self.var_top, style="Switch.TCheckbutton",
                        command=self._aplicar_top).grid(row=0, column=1, sticky="e")
        bg, fg = ("#1f1f1f", "#e6e6e6") if self.oscuro else ("#ffffff", "#1b1b1b")
        self.log = tk.Text(pie, height=7, state="disabled", wrap="word", font=("Consolas", 9), bg=bg, fg=fg,
                           relief="flat", borderwidth=0, highlightthickness=1,
                           highlightbackground="#3a3a3a" if self.oscuro else "#d0d0d0", padx=8, pady=6)
        self._ver_registro()
        self._aplicar_top()

    def _lista_actuarios(self):
        return ["Automatico (segun el Rol)"] + [n.title() for n in T.ACTUARIOS]

    def _crear_menu(self, padre):
        m = tk.Menu(padre, tearoff=0)
        for it in (("Teclear seleccionados", self.teclear_seleccion), None,
                   ("Editar\u2026", self.editar), ("Ver plan", self.ver_plan), None,
                         ("Marcar como ingresado", lambda: self.marcar("ingresado")),
                         ("Marcar como pendiente", lambda: self.marcar("pendiente")),
                         ("Prefijo 99 (folio repetido)", self.prefijo99), None,
                         ("Quitar seleccionados", self.quitar_sel), ("Quitar ingresados", self.quitar_ingresados),
                         ("Restaurar quitados", self.restaurar), None, ("Ajustes\u2026", self.ajustes)):
            if it is None:
                m.add_separator()
            else:
                m.add_command(label=it[0], command=it[1])
        return m

    def _menu_contextual(self, ev):
        fila = self.tree.identify_row(ev.y)
        if fila and fila not in self.tree.selection():
            self.tree.selection_set(fila)
        try:
            self.menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            self.menu.grab_release()

    def _colores_estado(self):
        i = 1 if self.oscuro else 0
        for e, c in ESTADO_COLOR.items():
            self.tree.tag_configure(e, foreground=c[i])

    # ------------------------------------------------------------------ ventana: lado a lado
    def _ubicar(self, lado, inicio=False):
        """izq / der: ocupa media pantalla (para dejar el sistema en la otra mitad). libre: tamano propio."""
        x, y, w, h = _area_trabajo(self.root)
        if lado in ("izq", "der"):
            mw = w // 2
            self.root.geometry(f"{mw}x{h}+{x if lado == 'izq' else x + mw}+{y}")
        else:
            gw, gh = min(980, w - 40), min(640, h - 40)
            if inicio and self.cfg.get("geometria"):
                self.root.geometry(self.cfg["geometria"])
            else:
                self.root.geometry(f"{gw}x{gh}+{x + (w - gw) // 2}+{y + (h - gh) // 2}")
        self.cfg["lado"] = lado
        self.root.after(80, self._ajustar_columnas)

    def ajustes(self):
        if getattr(self, "_win_aj", None) and self._win_aj.winfo_exists():
            self._win_aj.lift()
            return
        win = self._win_aj = tk.Toplevel(self.root)
        win.title("Ajustes")
        win.transient(self.root)
        win.geometry("+%d+%d" % (self.root.winfo_x() + 40, self.root.winfo_y() + 40))
        marco = ttk.Frame(win, padding=16)
        marco.pack(fill="both", expand=True)
        nb = ttk.Notebook(marco)
        nb.pack(fill="both", expand=True)

        # --- Actuarias
        t1 = ttk.Frame(nb, padding=14)
        nb.add(t1, text="Actuarias")
        ttk.Label(t1, text="Nombre y codigo con que se escribe en el sistema (campo Actuario).").grid(
            row=0, column=0, columnspan=3, sticky="w")
        filas = []
        cont = ttk.Frame(t1)
        cont.grid(row=1, column=0, columnspan=3, sticky="ew", pady=6)

        def fila(nombre="", codigo=""):
            f = ttk.Frame(cont)
            f.pack(fill="x", pady=2)
            vn, vc = tk.StringVar(value=nombre.title()), tk.StringVar(value=str(codigo))
            ttk.Entry(f, textvariable=vn, width=22).pack(side="left")
            ttk.Entry(f, textvariable=vc, width=7).pack(side="left", padx=6)
            reg = (f, vn, vc)
            filas.append(reg)
            ttk.Button(f, text="Quitar", width=7, command=lambda: (filas.remove(reg), f.destroy(), refrescar_combos())).pack(
                side="left")
            vn.trace_add("write", lambda *a: refrescar_combos())
        for n, c in T.ACTUARIOS.items():
            fila(n, c)
        ttk.Button(t1, text="+ Agregar actuaria", command=lambda: fila()).grid(row=2, column=0, sticky="w")

        ttk.Separator(t1).grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(t1, text="Quien recibe cada causa segun el ultimo digito del Rol:").grid(
            row=4, column=0, columnspan=3, sticky="w")
        digs = ttk.Frame(t1)
        digs.grid(row=5, column=0, columnspan=3, sticky="w", pady=6)
        combos = {}
        for k, d in enumerate("1234567890"):
            ttk.Label(digs, text="Termina en " + d).grid(row=k % 5, column=(k // 5) * 2, sticky="e", padx=(0, 6), pady=2)
            v = tk.StringVar(value=T.ROL_ACTUARIO.get(d, "").title())
            cb = ttk.Combobox(digs, textvariable=v, width=16, state="readonly")
            cb.grid(row=k % 5, column=(k // 5) * 2 + 1, padx=(0, 18), pady=2)
            combos[d] = (v, cb)

        def nombres():
            return [vn.get().strip().title() for _, vn, _ in filas if vn.get().strip()]

        def refrescar_combos():
            ns = nombres()
            for d, (v, cb) in combos.items():
                cb["values"] = [""] + ns
                if v.get() not in ns:
                    v.set("")
        refrescar_combos()
        for d, (v, cb) in combos.items():
            v.set(T.ROL_ACTUARIO.get(d, "").title() if T.ROL_ACTUARIO.get(d, "").title() in nombres() else "")
        ttk.Label(t1, text="Si un digito queda vacio, el programa espera que elijas la actuaria a mano.",
                  style="Tenue.TLabel").grid(row=6, column=0, columnspan=3, sticky="w")

        # --- Juzgado
        t4 = ttk.Frame(nb, padding=14)
        nb.add(t4, text="Juzgado")
        pj0 = PERFIL.cargar()
        j_juz, j_comuna = tk.StringVar(value=pj0["juzgado"]), tk.StringVar(value=pj0["comuna"])
        j_titulo = tk.StringVar(value=pj0["titulo_ventana"])
        j_ofcar = tk.StringVar(value=pj0["oficina_carabineros"])
        for r, (txt, w) in enumerate((
                ("Nombre del juzgado", ttk.Entry(t4, textvariable=j_juz, width=38)),
                ("Ciudad / comuna", ttk.Entry(t4, textvariable=j_comuna, width=24)),
                ("La pantalla de ingreso empieza con", ttk.Entry(t4, textvariable=j_titulo, width=24)),
                ("Oficina si el parte no dice la unidad", ttk.Combobox(
                    t4, textvariable=j_ofcar, width=36, values=[d for _c, d in PERFIL.oficinas_ordenadas()])))):
            ttk.Label(t4, text=txt).grid(row=r, column=0, sticky="w", pady=4, padx=(0, 14))
            w.grid(row=r, column=1, sticky="w")
        ttk.Separator(t4).grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(t4, text="Listas del sistema (cada juzgado tiene sus propios codigos)").grid(
            row=6, column=0, columnspan=2, sticky="w")
        est = {}
        for k, (tipo, nombre) in enumerate((("infracciones", "Infracciones"), ("oficinas", "Oficinas remisoras"))):
            fr = ttk.Frame(t4)
            fr.grid(row=7 + k, column=0, columnspan=2, sticky="ew", pady=6)
            ttk.Label(fr, text=nombre, width=18).pack(side="left")
            est[tipo] = ttk.Label(fr, text="", style="Tenue.TLabel", width=36)
            est[tipo].pack(side="left")
            ttk.Button(fr, text="Leer desde el sistema", command=lambda t=tipo: self._leer_lista_sistema(t, win, est)).pack(side="left", padx=4)
            ttk.Button(fr, text="Importar .csv", command=lambda t=tipo: self._importar_lista(t, win, est)).pack(side="left")
            ttk.Button(fr, text="De fabrica", command=lambda t=tipo: self._lista_fabrica(t, win, est)).pack(side="left", padx=4)
        self._estado_listas(est)
        ttk.Label(t4, text="Para leerlas: abre en el sistema el cuadro «Busca Infracciones» o «Busca Oficinas Remisoras» y pulsa el boton.",
                  style="Tenue.TLabel", wraplength=560).grid(row=9, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # --- Tecleo
        t2 = ttk.Frame(nb, padding=14)
        nb.add(t2, text="Tecleo")
        v_vel = tk.StringVar(value=next((k for k, x in VELOCIDADES.items() if abs(x - T.PAUSA_TECLA) < 1e-9), "Normal"))
        v_esp = tk.StringVar(value=str(int(T.ESPERA_INICIO)))
        v_tipo = tk.StringVar(value=self.cfg.get("tipo_defecto", ""))
        v_marca = tk.StringVar(value=self.cfg.get("marca_defecto", ""))
        v_auto = tk.BooleanVar(value=bool(self.cfg.get("aceptar_auto", False)))
        for r, (txt, w) in enumerate((
                ("Velocidad de tecleo", ttk.Combobox(t2, textvariable=v_vel, values=list(VELOCIDADES), state="readonly", width=12)),
                ("Segundos de aviso antes de cada parte", ttk.Spinbox(t2, textvariable=v_esp, from_=0, to=15, width=6)),
                ("Tipo de vehiculo si el parte no lo trae", ttk.Entry(t2, textvariable=v_tipo, width=24)),
                ("Marca si el parte no la trae", ttk.Entry(t2, textvariable=v_marca, width=24)))):
            ttk.Label(t2, text=txt).grid(row=r, column=0, sticky="w", pady=6, padx=(0, 14))
            w.grid(row=r, column=1, sticky="w")
        ttk.Checkbutton(t2, text="Aceptar cada parte automaticamente al abrir el programa", variable=v_auto,
                        style="Switch.TCheckbutton").grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Label(t2, text="El tipo y la marca solo se usan en partes con placa y sin ese dato (por ejemplo, 'Station Wagon' y 'Honda').",
                  style="Tenue.TLabel", wraplength=420).grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # --- Apariencia
        t3 = ttk.Frame(nb, padding=14)
        nb.add(t3, text="Apariencia")
        v_tema = tk.StringVar(value=self.cfg.get("tema", TEMAS[0]))
        ttk.Label(t3, text="Tema").grid(row=0, column=0, sticky="w", padx=(0, 14), pady=6)
        ttk.Combobox(t3, textvariable=v_tema, values=TEMAS, state="readonly", width=24).grid(row=0, column=1)
        ttk.Checkbutton(t3, text="Mostrar siempre encima de otras ventanas", variable=self.var_top,
                        style="Switch.TCheckbutton", command=self._aplicar_top).grid(row=1, column=0, columnspan=2, sticky="w", pady=10)

        def guardar_aj():
            ns = [(vn.get().strip().upper(), vc.get().strip()) for _, vn, vc in filas if vn.get().strip()]
            if len({n for n, _ in ns}) != len(ns):
                messagebox.showerror("Ajustes", "Hay dos actuarias con el mismo nombre.", parent=win)
                return
            malas = [n.title() for n, c in ns if not c.isdigit()]
            if malas:
                messagebox.showerror("Ajustes", "El codigo debe ser un numero (" + ", ".join(malas) + ").", parent=win)
                return
            try:
                esp = max(0, min(15, int(v_esp.get())))
            except ValueError:
                messagebox.showerror("Ajustes", "Los segundos de aviso deben ser un numero.", parent=win)
                return
            pj = PERFIL.cargar()
            pj.update({"actuarios": {n: c for n, c in ns},
                       "rol_actuario": {d: v.get().upper() for d, (v, _) in combos.items() if v.get()},
                       "juzgado": j_juz.get().strip() or pj["juzgado"], "comuna": j_comuna.get().strip().upper() or pj["comuna"],
                       "titulo_ventana": j_titulo.get().strip() or pj["titulo_ventana"],
                       "oficina_carabineros": j_ofcar.get().strip() or pj["oficina_carabineros"]})
            PERFIL.guardar(pj)
            self.lbl_juz.config(text=pj["juzgado"] + "  \u00B7  v" + getattr(T, "VERSION", "?"))
            self.cfg.update({
                "pausa_tecla": VELOCIDADES[v_vel.get()], "espera_inicio": esp,
                "tipo_defecto": v_tipo.get().strip(), "marca_defecto": v_marca.get().strip(),
                "aceptar_auto": bool(v_auto.get()), "tema": v_tema.get()})
            aplicar_ajustes(self.cfg)
            self.cb_act["values"] = self._lista_actuarios()
            if self.var_act.get() not in self.cb_act["values"]:
                self.var_act.set(self.cb_act["values"][0])
            _guardar_config(self.cfg)
            self._cambiar_tema()
            self._log("Ajustes guardados.")
            win.destroy()

        def restaurar_aj():
            if messagebox.askyesno("Ajustes", "Volver a los valores originales (actuarias, reparto por Rol y velocidad; las listas no se tocan)?", parent=win):
                for k in ("pausa_tecla", "espera_inicio", "tipo_defecto", "marca_defecto"):
                    self.cfg.pop(k, None)
                pj = PERFIL.cargar()
                for k in ("actuarios", "rol_actuario"):
                    pj[k] = PERFIL.DEFECTO[k]
                PERFIL.guardar(pj)
                aplicar_ajustes(self.cfg)
                self.cb_act["values"] = self._lista_actuarios()
                _guardar_config(self.cfg)
                win.destroy()
                self.ajustes()

        pie = ttk.Frame(marco)
        pie.pack(fill="x", pady=(12, 0))
        ttk.Button(pie, text="Valores originales", command=restaurar_aj).pack(side="left")
        ttk.Button(pie, text="Guardar", style="Accent.TButton", command=guardar_aj).pack(side="right")
        ttk.Button(pie, text="Cancelar", command=win.destroy).pack(side="right", padx=6)
        _barra_titulo(win, self.oscuro)

    def _estado_listas(self, est):
        for tipo, lb in est.items():
            n = len(PERFIL.infracciones() if tipo == "infracciones" else PERFIL.oficinas())
            lb.config(text=("Propia" if PERFIL.es_lista_propia(tipo) else "De fabrica") + f" · {n} codigos")

    def _resumen_lista(self, r):
        t = f"{r['n']} codigos.  Nuevos: {len(r['nuevos'])}.  Con descripcion distinta: {len(r['cambiados'])}.  Que ya no estan: {len(r['quitados'])}."
        if r["nuevos"]:
            t += "\nNuevos: " + ", ".join(r["nuevos"][:25]) + (" ..." if len(r["nuevos"]) > 25 else "")
        return t

    def _leer_lista_sistema(self, tipo, win, est):
        """Espera a que abras «Busca …» en el sistema y la lee completa (solo lectura)."""
        esp = tk.Toplevel(win)
        esp.title("Leer lista del sistema")
        esp.transient(win)
        esp.attributes("-topmost", True)
        marco = ttk.Frame(esp, padding=18)
        marco.pack()
        ttk.Label(marco, text="Abre ahora en el sistema el cuadro «Busca %s».\nLo detecto solo; no lo cierres hasta que termine." %
                  ("Infracciones" if tipo == "infracciones" else "Oficinas Remisoras"), justify="left").pack(anchor="w")
        pb = ttk.Progressbar(marco, mode="indeterminate", length=320)
        pb.pack(pady=12)
        pb.start(12)
        estado = {"vivo": True, "t0": time.time()}

        def cancelar():
            estado["vivo"] = False
            esp.destroy()
        ttk.Button(marco, text="Cancelar", command=cancelar).pack(anchor="e")
        esp.protocol("WM_DELETE_WINDOW", cancelar)
        _barra_titulo(esp, self.oscuro)

        def sondear():
            if not estado["vivo"]:
                return
            try:
                r = T.capturar_lista_abierta()
            except Exception:
                r = None
            if r and r[2]:
                estado["vivo"] = False
                esp.destroy()
                t_leido, titulo, filas = r
                t_final = t_leido or tipo
                if t_leido and t_leido != tipo:
                    messagebox.showinfo("Ajustes", f"El cuadro abierto es «{titulo}»: se guardara como lista de "
                                        f"{'infracciones' if t_leido == 'infracciones' else 'oficinas'}.", parent=win)
                if len(filas) < 3 or not messagebox.askyesno(
                        "Ajustes", f"Lei {len(filas)} elementos de «{titulo}».\n\nGuardar como lista de {t_final}?", parent=win):
                    if len(filas) < 3:
                        messagebox.showwarning("Ajustes", "La lista leida es muy corta; no se guardo.", parent=win)
                    return
                res = PERFIL.guardar_lista(t_final, filas)
                T.cargar_perfil()
                self._estado_listas(est)
                self._log(f"Lista de {t_final} actualizada desde el sistema.\n" + self._resumen_lista(res))
                messagebox.showinfo("Ajustes", "Lista guardada.\n\n" + self._resumen_lista(res), parent=win)
                return
            if time.time() - estado["t0"] > 180:
                cancelar()
                messagebox.showwarning("Ajustes", "No encontre el cuadro abierto (espere 3 minutos).", parent=win)
                return
            esp.after(700, sondear)
        esp.after(500, sondear)

    def _importar_lista(self, tipo, win, est):
        ruta = filedialog.askopenfilename(parent=win, title="Lista en .csv (codigo;descripcion)",
                                          filetypes=[("CSV", "*.csv *.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            res = PERFIL.importar(tipo, Path(ruta).read_text(encoding="utf-8-sig", errors="replace"))
        except Exception as e:
            messagebox.showerror("Ajustes", str(e), parent=win)
            return
        T.cargar_perfil()
        self._estado_listas(est)
        messagebox.showinfo("Ajustes", "Lista importada.\n\n" + self._resumen_lista(res), parent=win)

    def _lista_fabrica(self, tipo, win, est):
        if messagebox.askyesno("Ajustes", "Volver a la lista de fabrica (2° Juzgado de Valdivia)?", parent=win):
            PERFIL.restaurar_lista(tipo)
            T.cargar_perfil()
            self._estado_listas(est)

    def _cambiar_tema(self):
        osc = self._tema_oscuro()
        if osc == self.oscuro:
            return
        self.oscuro = osc
        if sv_ttk:
            sv_ttk.set_theme("dark" if osc else "light")
            ttk.Style().configure("Treeview", rowheight=int(self.root.winfo_fpixels("1i") / 96 * 28))
            ttk.Style().configure("Titulo.TLabel", font=("Segoe UI Semibold", 15))
            ttk.Style().configure("Tenue.TLabel", foreground="#8a8a8a")
        self._colores_estado()
        self.log.config(bg="#1f1f1f" if osc else "#ffffff", fg="#e6e6e6" if osc else "#1b1b1b",
                        highlightbackground="#3a3a3a" if osc else "#d0d0d0")
        _barra_titulo(self.root, osc)

    def _aplicar_top(self):
        self.root.attributes("-topmost", bool(self.var_top.get()))

    def _ver_registro(self):
        if self.var_log.get():
            self.log.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        else:
            self.log.grid_remove()

    def _al_cambiar_tamano(self, ev):
        if ev.widget is self.root:
            if getattr(self, "_t_aj", None):
                self.root.after_cancel(self._t_aj)
            self._t_aj = self.root.after(120, self._ajustar_columnas)

    def _ajustar_columnas(self):
        self._t_aj = None
        angosto = self.root.winfo_width() < int(self.root.winfo_fpixels("1i") / 96 * 860)
        self.tree.configure(displaycolumns=COLUMNAS_ANGOSTAS if angosto else COLUMNAS_ANCHAS)

    # ------------------------------------------------------------------ datos
    def _estado_ruta(self):
        return self.ruta.with_suffix(".estado.json")

    def abrir(self, ruta=None):
        if ruta is None:
            ruta = filedialog.askopenfilename(title="partes-para-tecleo.json",
                                              initialdir=str(T.ruta_por_defecto().parent),
                                              filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            partes = T.cargar_partes(ruta)
        except Exception as e:
            messagebox.showerror("PartesTeclea", f"No pude leer el archivo:\n{e}")
            return
        self.ruta = Path(ruta)
        vistas = {}
        for p in partes:
            c = f"{p['n_parte']}|{p['fecha_parte']}|{p['boleta']}"
            vistas[c] = vistas.get(c, 0) + 1
            p["_clave"] = c if vistas[c] == 1 else f"{c}#{vistas[c]}"
        est = {}
        try:
            d = json.loads(self._estado_ruta().read_text(encoding="utf-8"))
            est = d.get("estados", {})
            self.quitados = set(d.get("quitados", []))
            self.ediciones = d.get("ediciones", {})
        except Exception:
            self.quitados, self.ediciones = set(), {}
        for p in partes:
            p["_estado"] = est.get(p["_clave"], "pendiente")
            p["_aviso"] = ""
            p["_n_original"] = p["n_parte"]
            for k, v in self.ediciones.get(p["_clave"], {}).items():
                p[k] = v
        for p in partes:     # valores por defecto de Ajustes: solo rellenan lo que el parte no trae
            if p["placa"] and not p["tipo_vehiculo"] and self.cfg.get("tipo_defecto"):
                p["tipo_vehiculo"] = self.cfg["tipo_defecto"]
            if p["placa"] and not p["marca"] and self.cfg.get("marca_defecto"):
                p["marca"] = self.cfg["marca_defecto"]
        self.partes = partes
        self.lbl_ruta.config(text=f"{self.ruta.name}  ({len(partes)} partes)")
        self.refrescar()
        self._log(f"Cargado {self.ruta} con {len(partes)} partes.")

    def guardar(self):
        if not self.ruta:
            return
        d = {"estados": {p["_clave"]: p["_estado"] for p in self.partes},
             "quitados": sorted(self.quitados), "ediciones": self.ediciones}
        try:
            self._estado_ruta().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            self._log(f"No pude guardar el estado: {e}")

    def visibles(self):
        return [i for i, p in enumerate(self.partes) if p["_clave"] not in self.quitados]

    def _chequeo(self):
        for i, p in enumerate(self.partes):
            fat, avi = T.validar_parte(p)
            avi = [a for a in avi if not a.startswith("sin rut")]
            p["_chk"] = "; ".join(fat + avi)

    def refrescar(self):
        self._chequeo()
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for n, i in enumerate(self.visibles(), 1):
            p = self.partes[i]
            fila = (ESTADO_TXT.get(p["_estado"], p["_estado"]), n, p["n_parte"], p["fecha_parte"],
                    p.get("oficina", ""), p["rut"], p["placa"], (T.resolver_infraccion(p["infracciones"][0])[0] if p["infracciones"] else ""), " | ".join(x for x in (p["_aviso"], p["_chk"]) if x))
            self.tree.insert("", "end", iid=str(i), values=fila, tags=(p["_estado"],))
        for i in sel:
            if self.tree.exists(i):
                self.tree.selection_add(i)
        self._resumen()

    def _resumen(self):
        v = [self.partes[i] for i in self.visibles()]
        if not v:
            self.lbl_resumen.config(text="Sin partes cargadas")
            self.barra.config(value=0, maximum=1)
            return
        cuenta = lambda e: sum(1 for p in v if p["_estado"] == e)
        ing, pen = cuenta("ingresado"), cuenta("pendiente")
        otros = []
        if cuenta("tecleado"):
            otros.append(f"{cuenta('tecleado')} por aceptar")
        if cuenta("interrumpido") + cuenta("cancelado"):
            otros.append(f"{cuenta('interrumpido') + cuenta('cancelado')} sin ingresar")
        self.lbl_resumen.config(text=f"{ing} de {len(v)} ingresados  \u00B7  {pen} pendientes" +
                                ("".join("  \u00B7  " + o for o in otros)))
        self.barra.config(maximum=len(v), value=ing)

    def _sel(self):
        return sorted(int(i) for i in self.tree.selection())

    # ------------------------------------------------------------------ acciones sobre la lista
    def marcar(self, estado):
        for i in self._sel():
            self.partes[i]["_estado"] = estado
        self.guardar()
        self.refrescar()

    def quitar_sel(self):
        s = self._sel()
        if s and messagebox.askyesno("PartesTeclea", f"Quitar {len(s)} parte(s) de la lista?\n"
                                     "(No se borra nada del sistema ni del archivo.)"):
            self.quitados.update(self.partes[i]["_clave"] for i in s)
            self.guardar()
            self.refrescar()

    def quitar_ingresados(self):
        ing = [p["_clave"] for p in self.partes if p["_estado"] == "ingresado"]
        if ing and messagebox.askyesno("PartesTeclea", f"Quitar los {len(ing)} partes ya ingresados de la lista?"):
            self.quitados.update(ing)
            self.guardar()
            self.refrescar()

    def restaurar(self):
        self.quitados.clear()
        self.guardar()
        self.refrescar()

    def prefijo99(self):
        for i in self._sel():
            p = self.partes[i]
            if not p["n_parte"].startswith("99"):
                p["n_parte"] = "99" + p["n_parte"]
                self.ediciones.setdefault(p["_clave"], {})["n_parte"] = p["n_parte"]
            p["_estado"] = "pendiente"
        self.guardar()
        self.refrescar()

    def editar(self):
        s = self._sel()
        if not s:
            return
        p = self.partes[s[0]]
        win = tk.Toplevel(self.root)
        win.title(f"Editar parte {p['n_parte']}")
        win.transient(self.root)
        win.attributes("-topmost", True)
        marco = ttk.Frame(win, padding=16)
        marco.pack(fill="both", expand=True)
        marco.columnconfigure(1, weight=1)
        vars_ = {}
        for r, (k, t) in enumerate(CAMPOS_EDITABLES):
            ttk.Label(marco, text=t).grid(row=r, column=0, sticky="e", padx=(0, 10), pady=3)
            v = ", ".join(p.get(k, [])) if k == "infracciones" else str(p.get(k, ""))
            vars_[k] = tk.StringVar(value=v)
            ttk.Entry(marco, textvariable=vars_[k], width=56).grid(row=r, column=1, sticky="ew", pady=3)
        _barra_titulo(win, self.oscuro)

        def ok():
            ed = self.ediciones.setdefault(p["_clave"], {})
            for k, v in vars_.items():
                nuevo = [x.strip() for x in v.get().split(",") if x.strip()] if k == "infracciones" else v.get().strip()
                if nuevo != p.get(k, ""):
                    p[k] = nuevo
                    ed[k] = nuevo
            self.guardar()
            self.refrescar()
            win.destroy()
        ttk.Button(marco, text="Guardar", style="Accent.TButton", command=ok).grid(
            row=len(CAMPOS_EDITABLES), column=1, sticky="e", pady=(12, 0))

    def ver_plan(self):
        s = self._sel() or self.visibles()[:1]
        old = sys.stdout
        sys.stdout = Salida(self.q)
        try:
            for i in s[:5]:
                fat, avi = T.validar_parte(self.partes[i])
                T.mostrar_plan(i + 1, len(self.partes), self.partes[i], fat, avi)
        finally:
            sys.stdout = old

    # ------------------------------------------------------------------ ejecucion
    def _aplicar_actuario(self):
        v = self.var_act.get()
        T.ACTUARIO = "" if v.startswith("Auto") else v.upper()

    def teclear_pendientes(self):
        idx = [i for i in self.visibles() if self.partes[i]["_estado"] in ("pendiente", "interrumpido", "cancelado")]
        self._lanzar(idx)

    def teclear_seleccion(self):
        self._lanzar([i for i in self._sel()])

    def _lanzar(self, idx):
        if self.hilo and self.hilo.is_alive():
            messagebox.showinfo("PartesTeclea", "Ya hay un ingreso en curso.")
            return
        if not idx:
            messagebox.showinfo("PartesTeclea", "No hay partes para teclear.")
            return
        graves = []
        for i in idx:
            fat, _ = T.validar_parte(self.partes[i])
            if fat:
                graves.append(f"Parte {self.partes[i]['n_parte']}: " + "; ".join(fat))
        if graves:
            messagebox.showerror("PartesTeclea", "Corrige estos datos (Editar...):\n\n" + "\n".join(graves))
            return
        T.cargar_perfil()          # por si cambio el perfil (ParteScan u otro computador de la oficina)
        self._aplicar_actuario()
        T.PARAR.clear()
        T.SALTAR.clear()
        self._log(f"--- Ingresando {len(idx)} parte(s) ---")
        self.hilo = threading.Thread(target=self._worker, args=(idx, self.var_auto.get()), daemon=True)
        self.hilo.start()

    def _worker(self, idx, auto=False):
        old = sys.stdout
        sys.stdout = Salida(self.q)
        try:
            if not T.WIN or T.send_keys is None:
                raise T.Detener("Se necesita Windows y pywinauto (pip install pywinauto).")
            sis = T.Sistema()
            T.procesar_lote(sis, self.partes, idx,
                            on_estado=lambda i, e, d="": self.q.put(("parte", i, e, d)),
                            aceptar_auto=auto)
        except T.Detener as e:
            self.q.put(("log", f"[detenido] {e}\nNo se hizo clic en nada."))
        except Exception:
            self.q.put(("log", "[error inesperado]\n" + traceback.format_exc()))
        finally:
            sys.stdout = old
            self.q.put(("fin",))

    def detener(self):
        T.PARAR.set()
        self._log("Deteniendo...")

    # ------------------------------------------------------------------ cola de eventos
    def _poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "log":
                    self._log(m[1])
                elif m[0] == "estado_txt":
                    self.lbl_estado.config(text=m[1])
                elif m[0] == "parte":
                    _, i, e, d = m
                    p = self.partes[i]
                    p["_estado"] = e
                    p["_aviso"] = d if e in ("tecleado", "interrumpido") else ""
                    self.lbl_estado.config(text=f"Parte {p['n_parte']}: {ESTADO_TXT.get(e, e)}")
                    self.guardar()
                    self.refrescar()
                elif m[0] == "fin":
                    self.lbl_estado.config(text="Listo.")
                    self.guardar()
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _log(self, t):
        self.log.config(state="normal")
        self.log.insert("end", t.rstrip("\n") + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _cerrar(self):
        if self.hilo and self.hilo.is_alive():
            T.PARAR.set()
        self.guardar()
        self.cfg["siempre_visible"] = bool(self.var_top.get())
        self.cfg["ver_registro"] = bool(self.var_log.get())
        self.cfg["aceptar_auto"] = bool(self.cfg.get("aceptar_auto", False))
        if self.cfg.get("lado") == "libre":
            self.cfg["geometria"] = self.root.geometry()
        _guardar_config(self.cfg)
        self.root.destroy()

    def run(self, ruta=None):
        if ruta:
            self.abrir(ruta)
        self.root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--autotest":   # prueba de humo para la compilacion automatica
        try:      # abre la ventana de verdad (comprueba que el tema Windows 11 quedo empaquetado) y la cierra
            _a = App()
            _a.root.update()
            _a.root.destroy()
            gui = "gui=ok tema=" + ("sv_ttk" if sv_ttk else "basico")
        except Exception:
            gui = "gui=ERROR " + traceback.format_exc().replace("\n", " | ")
        Path(sys.argv[2]).write_text("ok " + getattr(T, "VERSION", "?") + " tabla=%d " % len(T.tabla_infracciones()) + gui,
                                     encoding="utf-8")
        raise SystemExit(0)
    App().run(sys.argv[1] if len(sys.argv) > 1 else None)

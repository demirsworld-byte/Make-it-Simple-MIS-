import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import sys
import yaml
import hashlib
import logging
import random
import time
import math
import psutil
import subprocess

# ===========================
# Dizinler
# ===========================
APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
PROGRAM_FOLDER = os.path.join(APPDATA, "Make_It_Simple")
SETTINGS_PATH = os.path.join(PROGRAM_FOLDER, "settings.yml")
SECRETS_PATH = os.path.join(PROGRAM_FOLDER, "secrets.yml")
EXTENSIONS_FOLDER = os.path.join(PROGRAM_FOLDER, "extensions")

os.makedirs(PROGRAM_FOLDER, exist_ok=True)
os.makedirs(EXTENSIONS_FOLDER, exist_ok=True)

# ===========================
# Logging
# ===========================
logging.basicConfig(
    filename=os.path.join(PROGRAM_FOLDER, "error.log"),
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def tum_hatalari_yakala(exc_type, exc_value, exc_traceback):
    logging.critical(
        "YAKALANMAYAN HATA",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

sys.excepthook = tum_hatalari_yakala

# ===========================
# Ayarlar + Token
# ===========================
default_settings = {"theme": "dark"}

def set_settings_to_default():
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(default_settings, f)

def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        set_settings_to_default()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or default_settings
    except Exception:
        logging.exception("settings.yml okunamadı, varsayılan kullanılıyor")
        settings = default_settings
    ctk.set_appearance_mode(settings.get("theme", "dark"))
    return settings

def reset_secrets(token: str) -> str:
    return hashlib.sha256(str(token).encode()).hexdigest()

FIRST_RUN = False
READABLE_TOKEN = None
secrets = {}

def load_secrets():
    global FIRST_RUN, READABLE_TOKEN, secrets
    if not os.path.exists(SECRETS_PATH):
        FIRST_RUN = True
        READABLE_TOKEN = random.randint(100000, 999999)
        secrets = {"token": reset_secrets(READABLE_TOKEN)}
        with open(SECRETS_PATH, "w", encoding="utf-8") as f:
            yaml.dump(secrets, f)
    else:
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {}
        except Exception:
            logging.exception("secrets.yml okunamadı, yeni token oluşturuluyor")
            FIRST_RUN = True
            READABLE_TOKEN = random.randint(100000, 999999)
            secrets = {"token": reset_secrets(READABLE_TOKEN)}
            with open(SECRETS_PATH, "w", encoding="utf-8") as f:
                yaml.dump(secrets, f)

def check_token(action_text="Bu işlem"):
    if "token" not in secrets:
        messagebox.showerror("Güvenlik Hatası", "Güvenlik tokeni bulunamadı.")
        return False

    dialog = ctk.CTkInputDialog(
        text=f"{action_text} için güvenlik tokenini girin:",
        title="Güvenlik Doğrulaması"
    )
    entered = dialog.get_input()

    if not entered:
        return False

    if reset_secrets(entered) == secrets["token"]:
        return True

    messagebox.showerror("Hatalı Token", "Girdiğiniz token yanlış.")
    return False

# ===========================
# Plugin Event Bus (api.emit / api.on)
# ===========================
class PluginEventBus:
    def __init__(self):
        self._handlers = {}

    def on(self, event_name: str, callback):
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(callback)

    def emit(self, event_name: str, data=None):
        if event_name not in self._handlers:
            return
        for cb in self._handlers[event_name]:
            try:
                cb(data)
            except Exception:
                logging.exception(f"Event handler hatası: {event_name}")

# ===========================
# Plugin API (güçlü sürüm)
# ===========================
class PluginAPI:
    def __init__(self, app, plugin_panel, top_menu, tabview, event_bus: PluginEventBus):
        self.app = app
        self.plugin_panel = plugin_panel
        self.top_menu = top_menu
        self.tabview = tabview
        self.event_bus = event_bus

    # ---- UI Temel ----
    def notify(self, title: str, message: str):
        messagebox.showinfo(title, message)

    def alert(self, title: str, message: str):
        messagebox.showwarning(title, message)

    def error(self, title: str, message: str):
        messagebox.showerror(title, message)

    def log(self, msg: str):
        logging.info("[PLUGIN] " + msg)

    # ---- Token / Güvenlik ----
    def require_token(self, action_name="Bu işlem") -> bool:
        return check_token(action_name)

    # ---- Plugin paneline buton ekleme ----
    def button(self, text: str, command):
        btn = ctk.CTkButton(self.plugin_panel, text=text, command=command)
        btn.pack(pady=4, padx=8, anchor="w")
        return btn

    # ---- Üst menüye buton ekleme ----
    def menu_button(self, text: str, command, side="right"):
        btn = ctk.CTkButton(self.top_menu, text=text, command=command, width=120)
        btn.pack(side=side, padx=4, pady=6)
        return btn

    # ---- Yeni pencere oluşturma ----
        # Yeni pencere açma (Eski sisteme tam uyumlu)
    def create_window(self, title="Pencere", size="400x300"):
        import customtkinter as ctk
        win = ctk.CTkToplevel()
        win.title(title)
        win.geometry(size)

        frame = ctk.CTkFrame(win)
        frame.pack(expand=True, fill="both", padx=15, pady=15)

        return win, frame


    # ---- TabView içine yeni sekme ekleme ----
    def add_tab(self, name: str):
        tab = self.tabview.add(name)
        return tab

    # ---- Dosya & klasör diyalogları ----
    def ask_file(self, title="Dosya Seç", filetypes=(("Tüm Dosyalar", "*.*"),)):
        return filedialog.askopenfilename(title=title, filetypes=filetypes)

    def ask_folder(self, title="Klasör Seç"):
        return filedialog.askdirectory(title=title)

    # ---- Dosya okuma / yazma ----
    def read_file(self, path: str, mode="r", encoding="utf-8"):
        with open(path, mode, encoding=encoding if "b" not in mode else None) as f:
            return f.read()

    def write_file(self, path: str, content: str, mode="w", encoding="utf-8"):
        with open(path, mode, encoding=encoding if "b" not in mode else None) as f:
            f.write(content)

    # ---- Sistem bilgisi ----
    def get_cpu(self) -> float:
        return psutil.cpu_percent(interval=0.1)

    def get_ram(self) -> float:
        return psutil.virtual_memory().percent

    def get_disk(self, drive="C:/") -> float:
        try:
            return psutil.disk_usage(drive).percent
        except Exception:
            return 0.0

    # ---- Event sistemi ----
    def emit(self, event_name: str, data=None):
        self.event_bus.emit(event_name, data)

    def on(self, event_name: str, callback):
        self.event_bus.on(event_name, callback)
# ===========================
# Başlatma (settings + secrets)
# ===========================
settings = load_settings()
load_secrets()
event_bus = PluginEventBus()

# ===========================
# Ana Uygulama
# ===========================
app = ctk.CTk()
app.geometry("1000x650")
app.title("Make It Simple")

# İlk defa çalışıyorsa token göster
if FIRST_RUN and READABLE_TOKEN is not None:
    app.after(300, lambda: messagebox.showinfo(
        "Güvenlik Tokeni",
        f"İlk tokeniniz:\n\n{READABLE_TOKEN}\n\nBunu güvenli bir yere kaydedin!"
    ))

# ===========================
# Splash ekran (isteğe bağlı)
# ===========================
splash = ctk.CTkToplevel(app)
splash.title("Yükleniyor...")
splash.geometry("380x180")
splash.resizable(False, False)

s_frame = ctk.CTkFrame(splash)
s_frame.pack(expand=True, fill="both", padx=20, pady=20)

s_canvas = ctk.CTkCanvas(s_frame, width=200, height=80, highlightthickness=0, bg="#101010")
s_canvas.pack(pady=10)

s_label = ctk.CTkLabel(s_frame, text="Make It Simple açılıyor...", font=ctk.CTkFont(size=14))
s_label.pack()

angle = 0
start_time = time.time()

def animate_splash():
    global angle
    if time.time() - start_time > 2.0:
        splash.destroy()
        app.deiconify()
        return

    s_canvas.delete("all")
    for i in range(10):
        x = 100 + 28 * math.cos(math.radians(angle + i * 36))
        y = 40 + 28 * math.sin(math.radians(angle + i * 36))
        s_canvas.create_oval(x-4, y-4, x+4, y+4, fill="#00aaff", outline="")
    angle += 10
    splash.after(40, animate_splash)

# Başta ana pencere gizli olsun
app.withdraw()
animate_splash()

# ===========================
# Üst Menü
# ===========================
top_menu = ctk.CTkFrame(app, height=50, fg_color="#111827")
top_menu.pack(fill="x")

title_label = ctk.CTkLabel(
    top_menu,
    text="Make It Simple",
    font=ctk.CTkFont(size=20, weight="bold")
)
title_label.pack(side="left", padx=20)

loaded_plugins = ["Varsayılan Eklenti"]

def show_plugins():
    if loaded_plugins:
        text = "Yüklü eklentiler:\n\n" + "\n".join(f"• {p}" for p in loaded_plugins)
    else:
        text = "Yüklü eklenti bulunamadı."
    messagebox.showinfo("Eklentiler", text)

def close_ps():
    if not check_token("Bilgisayarı kapatmak"):
        return
    os.system("shutdown /s /t 1")

def restart_ps():
    if not check_token("Bilgisayarı yeniden başlatmak"):
        return
    os.system("shutdown /r /t 1")

def sleep_ps():
    if not check_token("Bilgisayarı uyku moduna almak"):
        return
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

def close_app():
    if not check_token("Programdan çıkmak"):
        return
    app.destroy()

ctk.CTkButton(top_menu, text="Eklentiler", command=show_plugins, width=110).pack(side="right", padx=4, pady=8)
ctk.CTkButton(top_menu, text="Kapat", command=close_ps, width=90).pack(side="right", padx=4)
ctk.CTkButton(top_menu, text="Yeniden Başlat", command=restart_ps, width=130).pack(side="right", padx=4)
ctk.CTkButton(top_menu, text="Uyku", command=sleep_ps, width=90).pack(side="right", padx=4)
ctk.CTkButton(top_menu, text="Çıkış", command=close_app, width=90).pack(side="right", padx=10)

# ===========================
# Ana Layout: Plugin Panel + TabView
# ===========================
plugin_panel = ctk.CTkFrame(app)
plugin_panel.pack(fill="x", padx=20, pady=(10, 0))

ctk.CTkLabel(plugin_panel, text="Eklentiler", anchor="w").pack(fill="x", padx=10, pady=4)

main_frame = ctk.CTkFrame(app)
main_frame.pack(expand=True, fill="both", padx=20, pady=20)

tabview = ctk.CTkTabview(main_frame)
tabview.pack(expand=True, fill="both")

tab_system = tabview.add("Sistem Durumu")

sys_label = ctk.CTkLabel(tab_system, text="Sistem bilgisi yükleniyor...", font=ctk.CTkFont(size=14))
sys_label.pack(pady=10)

def update_system():
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("C:/").percent
        sys_label.configure(text=f"CPU: {cpu:.1f}% | RAM: {ram:.1f}% | Disk: {disk:.1f}%")
        # Event ile eklentilere sistem güncellendi sinyali gönder
        event_bus.emit("system.update", {"cpu": cpu, "ram": ram, "disk": disk})
    except Exception:
        logging.exception("Sistem bilgisi okunamadı")
    app.after(1000, update_system)

update_system()

# ===========================
# Plugin Loader
# ===========================
def load_plugins():
    loaded_plugins.clear()
    for folder in os.listdir(EXTENSIONS_FOLDER):
        plug_path = os.path.join(EXTENSIONS_FOLDER, folder)
        manifest = os.path.join(plug_path, "manifest.yml")
        main_file = os.path.join(plug_path, "main.py")

        if not (os.path.isdir(plug_path) and os.path.exists(manifest) and os.path.exists(main_file)):
            continue

        try:
            with open(manifest, "r", encoding="utf-8") as f:
                info = yaml.safe_load(f) or {}

            spec = {}
            with open(main_file, "r", encoding="utf-8") as f:
                code = f.read()
                exec(code, spec)

            if "run" in spec and callable(spec["run"]):
                api = PluginAPI(app, plugin_panel, top_menu, tabview, event_bus)
                spec["run"](api)
                plugin_name = info.get("name", folder)
                loaded_plugins.append(plugin_name)
        except Exception:
            logging.exception(f"Eklenti yüklenemedi: {folder}")

def reload_plugins():
    # Paneli temizle
    for child in plugin_panel.winfo_children():
        if isinstance(child, ctk.CTkButton) or isinstance(child, ctk.CTkLabel):
            # başlıktaki label kalsın
            if getattr(child, "cget", None) and child.cget("text") == "Eklentiler":
                continue
            child.destroy()
    load_plugins()
    messagebox.showinfo("Eklentiler", "Eklentiler yenilendi.")

# Üst menüye Eklentileri Yenile butonu ekleyelim
ctk.CTkButton(top_menu, text="Eklentileri Yenile", command=reload_plugins, width=140).pack(side="right", padx=4)

# İlk otomatik yükleme
app.after(1500, load_plugins)
# ===========================
# MAINLOOP
# ===========================
app.mainloop()
# 275529
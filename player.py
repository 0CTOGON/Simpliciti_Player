import customtkinter as ctk
from tkinter import filedialog
import pygame
import os
import json
import random
import ctypes
import sys
from pathlib import Path

# ----- 3rd‑party audio meta data --------------------------------
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from PIL import Image

# --------------------------------------------------------------
# 1️⃣   APP‑DATA PATH SETUP
# --------------------------------------------------------------
# 1️⃣.1  Cross‑platform “user data” folder -------------------------------------------------
# You can replace this with the tiny `appdirs` package if you prefer:
#   from appdirs import user_data_dir
#   APPDATA_ROOT = Path(user_data_dir("SimplicitiPlayer"))
# For pure‑standard‑lib we construct it manually on Windows:

if sys.platform.startswith("win"):
    # Windows → %APPDATA% (Roaming)
    APPDATA_ROOT = Path(os.getenv("APPDATA")) / "SimplicitiPlayer"
else:
    # macOS & Linux → XDG / Home fallback
    APPDATA_ROOT = Path.home() / ".simpliciti_player"

# 1️⃣.2  Make sure the folder exists -------------------------------------------------
APPDATA_ROOT.mkdir(parents=True, exist_ok=True)

# 1️⃣.3  Where the JSON file will live ------------------------------------------------
PLAYLIST_FILE = APPDATA_ROOT / "playlist.json"

# --------------------------------------------------------------
# 2️⃣   TKINTER / PYGAME INITIALISATION
# --------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

pygame.mixer.init()
pygame.mixer.music.set_volume(1.0)

playlist = []          # list of absolute file‑paths (strings)
current_index = 0
is_playing = False
paused = False
loop_mode = False
shuffle_mode = False

# --------------------------------------------------------------
# 3️⃣   FONTS & SIZES (unchanged)
# --------------------------------------------------------------
p = ("Google Sans Code", 12)
h = ("Google Sans Code", 22, "bold")
small = ("Google Sans Code", 10)

ICON_MAIN = (24, 24)
ICON_SMALL = (20, 20)
ICON_ADD = (26, 26)

BTN_MAIN = 50
BTN_SMALL = 40

# --------------------------------------------------------------
# 4️⃣   HELPER: RESOURCE PATH (works both when frozen & when running from source)
# --------------------------------------------------------------
def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        # cx_Freeze executable directory
        base_path = Path(sys.executable).parent
    else:
        # running from source
        base_path = Path(__file__).parent

    return base_path / relative_path

# --------------------------------------------------------------
# 5️⃣   APP WINDOW SETUP
# --------------------------------------------------------------
app = ctk.CTk()
app.geometry("400x370")
app.title("Simpliciti Player")
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Simpliciti.Player.1")
app.iconbitmap(str(resource_path("icons/logo.ico")))
app.overrideredirect(True)

# ----- Task‑bar fix (unchanged) ---------------------------------
app.update_idletasks()
hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
style = style & ~WS_EX_TOOLWINDOW | WS_EX_APPWINDOW
ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
app.withdraw()
app.after(10, app.deiconify)

# --------------------------------------------------------------
# 6️⃣   CUSTOM TITLE BAR (unchanged)
# --------------------------------------------------------------
title_bar = ctk.CTkFrame(app, height=30)
title_bar.pack(fill="x")

def start_move(event):
    app.x = event.x
    app.y = event.y

def do_move(event):
    x = event.x_root - app.x
    y = event.y_root - app.y
    app.geometry(f"+{x}+{y}")

title_bar.bind("<Button-1>", start_move)
title_bar.bind("<B1-Motion>", do_move)

def close_app():
    save_playlist()
    app.destroy()

logo_img = ctk.CTkImage(Image.open(resource_path("icons/logo.png")), size=(20, 20))
ctk.CTkLabel(title_bar, image=logo_img, text="").pack(side="left", padx=5)
ctk.CTkLabel(title_bar, text="Simpliciti", font=small).pack(side="left", padx=5)
ctk.CTkButton(title_bar, text="✕", width=30,
              fg_color="transparent", hover_color="#ff0000",
              command=close_app).pack(side="right", padx=5)

# --------------------------------------------------------------
# 7️⃣   ICONS (unchanged, now loaded via resource_path)
# --------------------------------------------------------------
loop_img = ctk.CTkImage(Image.open(resource_path("icons/loop.png")), size=ICON_SMALL)
shuffle_img = ctk.CTkImage(Image.open(resource_path("icons/shuffle.png")), size=ICON_SMALL)

play_img = ctk.CTkImage(Image.open(resource_path("icons/play.png")), size=ICON_MAIN)
pause_img = ctk.CTkImage(Image.open(resource_path("icons/pause.png")), size=ICON_MAIN)
rewind_img = ctk.CTkImage(Image.open(resource_path("icons/rewind.png")), size=ICON_MAIN)
forward_img = ctk.CTkImage(Image.open(resource_path("icons/forward.png")), size=ICON_MAIN)

add_img = ctk.CTkImage(Image.open(resource_path("icons/add.png")), size=ICON_ADD)

logo_big_img = ctk.CTkImage(Image.open(resource_path("icons/logo.png")), size=(100, 100))

# --------------------------------------------------------------
# 8️⃣   UI ELEMENTS (unchanged)
# --------------------------------------------------------------
title = ctk.CTkLabel(app, text="", image=logo_big_img, font=h)
title.pack(pady=(10, 10))

status = ctk.CTkLabel(app, text="No track loaded", font=small)
status.pack(pady=(5, 0))

time_label = ctk.CTkLabel(app, text="00:00 / 00:00", font=p)
time_label.pack(pady=(5, 15))

# --------------------------------------------------------------
# 9️⃣   PLAYLIST PERSISTENCE (now in AppData)
# --------------------------------------------------------------
def get_track_length(path: str) -> float:
    """Return length in seconds (supports MP3 & WAV)."""
    if path.lower().endswith(".mp3"):
        return MP3(path).info.length
    if path.lower().endswith(".wav"):
        return WAVE(path).info.length
    return 0.0

def format_time(seconds: float) -> str:
    """Convert seconds → mm:ss string."""
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

def save_playlist() -> None:
    """Write the current `playlist` list to the JSON file in AppData."""
    try:
        # `playlist` contains absolute paths – they are safe to JSON‑dump.
        with PLAYLIST_FILE.open("w", encoding="utf-8") as f:
            json.dump(playlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # In a real app you might want to log this somewhere.
        print(f"[DEBUG] Could not write playlist: {e}")

def load_playlist() -> None:
    """Read the JSON file from AppData (if it exists) and populate `playlist`."""
    global playlist
    try:
        if PLAYLIST_FILE.is_file():
            with PLAYLIST_FILE.open("r", encoding="utf-8") as f:
                playlist = json.load(f)
    except Exception as e:
        print(f"[DEBUG] Could not read playlist: {e}")

def add_songs() -> None:
    """Open file‑dialog, append selected files to the list, then persist."""
    files = filedialog.askopenfilenames(
        filetypes=[("Audio Files", "*.mp3 *.wav")],
        title="Add songs to Simpliciti"
    )
    if files:
        playlist.extend(files)
        save_playlist()
        # If nothing was playing before, start the first newly added track:
        if not is_playing and not paused:
            play_track(0)

# --------------------------------------------------------------
# 10️⃣   PLAYBACK LOGIC (unchanged, only tiny refactors)
# --------------------------------------------------------------
def play_track(index: int | None = None) -> None:
    global current_index, is_playing, paused
    if not playlist:
        return
    if index is not None:
        current_index = index
    pygame.mixer.music.load(playlist[current_index])
    pygame.mixer.music.play()
    is_playing = True
    paused = False
    play_btn.configure(image=pause_img)
    update_status()

def toggle_play() -> None:
    global is_playing, paused
    if not playlist:
        return
    if not pygame.mixer.music.get_busy() and not paused:
        play_track()
        return
    if is_playing:
        pygame.mixer.music.pause()
        is_playing = False
        paused = True
        play_btn.configure(image=play_img)
    else:
        pygame.mixer.music.unpause()
        is_playing = True
        paused = False
        play_btn.configure(image=pause_img)
    update_status()

def next_track() -> None:
    global current_index
    if shuffle_mode and len(playlist) > 1:
        current_index = random.choice([i for i in range(len(playlist)) if i != current_index])
    else:
        current_index = (current_index + 1) % len(playlist)
    play_track()

def prev_track() -> None:
    global current_index
    current_index = (current_index - 1) % len(playlist)
    play_track()

def update_status() -> None:
    if not playlist:
        status.configure(text="No track loaded")
        time_label.configure(text="00:00 / 00:00")
        return
    name = os.path.basename(playlist[current_index])
    if is_playing:
        status.configure(text=f"▶ {name}")
    elif paused:
        status.configure(text=f"⏸ {name}")
    else:
        status.configure(text=f"⏹ {name}")

def update_time_label() -> None:
    if playlist:
        pos = pygame.mixer.music.get_pos() / 1000   # milliseconds → seconds
        total = get_track_length(playlist[current_index])
        time_label.configure(text=f"{format_time(pos)} / {format_time(total)}")
    app.after(500, update_time_label)

def set_volume(value: float) -> None:
    pygame.mixer.music.set_volume(value)

def toggle_loop() -> None:
    global loop_mode
    loop_mode = not loop_mode
    loop_btn.configure(fg_color="#1f6aa5" if loop_mode else "transparent")

def toggle_shuffle() -> None:
    global shuffle_mode
    shuffle_mode = not shuffle_mode
    shuffle_btn.configure(fg_color="#1f6aa5" if shuffle_mode else "transparent")

def check_track_end() -> None:
    """Poll every second – if the current track stopped playing,
    either loop it or jump to the next one."""
    if playlist and not pygame.mixer.music.get_busy() and is_playing:
        if loop_mode:
            play_track(current_index)
        else:
            next_track()
    app.after(1000, check_track_end)

# --------------------------------------------------------------
# 11️⃣   CONTROLS UI (unchanged)
# --------------------------------------------------------------
controls = ctk.CTkFrame(app)
controls.pack(pady=10)

loop_btn = ctk.CTkButton(
    controls, image=loop_img, text="",
    width=BTN_SMALL, height=BTN_SMALL,
    fg_color="transparent", hover_color="#333",
    command=toggle_loop
)
loop_btn.grid(row=0, column=0, padx=5)

prev_btn = ctk.CTkButton(
    controls, image=rewind_img, text="",
    width=BTN_MAIN, height=BTN_MAIN,
    fg_color="transparent", hover_color="#333",
    command=prev_track
)
prev_btn.grid(row=0, column=1, padx=5)

play_btn = ctk.CTkButton(
    controls, image=play_img, text="",
    width=BTN_MAIN, height=BTN_MAIN,
    fg_color="transparent", hover_color="#333",
    command=toggle_play
)
play_btn.grid(row=0, column=2, padx=5)

next_btn = ctk.CTkButton(
    controls, image=forward_img, text="",
    width=BTN_MAIN, height=BTN_MAIN,
    fg_color="transparent", hover_color="#333",
    command=next_track
)
next_btn.grid(row=0, column=3, padx=5)

shuffle_btn = ctk.CTkButton(
    controls, image=shuffle_img, text="",
    width=BTN_SMALL, height=BTN_SMALL,
    fg_color="transparent", hover_color="#333",
    command=toggle_shuffle
)
shuffle_btn.grid(row=0, column=4, padx=5)

# ➕ Add button (top‑left)
add_btn = ctk.CTkButton(
    app, image=add_img, text="",
    width=36, height=36,
    fg_color="transparent", hover_color="#333",
    command=add_songs
)
add_btn.place(x=12, y=35)

# Volume slider
ctk.CTkLabel(app, text="Volume", font=small).pack()
volume = ctk.CTkSlider(app, from_=0, to=1,
                      number_of_steps=100, command=set_volume)
volume.set(1.0)
volume.pack(pady=5)

# --------------------------------------------------------------
# STARTUP – load playlist, kick timers, start UI loop
# --------------------------------------------------------------
load_playlist()               # <‑‑ reads from AppData
update_time_label()
check_track_end()
app.mainloop()
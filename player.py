import os
import sys
from pathlib import Path

# 🔧 DLL FIX (must be before pygame import)
if getattr(sys, "frozen", False):
    os.add_dll_directory(str(Path(sys.executable).parent))

import customtkinter as ctk
from tkinter import filedialog
import pygame
import json
import random
import ctypes
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from PIL import Image

# 🎯 DRAG & DROP
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
    # We'll create the root window with TkinterDnD instead of CTk
except ImportError:
    HAS_DND = False
    TkinterDnD = None

# --------------------------------------------------------------
# APPDATA PATH
# --------------------------------------------------------------
if sys.platform.startswith("win"):
    APPDATA_ROOT = Path(os.getenv("APPDATA")) / "SimplicitiPlayer"
else:
    APPDATA_ROOT = Path.home() / ".simpliciti_player"

APPDATA_ROOT.mkdir(parents=True, exist_ok=True)
PLAYLIST_FILE = APPDATA_ROOT / "playlist.json"

# --------------------------------------------------------------
# INIT
# --------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

pygame.mixer.init()
pygame.mixer.music.set_volume(1.0)

playlist = []
current_index = 0
is_playing = False
paused = False
loop_mode = False
shuffle_mode = False

# --------------------------------------------------------------
# FONTS
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
# RESOURCE PATH
# --------------------------------------------------------------
def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent
    return base_path / relative_path

# --------------------------------------------------------------
# WINDOW
# --------------------------------------------------------------
# Use TkinterDnD.Tk if available, otherwise fall back to CTk
if HAS_DND and TkinterDnD:
    app = TkinterDnD.Tk()
    # Apply dark styling to TkinterDnD window (uses tkinter config, not CustomTkinter)
    app.configure(bg="#212121")
else:
    app = ctk.CTk()

app.geometry("400x370")
app.title("Simpliciti Player")

ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Simpliciti.Player.1")
app.iconbitmap(str(resource_path("icons/logo.ico")))
app.overrideredirect(True)

# 🎯 DRAG & DROP SETUP
if HAS_DND:
    try:
        app.drop_target_register(DND_FILES)
        app.dnd_bind("<<Drop>>", lambda e: handle_drop_event(e))
    except Exception as e:
        print(f"[DEBUG] Drag & drop setup failed: {e}")

# Taskbar fix
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
# TITLE BAR
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

ctk.CTkButton(
    title_bar,
    text="✕",
    width=30,
    fg_color="transparent",
    hover_color="#ff0000",
    command=close_app
).pack(side="right", padx=5)

# --------------------------------------------------------------
# ICONS
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
# UI
# --------------------------------------------------------------
title = ctk.CTkLabel(app, text="", image=logo_big_img, font=h)
title.pack(pady=(10, 10))

status = ctk.CTkLabel(app, text="No track loaded", font=small)
status.pack(pady=(5, 0))

time_label = ctk.CTkLabel(app, text="00:00 / 00:00", font=p)
time_label.pack(pady=(5, 15))

# --------------------------------------------------------------
# PLAYLIST
# --------------------------------------------------------------
def get_track_length(path: str) -> float:
    if path.lower().endswith(".mp3"):
        return MP3(path).info.length
    if path.lower().endswith(".wav"):
        return WAVE(path).info.length
    return 0.0

def format_time(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

def save_playlist():
    try:
        with PLAYLIST_FILE.open("w", encoding="utf-8") as f:
            json.dump(playlist, f, indent=2)
    except Exception as e:
        print(f"[DEBUG] Save error: {e}")

def load_playlist():
    global playlist
    try:
        if PLAYLIST_FILE.is_file():
            with PLAYLIST_FILE.open("r", encoding="utf-8") as f:
                playlist = json.load(f)
    except Exception as e:
        print(f"[DEBUG] Load error: {e}")

def handle_drop_event(event):
    """Handle drag & drop files into the player."""
    global playlist

    # Parse dropped files (tkinterdnd2 format: {C:\file1.mp3} {C:\file2.wav})
    data = event.data

    # Split by spaces and clean up braces
    files = []
    for item in data.split():
        # Remove braces if present
        path = item.strip('{}')
        if path:
            files.append(path)

    # Filter for audio files
    valid_files = [f for f in files if f.lower().endswith((".mp3", ".wav"))]

    if valid_files:
        playlist.extend(valid_files)
        save_playlist()

        # Auto-play if nothing is playing
        if not is_playing and not paused:
            play_track(0)

        status.configure(text=f"Added {len(valid_files)} song(s)!")
        app.after(2000, update_status)  # revert message after 2 seconds

def add_songs():
    files = filedialog.askopenfilenames(
        filetypes=[("Audio Files", "*.mp3 *.wav")],
        title="Add songs"
    )
    if files:
        playlist.extend(files)
        save_playlist()
        if not is_playing and not paused:
            play_track(0)

# --------------------------------------------------------------
# PLAYBACK
# --------------------------------------------------------------
def play_track(index=None):
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

def toggle_play():
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

def next_track():
    global current_index
    if shuffle_mode and len(playlist) > 1:
        current_index = random.choice([i for i in range(len(playlist)) if i != current_index])
    else:
        current_index = (current_index + 1) % len(playlist)
    play_track()

def prev_track():
    global current_index
    current_index = (current_index - 1) % len(playlist)
    play_track()

def update_status():
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

def update_time_label():
    if playlist:
        pos = pygame.mixer.music.get_pos() / 1000
        total = get_track_length(playlist[current_index])
        time_label.configure(text=f"{format_time(pos)} / {format_time(total)}")
    app.after(500, update_time_label)

def set_volume(value):
    pygame.mixer.music.set_volume(value)

def toggle_loop():
    global loop_mode
    loop_mode = not loop_mode
    loop_btn.configure(fg_color="#1f6aa5" if loop_mode else "transparent")

def toggle_shuffle():
    global shuffle_mode
    shuffle_mode = not shuffle_mode
    shuffle_btn.configure(fg_color="#1f6aa5" if shuffle_mode else "transparent")

def check_track_end():
    if playlist and not pygame.mixer.music.get_busy() and is_playing:
        if loop_mode:
            play_track(current_index)
        else:
            next_track()
    app.after(1000, check_track_end)

# --------------------------------------------------------------
# CONTROLS
# --------------------------------------------------------------
controls = ctk.CTkFrame(app)
controls.pack(pady=10)

loop_btn = ctk.CTkButton(controls, image=loop_img, text="", width=BTN_SMALL, height=BTN_SMALL,
                         fg_color="transparent", command=toggle_loop)
loop_btn.grid(row=0, column=0, padx=5)

prev_btn = ctk.CTkButton(controls, image=rewind_img, text="", width=BTN_MAIN, height=BTN_MAIN,
                         fg_color="transparent", command=prev_track)
prev_btn.grid(row=0, column=1, padx=5)

play_btn = ctk.CTkButton(controls, image=play_img, text="", width=BTN_MAIN, height=BTN_MAIN,
                         fg_color="transparent", command=toggle_play)
play_btn.grid(row=0, column=2, padx=5)

next_btn = ctk.CTkButton(controls, image=forward_img, text="", width=BTN_MAIN, height=BTN_MAIN,
                         fg_color="transparent", command=next_track)
next_btn.grid(row=0, column=3, padx=5)

shuffle_btn = ctk.CTkButton(controls, image=shuffle_img, text="", width=BTN_SMALL, height=BTN_SMALL,
                            fg_color="transparent", command=toggle_shuffle)
shuffle_btn.grid(row=0, column=4, padx=5)

add_btn = ctk.CTkButton(app, image=add_img, text="", width=36, height=36,
                        fg_color="transparent", command=add_songs)
add_btn.place(x=12, y=35)

ctk.CTkLabel(app, text="Volume", font=small).pack()
volume = ctk.CTkSlider(app, from_=0, to=1, number_of_steps=100, command=set_volume)
volume.set(1.0)
volume.pack(pady=5)

# --------------------------------------------------------------
# START
# --------------------------------------------------------------
load_playlist()
update_time_label()
check_track_end()
app.mainloop()
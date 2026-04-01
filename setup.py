import sys
from cx_Freeze import setup, Executable

# Dependencies to include
build_exe_options = {
    "packages": [
        "customtkinter",
        "tkinter",
        "pygame",
        "mutagen",
        "PIL",
    ],
    "include_files": [
        ("icons", "icons"),
    ],
}

# Define the executable
exe = Executable(
    script="player.py",
    base="Win32GUI" if sys.platform == "win32" else None,
    icon="icons/logo.ico",
    target_name="simpliciti.exe",
)

setup(
    name="Simpliciti Player",
    version="1.0",
    description="A music player... without the muck.",
    options={"build_exe": build_exe_options},
    executables=[exe],
)

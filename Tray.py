# Tray.py
import sys
from pathlib import Path
from PIL import Image
import pystray

# Resolve directory whether running as script or frozen EXE
BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
FLAG_FILE  = BASE_DIR / "pause.flag"
GREEN_ICON = BASE_DIR / "green.png"
RED_ICON   = BASE_DIR / "red.png"

state = {"paused": FLAG_FILE.exists()}

def menu_label(item):          # must accept 1 positional arg!
    return "Resume" if state["paused"] else "Pause"

def toggle_pause(icon, item):
    state["paused"] = not state["paused"]
    if state["paused"]:
        FLAG_FILE.touch()
    else:
        FLAG_FILE.unlink(missing_ok=True)
    icon.icon = Image.open(RED_ICON if state["paused"] else GREEN_ICON)

def quit_app(icon, item):
    icon.stop()                # closes tray loop
    sys.exit(0)

menu = pystray.Menu(
    pystray.MenuItem(menu_label, toggle_pause),
    pystray.MenuItem("Quit", quit_app)
)

icon = pystray.Icon(
    "log_forwarder_tray",
    Image.open(RED_ICON if state["paused"] else GREEN_ICON),
    menu=menu
)

if __name__ == "__main__":
    icon.run()

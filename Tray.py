import sys
from pathlib import Path
from PIL import Image
import pystray

# ── Directories ────────────────────────────────────────────
APP_DIR      = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
# When frozen, PyInstaller unpacks resources into sys._MEIPASS
RESOURCE_DIR = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else APP_DIR

FLAG_FILE  = APP_DIR / "pause.flag"
GREEN_ICON = RESOURCE_DIR / "green.png"
RED_ICON   = RESOURCE_DIR / "red.png"

state = {"paused": FLAG_FILE.exists()}

# ── Menu callbacks ─────────────────────────────────────────
def label(item):
    return "Resume" if state["paused"] else "Pause"

def toggle_pause(icon, item):
    state["paused"] = not state["paused"]
    if state["paused"]:
        FLAG_FILE.touch()
    else:
        FLAG_FILE.unlink(missing_ok=True)
    icon.icon = Image.open(RED_ICON if state["paused"] else GREEN_ICON)

def quit_app(icon, item):
    icon.stop()
    sys.exit(0)

# ── Build tray icon ────────────────────────────────────────
menu = pystray.Menu(
    pystray.MenuItem(label, toggle_pause),
    pystray.MenuItem("Quit", quit_app)
)

icon = pystray.Icon(
    "LogForwarderTray",
    Image.open(RED_ICON if state["paused"] else GREEN_ICON),
    menu=menu
)

if __name__ == "__main__":
    icon.run()

import time, glob, os, json, sys, threading, ctypes, tempfile, atexit, easygui, msvcrt, shutil
import win32evtlogutil, win32evtlog
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

# ───────── Globals ─────────
BASE_DIR    = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
LOCK_PATH   = Path(tempfile.gettempdir()) / "log_forwarder.lock"
CONFIG_FILE = BASE_DIR / "config.json"
OFFSET_FILE = BASE_DIR / "offsets.json"
STATUS_FILE = BASE_DIR / "status.json"
PAUSE_FLAG  = BASE_DIR / "pause.flag"
offsets     = {}                           # {filepath: last_byte}

# ───────── Singleton lock ─────────
lock_file = open(LOCK_PATH, "w")
try: msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except OSError: print("❌ Another instance is already running."); sys.exit(0)
atexit.register(lambda: lock_file.close())

# ───── Admin check ─────
if not ctypes.windll.shell32.IsUserAnAdmin():
    easygui.msgbox("❌  Please right-click and choose 'Run as administrator'.",
                   title="Log Forwarder – Admin Required")
    sys.exit(1)

# ───────── Config loader / creator ─────────
def load_or_create_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text("utf-8"))

    easygui.msgbox("Select folders to monitor. You may skip either set; at least one is required.")
    appsrv_dir = easygui.diropenbox("📂 APPSRV logs folder (APPSRV_*.LOG*). Click Cancel to skip:")
    other_dir  = easygui.diropenbox("📂 CSDEV/PIA logs folder (CSDEV.log*, PIA_weblogic.log*). Click Cancel to skip:")
    if not appsrv_dir and not other_dir:
        sys.exit("❌ Nothing selected. At least one folder is required.")
    evt_source = None
    while not evt_source:
        evt_source = easygui.enterbox("📝 Enter Event Source name (required):")

    cfg = {"appsrv_dir": appsrv_dir, "other_dir": other_dir, "event_source": evt_source}
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), "utf-8")
    return cfg

# ───────── Offset helpers ─────────
def load_offsets():
    try:  return json.loads(OFFSET_FILE.read_text("utf-8"))
    except: return {}

def save_offsets():
    OFFSET_FILE.write_text(json.dumps(offsets, indent=2), "utf-8")

# ───────── Status helpers ─────────
def write_global_state():
    try:
        if STATUS_FILE.exists():
            with STATUS_FILE.open("r+", encoding="utf-8") as f:
                data = json.load(f)
                data["_state"] = "Paused" if PAUSE_FLAG.exists() else "Running"
                f.seek(0); json.dump(data, f, indent=2); f.truncate()
    except: pass

def update_status(label, file_path, line):
    new_piece = {
        label: {
            "file": os.path.basename(file_path),
            "offset": offsets.get(file_path, 0),
            "last_line": line[:150],
            "time": datetime.now().isoformat(timespec="seconds")
        }
    }
    try:
        status = json.loads(STATUS_FILE.read_text("utf-8")) if STATUS_FILE.exists() else {}
    except: status = {}

    status.update(new_piece)
    status["_state"] = "Paused" if PAUSE_FLAG.exists() else "Running"

    try:
        with NamedTemporaryFile("w", delete=False, dir=BASE_DIR, encoding="utf-8") as tmp:
            json.dump(status, tmp, indent=2)
            tmp_path = Path(tmp.name)

        # retry-safe atomic move (viewer may hold file)
        for _ in range(3):
            try:
                shutil.move(tmp_path, STATUS_FILE)
                break
            except PermissionError:
                time.sleep(0.2)
    except Exception as e:
        print(f"[STATUS_WRITE_ERROR] {e}")

# ───────── Helpers ─────────
def latest_file(folder, pattern):
    files = glob.glob(str(Path(folder) / pattern))
    return max(files, key=os.path.getmtime) if files else None

def tail_rotating(folder, pattern, label):
    current_file, fp = None, None
    first_open = True

    while True:
        if PAUSE_FLAG.exists():
            time.sleep(1)
            continue

        try:
            newest = latest_file(folder, pattern)
            if newest != current_file:
                if fp:
                    offsets[current_file] = fp.tell()
                    save_offsets()
                    fp.close()

                current_file = newest
                if not current_file:
                    time.sleep(1)
                    continue

                print(f"[{label}] ➡️ Watching {os.path.basename(current_file)}")
                fp = open(current_file, "r", encoding="utf-8", errors="ignore")
                size = os.path.getsize(current_file)

                if current_file not in offsets:
                    # 🧠 First time ever seeing this file → Catch-up logic
                    fp.seek(max(0, size - 4096))
                    tail_lines = fp.read().splitlines()
                    last_line = next((x for x in reversed(tail_lines) if x.strip()), "")
                    if last_line:
                        # Register last known point
                        offsets[current_file] = size
                        save_offsets()
                        update_status(label, current_file, last_line)
                        log_to_event_viewer(f"[{label}] {last_line}")
                    first_open = False
                    continue  # Wait for new lines next loop
                else:
                    # 🟢 Resume from last known offset
                    pos = offsets[current_file]
                    fp.seek(pos if pos <= size else 0)
                    first_open = False

            # Read and yield new lines
            line = fp.readline()
            if line.strip():
                offsets[current_file] = fp.tell()
                save_offsets()
                update_status(label, current_file, line)
                yield f"[{label}] {line.rstrip()}", current_file
            else:
                time.sleep(0.3)

        except Exception as e:
            print(f"[{label}] ⚠️ {e}")
            time.sleep(1)

    current_file, fp = None, None
    while True:
        if PAUSE_FLAG.exists(): time.sleep(1); continue

        try:
            newest = latest_file(folder, pattern)
            if newest != current_file:
                if fp:
                    offsets[current_file] = fp.tell(); save_offsets(); fp.close()
                current_file = newest
                if not current_file: time.sleep(1); continue
                print(f"[{label}] ➡️ Watching {os.path.basename(current_file)}")
                fp = open(current_file, "r", encoding="utf-8", errors="ignore")
                size = os.path.getsize(current_file)
                fp.seek(offsets.get(current_file, 0) if offsets.get(current_file, 0) <= size else 0)
                offsets[current_file] = fp.tell()

            line = fp.readline()
            if line.strip():  # skip blanks
                offsets[current_file] = fp.tell(); save_offsets()
                update_status(label, current_file, line)
                yield f"[{label}] {line.rstrip()}", current_file
            else:
                time.sleep(0.3)
        except Exception as e:
            print(f"[{label}] ⚠️ {e}"); time.sleep(1)

def log_to_event_viewer(msg):
    try:
        win32evtlogutil.ReportEvent(EVENT_SOURCE, 1000, 0,
                                    win32evtlog.EVENTLOG_INFORMATION_TYPE, [msg])
        print(f"[LOGGED] ✅ {msg[:120]}")
    except Exception as exc:
        print(f"[ERROR] {exc}")

def watcher(folder, pattern, label):
    for line, _ in tail_rotating(folder, pattern, label):
        log_to_event_viewer(line)

# ───────── Init ─────────
cfg = load_or_create_config()
offsets.update(load_offsets())
APPSRV_DIR, OTHER_DIR, EVENT_SOURCE = cfg.values()
write_global_state()                                    # initial state line

try: win32evtlogutil.AddSourceToRegistry(EVENT_SOURCE, "Application", msgDLL=None, eventID=1)
except win32evtlog.error: pass
except Exception as exc: print(f"⚠️  Source ({exc}) already exists?")

# ───────── Main ─────────
print("\n======== Log Forwarder Started ========\n")
print(f"APPSRV dir  : {APPSRV_DIR or '[None]'}")
print(f"CSDEV/PIA dir : {OTHER_DIR or '[None]'}")
print(f"Event Source  : {EVENT_SOURCE}\n")

threads = []
if APPSRV_DIR:
    threads.append(threading.Thread(target=watcher, args=(APPSRV_DIR, "APPSRV_*.LOG*", "APPSRV"), daemon=True))
if OTHER_DIR:
    threads += [
        threading.Thread(target=watcher, args=(OTHER_DIR, "CSDEV.log*", "CSDEV"), daemon=True),
        threading.Thread(target=watcher, args=(OTHER_DIR, "PIA_weblogic.log*", "PIA"), daemon=True),
    ]
for t in threads: t.start()

try:
    while True:
        write_global_state()
        time.sleep(1)
except KeyboardInterrupt:
    print("\n👋 Exiting."); sys.exit(0)

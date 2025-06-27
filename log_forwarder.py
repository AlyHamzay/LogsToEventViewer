"""
Rewterz Log-Forwarder  –  self-contained
• On first run (no config.json) → shows Tkinter table GUI
• After that → runs watchers headless
• Supports rotating folders and static files
• Pause/Resume via Tray (pause.flag)
• Writes offsets.json & status.json (Viewer)
"""

import time, glob, os, json, sys, threading, ctypes, tempfile, atexit, msvcrt, shutil
import win32evtlogutil, win32evtlog
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

# ───────── Paths / files ─────────
BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"
OFFSET_FILE = BASE / "offsets.json"
STATUS_FILE = BASE / "status.json"
PAUSE_FLAG  = BASE / "pause.flag"
LOCK_PATH   = Path(tempfile.gettempdir()) / "log_forwarder.lock"
offsets     = {}

# ───────── Singleton lock ─────────
lock = open(LOCK_PATH, "w")
try: msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
except OSError: sys.exit("❌ Already running.")
atexit.register(lambda: lock.close())

# ───────── Admin check ─────────
if not ctypes.windll.shell32.IsUserAnAdmin():
    messagebox.showerror("Admin Needed", "Run log_forwarder.exe as Administrator.")
    sys.exit(1)

# ───────── Tkinter GUI (only if CONFIG_FILE missing) ─────────
def run_config_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    class ConfigGUI(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Log-Forwarder Setup")
            self.geometry("850x450")
            tk.Label(self, text="Add folders (rotating) and/or files (static)", font=("Segoe UI", 12, "bold")).pack(pady=5)
            self.tree = ttk.Treeview(self, columns=("type","path","pattern","source"), show="headings")
            for c,t in zip(("type","path","pattern","source"),
                           ("Type","Folder/File Path","Pattern (folders)","Event Source")):
                self.tree.heading(c, text=t); self.tree.column(c, width=180 if c!="path" else 340)
            self.tree.pack(fill="both", expand=True, padx=10)

            b = tk.Frame(self); b.pack(pady=6)
            tk.Button(b, text="Add Folder",  command=self.add_folder).pack(side="left", padx=4)
            tk.Button(b, text="Add File",    command=self.add_file).pack(side="left", padx=4)
            tk.Button(b, text="Remove Selected", command=lambda:[self.tree.delete(i) for i in self.tree.selection()]).pack(side="left", padx=4)
            tk.Button(b, text="Save & Exit", bg="green", fg="white", command=self.save).pack(side="left", padx=4)

        def add_folder(self):
            folder = filedialog.askdirectory()
            if not folder: return
            patt  = simple_input("File pattern (e.g. *.log or APPSRV_*.LOG*):")
            src   = simple_input("Event Source name for this folder:")
            if patt and src:
                self.tree.insert("", "end", values=("folder",folder,patt,src))

        def add_file(self):
            path = filedialog.askopenfilename()
            if not path: return
            src  = simple_input("Event Source name for this file:")
            if src:
                self.tree.insert("", "end", values=("file",path,"",src))

        def save(self):
            rows=[self.tree.item(i)['values'] for i in self.tree.get_children()]
            if not rows:
                messagebox.showerror("Error","At least one row required."); return
            cfg=[{"type":r[0], "path":r[1], "pattern":r[2], "source":r[3]} for r in rows]
            CONFIG_FILE.write_text(json.dumps(cfg,indent=2), "utf-8")
            self.destroy()

    def simple_input(prompt):
        w=tk.Toplevel(); w.title("Input"); tk.Label(w,text=prompt).pack(padx=10,pady=6)
        e=tk.Entry(w); e.pack(padx=10); v=[]
        tk.Button(w,text="OK",command=lambda:[v.append(e.get()),w.destroy()]).pack(pady=6)
        w.grab_set(); w.wait_window(); return v[0] if v else None

    ConfigGUI().mainloop()

# If no config yet, launch GUI
if not CONFIG_FILE.exists():
    run_config_gui()
    if not CONFIG_FILE.exists(): sys.exit("Setup cancelled.")

CONFIG = json.loads(CONFIG_FILE.read_text("utf-8"))
if not CONFIG: sys.exit("Config is empty.")

# ───────── Offset helpers ─────────
def load_offsets():
    try: return json.loads(OFFSET_FILE.read_text("utf-8"))
    except: return {}
def save_offsets():
    OFFSET_FILE.write_text(json.dumps(offsets,indent=2),"utf-8")

offsets.update(load_offsets())

# ───────── Status helper ─────────
from tempfile import NamedTemporaryFile
def update_status(label, path, line):
    line=line.rstrip("\r\n"); data={}
    try: data=json.loads(STATUS_FILE.read_text("utf-8")) if STATUS_FILE.exists() else {}
    except: pass
    if label!="__ping__":
        data[label]={"file":os.path.basename(path),"offset":offsets.get(path,0),
                     "last_line":line[:150],"time":datetime.now().isoformat(timespec="seconds")}
    data["_state"]="Paused" if PAUSE_FLAG.exists() else "Running"
    try:
        with NamedTemporaryFile("w",delete=False,dir=BASE,encoding="utf-8") as tmp:
            json.dump(data,tmp,indent=2); tmp_path=Path(tmp.name)
        for _ in range(5):
            try: shutil.move(tmp_path,STATUS_FILE); break
            except PermissionError: time.sleep(0.2)
    except Exception as e: print("[STATUS_WRITE]",e)

# ───────── Event log helper ───────
def emit(src,msg):
    try:
        win32evtlogutil.ReportEvent(src,1000,0,win32evtlog.EVENTLOG_INFORMATION_TYPE,[msg.rstrip()])
        print(f"[LOGGED] {src}: {msg[:80]}")
    except Exception as e: print("[EVENT_ERROR]",e)

# ───────── Tailers ────────────────
def latest(folder,pattern):
    files=glob.glob(str(Path(folder)/pattern))
    return max(files,key=os.path.getmtime) if files else None

def tail_rotating(folder,pattern,src):
    current,fp=None,None
    while True:
        if PAUSE_FLAG.exists(): time.sleep(1); continue
        try:
            nf=latest(folder,pattern)
            if nf!=current:
                if fp: offsets[current]=fp.tell(); save_offsets(); fp.close()
                current=nf
                if not current: time.sleep(1); continue
                print(f"▶ {src} -> {os.path.basename(current)}")
                fp=open(current,"r",encoding="utf-8",errors="ignore")
                # first-time file
                if current not in offsets:
                    fp.seek(0,os.SEEK_END); size=fp.tell()
                    fp.seek(max(0,size-4096)); lines=fp.read().splitlines()
                    last=next((l for l in reversed(lines) if l.strip()),"")
                    offsets[current]=size; save_offsets()
                    if last: emit(src,last); update_status(src,current,last)
                else: fp.seek(offsets[current])

            line=fp.readline()
            if line.strip():
                offsets[current]=fp.tell(); save_offsets()
                emit(src,line); update_status(src,current,line)
            else: time.sleep(0.3)
        except Exception as e: print(f"[{src}] {e}"); time.sleep(1)

def tail_static(path,src):
    if not Path(path).exists():
        print(f"[{src}] File not found: {path}"); return
    fp=open(path,"r",encoding="utf-8",errors="ignore")
    fp.seek(offsets.get(path,os.path.getsize(path)))
    while True:
        if PAUSE_FLAG.exists(): time.sleep(1); continue
        line=fp.readline()
        if line.strip():
            offsets[path]=fp.tell(); save_offsets()
            emit(src,line); update_status(src,path,line)
        else: time.sleep(0.3)

# ───────── Register event sources ──
for r in CONFIG:
    try: win32evtlogutil.AddSourceToRegistry(r["source"],"Application")
    except: pass

# ───────── Start watchers ──────────
threads=[]
for r in CONFIG:
    if r["type"]=="folder":
        print(f"🔁 Rotating → {r['path']} | {r['pattern']} | {r['source']}")
        t=threading.Thread(target=tail_rotating,args=(r["path"],r["pattern"],r["source"]),daemon=True)
    else:
        print(f"📄 Static   → {r['path']} | {r['source']}")
        t=threading.Thread(target=tail_static,args=(r["path"],r["source"]),daemon=True)
    t.start(); threads.append(t)

# ── ping thread keeps _state fresh ──
def ping_loop():
    while True:
        update_status("__ping__", "__", "")
        time.sleep(1)

threading.Thread(target=ping_loop, daemon=True).start()

print(f"▶ Forwarder running with {len(threads)} watchers.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting")

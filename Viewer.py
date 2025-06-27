import json, time, tkinter as tk, sys
from pathlib import Path

BASE_DIR    = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
STATUS_FILE = BASE_DIR / "status.json"
REFRESH_MS  = 1000

class Viewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rewterz Log-Forwarder – Live Status")
        self.geometry("650x400")
        self.txt = tk.Text(self, wrap="none", state="disabled", font=("Consolas", 10))
        self.txt.pack(fill="both", expand=True)
        self.after(REFRESH_MS, self.refresh)

    def refresh(self):
        try:
            data = json.loads(STATUS_FILE.read_text("utf-8"))
        except: data = {}
        state  = data.pop("_state", "UNKNOWN")
        header = f"STATUS: {state}\n" + "="*60 + "\n"
        body   = "(no data yet)" if not data else "\n".join(
            f"[{k}] file={v['file']}  offset={v['offset']}  time={v['time']}\n   last: {v['last_line']}"
            for k,v in data.items())
        self.txt.config(state="normal"); self.txt.delete("1.0","end")
        self.txt.insert("1.0", header+body); self.txt.config(state="disabled")
        self.after(REFRESH_MS, self.refresh)

if __name__ == "__main__":
    Viewer().mainloop()

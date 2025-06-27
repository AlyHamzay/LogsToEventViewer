import json, time, tkinter as tk, sys
from pathlib import Path

BASE_DIR    = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
STATUS_FILE = BASE_DIR / "status.json"
REFRESH_MS  = 1000

class StatusViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Log-Forwarder Status")
        self.geometry("600x380")
        self.text = tk.Text(self, wrap="none", state="disabled", font=("Consolas", 10))
        self.text.pack(fill="both", expand=True)
        self.after(REFRESH_MS, self.refresh)

    def refresh(self):
        # tolerate partial writes
        for _ in range(3):
            try:
                data = json.loads(STATUS_FILE.read_text("utf-8"))
                break
            except Exception as e:
                data = {}
                time.sleep(0.1)

        state  = data.pop("_state", "UNKNOWN")
        header = f"Log Forwarder Status: {state.upper()}\n{'='*50}\n\n"
        body   = "(No log data yet)" if not data else "\n".join(
            f"[{k}] file={v['file']}  offset={v['offset']}  time={v['time']}\n   last: {v['last_line']}"
            for k, v in data.items()
        )
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", header + body)
        self.text.config(state="disabled")
        self.after(REFRESH_MS, self.refresh)

if __name__ == "__main__":
    StatusViewer().mainloop()

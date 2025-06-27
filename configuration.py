import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os

CONFIG_FILE = "config.json"

class LogForwarderConfig:
    def __init__(self, root):
        self.root = root
        self.root.title("Log Forwarder Config")
        self.root.geometry("800x400")

        tk.Label(root, text="Rewterz Log - Forwarder Setup", font=("Segoe UI", 14, "bold")).pack(pady=10)

        self.tree = ttk.Treeview(root, columns=("type", "path", "pattern", "source"), show="headings")
        self.tree.heading("type", text="Type")
        self.tree.heading("path", text="Folder/File Path")
        self.tree.heading("pattern", text="Pattern (folders only)")
        self.tree.heading("source", text="Event Source")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Add File", command=self.add_file).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Save & Exit", bg="green", fg="white", command=self.save_and_exit).pack(side=tk.LEFT, padx=5)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        pattern = simple_input("Enter file name pattern (e.g. *.log):")
        source = simple_input("Enter Event Source for this folder:")
        if pattern and source:
            self.tree.insert("", "end", values=("Folder", folder, pattern, source))

    def add_file(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
        source = simple_input("Enter Event Source for this file:")
        if source:
            self.tree.insert("", "end", values=("File", file_path, "", source))

    def remove_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)

    def save_and_exit(self):
        entries = []
        for row in self.tree.get_children():
            values = self.tree.item(row)['values']
            entries.append({
                "type": values[0],
                "path": values[1],
                "pattern": values[2],
                "source": values[3]
            })
        if not entries:
            messagebox.showerror("Error", "You must configure at least one folder or file.")
            return
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        self.root.destroy()


def simple_input(prompt):
    input_window = tk.Toplevel()
    input_window.title("Input Required")
    input_window.geometry("300x120")
    tk.Label(input_window, text=prompt, wraplength=280).pack(pady=10)
    entry = tk.Entry(input_window)
    entry.pack(pady=5)
    result = []

    def confirm():
        result.append(entry.get())
        input_window.destroy()

    tk.Button(input_window, text="OK", command=confirm).pack(pady=5)
    input_window.grab_set()
    input_window.wait_window()
    return result[0] if result else None


if __name__ == "__main__":
    root = tk.Tk()
    app = LogForwarderConfig(root)
    root.mainloop()

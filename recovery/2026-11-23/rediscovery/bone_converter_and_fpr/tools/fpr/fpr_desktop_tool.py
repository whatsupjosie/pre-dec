#!/usr/bin/env python3
"""
Desktop wrapper for Functional Purpose Report generation.

Features:
- Clickable Tkinter GUI
- Choose a project folder
- Enter feature/system name
- Runs fpr_autogen.py
- Saves a draft FPR JSON report
- Optional: open the report folder after generation

This is intended to be easy to package into a desktop shortcut on Windows.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

APP_TITLE = "FPR Desktop Tool"
HERE = Path(__file__).resolve().parent
AUTOGEN = HERE / "fpr_autogen.py"
SCHEMA = HERE / "functional_purpose_report.schema.json"


class FPRTool(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x520")
        self.minsize(720, 500)

        self.project_var = tk.StringVar()
        self.name_var = tk.StringVar(value="Unnamed system")
        self.out_var = tk.StringVar(value=str(Path.home() / "Desktop" / "draft_fpr.json"))
        self.open_after_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self) -> None:
        padx = 10
        pady = 8

        title = tk.Label(self, text="Functional Purpose Report Generator", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w", padx=padx, pady=(12, 2))

        desc = tk.Label(
            self,
            text=(
                "Pick a project folder, name the feature/system, and generate a draft FPR JSON report.\n"
                "This tool uses fpr_autogen.py as the backend."
            ),
            justify="left",
            wraplength=700,
        )
        desc.pack(anchor="w", padx=padx, pady=(0, 12))

        form = tk.Frame(self)
        form.pack(fill="x", padx=padx)

        # Project folder
        tk.Label(form, text="Project folder:").grid(row=0, column=0, sticky="w", pady=pady)
        tk.Entry(form, textvariable=self.project_var, width=70).grid(row=0, column=1, sticky="ew", pady=pady)
        tk.Button(form, text="Browse…", command=self.browse_project).grid(row=0, column=2, padx=(8, 0), pady=pady)

        # Feature/system name
        tk.Label(form, text="Feature / system name:").grid(row=1, column=0, sticky="w", pady=pady)
        tk.Entry(form, textvariable=self.name_var, width=70).grid(row=1, column=1, sticky="ew", pady=pady)

        # Output file
        tk.Label(form, text="Output JSON:").grid(row=2, column=0, sticky="w", pady=pady)
        tk.Entry(form, textvariable=self.out_var, width=70).grid(row=2, column=1, sticky="ew", pady=pady)
        tk.Button(form, text="Save As…", command=self.browse_output).grid(row=2, column=2, padx=(8, 0), pady=pady)

        form.columnconfigure(1, weight=1)

        options = tk.Frame(self)
        options.pack(fill="x", padx=padx, pady=(10, 4))
        tk.Checkbutton(options, text="Open report folder after generation", variable=self.open_after_var).pack(anchor="w")

        actions = tk.Frame(self)
        actions.pack(fill="x", padx=padx, pady=(6, 8))
        tk.Button(actions, text="Generate FPR", command=self.generate, font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Button(actions, text="Open schema", command=self.open_schema).pack(side="left", padx=(8, 0))
        tk.Button(actions, text="Quit", command=self.destroy).pack(side="right")

        tk.Label(self, text="Log:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=padx)
        self.log = tk.Text(self, wrap="word", height=18)
        self.log.pack(fill="both", expand=True, padx=padx, pady=(4, 12))
        self.log.insert("end", f"Backend script: {AUTOGEN}\nSchema: {SCHEMA}\n")
        self.log.configure(state="disabled")

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + ("\n" if not text.endswith("\n") else ""))
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def browse_project(self) -> None:
        folder = filedialog.askdirectory(title="Choose project folder")
        if folder:
            self.project_var.set(folder)
            default_out = Path(folder) / "draft_fpr.json"
            self.out_var.set(str(default_out))

    def browse_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Save FPR JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=Path(self.out_var.get()).name or "draft_fpr.json",
        )
        if filename:
            self.out_var.set(filename)

    def open_schema(self) -> None:
        if not SCHEMA.exists():
            messagebox.showwarning(APP_TITLE, f"Schema file not found:\n{SCHEMA}")
            return
        self._open_path(SCHEMA)

    def generate(self) -> None:
        project = Path(self.project_var.get().strip())
        name = self.name_var.get().strip() or "Unnamed system"
        out = Path(self.out_var.get().strip())

        if not project.exists() or not project.is_dir():
            messagebox.showerror(APP_TITLE, "Please choose a valid project folder.")
            return
        if not AUTOGEN.exists():
            messagebox.showerror(APP_TITLE, f"Backend script not found:\n{AUTOGEN}")
            return

        out.parent.mkdir(parents=True, exist_ok=True)

        cmd = [sys.executable, str(AUTOGEN), str(project), "--name", name, "--out", str(out)]
        self.append_log("Running:\n  " + " ".join(f'"{part}"' if ' ' in part else part for part in cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HERE))
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Failed to run backend script:\n{exc}")
            self.append_log(f"ERROR: {exc}")
            return

        if result.stdout:
            self.append_log(result.stdout.rstrip())
        if result.stderr:
            self.append_log("STDERR:\n" + result.stderr.rstrip())

        if result.returncode != 0:
            messagebox.showerror(APP_TITLE, f"Generation failed with exit code {result.returncode}.")
            return

        try:
            data = json.loads(out.read_text(encoding="utf-8"))
            summary = data.get("fpr_summary", {})
            self.append_log(
                "\nFPR generated successfully.\n"
                f"Status: {summary.get('status', 'Unknown')}\n"
                f"Confidence: {summary.get('confidence', 'Unknown')}\n"
                f"Recommended action: {summary.get('recommended_action', 'n/a')}\n"
                f"Saved to: {out}"
            )
        except Exception:
            self.append_log(f"Generated output saved to: {out}")

        messagebox.showinfo(APP_TITLE, f"Draft FPR created:\n{out}")
        if self.open_after_var.get():
            self._open_path(out.parent)

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                import os
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self.append_log(f"Could not open {path}: {exc}")


if __name__ == "__main__":
    app = FPRTool()
    app.mainloop()

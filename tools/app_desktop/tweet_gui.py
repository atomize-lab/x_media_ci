"""x_media CI — Desktop GUI (Tkinter, single file).

What this is
------------
A *real* desktop app. You double-click it, a window opens, you paste a
tweet URL, click a button, the app downloads / converts / opens the
folder for you. No browser, no terminal, no HTTP server.

It does not talk to X directly. It drives the existing
``tools/x_media_ci.py`` pipeline that you already have working.

Layout
------
+--------------------------------------------------+
|  Tweet URL :  [_____________________________] [Fetch]
|  Save to   :  [____________] [Browse...]         |
|  Status    :  [----------------------]          |
|  Log:                                               |
|  +-----------------------------------------+       |
|  |                                          |       |
|  |                                          |       |
|  +-----------------------------------------+       |
|  [ Save Markdown ]  [ Save PDF ]                   |
|  [ Save Media   ]  [ Save All   ]  [ Open Folder ] |
+--------------------------------------------------+

Run directly:
    python tools/app_desktop/tweet_gui.py

Build a Windows .exe (no Python needed on the target machine):
    pyinstaller --noconfirm --clean tools/app_desktop/tweet_gui.spec
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Local module
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tweet_fetcher as tf  # noqa: E402


APP_TITLE = "x_media CI"
APP_W, APP_H = 820, 600


# ---------------------------------------------------------------------------
# Background worker (uses a thread + queue; tkinter is not thread-safe so
# we only touch widgets from the main thread)
# ---------------------------------------------------------------------------

class Worker(threading.Thread):
    def __init__(self, q: "queue.Queue[tuple[str, object]]", task, *args, **kwargs):
        super().__init__(daemon=True)
        self.q = q
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            def on_line(line: str, frac: float) -> None:
                self.q.put(("line", line))
                if self._cancel.is_set():
                    raise StopIteration()
            result = self.task(*self.args, on_line=on_line, **self.kwargs)
            self.q.put(("done", result))
        except StopIteration:
            self.q.put(("cancelled", None))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", f"{type(e).__name__}: {e}"))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_W}x{APP_H}")
        self.minsize(720, 520)

        # Persistent state
        self._ref: tf.TweetRef | None = None
        self._save_root: Path = self._default_save_root()
        self._userdata: Path = self._default_userdata_dir()
        self._worker: Worker | None = None
        self._q: "queue.Queue[tuple[str, object]]" = queue.Queue()

        # Tk variables (must exist before _build_ui)
        self.var_url = tk.StringVar()
        self.var_save = tk.StringVar(value=str(self._save_root))
        self.var_userdata = tk.StringVar(value=str(self._userdata))
        self.var_auth_token = tk.StringVar()
        self.var_ct0 = tk.StringVar()
        self.var_headed = tk.BooleanVar(value=False)
        self.var_skip_fetch = tk.BooleanVar(value=False)
        self.var_status = tk.StringVar(value="Idle")

        self._build_ui()
        self.after(100, self._poll_queue)

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, **pad)

        # Row: URL
        row1 = ttk.Frame(frm); row1.pack(fill=tk.X, **pad)
        ttk.Label(row1, text="Tweet URL:").pack(side=tk.LEFT)
        self.var_url = tk.StringVar()
        ent_url = ttk.Entry(row1, textvariable=self.var_url)
        ent_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        ent_url.bind("<Return>", lambda _e: self._do_fetch())
        ttk.Button(row1, text="Fetch", command=self._do_fetch).pack(side=tk.LEFT)

        # Row: save dir
        row2 = ttk.Frame(frm); row2.pack(fill=tk.X, **pad)
        ttk.Label(row2, text="Save to:").pack(side=tk.LEFT)
        self.var_save = tk.StringVar(value=str(self._save_root))
        ttk.Entry(row2, textvariable=self.var_save).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        ttk.Button(row2, text="Browse…", command=self._browse_save).pack(side=tk.LEFT)

        # Row: user-data-dir (Playwright login session cache)
        row2b = ttk.Frame(frm); row2b.pack(fill=tk.X, **pad)
        ttk.Label(row2b, text="User-data:").pack(side=tk.LEFT)
        self.var_userdata = tk.StringVar(value=str(self._userdata))
        ttk.Entry(row2b, textvariable=self.var_userdata).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        ttk.Button(row2b, text="Browse…", command=self._browse_userdata).pack(side=tk.LEFT)

        # Row: cookies (optional, avoids login flow)
        row2d = ttk.Frame(frm); row2d.pack(fill=tk.X, **pad)
        ttk.Label(row2d, text="auth_token:").pack(side=tk.LEFT)
        ttk.Entry(row2d, textvariable=self.var_auth_token, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        ttk.Label(row2d, text="ct0:").pack(side=tk.LEFT, padx=(6, 0))
        ttk.Entry(row2d, textvariable=self.var_ct0, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        # Row: checkboxes
        row2c = ttk.Frame(frm); row2c.pack(fill=tk.X, **pad)
        self.chk_headed = ttk.Checkbutton(
            row2c, text="Headed (show browser — first time you need to log in to x.com)",
            variable=self.var_headed,
        )
        self.chk_headed.pack(side=tk.LEFT)
        ttk.Checkbutton(
            row2c, text="Local only (skip fetching from x.com)",
            variable=self.var_skip_fetch,
        ).pack(side=tk.LEFT, padx=(12, 0))

        # Status / progress
        row3 = ttk.Frame(frm); row3.pack(fill=tk.X, **pad)
        ttk.Label(row3, text="Status:").pack(side=tk.LEFT)
        self.var_status = tk.StringVar(value="Idle")
        ttk.Label(row3, textvariable=self.var_status, foreground="#0066cc").pack(side=tk.LEFT, padx=(8, 8))
        self.progress = ttk.Progressbar(row3, mode="indeterminate", length=200)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Log
        row4 = ttk.Frame(frm); row4.pack(fill=tk.BOTH, expand=True, **pad)
        ttk.Label(row4, text="Log:").pack(anchor=tk.W)
        self.txt = tk.Text(row4, wrap=tk.NONE, height=12, font=("Consolas", 9))
        self.txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(row4, orient=tk.VERTICAL, command=self.txt.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.tag_configure("err", foreground="#cc0000")
        self.txt.tag_configure("ok", foreground="#008844")
        self.txt.tag_configure("dim", foreground="#888888")

        # Action buttons
        row5 = ttk.Frame(frm); row5.pack(fill=tk.X, **pad)
        ttk.Button(row5, text="Save Markdown",  command=self._do_md).pack(side=tk.LEFT, padx=2)
        ttk.Button(row5, text="Save PDF",       command=self._do_pdf).pack(side=tk.LEFT, padx=2)
        ttk.Button(row5, text="Save Media",     command=self._do_media).pack(side=tk.LEFT, padx=2)
        ttk.Button(row5, text="Save ALL (md+pdf+ocr+media)",
                   command=self._do_all).pack(side=tk.LEFT, padx=2)
        ttk.Separator(row5, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(row5, text="Open Folder",    command=self._do_open).pack(side=tk.LEFT, padx=2)
        ttk.Button(row5, text="Check setup",    command=self._do_check).pack(side=tk.LEFT, padx=2)
        ttk.Button(row5, text="Stop",           command=self._do_stop).pack(side=tk.RIGHT, padx=2)

    # -- helpers ------------------------------------------------------------

    def _default_save_root(self) -> Path:
        # Prefer <repo>/CI/accounts when present (matches the existing data).
        # Otherwise fall back to <user>/Documents/x_media_ci.
        candidates = [
            Path(__file__).resolve().parents[2] / "accounts",   # tools/app_desktop -> CI/accounts
            Path.home() / "Documents" / "x_media_ci" / "accounts",
        ]
        for c in candidates:
            if c.exists():
                return c
        return candidates[-1]

    def _default_userdata_dir(self) -> Path:
        """Persistent browser profile for the X login session.

        This is a folder (not a file) that Playwright keeps cookies in.
        Reusing it means you only need to log in once.
        """
        candidates = [
            Path(__file__).resolve().parents[2] / ".x_userdata",   # <repo>/.x_userdata
            Path.home() / ".x_media_ci" / "userdata",
        ]
        # Pick the first that exists, else the repo-local one (so devs
        # can git-ignore it but it lives next to the CI data).
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]

    def _browse_save(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=str(self._save_root),
            title="Choose folder where tweet folders live",
        )
        if chosen:
            self._save_root = Path(chosen)
            self.var_save.set(str(self._save_root))

    def _browse_userdata(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=str(self.var_userdata.get() or str(Path.cwd())),
            title="Choose a persistent user-data-dir (login session cache)",
        )
        if chosen:
            self.var_userdata.set(chosen)

    def _set_status(self, text: str, busy: bool) -> None:
        self.var_status.set(text)
        if busy:
            self.progress.start(80)
        else:
            self.progress.stop()

    def _log(self, line: str, tag: str = "") -> None:
        self.txt.insert(tk.END, line + "\n", tag)
        self.txt.see(tk.END)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for w in self.winfo_children():
            self._toggle(w, enabled)

    def _toggle(self, widget, enabled: bool) -> None:
        cls = widget.winfo_class()
        if cls in ("TButton", "TEntry"):
            try:
                widget.configure(state=("normal" if enabled else "disabled"))
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self._toggle(child, enabled)

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "line":
                    self._log(str(payload), tag="dim")
                elif kind == "done":
                    payload_obj = payload
                    # The fetch task returns (TweetRef, RunResult).
                    # Other tasks return a single RunResult.
                    if isinstance(payload_obj, tuple) and len(payload_obj) == 2:
                        ref, res = payload_obj
                        if isinstance(ref, tf.TweetRef):
                            self._ref = ref
                            if ref.tweet_dir:
                                self._log(f"[ref] tweet_dir = {ref.tweet_dir}", "dim")
                    else:
                        res = payload_obj
                    if not isinstance(res, tf.RunResult):
                        res = tf.RunResult(returncode=0, stdout="")
                    # Special exit codes from the scraper
                    if res.returncode == 10:
                        msg = (
                            "Playwright is not installed in the system Python.\n\n"
                            "Open a terminal and run:\n"
                            "    pip install playwright\n"
                            "    playwright install chromium\n\n"
                            "Then click Fetch again."
                        )
                        self._log("ERROR: " + msg, "err")
                        self._set_status("Needs Playwright", False)
                        messagebox.showerror(APP_TITLE, msg)
                    elif res.returncode == 11:
                        msg = (
                            "Playwright is installed but Chromium is missing.\n\n"
                            "Open a terminal and run:\n"
                            "    playwright install chromium\n\n"
                            "Then click Fetch again."
                        )
                        self._log("ERROR: " + msg, "err")
                        self._set_status("Needs Chromium", False)
                        messagebox.showerror(APP_TITLE, msg)
                    elif res.error:
                        self._log("ERROR: " + res.error, "err")
                        self._set_status("Error", False)
                        messagebox.showerror(APP_TITLE, res.error)
                    else:
                        self._log("Done. returncode=" + str(res.returncode),
                                  "ok" if res.returncode == 0 else "err")
                        self._set_status("Idle", False)
                        # If the run came from check_setup, show a summary
                        self._maybe_show_setup_summary(res.stdout)
                    self._set_buttons_enabled(True)
                elif kind == "cancelled":
                    self._log("Cancelled.", "err")
                    self._set_status("Cancelled", False)
                    self._set_buttons_enabled(True)
                elif kind == "error":
                    self._log("ERROR: " + str(payload), "err")
                    self._set_status("Error", False)
                    self._set_buttons_enabled(True)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # -- actions ------------------------------------------------------------

    def _ensure_ref(self) -> bool:
        if not self._ref or not self._ref.tweet_dir:
            messagebox.showinfo(APP_TITLE, "Click 'Fetch' first to resolve the URL.")
            return False
        if not self._ref.tweet_dir.exists():
            messagebox.showerror(APP_TITLE, f"tweet_dir missing: {self._ref.tweet_dir}")
            return False
        return True

    def _do_fetch(self) -> None:
        url = self.var_url.get().strip()
        if not url:
            messagebox.showinfo(APP_TITLE, "Paste a tweet URL first.")
            return
        self._save_root = Path(self.var_save.get().strip() or str(self._default_save_root()))
        if not self._save_root.exists():
            if not messagebox.askyesno(APP_TITLE,
                                       f"Save folder does not exist:\n{self._save_root}\nCreate it?"):
                return
            self._save_root.mkdir(parents=True, exist_ok=True)

        # Optional paths
        userdata_raw = self.var_userdata.get().strip()
        userdata = Path(userdata_raw) if userdata_raw else None
        if userdata and not userdata.exists():
            userdata.mkdir(parents=True, exist_ok=True)

        auth_token = self.var_auth_token.get().strip()
        ct0 = self.var_ct0.get().strip()

        # CI root is the parent of `accounts/` (so x_media_ci fix walks
        # the whole tree). Fall back to save_root.
        ci_root = self._save_root.parent if self._save_root.name == "accounts" else self._save_root

        skip_fetch = bool(self.var_skip_fetch.get())
        headed     = bool(self.var_headed.get())
        if not skip_fetch and not headed:
            # Friendly first-time hint
            self._log(
                "[hint] first time? tick 'Headed' so a browser opens for you to "
                "log in to x.com; after that the user-data-dir caches the session.",
                tag="dim",
            )

        self._set_status("Fetching…" if not skip_fetch else "Resolving…", True)
        self._set_buttons_enabled(False)
        self._log(f">> fetch {url} (skip_fetch={skip_fetch} headed={headed})")

        # NOTE: Worker.run() injects `on_line` as a kwarg automatically,
        # so the rest of the options must be passed as **kwargs (not
        # positional) to avoid "got multiple values for argument 'on_line'".
        def task(url, save_root, on_line, **kw):
            return tf.action_fetch(
                url, save_root, on_line=on_line, **kw,
            )
        self._worker = Worker(
            self._q, task, url, self._save_root,
            ci_root=ci_root, headed=headed,
            user_data_dir=userdata, skip_fetch=skip_fetch,
            auth_token=auth_token, ct0=ct0,
        )
        self._worker.start()

    def _do_md(self) -> None:
        if not self._ensure_ref(): return
        self._set_status("Building markdown…", True)
        self._set_buttons_enabled(False)
        self._log(">> md")
        self._worker = Worker(self._q, lambda on_line: tf.action_save_md(self._ref, on_line=on_line))
        self._worker.start()

    def _do_pdf(self) -> None:
        if not self._ensure_ref(): return
        self._set_status("Building PDF…", True)
        self._set_buttons_enabled(False)
        self._log(">> pdf")
        self._worker = Worker(self._q, lambda on_line: tf.action_save_pdf(self._ref, on_line=on_line))
        self._worker.start()

    def _do_media(self) -> None:
        if not self._ensure_ref(): return
        self._set_status("Transcoding media…", True)
        self._set_buttons_enabled(False)
        self._log(">> transcode (apply)")
        self._worker = Worker(self._q, lambda on_line: tf.action_save_media(self._ref, on_line=on_line))
        self._worker.start()

    def _do_all(self) -> None:
        if not self._ensure_ref(): return
        self._set_status("Running full pipeline…", True)
        self._set_buttons_enabled(False)
        self._log(">> all (md+pdf+ocr+transcode)")
        self._worker = Worker(self._q, lambda on_line: tf.action_save_all(self._ref, on_line=on_line))
        self._worker.start()

    def _do_stop(self) -> None:
        if self._worker and self._worker.is_alive():
            self._log(">> stop requested", "err")
            self._worker.cancel()

    def _do_check(self) -> None:
        self._set_status("Checking setup…", True)
        self._set_buttons_enabled(False)
        self._log(">> check setup")
        def task(on_line):
            return tf.check_setup(on_line=on_line)
        self._worker = Worker(self._q, task)
        self._worker.start()

    def _maybe_show_setup_summary(self, stdout: str) -> None:
        """If the last child process printed a JSON object as the last
        line (as check_setup does), parse it and pop a summary box."""
        import json
        last = ""
        for line in (stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                last = line
        if not last:
            return
        try:
            data = json.loads(last)
        except Exception:
            return
        # Only react if it looks like the probe payload
        if "playwright" not in data and "chromium" not in data:
            return

        def fmt(v) -> str:
            s = str(v) if v is not None else ""
            if s.startswith("MISSING") or "MISSING" in s:
                return f"MISSING ({s})"
            return s or "—"

        lines = [
            "Setup check:",
            f"  Python        : {fmt(data.get('python'))}  ({data.get('version','?')})",
            f"  Playwright    : {fmt(data.get('playwright'))}",
            f"  Chromium bin  : {fmt(data.get('chromium'))}",
            f"  ffmpeg        : {fmt(data.get('ffmpeg'))}",
        ]
        msg = "\n".join(lines)
        self._log("\n" + msg, "ok" if "MISSING" not in msg else "err")
        missing = []
        if "MISSING" in str(data.get("playwright", "")):
            missing.append("playwright")
        if "MISSING" in str(data.get("chromium", "")):
            missing.append("chromium")
        if "MISSING" in str(data.get("ffmpeg", "")):
            missing.append("ffmpeg")
        if missing:
            messagebox.showwarning(
                APP_TITLE,
                msg + "\n\n"
                + "Missing: " + ", ".join(missing) + "\n\n"
                + "To install the fetcher deps:\n"
                + "    pip install playwright\n"
                + "    playwright install chromium\n"
                + "  (ffmpeg is optional, only needed for HLS videos)",
            )
        else:
            messagebox.showinfo(APP_TITLE, msg + "\n\nAll good — you can hit Fetch.")

    def _do_open(self) -> None:
        target = (self._ref.tweet_dir if (self._ref and self._ref.tweet_dir)
                  else self._save_root)
        if not target or not target.exists():
            messagebox.showerror(APP_TITLE, f"Folder missing: {target}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Cannot open: {e}")


def main() -> int:
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Metro Access Control — Submittal Builder (desktop app)

Runs the web server quietly in a background thread and shows the UI in a
native OS window via pywebview — no browser, no tabs, no address bar. This
is the entry point packaged into SubmittalBuilder.exe.

    python desktop.py            # open the native window
    python desktop.py --selftest # boot server, hit endpoints, exit (no GUI)

The headless server (app.py) is still available for the homelab/PM2 deploy.
"""
import os
import sys
import threading
import time
import traceback
import urllib.request

from paths import data

# pythonw.exe (the windowed launcher used by the shortcut) provides NO console,
# so sys.stdout / sys.stderr are None. print() and uvicorn's logging both write
# to those streams and would crash the server thread silently. Redirect to a
# log file next to the app BEFORE importing uvicorn, so logging has a real sink.
LOGFILE = data("desktop.log")
if sys.stdout is None or sys.stderr is None:
    _logf = open(LOGFILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = _logf
    sys.stderr = _logf

import uvicorn

from app import app

HOST, PORT = "127.0.0.1", 8484
URL = f"http://{HOST}:{PORT}"


class Api:
    """Bridge the window's UI can call (window.pywebview.api.*) to open a
    finished submittal or its folder in the OS default app — the desktop
    equivalent of a browser download."""

    def open_pdf(self, slug, fname):
        p = data("jobs", os.path.basename(slug), os.path.basename(fname))
        if os.path.isfile(p):
            os.startfile(p)          # opens in the default PDF viewer (Windows)
            return True
        return False

    def open_folder(self, slug):
        p = data("jobs", os.path.basename(slug))
        if os.path.isdir(p):
            os.startfile(p)          # opens the job folder in Explorer
            return True
        return False

    def open_drawing(self, fname):
        p = data("drawings", os.path.basename(fname))
        if os.path.isfile(p):
            os.startfile(p)
            return True
        return False

    def open_path(self, path):
        """Open any file in its default app (used for saved drawing PDFs)."""
        p = os.path.abspath(path)
        if os.path.isfile(p):
            os.startfile(p)
            return True
        return False

    def pick_folder(self):
        """Native 'choose folder' dialog; returns the path or '' if cancelled."""
        try:
            import webview
            res = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if res:
                return res[0] if isinstance(res, (list, tuple)) else str(res)
        except Exception:
            pass
        return ""

    def reveal(self, path):
        """Open a folder (or a file's folder) in Windows Explorer."""
        p = os.path.abspath(path)
        if os.path.isdir(p):
            os.startfile(p)
            return True
        if os.path.isfile(p):
            os.startfile(os.path.dirname(p))
            return True
        return False


def _serve():
    # uvicorn skips signal-handler install off the main thread, so this is safe
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def _wait_until_up(timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL + "/api/config", timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main(headless=False):
    threading.Thread(target=_serve, daemon=True).start()
    if not _wait_until_up():
        print("ERROR: server did not start", file=sys.stderr)
        sys.exit(1)
    print(f"server up at {URL}")

    if headless:
        body = urllib.request.urlopen(URL + "/").read()
        cfg = urllib.request.urlopen(URL + "/api/config").read()
        print(f"selftest: index {len(body)} bytes, config {len(cfg)} bytes")
        # full build smoke test — exercises bundled cover template +
        # external library sheet + writing into the external jobs/ folder
        import os
        import yaml
        import build as builder
        from paths import data, bundled
        print(f"selftest: bundled assets at {bundled('assets')}")
        print(f"selftest: external data at {data('')}")
        jobdir = data("jobs", "_selftest")
        os.makedirs(os.path.join(jobdir, "drawings"), exist_ok=True)
        job = {"project": {"name": "SELFTEST", "address": ["x"], "submitted": "01/01/2026"},
               "gates": [{"id": "g", "heading": "SELFTEST", "label": "",
                          "items": [{"id": "diablo-dsp7", "qty": 1}]}],
               "drawings": []}
        with open(os.path.join(jobdir, "job.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(job, f, allow_unicode=True)
        builder.main(jobdir)
        pdfs = [x for x in os.listdir(jobdir) if x.lower().endswith(".pdf")]
        print(f"selftest ok: built {pdfs}")
        return

    # Native window. If the WebView2 engine is somehow unavailable, the
    # packaged app has no console to show the error — so log it next to the
    # exe and fall back to the default browser rather than dying silently.
    try:
        import webview
        webview.create_window("Metro Submittal Builder", URL,
                              width=1180, height=900, js_api=Api())
        webview.start()   # blocks until the window is closed; daemon thread then dies
    except Exception:
        import traceback
        import webbrowser
        from paths import data
        try:
            with open(data("desktop-error.log"), "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        webbrowser.open(URL)
        try:
            while True:                # keep the server alive for the browser
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    try:
        main(headless="--selftest" in sys.argv)
    except Exception:
        # last-resort breadcrumb so a windowed (pythonw) crash isn't silent
        try:
            with open(data("desktop-error.log"), "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise

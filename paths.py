"""Resource/data path resolution that works both as plain source and as a
frozen PyInstaller app.

Two roots:
  * BUNDLE  — read-only resources shipped *inside* the app (static UI, the
              cover template, fonts). When frozen these live in the
              PyInstaller temp dir (sys._MEIPASS); in source they're next to
              this file.
  * APPDIR  — editable data that lives *next to the .exe* (or next to the
              source in dev): the spec-sheet library, presets, and the jobs
              output folder. Kept external so the library can grow and jobs
              can be written without rebuilding the app.

In plain-source runs BUNDLE == APPDIR == the submittal-tool folder, so the
CLI (`python build.py jobs/<slug>`) and `python app.py` behave exactly as
before.
"""
import os
import sys

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    BUNDLE = sys._MEIPASS                      # PyInstaller extraction dir
    APPDIR = os.path.dirname(sys.executable)   # folder containing the .exe
else:
    BUNDLE = os.path.dirname(os.path.abspath(__file__))
    APPDIR = BUNDLE


def bundled(*parts):
    """Path to a shipped resource (static/, assets/, fonts/)."""
    return os.path.join(BUNDLE, *parts)


def data(*parts):
    """Path to editable external data (library/, presets/, jobs/)."""
    return os.path.join(APPDIR, *parts)

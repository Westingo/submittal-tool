#!/usr/bin/env python3
"""
App settings — persisted next to the app as config.json.

The main setting is the WORKSPACE: the folder on the user's PC where jobs
live (one folder per job). The app reads/writes that real folder directly,
so it mirrors Windows Explorer. config.json itself stays next to the app
(it just remembers where the workspace is).
"""
import json
import os

from paths import data

_CONFIG = data("config.json")


def _default_workspace():
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    base = docs if os.path.isdir(docs) else home
    return os.path.join(base, "Metro Submittals")


def load():
    try:
        with open(_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(cfg):
    with open(_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_workspace():
    """Absolute path to the workspace folder (created if missing)."""
    ws = load().get("workspace") or _default_workspace()
    try:
        os.makedirs(ws, exist_ok=True)
    except Exception:
        pass
    return ws


def set_workspace(path):
    path = os.path.abspath(os.path.expanduser(path.strip()))
    cfg = load()
    cfg["workspace"] = path
    save(cfg)
    os.makedirs(path, exist_ok=True)
    return path

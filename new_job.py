#!/usr/bin/env python3
"""Scaffold a new job folder from the clean template.

    python new_job.py "Acme Warehouse"

Creates jobs/acme-warehouse/ with a fresh job.yaml (today's date filled in)
and an empty drawings/ folder. Then edit job.yaml and run build.py.
"""
import sys, os, re, shutil
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) != 2:
    sys.exit(__doc__)

name = sys.argv[1].strip()
slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
dest = os.path.join(ROOT, "jobs", slug)
if os.path.exists(dest):
    sys.exit(f"jobs/{slug} already exists")

shutil.copytree(os.path.join(ROOT, "jobs", "_template"), dest)
p = os.path.join(dest, "job.yaml")
s = open(p, encoding="utf-8").read()
s = s.replace("PROJECT NAME", name.upper())
s = s.replace("MM/DD/YYYY", date.today().strftime("%m/%d/%Y"))
open(p, "w", encoding="utf-8").write(s)
print(f"created jobs/{slug}/ — edit job.yaml, drop drawings in jobs/{slug}/drawings/, then:")
print(f"    python build.py jobs/{slug}")

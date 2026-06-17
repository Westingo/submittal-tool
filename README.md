# Metro Access Control — Submittal Package Builder

Builds a complete submittal PDF (cover/scope pages + stamped spec sheets +
drawings) from a small YAML job file.

## Quick start — web UI

    pip install pymupdf pyyaml fastapi uvicorn python-multipart
    python app.py

Open http://localhost:8484. Fill in the project, add gates (each starts
from a preset — check/uncheck devices and adjust quantities), attach the
contractor drawings, and click Build package. Warnings show in red in the
build log; the finished PDF downloads from the sidebar. Every build also
writes a normal jobs/<slug>/job.yaml, so UI jobs and hand-edited jobs are
interchangeable.

To reach it from other machines on the network, it already listens on
0.0.0.0:8484 — run it on the homelab under PM2:

    pm2 start app.py --name submittal-builder --interpreter python3

## Quick start — command line

    python3 build.py jobs/pdx-fuel

Output lands in the job folder as `Submittal - <Project> - <date>.pdf`.

Requires Python 3 with `pymupdf` and `pyyaml`:

    pip install pymupdf pyyaml

## Starting a new job

1. Copy `jobs/pdx-fuel/` to `jobs/<new-job>/` and edit `job.yaml`:
   project name/address/date, one entry per gate (pick a preset, set the
   gate label text), any red notes.
2. Drop the contractor's drawing PDFs into `jobs/<new-job>/drawings/` and
   list them (in order) under `drawings:` with an optional gate label + position.
3. Run the build. Read the console output — it warns if a scope item has no
   cut sheet or if a cover page overflows into the exclusions block.

## Tweaking a gate's kit without editing the preset

In job.yaml, under a gate:

    remove: [opticom-721]
    qty_overrides:
      - {id: presence-loops, qty: 3}
    add:
      - {id: loopdetlm, qty: 2}

## Adding a device to the library

1. Put the cut sheet PDF in `library/` (strip any old annotations first —
   the builder stamps fresh gate callouts every run).
2. Add an entry to `library/library.yaml`: scope line (use `{qty}`),
   sheet file(s), a `stamp: [x, y]` position for the callout box
   (PDF points, origin top-left, page is 612x792 portrait), and
   `last_verified` date.
3. Reference its id from a preset or a job's `add:` list.

If a sheet imports with baked-in page rotation, normalize it first:

    python3 -c "import fitz; d=fitz.open('library/x.pdf'); [p.remove_rotation() for p in d]; d.save('library/x2.pdf')"

## Fonts

Covers render in Liberation Serif by default (very close to the original
Cambria). For an exact match, copy `cambria.ttc`/`cambriab.ttf` from any
Windows machine (`C:\Windows\Fonts`) into `fonts/`.

## Notes from the initial import (2026-06-10)

- Library was seeded from the PDX Fuel 06/10/2026 submittal with all
  annotations stripped; stamp positions preserved from the manual layout.
- The original package had the fall-post sheet twice and the ILSCO clamp
  catalog page three times; the library dedupes these (clamp page rides
  inside `ground-rod.pdf`).
- `emx-photo-eyes` has no cut sheet yet (`sheet_pending: true`) — the
  original package shipped the LiftMaster LMTBUL sheet against an EMX
  scope line for the AOA gate. Add the EMX IRB-MON2 sheet when you have it.
- Fixed "SIGNLE" -> "SINGLE" typo in the HyInverter scope note.

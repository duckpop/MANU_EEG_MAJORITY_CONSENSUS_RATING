#!/usr/bin/env python3
"""Check the downloads: every file Zenodo lists must be here with the right
size and MD5 checksum, and all 400 Dreem scorer label files must load.

Needs internet (it asks Zenodo for the checksums). Standard library only.
Usage: python check_download.py [--eeg DIR] [--dreem DIR] [--scorers DIR]
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import urllib.request

DL = os.path.expanduser("~/Downloads")
ap = argparse.ArgumentParser(description="Check that the datasets downloaded completely.")
ap.add_argument("--eeg", default=os.path.join(DL, "zenodo_2547147_neonatal_eeg"))
ap.add_argument("--dreem", default=os.path.join(DL, "zenodo_15900394_dreem"))
ap.add_argument("--scorers", default=os.path.join(DL, "dreem_scorer_labels", "scorers"))
args = ap.parse_args()


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


problems = 0
for record, folder in (("2547147", args.eeg), ("15900394", args.dreem)):
    print(f"\nZenodo record {record}  ->  {folder}")
    try:
        with urllib.request.urlopen(f"https://zenodo.org/api/records/{record}", timeout=30) as r:
            files = json.load(r)["files"]
    except (OSError, ValueError) as e:
        print(f"  could not get the file list from Zenodo: {e}")
        problems += 1
        continue
    for f in sorted(files, key=lambda f: f["key"]):
        path = os.path.join(folder, f["key"])
        if not os.path.exists(path):
            status = "MISSING"
        elif os.path.getsize(path) != f["size"]:
            status = f"INCOMPLETE ({os.path.getsize(path):,} of {f['size']:,} bytes)"
        elif md5(path) != f["checksum"].split(":")[1]:
            status = "CORRUPT (checksum differs)"
        else:
            status = "ok"
        problems += status != "ok"
        print(f"  {status:<10} {f['key']}", flush=True)

print(f"\nDreem scorer labels (GitHub)  ->  {args.scorers}")
for d, nights in (("dodh", 25), ("dodo", 55)):
    paths = glob.glob(os.path.join(args.scorers, d, "scorer_*", "*.json"))
    unreadable = 0
    for p in paths:
        try:
            with open(p) as fh:
                json.load(fh)
        except (OSError, ValueError):
            unreadable += 1
    ok = len(paths) == 5 * nights and not unreadable
    problems += not ok
    print(f"  {'ok' if ok else 'PROBLEM':<10} {d}: {len(paths)} of {5 * nights} files, "
          f"{unreadable} unreadable")

print("\nEverything downloaded correctly." if not problems else f"\n{problems} problem(s) found.")
sys.exit(1 if problems else 0)

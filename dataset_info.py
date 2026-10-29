#!/usr/bin/env python3
"""Write dataset_info.txt: one line of basic info for every file in the datasets.

The neonatal EEG part needs only the standard library; the Dreem part needs
h5py. Dreem nights are read from extracted dodh/ and dodo/ folders if they
exist, otherwise straight from the zips (about 15 s per night).
Usage: python dataset_info.py [--eeg DIR] [--dreem DIR] [--scorers DIR] [--out FILE]
"""
import argparse
import csv
import glob
import json
import os
import re
import zipfile

DL = os.path.expanduser("~/Downloads")
ap = argparse.ArgumentParser(description="Write basic info about every dataset file to a .txt.")
ap.add_argument("--eeg", default=os.path.join(DL, "zenodo_2547147_neonatal_eeg"))
ap.add_argument("--dreem", default=os.path.join(DL, "zenodo_15900394_dreem"))
ap.add_argument("--scorers", default=os.path.join(DL, "dreem_scorer_labels", "scorers"))
ap.add_argument("--out", default="dataset_info.txt")
args = ap.parse_args()
STAGES = ["Wake", "N1", "N2", "N3", "REM"]


def size(n):
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000


def edf_info(path):
    with open(path, "rb") as fh:
        h = fh.read(256)
        ns = int(h[252:256])
        s = fh.read(256 * ns)
    record_s = float(h[244:252])
    minutes = int(h[236:244]) * record_s / 60
    rate = int(s[216 * ns:216 * ns + 8]) / record_s
    return f"{minutes:.1f} min, {ns} signals at {rate:g} Hz"


def csv_info(path, name):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if name.startswith("annotations"):
        seizure = sum(r.count("1") for r in rows[1:])
        return (f"expert {name[-5]}: {len(rows[0])} recordings x {len(rows) - 1:,} seconds, "
                f"{seizure:,} seconds marked seizure")
    return f"{len(rows) - 1} rows; columns: {', '.join(rows[0])}"


def h5_info(f):
    channels = json.loads(f.attrs["description"])
    hyp = f["hypnogram"][()].tolist()
    stages = " ".join(f"{s} {hyp.count(i)}" for i, s in enumerate(STAGES))
    return (f"{f.attrs['duration'] / 3600:.1f} h, {len(channels)} channels at "
            f"{channels[0]['fs']} Hz, official answer for {len(hyp)} epochs ({stages})")


def read_night(member, zpath):
    import h5py
    if zpath is None:
        with h5py.File(member, "r") as f:
            return h5_info(f)
    with zipfile.ZipFile(zpath) as z, z.open(member) as fh, h5py.File(fh, "r") as f:
        return h5_info(f)


def list_nights(folder, d):
    """Return [(name, size, path or zip member, zip path or None)]."""
    files = sorted(glob.glob(os.path.join(folder, d, "*.h5")))
    if files:
        return [(os.path.basename(p), os.path.getsize(p), p, None) for p in files]
    zpath = os.path.join(folder, d + ".zip")
    if not os.path.exists(zpath):
        return []
    with zipfile.ZipFile(zpath) as z:
        return sorted((os.path.basename(i.filename), i.file_size, i.filename, zpath)
                      for i in z.infolist()
                      if i.filename.endswith(".h5") and not i.filename.startswith("__MACOSX"))


def scorer_info(d, night):
    lengths = set()
    paths = glob.glob(os.path.join(args.scorers, d, "scorer_*", night[:-3] + ".json"))
    for p in paths:
        with open(p) as fh:
            lengths.add(len(json.load(fh)))
    if not paths:
        return "no scorer labels"
    return f"{len(paths)} scorers' labels of {'/'.join(map(str, sorted(lengths)))} epochs"


with open(args.out, "w") as out:
    def write(line=""):
        print(line, file=out, flush=True)

    write(f"== Neonatal EEG seizure dataset (Zenodo 2547147): {args.eeg}")
    if not os.path.isdir(args.eeg):
        write("   folder not found")
    else:
        natural = lambda n: (re.sub(r"\d+", "", n), int(re.sub(r"\D", "", n) or 0))
        for name in sorted(os.listdir(args.eeg), key=natural):
            path = os.path.join(args.eeg, name)
            if name.startswith(".") or not os.path.isfile(path):
                continue
            info = (edf_info(path) if name.endswith(".edf")
                    else csv_info(path, name) if name.endswith(".csv") else "")
            write(f"   {name:<28} {size(os.path.getsize(path)):>9}   {info}")

    for d, title in (("dodh", "Dreem DOD-H, healthy adults"), ("dodo", "Dreem DOD-O, sleep apnea")):
        write(f"\n== {title} (Zenodo 15900394): {args.dreem}")
        nights = list_nights(args.dreem, d)
        if not nights:
            write(f"   no {d}/ folder or {d}.zip found")
        for i, (name, n_bytes, member, zpath) in enumerate(nights, 1):
            print(f"{d} night {i}/{len(nights)}: {name}", flush=True)
            try:
                info = read_night(member, zpath)
            except Exception as e:  # a damaged file should not stop the listing
                info = f"ERROR reading file: {e}"
            write(f"   {name}  {size(n_bytes):>8}   {info}; {scorer_info(d, name)}")

print(f"Wrote {os.path.abspath(args.out)}")

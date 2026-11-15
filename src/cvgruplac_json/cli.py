"""Command line entry point: `cvgruplac-json`.

    cvgruplac-json --cvlac CVLAC_DIR [...] --gruplac GRUPLAC_DIR [...] --out OUT_DIR [--workers N] [--only gruplac]

Inputs are folders (their cvlac_*.json[.gz] or gruplac_*.json[.gz] files) or single files. Three passes:
1. read every CvLAC and keep its owner's product_hashes;
2. link every GrupLAC (link_gruplac) and write it to OUT/gruplac/;
3. link every CvLAC (link_cvlac) with the GrupLAC products found in pass 2 and write it to OUT/cvlac/.
Outputs keep the input's name and compression; inputs are not changed. OUT/cvgruplac_summary.json has the counts.
"""

import argparse
import gzip
import json
import multiprocessing as mp
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from . import __version__
from .link import link_cvlac, link_gruplac, owner_hashes

_STATE = {}  # shared with forked workers: hashes, cods, index, out


def _files(paths, prefix):
    """{key: path} for cvlac_<COD>.json[.gz] or gruplac_<CODE>.json[.gz]; the first path given wins."""
    out = {}
    for p in map(Path, paths):
        cands = sorted(p.glob(f"{prefix}_*.json")) + sorted(p.glob(f"{prefix}_*.json.gz")) if p.is_dir() else [p]
        for f in cands:
            m = re.match(rf"{prefix}_(.+?)\.json(\.gz)?$", f.name)
            out.setdefault(m.group(1) if m else f.name, f)
    return out


def _read(path):
    with (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _write(data, path):
    tmp = path.with_name(path.name + ".tmp")
    with (gzip.open if path.suffix == ".gz" else open)(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def _hashes(path):
    try:
        d = _read(path)
        return d["cod_rh"], owner_hashes(d), None
    except Exception as e:
        return None, set(), f"{path}: {type(e).__name__}: {e}"


def _gruplac(path):
    try:
        d = _read(path)
        matches = link_gruplac(d, _STATE["hashes"], _STATE["cods"])
        d["cvgruplac"] = {"version": __version__, "cvlac_checked": _STATE["cods"] is not None}
        _write(d, _STATE["out"] / "gruplac" / path.name)
        c = Counter({k: v for k, v in d["counts"].items() if k.startswith(("products_", "cvlac_ids_"))})
        return matches, c + Counter(gruplacs=1), None
    except Exception as e:
        return [], Counter(), f"{path}: {type(e).__name__}: {e}"


def _cvlac(path):
    try:
        d = _read(path)
        link_cvlac(d, _STATE["index"])
        d["cvgruplac"] = {"version": __version__}
        _write(d, _STATE["out"] / "cvlac" / path.name)
        return Counter(cvlac_products_in_gruplac=d["counts"]["products_in_gruplac"], cvlacs=1), None
    except Exception as e:
        return Counter(), f"{path}: {type(e).__name__}: {e}"


def _map(fn, items, workers, label, log):
    """Results of fn over items, with forked workers when possible (they share _STATE without copying it)."""
    t0, n = time.time(), len(items)
    if workers > 1 and "fork" in mp.get_all_start_methods():
        pool = mp.get_context("fork").Pool(workers)
        it = pool.imap_unordered(fn, items, chunksize=16)
    else:
        pool, it = None, map(fn, items)
    try:
        for i, r in enumerate(it, 1):
            if i % 5000 == 0 or i == n:
                log(f"{label}: {i}/{n} ({time.time() - t0:.0f} s)")
            yield r
    finally:
        if pool:
            pool.close()
            pool.join()


def run(cvlac, gruplac, out, workers=4, only=None, log=print):
    """Link the files or folders given; returns the summary also written to OUT/cvgruplac_summary.json."""
    out = Path(out)
    cv, gr = _files(cvlac or [], "cvlac"), _files(gruplac or [], "gruplac")
    log(f"{len(cv)} CvLAC and {len(gr)} GrupLAC files")
    errors, cods, hashes = [], set(), set()
    for cod, hs, err in _map(_hashes, list(cv.values()), workers, "1/3 CvLAC hashes", log):
        if err:
            errors.append(err)
        else:
            cods.add(cod)
            hashes |= hs
    _STATE.update(hashes=hashes, cods=cods if cv else None, out=out, index={})
    (out / "gruplac").mkdir(parents=True, exist_ok=True)
    total = Counter()
    for matches, c, err in _map(_gruplac, list(gr.values()), workers, "2/3 GrupLAC", log):
        errors += [err] if err else []
        total += c
        for h, group, gid in matches:
            _STATE["index"].setdefault(h, []).append((group, gid))
    if only != "gruplac" and cv:
        (out / "cvlac").mkdir(parents=True, exist_ok=True)
        for c, err in _map(_cvlac, list(cv.values()), workers, "3/3 CvLAC", log):
            errors += [err] if err else []
            total += c
    summary = {"version": __version__, "cvlac_files": len(cv), "gruplac_files": len(gr), **total, "errors": errors}
    out.mkdir(parents=True, exist_ok=True)
    _write(summary, out / "cvgruplac_summary.json")
    _STATE.clear()
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cvgruplac-json",
        description="Link the JSONs of cvlac-json and gruplac-json: one id per product, in both directions.",
        epilog="Example: cvgruplac-json --cvlac cvlac_json/ --gruplac gruplac_json/ --out linked/",
    )
    ap.add_argument("--cvlac", nargs="+", default=[], metavar="PATH", help="cvlac-json files or folders")
    ap.add_argument("--gruplac", nargs="+", default=[], metavar="PATH", help="gruplac-json files or folders")
    ap.add_argument("--out", required=True, help="output folder (gruplac/, cvlac/, cvgruplac_summary.json)")
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1), help="processes (default: up to 4)")
    ap.add_argument("--only", choices=["gruplac"], help="write only the linked GrupLACs")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = ap.parse_args(argv)
    if not a.gruplac and not a.cvlac:
        ap.error("give --gruplac and/or --cvlac")
    s = run(a.cvlac, a.gruplac, a.out, a.workers, a.only, log=lambda m: print(m, file=sys.stderr))
    print(json.dumps({k: v for k, v in s.items() if k != "errors"} | {"errors": len(s["errors"])}, indent=1))
    for e in s["errors"][:20]:
        print(e, file=sys.stderr)
    return 1 if s["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Command line entry point: `cvgruplac-json`.

    cvgruplac-json --cvlac CVLAC_DIR [...] --gruplac GRUPLAC_DIR [...] --out OUT_DIR [--products] [--only gruplac]

Inputs are folders (their cvlac_*.json[.gz] or gruplac_*.json[.gz] files) or single files. Three passes:
1. read every CvLAC and keep its owner's product_hashes (and, with --products, its DOIs);
2. link every GrupLAC (link_gruplac) and write it to OUT/gruplac/;
3. link every CvLAC (link_cvlac) with the GrupLAC products found in pass 2 and write it to OUT/cvlac/.
With --products, the CvLACs whose products join a line another record writes are read once more before pass 3, for
their author entries (merged into that line's record).
Outputs keep the input's name and compression; inputs are not changed. OUT/cvgruplac_summary.json has the counts.
--products also writes OUT/products.jsonl.gz, one line per distinct product (products.py), and
OUT/possible_duplicates.jsonl.gz, groups of lines of different people with the same title, kind and year.
"""

import argparse
import gc
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
from .products import ProductBuilder, cvlac_doi_entries, gruplac_summary

_STATE = {}  # shared with forked workers: hashes, cods, index, out, products, builder
GRUPLAC_COUNTS = ("products_with_cvlac_id", "products_gruplac_id_only", "cvlac_ids_verified", "cvlac_ids_unverified")


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


def _opener(path, gz=None):
    """Text writer, gzipped (level 6: gzip's default 9 is several times slower) when gz, or by default when the name
    ends in .gz."""
    if gz if gz is not None else path.suffix == ".gz":
        return gzip.open(path, "wt", encoding="utf-8", compresslevel=6)
    return open(path, "w", encoding="utf-8")


def _write(data, path):
    tmp = path.with_name(path.name + ".tmp")
    with _opener(tmp, gz=path.suffix == ".gz") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def _dumps(line):
    return json.dumps(line, ensure_ascii=False, separators=(",", ":"))


def _hashes(path):
    try:
        d = _read(path)
        dois = []
        if _STATE["products"]:
            link_cvlac(d)  # the ids pass 3 gives; DOIs are keyed by them
            dois = cvlac_doi_entries(d)
        return d["cod_rh"], owner_hashes(d), dois, None
    except Exception as e:  # a bad file is reported, not fatal
        return None, set(), [], f"{path}: {type(e).__name__}: {e}"


def _gruplac(path):
    try:
        d = _read(path)
        matches = link_gruplac(d, _STATE["hashes"], _STATE["cods"])
        d["cvgruplac"] = {"version": __version__, "cvlac_checked": _STATE["cods"] is not None}
        _write(d, _STATE["out"] / "gruplac" / path.name)
        c = Counter({k: d["counts"][k] for k in GRUPLAC_COUNTS}) + Counter(gruplacs=1)
        if not _STATE["products"]:
            return matches, c, None, None
        periods, lines, summaries = gruplac_summary(d)
        return matches, c, (periods, [_dumps(x) for x in lines], summaries), None
    except Exception as e:
        return [], Counter(), None, f"{path}: {type(e).__name__}: {e}"


def _authors(path):
    try:
        d = _read(path)
        link_cvlac(d)
        return _STATE["builder"].cvlac_authors(d), None
    except Exception as e:
        return [], f"{path}: {type(e).__name__}: {e}"


def _cvlac(path):
    try:
        d = _read(path)
        link_cvlac(d, _STATE["index"])
        d["cvgruplac"] = {"version": __version__}
        if _STATE["write_cvlac"]:
            _write(d, _STATE["out"] / "cvlac" / path.name)
        c = Counter(cvlac_products_in_gruplac=d["counts"]["products_in_gruplac"], cvlacs=1)
        lines = []
        if _STATE["products"]:
            for ln, key in _STATE["builder"].cvlac_lines(d):
                lines.append((_dumps(ln), ln["id"], key, d["cod_rh"]))
                c.update(f"owners_{o['group_status']}" for o in ln["owners"])
        return c, lines, None
    except Exception as e:
        return Counter(), [], f"{path}: {type(e).__name__}: {e}"


def _map(fn, items, workers, label, log):
    """Results of fn over items, with forked workers when possible (they share _STATE without copying it)."""
    t0, n = time.time(), len(items)
    if workers > 1 and "fork" in mp.get_all_start_methods():
        gc.freeze()  # the garbage collector of the workers would otherwise touch, and so copy, the shared objects
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
            gc.unfreeze()


def run(cvlac, gruplac, out, workers=4, only=None, products=False, log=print):
    """Link the files or folders given; returns the summary also written to OUT/cvgruplac_summary.json."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cv, gr = _files(cvlac or [], "cvlac"), _files(gruplac or [], "gruplac")
    log(f"{len(cv)} CvLAC and {len(gr)} GrupLAC files")
    builder = ProductBuilder() if products else None
    _STATE.update(products=products)
    errors, cods, hashes = [], set(), set()
    for cod, hs, dois, err in _map(_hashes, list(cv.values()), workers, "1/3 CvLAC hashes", log):
        if err:
            errors.append(err)
            continue
        cods.add(cod)
        hashes |= hs
        if builder:
            builder.add_cvlac_dois(cod, dois)
    _STATE.update(hashes=hashes, cods=cods if cv else None, out=out, index={})
    (out / "gruplac").mkdir(exist_ok=True)
    total = Counter()
    pf = _opener(out / "products.jsonl.gz") if products else None
    try:
        for matches, c, summary, err in _map(_gruplac, list(gr.values()), workers, "2/3 GrupLAC", log):
            errors += [err] if err else []
            total += c
            for h, group, gid in matches:
                _STATE["index"].setdefault(h, []).append((group, gid))
            if summary:
                periods, lines, summaries = summary
                for x in builder.add_gruplac((periods, [], summaries)):
                    pf.write(_dumps(x) + "\n")
                for x in lines:
                    pf.write(x + "\n")
                total["product_lines"] += len(lines)
        _STATE.pop("hashes")
        if builder:
            builder.merge()
            log(f"merged: {len(builder.clusters)} products with GrupLAC entries or DOI matches")
        _STATE.update(builder=builder, write_cvlac=only != "gruplac")
        if builder and cv:
            need = [cv[k] for k in sorted(builder.wanted_authors() & cv.keys())]
            for entries, err in _map(_authors, need, workers, "authors of merged lines", log):
                errors += [err] if err else []
                builder.add_authors(entries)
            log(f"author entries to merge: {len(builder.authors)}")
        dups = {}
        if cv and (only != "gruplac" or products):
            if only != "gruplac":
                (out / "cvlac").mkdir(exist_ok=True)
            for c, lines, err in _map(_cvlac, list(cv.values()), workers, "3/3 CvLAC", log):
                errors += [err] if err else []
                total += c
                for s, lid, key, cod in lines:
                    pf.write(s + "\n")
                    if key:
                        dups.setdefault(key, []).append((lid, cod))
                total["product_lines"] += len(lines)
        if builder:
            for ln in builder.rest():
                pf.write(_dumps(ln) + "\n")
                total["product_lines"] += 1
                total.update(f"owners_{o['group_status']}" for o in ln["owners"])
            with _opener(out / "possible_duplicates.jsonl.gz") as f:
                for key, v in dups.items():
                    if len({cod for _, cod in v}) > 1:
                        f.write(_dumps({"key": key, "ids": [i for i, _ in v], "cod_rh": [cod for _, cod in v]}) + "\n")
                        total["possible_duplicate_groups"] += 1
    finally:
        if pf:
            pf.close()
    summary = {"version": __version__, "cvlac_files": len(cv), "gruplac_files": len(gr), **total, "errors": errors}
    _write(summary, out / "cvgruplac_summary.json")
    _STATE.clear()
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cvgruplac-json",
        description="Link the JSONs of cvlac-json and gruplac-json: one id per product, in both directions.",
        epilog="Example: cvgruplac-json --cvlac cvlac_json/ --gruplac gruplac_json/ --out linked/ --products",
    )
    ap.add_argument("--cvlac", nargs="+", default=[], metavar="PATH", help="cvlac-json files or folders")
    ap.add_argument("--gruplac", nargs="+", default=[], metavar="PATH", help="gruplac-json files or folders")
    ap.add_argument("--out", required=True, help="output folder (gruplac/, cvlac/, cvgruplac_summary.json)")
    ap.add_argument("--products", action="store_true", help="also write products.jsonl.gz: one line per product")
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1), help="processes (default: up to 4)")
    ap.add_argument("--only", choices=["gruplac"], help="do not write the linked CvLACs")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = ap.parse_args(argv)
    if not a.gruplac and not a.cvlac:
        ap.error("give --gruplac and/or --cvlac")
    s = run(a.cvlac, a.gruplac, a.out, a.workers, a.only, a.products, log=lambda m: print(m, file=sys.stderr))
    print(json.dumps({k: v for k, v in s.items() if k != "errors"} | {"errors": len(s["errors"])}, indent=1))
    for e in s["errors"][:20]:
        print(e, file=sys.stderr)
    return 1 if s["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

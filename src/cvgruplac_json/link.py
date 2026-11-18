"""Product ids that link a GrupLAC JSON (gruplac-json) with the CvLAC JSONs (cvlac-json) of its members.

Every product (work, project, event, patent, other product) of both gets two first keys:

    "id": "<40 hex>",
    "scrapping_ids": [{"id": ..., "source": "cvlac"}, ..., {"id": ..., "source": "gruplac"}]

GrupLAC product
- {"source": "cvlac"}: one per member author with a product_hash, in author order: the product's id in that member's
  CvLAC. With the member's CvLAC at hand, only when the hash is in it; without it, kept with "verified": false.
  None in the GrupLAC-only sections (data/sections.json), nor in projects and events (GrupLAC lists no authors).
- {"source": "gruplac"}, last: the first cvlac id when there is one, so a product in both has the same id; otherwise
  id_hash(title, group, kind, year, n), the product_hash recipe with the group's COL code (or GrupLAC number).
- "id": the gruplac one.

CvLAC product
- {"source": "cvlac"}: the owner's product_hash, or, for products without one (events), id_hash(title, cod_rh, kind,
  year, n).
- {"source": "gruplac", "group": <COL code>}: one per GrupLAC product that lists this one as a verified cvlac id.
- "id": the cvlac one.

Both also get the product's Minciencias type as the last entry of "types" (minciencias.py).

Ids are unique within a JSON: the n-th product with a repeated key gets "|n", and a candidate already used moves on to
the next n.
"""

import hashlib
import json
from importlib.resources import files

from .minciencias import add_minciencias_type
from .product_hash import KINDS, title_key

ID_KINDS = (*KINDS, "event")
SECTIONS = json.loads(files(__package__).joinpath("data", "sections.json").read_text(encoding="utf-8"))["sections"]
GRUPLAC_ONLY = frozenset(s["gruplac"] for s in SECTIONS if s["where"] == "gruplac")


def id_key(title, owner, kind, year=None, n=1):
    """'title|owner|kind|year', plus '|n' (n > 1); owner is a COL code, a GrupLAC number or a COD_RH (10 digits)."""
    if kind not in ID_KINDS:
        raise ValueError(f"kind must be one of {ID_KINDS}")
    owner = str(owner).strip()
    if owner.isdigit() and len(owner) <= 10:
        owner = owner.zfill(10)
    y = str(year).strip() if year not in (None, "") else ""
    key = f"{title_key(title)}|{owner}|{kind}|{y}"
    return key if n == 1 else f"{key}|{n}"


def id_hash(title, owner, kind, year=None, n=1):
    """SHA-1 hex digest of id_key(title, owner, kind, year, n). With a COD_RH and kind work, project, patent or other it
    equals product_hash."""
    return hashlib.sha1(id_key(title, owner, kind, year, n).encode("ascii")).hexdigest()


def record_title(rec):
    """The title, or the event's name, or, when it has no letter or digit, the record's text."""
    for t in (rec.get("title"), rec.get("name")):
        if title_key(t):
            return t
    page = rec.get("gruplac") or rec.get("cvlac") or {}
    return rec.get("text") or (page.get("text") if isinstance(page, dict) else None) or rec.get("title") or ""


def record_year(rec):
    """year_published, year, the year of start ({year, month} or 'YYYY-MM-DD'), or the year of date."""
    for v in (rec.get("year_published"), rec.get("year"), rec.get("start"), rec.get("date")):
        if isinstance(v, dict):
            v = v.get("year")
        s = str(v or "")[:4]
        if s.isdigit():
            return s
    return None


def products(data):
    """(section, kind, record) for every product of a cvlac-json or gruplac-json JSON, in page order."""
    src = "gruplac" if "nro" in data else "cvlac"
    for w in data.get("works") or []:
        yield (w.get(src) or {}).get("section"), "work", w
    for p in data.get("projects") or []:
        yield "Proyectos", "project", p
    for e in data.get("events") or []:
        yield "Eventos", "event", e
    for p in data.get("patents") or []:
        yield "Patentes", "patent", p
    for section, its in (data.get("other_products") or {}).items():
        for it in its:
            yield section, "patent" if section == "Patentes" else "other", it


def owner_hashes(cvlac):
    """Every product_hash of a CvLAC's owner."""
    cod = cvlac["cod_rh"]
    return {
        a["product_hash"]
        for _, _, rec in products(cvlac)
        for a in rec.get("authors") or []
        if a.get("id") == cod and a.get("product_hash")
    }


class _Ids:
    """New unique ids for one JSON."""

    def __init__(self, owner):
        self.owner, self.used, self.seen = owner, set(), {}

    def take(self, h):
        if h and h not in self.used:
            self.used.add(h)
            return h
        return None

    def new(self, rec, kind):
        title, year = record_title(rec), record_year(rec)
        key = id_key(title, self.owner, kind, year)
        n = self.seen[key] = self.seen.get(key, 0) + 1
        while (h := id_hash(title, self.owner, kind, year, n)) in self.used:
            n += 1
        self.used.add(h)
        return h


def _put(rec, rid, sids):
    rest = {k: v for k, v in rec.items() if k not in ("id", "scrapping_ids")}
    rec.clear()
    rec.update(id=rid, scrapping_ids=sids, **rest)


def link_gruplac(data, cvlac_hashes=None, cvlac_cods=None):
    """Set id and scrapping_ids on every product of a GrupLAC JSON. cvlac_hashes: every owner product_hash of the
    CvLACs at hand; cvlac_cods: their COD_RHs (None: no CvLAC at hand, every cvlac id is unverified). Returns
    [(product_hash, group, gruplac id)] for the verified cvlac ids, for link_cvlac."""
    group = data.get("col") or data["nro"]
    ids, matches = _Ids(group), []
    c = {"products_with_cvlac_id": 0, "products_gruplac_id_only": 0, "cvlac_ids_verified": 0, "cvlac_ids_unverified": 0}
    for section, kind, rec in products(data):
        cv = []
        if section not in GRUPLAC_ONLY:
            for a in rec.get("authors") or []:
                h = a.get("product_hash")
                if not h or any(x["id"] == h for x in cv):
                    continue
                if cvlac_cods is not None and a.get("id") in cvlac_cods:
                    if h in cvlac_hashes:
                        cv.append({"id": h, "source": "cvlac"})
                else:
                    cv.append({"id": h, "source": "cvlac", "verified": False})
        rid = (ids.take(cv[0]["id"]) if cv else None) or ids.new(rec, kind)
        _put(rec, rid, [*cv, {"id": rid, "source": "gruplac"}])
        add_minciencias_type(section, rec)
        matches += [(x["id"], group, rid) for x in cv if "verified" not in x]
        c["products_with_cvlac_id" if cv else "products_gruplac_id_only"] += 1
        c["cvlac_ids_unverified"] += sum("verified" in x for x in cv)
        c["cvlac_ids_verified"] += sum("verified" not in x for x in cv)
    data.setdefault("counts", {}).update(c)
    return matches


def link_cvlac(data, gruplac_index=None):
    """Set id and scrapping_ids on every product of a CvLAC JSON. gruplac_index: {product_hash: [(group, gruplac id)]}
    from link_gruplac."""
    cod = data["cod_rh"]
    ids, n_linked = _Ids(cod), 0
    for section, kind, rec in products(data):
        h = next((a["product_hash"] for a in rec.get("authors") or [] if a.get("id") == cod and a.get("product_hash")), None)
        rid = ids.take(h) or ids.new(rec, kind)
        gr = [{"id": gid, "source": "gruplac", "group": g} for g, gid in (gruplac_index or {}).get(h, ())] if h else []
        _put(rec, rid, [{"id": rid, "source": "cvlac"}, *gr])
        add_minciencias_type(section, rec)
        n_linked += bool(gr)
    data.setdefault("counts", {})["products_in_gruplac"] = n_linked


def link(gruplacs, cvlacs):
    """Link lists of GrupLAC and CvLAC JSONs in place; returns {product_hash: [(group, gruplac id)]}."""
    cods = {c["cod_rh"] for c in cvlacs}
    hashes = set().union(*(owner_hashes(c) for c in cvlacs))
    index = {}
    for g in gruplacs:
        for h, group, gid in link_gruplac(g, hashes, cods):
            index.setdefault(h, []).append((group, gid))
    for c in cvlacs:
        link_cvlac(c, index)
    return index

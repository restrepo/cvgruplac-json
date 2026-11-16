"""One line per distinct product of linked GrupLAC and CvLAC JSONs (after link.py), with why it is or is not in a group.

    {"id", "kind", "section", "title", "year", "groups": [COL...], "owners": [...], "scrapping_ids": [...],
     "merged_by": ["product_hash", "doi"], "record_source": "cvlac" | "gruplac", "record": {...}}

Products are merged (union-find) when they share a cvlac id (the same person's product_hash: one CvLAC entry and the
GrupLAC entries that list it) or a DOI with the same year and the same first 20 letters of the title. Every other
product is a line of its own: GrupLAC products with no member CvLAC id, and CvLAC products no group lists.

owners[]: {"cod_rh", "cvlac_id", "group_status", "candidate_groups"?, "verified"?}; group_status is
- in_group: a GrupLAC lists the product with this person's cvlac id ("verified": false when the person's CvLAC was
  not among the inputs);
- cvlac_only_section: a CvLAC section the GrupLAC does not have (data/sections.json);
- unmatchable_kind: a project or event, which GrupLAC lists without authors;
- no_group: the person is a member of no GrupLAC;
- no_year: a member, but the product has no year;
- in_group_other_author: merged by DOI with a product that candidate_groups (groups of this person in that year) list
  under another member's id;
- member_not_reported: a member of candidate_groups in the product's year, and none of them lists it;
- outside_membership: a member, but not in the product's year.
candidate_groups (for in_group_other_author, member_not_reported and unmatchable_kind) is a guess from membership
periods, kept apart from the record's affiliations.

record is the product as the first owner's CvLAC writes it when there is one, else as the first GrupLAC writes it,
without its own id and scrapping_ids. On a merged line its authors also hold every other owner: the author entry from
the owner's CvLAC (or, when that CvLAC is absent, from the GrupLAC) fills the record's author with the same COD_RH,
else replaces the record's author without COD_RH whose name matches (the same words, the same words in another order
or one name inside the other with three words or more, or one word off by a letter, as gruplac-json matches members),
else is appended; it says so in "cvgruplac": {"merged_from": cvlac id, "name_match": exact|words|spelling|null}.
authors_count is raised to the number of authors when it was lower.
"""

import json
import re
import unicodedata
import zlib

from .link import SECTIONS, products, record_title, record_year
from .product_hash import title_key

CVLAC_ONLY = frozenset(s["cvlac"] for s in SECTIONS if s["where"] == "cvlac")
OPEN_END = 9999


def doi_of(rec):
    d = rec.get("doi") or ""
    d = re.sub(r"^\s*(https?://(dx\.)?doi\.org/|doi:\s*)", "", str(d), flags=re.I).strip().lower()
    return d if d.startswith("10.") and "/" in d else None


def doi_key(rec):
    """DOI|year|first 20 letters of the title, or None."""
    d = doi_of(rec)
    return f"{d}|{record_year(rec) or ''}|{title_key(record_title(rec))[:20]}" if d else None


def member_periods(gruplac):
    """{cod_rh: [(group, start year, end year)]} from a GrupLAC's members."""
    group, out = gruplac.get("col") or gruplac["nro"], {}
    for m in gruplac.get("members") or []:
        s = (m.get("start") or {}).get("year")
        if not m.get("cod_rh") or not s:
            continue
        e = (m.get("end") or {}).get("year") or (OPEN_END if m.get("open_end") else s)
        out.setdefault(m["cod_rh"], []).append((group, s, e))
    return out


def owner_status(cod, kind, section, year, periods):
    """(group_status, candidate_groups) of a CvLAC product that no GrupLAC lists with this person's id."""
    if section in CVLAC_ONLY:
        return "cvlac_only_section", []
    per = periods.get(cod) or []
    y = int(year) if year and str(year).isdigit() else None
    cands = sorted({g for g, s, e in per if y and s <= y <= e})
    if kind in ("project", "event"):
        return "unmatchable_kind", cands
    if not per:
        return "no_group", []
    if not y:
        return "no_year", []
    return ("member_not_reported", cands) if cands else ("outside_membership", [])


RANK = {"exact": 0, "words": 1, "spelling": 2}


def name_words(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).split()


def _osa(a, b):
    """Edit distance with adjacent transpositions (optimal string alignment)."""
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def how_match(a, b):
    """How the words of two names match: exact, words, spelling or None (gruplac-json's member matching)."""
    if not a or not b:
        return None
    if a == b:
        return "exact"
    sa, sb = set(a), set(b)
    if sa == sb or (min(len(sa), len(sb)) >= 3 and (sa <= sb or sb <= sa)):
        return "words"
    if len(a) == len(b) >= 2:
        diff = [(x, y) for x, y in zip(a, b, strict=True) if x != y]
        if len(diff) == 1 and min(len(diff[0][0]), len(diff[0][1])) >= 4 and _osa(*diff[0]) <= 1:
            return "spelling"
    return None


def owner_author(rec, cod):
    return next((a for a in rec.get("authors") or [] if a.get("id") == cod), None)


def merge_authors(rec, others):
    """rec with the author entries of the other owners merged in (module docstring); others: [(cvlac id, author)]."""
    authors = [dict(a) for a in rec.get("authors") or []]
    for cid, e in others:
        if not e or not e.get("id"):
            continue
        same = next((a for a in authors if a.get("id") == e["id"]), None)
        if same:
            if not same.get("product_hash"):
                same["product_hash"] = e.get("product_hash")
            continue
        w = name_words(e.get("full_name"))
        hits = [(i, h) for i, a in enumerate(authors) if not a.get("id") and (h := how_match(name_words(a.get("full_name")), w))]
        if hits:
            best = min(RANK[h] for _, h in hits)
            hits = [x for x in hits if RANK[x[1]] == best]
        i, how = hits[0] if len(hits) == 1 else (None, None)
        new = {**e, "cvgruplac": {"merged_from": cid, "name_match": how}}
        if i is None:
            authors.append(new)
        else:
            authors[i] = new
    out = {**rec, "authors": authors}
    if len(authors) > (rec.get("authors_count") or 0):
        out["authors_count"] = len(authors)
    return out


def _pack(x):
    return zlib.compress(json.dumps(x, ensure_ascii=False).encode())


def _unpack(b):
    return json.loads(zlib.decompress(b))


def _body(rec):
    return {k: v for k, v in rec.items() if k not in ("id", "scrapping_ids")}


def _line(lid, kind, section, rec, source, groups, owners, sids, merged_by):
    return {
        "id": lid,
        "kind": kind,
        "section": section,
        "title": record_title(rec),
        "year": record_year(rec),
        "groups": groups,
        "owners": owners,
        "scrapping_ids": sids,
        "merged_by": merged_by,
        "record_source": source,
        "record": _body(rec),
    }


def cvlac_doi_entries(cvlac):
    """[(doi key, cvlac id)] of a linked CvLAC's products with a DOI."""
    return [(k, rec["id"]) for _, _, rec in products(cvlac) if (k := doi_key(rec))]


def gruplac_summary(gruplac):
    """What ProductBuilder needs from one linked GrupLAC: (member periods, standalone lines, summaries). A product
    with no cvlac id and no DOI is a line already; the others are summaries to merge."""
    group = gruplac.get("col") or gruplac["nro"]
    lines, summaries = [], []
    for section, kind, rec in products(gruplac):
        by_id = {a.get("product_hash"): a.get("id") for a in rec.get("authors") or [] if a.get("product_hash")}
        cv = [(x["id"], by_id.get(x["id"]), "verified" not in x) for x in rec["scrapping_ids"] if x["source"] == "cvlac"]
        unver = {x["id"] for x in rec["scrapping_ids"] if x["source"] == "cvlac" and "verified" in x}
        auth = [(a["product_hash"], _pack(a)) for a in rec.get("authors") or [] if a.get("product_hash") in unver]
        dk = doi_key(rec)
        if not cv and not dk:
            sids = [{"id": rec["id"], "source": "gruplac", "group": group}]
            lines.append(_line(rec["id"], kind, section, rec, "gruplac", [group], [], sids, []))
            continue
        body = None if any(v for *_, v in cv) else zlib.compress(json.dumps([section, kind, rec]).encode())
        summaries.append((group, rec["id"], cv, dk, body, auth))
    return member_periods(gruplac), lines, summaries


class ProductBuilder:
    """Collects summaries (cvlac_doi_entries, gruplac_summary), merges, then writes lines (cvlac_lines, rest)."""

    def __init__(self):
        self.periods, self.node, self.parent = {}, {}, []
        self.gr = []  # (group, gruplac id, [(cvlac id, cod_rh, verified)], body)
        self.doi = {}  # doi key -> [node]
        self.cod_of = {}  # cvlac id -> cod_rh, for owners not seen in a GrupLAC
        self.authors = {}  # cvlac id -> packed author entry, for owners merged into another owner's line
        self.clusters = None

    def _n(self, key):
        i = self.node.get(key)
        if i is None:
            i = self.node[key] = len(self.parent)
            self.parent.append(i)
        return i

    def _find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def _union(self, a, b):
        a, b = self._find(a), self._find(b)
        if a != b:
            self.parent[max(a, b)] = min(a, b)  # the earliest node stays the root

    def add_cvlac_dois(self, cod, entries):
        for dk, cid in entries:
            self.doi.setdefault(dk, []).append(self._n("c:" + cid))
            self.cod_of[cid] = cod

    def add_gruplac(self, summary):
        """Add one gruplac_summary; returns its standalone lines."""
        periods, lines, summaries = summary
        for cod, per in periods.items():
            self.periods.setdefault(cod, []).extend(per)
        for group, gid, cv, dk, body, auth in summaries:
            for cid, a in auth:
                self.authors.setdefault(cid, a)
            g = self._n("g:" + gid)
            for cid, cod, _ in cv:
                self._union(g, self._n("c:" + cid))
                if cod:
                    self.cod_of.setdefault(cid, cod)
            if dk:
                self.doi.setdefault(dk, []).append(g)
            self.gr.append((group, gid, cv, body))
        return lines

    def merge(self):
        """Union DOI look-alikes and build the clusters (products with a GrupLAC entry or merged by DOI); call once,
        after every add_*."""
        doi_merged = []
        for nodes in self.doi.values():
            for n in nodes[1:]:
                if self._find(n) != self._find(nodes[0]):
                    self._union(nodes[0], n)
                    doi_merged.append(n)
        self.doi = None
        size = {}
        for i in range(len(self.parent)):
            r = self._find(i)
            size[r] = size.get(r, 0) + 1
        new = lambda: {"gr": [], "cv": {}, "body": None, "doi": False}  # noqa: E731
        roots = {}
        for group, gid, cv, body in self.gr:
            c = roots.setdefault(self._find(self.node["g:" + gid]), new())
            c["gr"].append((group, gid))
            for cid, cod, ver in cv:
                o = c["cv"].setdefault(cid, {"cod": cod, "in_group": True, "verified": ver})
                o["verified"] = o["verified"] or ver
            c["body"] = c["body"] or body
        for key, i in self.node.items():
            r = self._find(i)
            if key.startswith("c:") and (r in roots or size[r] > 1):
                o = {"cod": self.cod_of.get(key[2:]), "in_group": False, "verified": True}
                roots.setdefault(r, new())["cv"].setdefault(key[2:], o)
        for n in doi_merged:
            roots[self._find(n)]["doi"] = True
        for c in roots.values():
            ver = [cid for cid, o in c["cv"].items() if o["verified"]]
            c["primary"] = ver[0] if ver else None
            c["id"] = c["gr"][0][1] if c["gr"] else c["primary"]
        self.clusters = roots

    def wanted_authors(self):
        """{cod_rh} of the CvLACs that hold an author entry cvlac_authors must collect (after merge)."""
        return {o["cod"] for c in self.clusters.values() for cid, o in c["cv"].items() if o["verified"] and cid != c["primary"]}

    def cvlac_authors(self, cvlac):
        """[(cvlac id, packed author entry)] of a linked CvLAC's products merged into a line another record writes."""
        cod, out = cvlac["cod_rh"], []
        for _, _, rec in products(cvlac):
            i = self.node.get("c:" + rec["id"])
            c = self.clusters.get(self._find(i)) if i is not None else None
            if c and c["primary"] != rec["id"] and (a := owner_author(rec, cod)):
                out.append((rec["id"], _pack(a)))
        return out

    def add_authors(self, entries):
        for cid, a in entries:
            self.authors[cid] = a

    def _cluster_line(self, c, section, kind, rec, source, periods):
        others = [(cid, _unpack(self.authors[cid])) for cid in c["cv"] if cid in self.authors]
        if others:
            rec = merge_authors(rec, others)
        year = record_year(rec)
        owners = []
        for cid, o in c["cv"].items():
            e = {"cod_rh": o["cod"], "cvlac_id": cid}
            if o["in_group"]:
                e["group_status"] = "in_group"
            else:
                e["group_status"], cands = owner_status(o["cod"], kind, section, year, periods)
                if set(cands) & {g for g, _ in c["gr"]}:
                    e["group_status"], cands = "in_group_other_author", sorted(set(cands) & {g for g, _ in c["gr"]})
                if cands:
                    e["candidate_groups"] = cands
            if not o["verified"]:
                e["verified"] = False
            owners.append(e)
        sids = [{"id": cid, "source": "cvlac"} | ({} if o["verified"] else {"verified": False}) for cid, o in c["cv"].items()]
        sids += [{"id": gid, "source": "gruplac", "group": g} for g, gid in c["gr"]]
        groups = sorted({g for g, _ in c["gr"]})
        merged = (["product_hash"] if c["gr"] and c["cv"] else []) + (["doi"] if c["doi"] else [])
        return _line(c["id"], kind, section, rec, source, groups, owners, sids, merged)

    def cvlac_lines(self, cvlac):
        """Lines written from one linked CvLAC: its products in no cluster, and the clusters it is the primary of.
        Returns [(line, duplicate key or None)]; the key (title|kind|year, titles of 20 letters or more) is set on lines
        of products no group lists."""
        cod, out = cvlac["cod_rh"], []
        for section, kind, rec in products(cvlac):
            i = self.node.get("c:" + rec["id"])
            c = self.clusters.get(self._find(i)) if i is not None else None
            if c is None:
                st, cands = owner_status(cod, kind, section, record_year(rec), self.periods)
                o = {"cod_rh": cod, "cvlac_id": rec["id"], "group_status": st} | ({"candidate_groups": cands} if cands else {})
                ln = _line(rec["id"], kind, section, rec, "cvlac", [], [o], [{"id": rec["id"], "source": "cvlac"}], [])
                tk = title_key(ln["title"])
                out.append((ln, f"{tk}|{kind}|{ln['year'] or ''}" if len(tk) >= 20 else None))
            elif c["primary"] == rec["id"]:
                out.append((self._cluster_line(c, section, kind, rec, "cvlac", self.periods), None))
        return out

    def rest(self):
        """Lines of the clusters with no verified CvLAC entry (their record comes from a GrupLAC)."""
        for c in self.clusters.values():
            if c["primary"] is None and c["body"]:
                section, kind, rec = json.loads(zlib.decompress(c["body"]))
                yield self._cluster_line(c, section, kind, rec, "gruplac", self.periods)


def product_lines(gruplacs, cvlacs):
    """Lines of linked GrupLAC and CvLAC JSONs (in memory): (lines, possible duplicate groups of line ids)."""
    b, lines, dups = ProductBuilder(), [], {}
    for c in cvlacs:
        b.add_cvlac_dois(c["cod_rh"], cvlac_doi_entries(c))
    for g in gruplacs:
        lines += b.add_gruplac(gruplac_summary(g))
    b.merge()
    for c in cvlacs:
        b.add_authors(b.cvlac_authors(c))
    for c in cvlacs:
        for ln, key in b.cvlac_lines(c):
            lines.append(ln)
            if key:
                dups.setdefault(key, []).append((ln["id"], c["cod_rh"]))
    lines += list(b.rest())
    return lines, duplicate_groups(dups)


def duplicate_groups(dups):
    """[[line id, ...]] of the keys shared by lines of two people or more."""
    return [[i for i, _ in v] for v in dups.values() if len({cod for _, cod in v}) > 1]

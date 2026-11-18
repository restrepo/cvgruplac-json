"""The Minciencias product type of a CvLAC or GrupLAC product, as one more entry of its record's "types":

    {"provenance": "cvgruplac", "source": "minciencias", "type": "Artículos de investigación", "level": 1}

The type comes from data/minciencias_types.json: section -> {product type: Minciencias type}, "*" for any other type of
the section. Names are ImpactU's level-1 "minciencias" types (the product types of Minciencias' measurement model). A
product with no Minciencias equivalent (events, projects, patents, juries, evaluation committees, short courses,
translations, maps, ...) gets "type": "". The product type read is the deepest level of the record's own types (works)
or its "type" (other products), as the cvlac-gruplac DuckDB stores it.
"""

import json
from importlib.resources import files

TABLE = json.loads(files(__package__).joinpath("data", "minciencias_types.json").read_text(encoding="utf-8"))["sections"]


def lac_type(rec):
    """The product's own type: the deepest cvlac/gruplac level of "types", else "type"."""
    own = [t for t in rec.get("types") or [] if t.get("source") != "minciencias" and t.get("type")]
    if own:
        return max(own, key=lambda t: t.get("level") or 0)["type"]
    t = rec.get("type")
    return t if isinstance(t, str) else ""


def minciencias_type(section, rec):
    """The Minciencias type of a product of this section, or "" when it has none."""
    s = TABLE.get(section or "") or {}
    return s.get(lac_type(rec), s.get("*", ""))


def add_minciencias_type(section, rec):
    """Put (or replace) the minciencias entry at the end of rec["types"]; returns the type."""
    t = minciencias_type(section, rec)
    rec["types"] = [x for x in rec.get("types") or [] if x.get("source") != "minciencias"]
    rec["types"].append({"provenance": "cvgruplac", "source": "minciencias", "type": t, "level": 1})
    return t

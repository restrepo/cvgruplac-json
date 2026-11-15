import hashlib

import pytest

from conftest import ANA, ART, BETO
from cvgruplac_json import id_hash, id_key, link, link_cvlac, link_gruplac, product_hash
from cvgruplac_json.link import GRUPLAC_ONLY, SECTIONS, products


def test_id_key():
    assert id_key("Jornada sintética", "COL0000001", "event", 2023) == "jornadasintetica|COL0000001|event|2023"
    assert id_key("Física I", "COL0000001", "other", None, n=2) == "fisicai|COL0000001|other||2"
    assert id_hash("x", "COL0000001", "event", 2023) == hashlib.sha1(b"x|COL0000001|event|2023").hexdigest()
    assert id_hash(ART, "1", "work", 2017) == product_hash(ART, ANA, "work", 2017)  # a COD_RH gives product_hash
    with pytest.raises(ValueError):
        id_key("x", "COL0000001", "book")


def test_sections():
    assert len(GRUPLAC_ONLY) == 15 and "Curso de maestría" in GRUPLAC_ONLY and "Softwares" not in GRUPLAC_ONLY
    assert {s["where"] for s in SECTIONS} == {"both", "cvlac", "gruplac"}


def test_without_cvlacs_every_member_id_is_unverified(gruplac):
    assert link_gruplac(gruplac) == []
    w = gruplac["works"][0]
    a, b = (product_hash(ART, c, "work", 2017) for c in (ANA, BETO))
    assert w["scrapping_ids"] == [
        {"id": a, "source": "cvlac", "verified": False},
        {"id": b, "source": "cvlac", "verified": False},
        {"id": a, "source": "gruplac"},
    ]
    assert list(w)[:2] == ["id", "scrapping_ids"] and w["id"] == a


def test_link_both_ways(gruplac, cvlacs):
    index = link([gruplac], cvlacs)
    w = gruplac["works"][0]
    a = product_hash(ART, ANA, "work", 2017)
    assert w["scrapping_ids"] == [
        {"id": a, "source": "cvlac"},
        {"id": a, "source": "gruplac"},
    ]  # Beto's is not in his CV
    assert index == {a: [("COL0000001", a)]}
    ana_w, beto_w = cvlacs[0]["works"][0], cvlacs[1]["works"][0]
    assert ana_w["id"] == a
    assert ana_w["scrapping_ids"] == [
        {"id": a, "source": "cvlac"},
        {"id": a, "source": "gruplac", "group": "COL0000001"},
    ]
    assert beto_w["scrapping_ids"] == [{"id": beto_w["id"], "source": "cvlac"}]
    assert gruplac["counts"]["cvlac_ids_verified"] == 1 and cvlacs[0]["counts"]["products_in_gruplac"] == 1
    # Beto's software: his CvLAC is at hand and does not list it
    assert gruplac["other_products"]["Softwares"][0]["scrapping_ids"][0]["source"] == "gruplac"


def test_gruplac_only_projects_events(gruplac):
    link_gruplac(gruplac)
    c1, c2 = gruplac["other_products"]["Curso de maestría"]
    assert c1["scrapping_ids"] == [{"id": c1["id"], "source": "gruplac"}]  # GrupLAC-only section: no cvlac id
    assert c1["id"] == id_hash("Física I", "COL0000001", "other", 2020)
    assert c2["id"] == id_hash("Física I", "COL0000001", "other", 2020, n=2)
    assert gruplac["projects"][0]["id"] == id_hash("Proyecto sintético", "COL0000001", "project", 2018)
    assert gruplac["events"][0]["id"] == id_hash("Jornada sintética", "COL0000001", "event", 2023)


def test_ids_unique_and_rerun(gruplac, cvlacs):
    link([gruplac], cvlacs)
    for d in [gruplac, *cvlacs]:
        ids = [r["id"] for *_, r in products(d)]
        assert len(ids) == len(set(ids))
    before = [r["scrapping_ids"] for *_, r in products(gruplac)]
    link([gruplac], cvlacs)  # again, on linked JSONs
    assert [r["scrapping_ids"] for *_, r in products(gruplac)] == before


def test_cvlac_events_get_owner_hashes(cvlacs):
    link_cvlac(cvlacs[0])
    e1, e2 = cvlacs[0]["events"]
    assert e1["id"] == id_hash("Congreso sintético", ANA, "event", 2011)
    assert e2["id"] == id_hash("Congreso sintético", ANA, "event", 2011, n=2)
    assert e1["scrapping_ids"] == [{"id": e1["id"], "source": "cvlac"}]


def test_group_without_col_uses_its_number(gruplac):
    gruplac["col"] = None
    link_gruplac(gruplac)
    assert gruplac["events"][0]["id"] == id_hash("Jornada sintética", "00000000000001", "event", 2023)


def test_used_candidate_moves_to_next_n(gruplac):
    # the external-only article has the same key as an id already taken: it gets the next free n
    g = gruplac
    g["works"][1]["title"], g["works"][1]["year_published"] = "Física I", 2020
    g["works"][1]["gruplac"]["section"] = "Curso de maestría"
    link_gruplac(g)
    ids = [r["id"] for *_, r in products(g)]
    assert len(ids) == len(set(ids))

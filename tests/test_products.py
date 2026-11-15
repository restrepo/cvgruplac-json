import copy

import pytest

from conftest import ANA, ART, BETO, _cvlac, author
from cvgruplac_json import link, product_hash
from cvgruplac_json.products import doi_of, owner_status, product_lines

CARLA = "0000000003"  # in no group
SHARED = "Shared paper with an outside colleague"
DOI = "https://doi.org/10.1234/Shared.2018"


@pytest.fixture
def lines(gruplac, cvlacs):
    ana = cvlacs[0]
    ana["works"] += _cvlac(ANA, [(SHARED, 2018, DOI), ("A paper without year at all", None)])["works"]
    ana["other_products"] = {
        "Par evaluador": [{"title": "", "text": "Revista Uno, 2020", "year": 2020, "authors": [author("X", ANA, "f" * 40)]}]
    }
    carla = _cvlac(CARLA, [(SHARED.upper() + ".", 2018, "10.1234/shared.2018")])
    cvs = [*cvlacs, carla]
    link([gruplac], cvs)
    ls, dups = product_lines([gruplac], cvs)
    return {ln["title"]: ln for ln in ls if ln["kind"] != "event"}, ls, dups


def owner(ln, cod):
    return next(o for o in ln["owners"] if o["cod_rh"] == cod)


def test_in_group_product_is_one_line(lines):
    a = product_hash(ART, ANA, "work", 2017)
    ln = next(x for x in lines[1] if x["id"] == a)
    assert ln["groups"] == ["COL0000001"] and ln["record_source"] == "cvlac"
    assert ln["owners"] == [{"cod_rh": ANA, "cvlac_id": a, "group_status": "in_group"}]
    assert ln["scrapping_ids"] == [{"id": a, "source": "cvlac"}, {"id": a, "source": "gruplac", "group": "COL0000001"}]
    assert ln["merged_by"] == ["product_hash"] and "id" not in ln["record"]


def test_statuses(lines):
    by, ls, _ = lines
    beto = next(x for x in ls if x["owners"] and x["owners"][0]["cod_rh"] == BETO and x["kind"] == "work")
    assert beto["owners"][0]["group_status"] == "outside_membership"  # 2016, member 2010-2012
    assert owner(by["A paper without year at all"], ANA)["group_status"] == "no_year"
    assert owner(by["Revista Uno, 2020"], ANA)["group_status"] == "cvlac_only_section"
    ev = next(x for x in ls if x["kind"] == "event" and x["owners"] and x["owners"][0]["cod_rh"] == ANA)
    assert ev["owners"][0]["group_status"] == "unmatchable_kind"


def test_doi_merge_and_candidate_groups(lines):
    by, *_ = lines
    ln = by[SHARED]
    assert ln["merged_by"] == ["doi"] and ln["groups"] == []
    assert owner(ln, ANA) | {} == {
        "cod_rh": ANA,
        "cvlac_id": product_hash(SHARED, ANA, "work", 2018),
        "group_status": "member_not_reported",
        "candidate_groups": ["COL0000001"],
    }
    assert owner(ln, CARLA)["group_status"] == "no_group"
    assert [x["source"] for x in ln["scrapping_ids"]] == ["cvlac", "cvlac"]


def test_gruplac_only_lines(lines):
    by, *_ = lines
    ln = by["Only in the group"]
    assert ln["owners"] == [] and ln["groups"] == ["COL0000001"] and ln["record_source"] == "gruplac"
    assert by["Proyecto sintético"]["owners"] == []
    sw = by["Analizador"]  # Beto's CvLAC does not list it: GrupLAC id only
    assert sw["owners"] == [] and [x["source"] for x in sw["scrapping_ids"]] == ["gruplac"]


def test_every_product_once_and_unique_ids(gruplac, cvlacs, lines):
    _, ls, _ = lines
    ids = [ln["id"] for ln in ls]
    assert len(ids) == len(set(ids))
    cv_ids = [o["cvlac_id"] for ln in ls for o in ln["owners"]]
    assert len(cv_ids) == len(set(cv_ids))
    # GrupLAC 7 products, 1 merged into Ana's line: 6; Ana 6 (2 merges included); Beto 3; Carla 2 (her paper is in Ana's)
    assert len(ls) == 17


def test_unverified_owner_keeps_gruplac_record(gruplac):
    g = copy.deepcopy(gruplac)
    link([g], [])
    ls, _ = product_lines([g], [])
    a = product_hash(ART, ANA, "work", 2017)
    ln = next(x for x in ls if x["id"] == a)
    assert ln["record_source"] == "gruplac"
    assert ln["owners"][0] == {"cod_rh": ANA, "cvlac_id": a, "group_status": "in_group", "verified": False}


def test_possible_duplicates(gruplac):
    t = "The same long title in two unrelated curricula"
    cvs = [_cvlac(BETO, [(t, 2020)]), _cvlac(CARLA, [(t, 2020)])]
    link([gruplac], cvs)
    _, dups = product_lines([gruplac], cvs)
    assert dups == [[product_hash(t, BETO, "work", 2020), product_hash(t, CARLA, "work", 2020)]]


def test_same_person_repeats_are_not_duplicates(gruplac):
    t = "The same long title in two unrelated curricula"
    cvs = [_cvlac(CARLA, [(t, 2020), (t, 2020)])]
    link([gruplac], cvs)
    assert product_lines([gruplac], cvs)[1] == []


def test_other_member_of_the_group_lists_it(gruplac):
    # Ana's CvLAC has the article with a DOI; Carla, a GFIF-like member in 2017, has it too but the group lists Ana's
    g = copy.deepcopy(gruplac)
    g["members"].append({"cod_rh": CARLA, "start": {"year": 2016, "month": 1}, "end": None, "open_end": True})
    cvs = [_cvlac(ANA, [(ART, 2017, DOI)]), _cvlac(CARLA, [(ART, 2017, DOI)])]
    link([g], cvs)
    ln = next(x for x in product_lines([g], cvs)[0] if x["id"] == product_hash(ART, ANA, "work", 2017))
    assert owner(ln, CARLA) | {} == {
        "cod_rh": CARLA,
        "cvlac_id": product_hash(ART, CARLA, "work", 2017),
        "group_status": "in_group_other_author",
        "candidate_groups": ["COL0000001"],
    }
    assert ln["merged_by"] == ["product_hash", "doi"]


def test_helpers():
    assert doi_of({"doi": "https://dx.doi.org/10.1/AB"}) == "10.1/ab" and doi_of({"doi": "n/a"}) is None
    periods = {ANA: [("COL1", 2015, 9999)]}
    assert owner_status(ANA, "work", "Artículos", 2014, periods) == ("outside_membership", [])
    assert owner_status(ANA, "work", "Artículos", "2016", periods) == ("member_not_reported", ["COL1"])
    assert owner_status(CARLA, "project", "Proyectos", 2016, periods) == ("unmatchable_kind", [])

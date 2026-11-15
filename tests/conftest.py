"""Synthetic cvlac-json and gruplac-json records (made-up people and titles): only the keys the linker reads."""

import copy

import pytest

from cvgruplac_json import product_hash

ANA, BETO = "0000000001", "0000000002"
ART = "A synthetic benchmark for testing linkers"


def author(name, cod=None, h=None):
    return {"full_name": name, "id": cod, "product_hash": h}


def _gruplac():
    return {
        "nro": "00000000000001",
        "col": "COL0000001",
        "works": [
            {  # signed by both members and an external author
                "id": None,
                "title": ART,
                "year_published": 2017,
                "gruplac": {"section": "Artículos publicados"},
                "authors": [
                    author("ANA", ANA, product_hash(ART, ANA, "work", 2017)),
                    author("BETO", BETO, product_hash(ART, BETO, "work", 2017)),
                    author("OTRO"),
                ],
            },
            {
                "title": "Only in the group",
                "year_published": 2019,
                "gruplac": {"section": "Artículos publicados"},
                "authors": [author("OTRO")],
            },
        ],
        "projects": [{"title": "Proyecto sintético", "start": {"year": 2018, "month": 2}}],
        "events": [{"name": "Jornada sintética", "start": "2023-10-05"}],
        "other_products": {
            "Curso de maestría": [
                {
                    "title": "Física I",
                    "year": 2020,
                    "authors": [author("ANA", ANA, product_hash("Física I", ANA, "other", 2020))],
                },
                {"title": "Física I", "year": 2020, "authors": []},
            ],
            "Softwares": [
                {
                    "title": "Analizador",
                    "year": 2022,
                    "authors": [author("BETO", BETO, product_hash("Analizador", BETO, "other", 2022))],
                }
            ],
        },
        "counts": {},
    }


def _cvlac(cod, titles):
    return {
        "cod_rh": cod,
        "works": [
            {
                "id": f"cvlac:{cod}:{i}",
                "title": t,
                "year_published": y,
                "cvlac": {"section": "Artículos"},
                "authors": [author("X", cod, product_hash(t, cod, "work", y))],
            }
            for i, (t, y) in enumerate(titles, 1)
        ],
        "projects": [],
        "events": [
            {"name": "Congreso sintético", "start": "2011-09-03"},
            {"name": "Congreso sintético", "start": "2011-09-03"},
        ],
        "patents": [],
        "other_products": {},
        "counts": {},
    }


@pytest.fixture
def gruplac():
    return copy.deepcopy(_gruplac())


@pytest.fixture
def cvlacs():
    # Ana lists the article; Beto lists it with another year, so his hash differs
    return [_cvlac(ANA, [(ART, 2017)]), _cvlac(BETO, [(ART, 2016)])]

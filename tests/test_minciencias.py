from conftest import ANA
from cvgruplac_json import link
from cvgruplac_json.link import products
from cvgruplac_json.minciencias import TABLE, add_minciencias_type, minciencias_type


def work(*types):
    return {"types": [{"source": "cvlac", "type": t, "level": i} for i, t in enumerate(types)]}


def test_types_of_works_and_other_products():
    art = work("Producción bibliográfica", "Artículo", "Publicado en revista especializada")
    assert minciencias_type("Artículos publicados", art) == "Artículos de investigación"
    chap = work("Producción bibliográfica", "Capítulo de libro", "Otro capítulo de libro publicado")
    assert minciencias_type("Capítulos de libro publicados", chap) == "Capítulos de libro"
    research = minciencias_type("Capítulos de libro publicados", work("x", "Capítulo de libro"))
    assert research == "Capítulos de libro de investigación"
    tesis = {"type": "Trabajos dirigidos/Tutorías - Tesis de doctorado"}
    assert minciencias_type("Trabajos dirigidos/tutorías", tesis) == "Tesis de doctorado"
    for unclear in ("Iniciación Científica", "Trabajos dirigidos/Tutorías de otro tipo"):
        assert minciencias_type("Trabajos dirigidos/tutorías", {"type": "Trabajos dirigidos/Tutorías - " + unclear}) == ""
    pregrado = {"type": "Trabajos dirigidos/Tutorías - Trabajos de grado de pregrado"}
    assert minciencias_type("Trabajos dirigidos/tutorías", pregrado) == "Tesis de pregrado"
    assert minciencias_type("Otros artículos publicados", {"type": "Columna de opinión"}) == ""
    assert minciencias_type("Otros artículos publicados", {"type": "Revista de divulgación"}) == "Artículos"
    assert minciencias_type("Secretos empresariales", {"type": "Any free text"}) == "Secreto empresarial"
    assert minciencias_type("Eventos", {"type": "Congreso"}) == ""
    assert minciencias_type("Proyectos", {"type": "Investigación y desarrollo"}) == ""
    assert minciencias_type("A section no one knows", {}) == ""
    assert all("*" in v for v in TABLE.values())


def test_entry_is_added_once():
    rec = work("Producción bibliográfica", "Artículo", "Corto (Resumen)")
    for _ in range(2):
        assert add_minciencias_type("Artículos", rec) == "Artículos de investigación"
    assert [t for t in rec["types"] if t["source"] == "minciencias"] == [
        {"provenance": "cvgruplac", "source": "minciencias", "type": "Artículos de investigación", "level": 1}
    ]
    other = {"type": "Congreso"}
    add_minciencias_type("Eventos", other)
    assert other["types"] == [{"provenance": "cvgruplac", "source": "minciencias", "type": "", "level": 1}]


def test_link_sets_it_on_every_product(gruplac, cvlacs):
    link([gruplac], cvlacs)
    for d in (gruplac, *cvlacs):
        for _, _, rec in products(d):
            assert sum(t.get("source") == "minciencias" for t in rec["types"]) == 1
    assert cvlacs[0]["cod_rh"] == ANA
